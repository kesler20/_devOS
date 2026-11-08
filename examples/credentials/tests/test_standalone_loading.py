from __future__ import annotations

import json
import os
import pathlib

import pytest
import redis

from examples.credentials import loading_creds as credentials


class FakeNoSQLDatabase:
    def __init__(self, values=None, error: Exception | None = None) -> None:
        self.values = values or {}
        self.error = error

    def get(self, key):
        if self.error is not None:
            raise self.error
        return self.values.get(key)


def test_runtime_loader_reads_only_its_project_and_serializes_json(monkeypatch) -> None:
    database = FakeNoSQLDatabase(
        {
            f"{credentials.PROJECT_CREDENTIALS_KEY_PREFIX}other-project": {
                "VALUE": "other-project",
                "GENERAL_ONLY": "must-not-load",
            },
            f"{credentials.PROJECT_CREDENTIALS_KEY_PREFIX}sample": {
                "VALUE": "project",
                "FLAGS": [True, False],
                "OBJECT": {"ratio": 1.5},
                "UNSPECIFIED": None,
            },
        }
    )
    monkeypatch.setenv("VALUE", "local")
    monkeypatch.setenv("UNSPECIFIED", "local")
    loader = credentials.LoadingCredsUseCase("sample", database)

    assert loader.execute() is True
    assert os.environ["VALUE"] == "project"
    assert json.loads(os.environ["FLAGS"]) == [True, False]
    assert json.loads(os.environ["OBJECT"]) == {"ratio": 1.5}
    assert "GENERAL_ONLY" not in os.environ
    # A null means the bundle does not specify the value, so the local one stays.
    assert os.environ["UNSPECIFIED"] == "local"


def test_runtime_loader_skips_reserved_bootstrap_values(monkeypatch) -> None:
    database = FakeNoSQLDatabase(
        {
            f"{credentials.PROJECT_CREDENTIALS_KEY_PREFIX}sample": {
                "devos_redis_url": "rediss://stored",
            }
        }
    )
    monkeypatch.setenv("devos_redis_url", "rediss://bootstrap")
    loader = credentials.LoadingCredsUseCase("sample", database)

    assert loader.execute() is True
    assert os.environ["devos_redis_url"] == "rediss://bootstrap"


def test_runtime_loader_keeps_local_values_without_bootstrap(monkeypatch) -> None:
    monkeypatch.setenv("LOCAL_ONLY", "fallback")
    loader = credentials.LoadingCredsUseCase("sample", None)

    assert loader.execute() is False
    assert os.environ["LOCAL_ONLY"] == "fallback"


def test_runtime_loader_falls_back_only_for_redis_unavailability(
    monkeypatch,
) -> None:
    monkeypatch.setenv("VALUE", "fallback")
    unavailable_loader = credentials.LoadingCredsUseCase(
        "sample",
        FakeNoSQLDatabase(error=redis.exceptions.ConnectionError("offline")),
    )

    assert unavailable_loader.execute() is False
    assert os.environ["VALUE"] == "fallback"

    corrupted_loader = credentials.LoadingCredsUseCase(
        "sample",
        FakeNoSQLDatabase(error=json.JSONDecodeError("bad", "{", 0)),
    )
    with pytest.raises(json.JSONDecodeError):
        corrupted_loader.execute()


def test_project_name_prefers_the_configured_variable() -> None:
    resolved_name = credentials.resolve_project_name(
        environment={credentials.PROJECT_NAME_VARIABLE: "configured"},
        start_directory=pathlib.Path.cwd(),
    )

    assert resolved_name == "configured"


def test_project_name_falls_back_to_the_git_remote(
    tmp_path: pathlib.Path, caplog
) -> None:
    git_directory = tmp_path / "workspace" / ".git"
    git_directory.mkdir(parents=True)
    (git_directory / "config").write_text(
        '[remote "origin"]\n\turl = https://github.com/kesler20/devOS.git\n',
        encoding="utf-8",
    )

    with caplog.at_level("WARNING"):
        resolved_name = credentials.resolve_project_name(
            environment={}, start_directory=tmp_path / "workspace"
        )

    assert resolved_name == "devOS"
    assert credentials.PROJECT_NAME_VARIABLE in caplog.text


def test_project_name_falls_back_to_the_directory_name(
    tmp_path: pathlib.Path, caplog
) -> None:
    workspace = tmp_path / "scratch-project"
    workspace.mkdir()

    with caplog.at_level("WARNING"):
        resolved_name = credentials.resolve_project_name(
            environment={}, start_directory=workspace
        )

    assert resolved_name == "scratch-project"
    assert "no git remote" in caplog.text


def test_redis_failure_does_not_log_confidential_exception_text(caplog):
    loader = credentials.LoadingCredsUseCase(
        "sample", FakeNoSQLDatabase(error=redis.exceptions.ConnectionError("private-test-marker"))
    )
    assert loader.execute() is False
    assert "private-test-marker" not in caplog.text
    assert "ConnectionError" in caplog.text


def test_build_redis_client_uses_selected_bootstrap_without_connecting(monkeypatch):
    calls = []
    monkeypatch.setattr(credentials.redis, "Redis", lambda **kwargs: calls.append(kwargs) or object())
    credentials.build_redis_client({"devos_redis_host": "offline.test", "devos_redis_ssl": "true"})
    assert calls == [{"host": "offline.test", "port": 6379, "username": None,
                      "password": None, "db": 0, "ssl": True, "decode_responses": True}]


class FakeSecretBlock:
    saved: dict[str, str] = {}

    def __init__(self, value: str) -> None:
        self.value = value

    @classmethod
    def load(cls, name: str):
        if name not in cls.saved:
            raise ValueError(f"Unable to find block document named {name}")
        return cls(cls.saved[name])

    def get(self) -> str:
        return self.value

    def save(self, name: str, overwrite: bool = False) -> None:
        if name in self.saved and not overwrite:
            raise ValueError("exists")
        self.saved[name] = self.value


def test_prefect_vault_creates_a_missing_block_from_the_environment() -> None:
    from examples.credentials import prefect_vault_adapter

    FakeSecretBlock.saved = {}
    adapter = prefect_vault_adapter.PrefectVaultAdapter(FakeSecretBlock)
    key = f"{credentials.PROJECT_CREDENTIALS_KEY_PREFIX}Sample_App"

    assert adapter.get(key) is None
    with pytest.raises(ValueError, match="no environment values"):
        adapter.ensure(key, {"VALUE": None})
    seeded = adapter.ensure(key, {"VALUE": "seeded", "UNSET": None})
    again = adapter.ensure(key, {"VALUE": "ignored"})

    assert seeded == again == {"VALUE": "seeded"}
    assert list(FakeSecretBlock.saved) == ["devos-projects-sample-app"]


def test_loader_accepts_the_prefect_vault_as_its_store(monkeypatch) -> None:
    from examples.credentials import prefect_vault_adapter

    FakeSecretBlock.saved = {
        "devos-projects-sample": json.dumps({"VALUE": "from-prefect"})
    }
    monkeypatch.delenv("VALUE", raising=False)
    adapter = prefect_vault_adapter.PrefectVaultAdapter(FakeSecretBlock)

    assert credentials.LoadingCredsUseCase("sample", adapter).execute() is True
    assert os.environ["VALUE"] == "from-prefect"


def test_store_variable_selects_the_adapter(monkeypatch) -> None:
    assert credentials.build_store({}) is None
    with pytest.raises(ValueError, match="Unknown credential store"):
        credentials.build_store({credentials.STORE_VARIABLE: "vault9"})
