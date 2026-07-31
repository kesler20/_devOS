from __future__ import annotations

import json
import os

import pytest
import redis

from snippets.python.config.credentials import runtime_loader


class FakeNoSQLDatabase:
    def __init__(self, values=None, error: Exception | None = None) -> None:
        self.values = values or {}
        self.error = error

    def put(self, key, value):
        self.values[key] = value
        return True

    def get(self, key):
        if self.error is not None:
            raise self.error
        return self.values.get(key)

    def delete(self, key):
        return self.values.pop(key, None) is not None


def test_runtime_loader_overlays_project_and_serializes_json(monkeypatch) -> None:
    database = FakeNoSQLDatabase(
        {
            runtime_loader.GENERAL_CREDENTIALS_KEY: {
                "VALUE": "general",
                "FLAGS": [True, False],
                "REMOVED": "present",
            },
            f"{runtime_loader.PROJECT_CREDENTIALS_KEY_PREFIX}sample": {
                "VALUE": "project",
                "OBJECT": {"ratio": 1.5},
                "REMOVED": None,
            },
        }
    )
    monkeypatch.setenv("VALUE", "local")
    monkeypatch.setenv("REMOVED", "local")
    loader = runtime_loader.LoadCredentialsUseCase("sample", database)

    assert loader.execute() is True
    assert os.environ["VALUE"] == "project"
    assert json.loads(os.environ["FLAGS"]) == [True, False]
    assert json.loads(os.environ["OBJECT"]) == {"ratio": 1.5}
    assert "REMOVED" not in os.environ


def test_runtime_loader_keeps_local_values_without_bootstrap(monkeypatch) -> None:
    monkeypatch.setenv("LOCAL_ONLY", "fallback")
    loader = runtime_loader.LoadCredentialsUseCase("sample", None)

    assert loader.execute() is False
    assert os.environ["LOCAL_ONLY"] == "fallback"


def test_runtime_loader_falls_back_only_for_redis_unavailability(
    monkeypatch,
) -> None:
    monkeypatch.setenv("VALUE", "fallback")
    unavailable_loader = runtime_loader.LoadCredentialsUseCase(
        "sample",
        FakeNoSQLDatabase(error=redis.exceptions.ConnectionError("offline")),
    )

    assert unavailable_loader.execute() is False
    assert os.environ["VALUE"] == "fallback"

    corrupted_loader = runtime_loader.LoadCredentialsUseCase(
        "sample",
        FakeNoSQLDatabase(error=json.JSONDecodeError("bad", "{", 0)),
    )
    with pytest.raises(json.JSONDecodeError):
        corrupted_loader.execute()
