from __future__ import annotations

import json
import os
import pathlib

import pytest
import redis

from snippets.python.config import credentials


class FakeNoSQLDatabase:
    def __init__(self, values=None, error: Exception | None = None) -> None:
        self.values = values or {}
        self.error = error

    def get(self, key):
        if self.error is not None:
            raise self.error
        return self.values.get(key)


def test_runtime_loader_overlays_project_and_serializes_json(monkeypatch) -> None:
    database = FakeNoSQLDatabase(
        {
            credentials.GENERAL_CREDENTIALS_KEY: {
                "VALUE": "general",
                "FLAGS": [True, False],
                "UNSPECIFIED": "present",
            },
            f"{credentials.PROJECT_CREDENTIALS_KEY_PREFIX}sample": {
                "VALUE": "project",
                "OBJECT": {"ratio": 1.5},
                "UNSPECIFIED": None,
            },
        }
    )
    monkeypatch.setenv("VALUE", "local")
    monkeypatch.setenv("UNSPECIFIED", "local")
    loader = credentials.LoadCredentialsUseCase("sample", database)

    assert loader.execute() is True
    assert os.environ["VALUE"] == "project"
    assert json.loads(os.environ["FLAGS"]) == [True, False]
    assert json.loads(os.environ["OBJECT"]) == {"ratio": 1.5}
    # A null means the bundle does not specify the value, so the local one stays.
    assert os.environ["UNSPECIFIED"] == "local"


def test_runtime_loader_skips_reserved_bootstrap_values(monkeypatch) -> None:
    database = FakeNoSQLDatabase(
        {
            credentials.GENERAL_CREDENTIALS_KEY: {
                "devos_redis_url": "rediss://stored",
            }
        }
    )
    monkeypatch.setenv("devos_redis_url", "rediss://bootstrap")
    loader = credentials.LoadCredentialsUseCase("sample", database)

    assert loader.execute() is True
    assert os.environ["devos_redis_url"] == "rediss://bootstrap"


def test_runtime_loader_keeps_local_values_without_bootstrap(monkeypatch) -> None:
    monkeypatch.setenv("LOCAL_ONLY", "fallback")
    loader = credentials.LoadCredentialsUseCase("sample", None)

    assert loader.execute() is False
    assert os.environ["LOCAL_ONLY"] == "fallback"


def test_runtime_loader_falls_back_only_for_redis_unavailability(
    monkeypatch,
) -> None:
    monkeypatch.setenv("VALUE", "fallback")
    unavailable_loader = credentials.LoadCredentialsUseCase(
        "sample",
        FakeNoSQLDatabase(error=redis.exceptions.ConnectionError("offline")),
    )

    assert unavailable_loader.execute() is False
    assert os.environ["VALUE"] == "fallback"

    corrupted_loader = credentials.LoadCredentialsUseCase(
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
