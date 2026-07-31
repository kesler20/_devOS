from __future__ import annotations

import json

import pytest
import redis

import devOS.infrastructure.credential_database as credential_database


class FakeRedisClient:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.available = True

    def ping(self) -> bool:
        return self.available

    def set(self, key: str, value: str) -> bool:
        self.values[key] = value
        return True

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def delete(self, key: str) -> int:
        return int(self.values.pop(key, None) is not None)


def test_redis_adapter_round_trips_arbitrary_json() -> None:
    fake_client = FakeRedisClient()
    adapter = credential_database.RedisKeyValueAdapter(
        credential_database.RedisCredentialClient(fake_client)
    )
    value: credential_database.JSONValue = {
        "text": "secret",
        "enabled": True,
        "ratio": 1.5,
        "items": ["one", 2],
        "missing": None,
    }

    assert adapter.put("bundle", value) is True
    assert adapter.get("bundle") == value
    assert adapter.delete("bundle") is True
    assert adapter.get("bundle") is None


def test_redis_adapter_propagates_corrupted_json() -> None:
    fake_client = FakeRedisClient()
    fake_client.values["bundle"] = "{invalid"
    adapter = credential_database.RedisKeyValueAdapter(
        credential_database.RedisCredentialClient(fake_client)
    )

    with pytest.raises(json.JSONDecodeError):
        adapter.get("bundle")


def test_redis_client_prefers_url_over_separate_variables(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_from_url(url: str, decode_responses: bool):
        captured["url"] = url
        captured["decode_responses"] = decode_responses
        return FakeRedisClient()

    monkeypatch.setattr(
        credential_database.redis.Redis, "from_url", fake_from_url
    )

    client = credential_database.RedisCredentialClient.from_environment(
        {
            "DEVOS_CREDENTIALS_REDIS_URL": "rediss://user:pass@example.test:6379/0",
            "DEVOS_CREDENTIALS_REDIS_HOST": "ignored.test",
        }
    )

    assert client is not None
    assert captured == {
        "url": "rediss://user:pass@example.test:6379/0",
        "decode_responses": True,
    }


def test_redis_client_supports_separate_variables(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_redis(**kwargs):
        captured.update(kwargs)
        return FakeRedisClient()

    monkeypatch.setattr(credential_database.redis, "Redis", fake_redis)

    client = credential_database.RedisCredentialClient.from_environment(
        {
            "DEVOS_CREDENTIALS_REDIS_HOST": "redis.test",
            "DEVOS_CREDENTIALS_REDIS_PORT": "6380",
            "DEVOS_CREDENTIALS_REDIS_USERNAME": "owner",
            "DEVOS_CREDENTIALS_REDIS_PASSWORD": "password",
            "DEVOS_CREDENTIALS_REDIS_DB": "4",
            "DEVOS_CREDENTIALS_REDIS_SSL": "true",
        }
    )

    assert client is not None
    assert captured == {
        "host": "redis.test",
        "port": 6380,
        "username": "owner",
        "password": "password",
        "db": 4,
        "ssl": True,
        "decode_responses": True,
    }


def test_redis_errors_are_not_converted_to_empty_values() -> None:
    class FailingRedisClient(FakeRedisClient):
        def get(self, key: str) -> str | None:
            raise redis.exceptions.ConnectionError("offline")

    adapter = credential_database.RedisKeyValueAdapter(
        credential_database.RedisCredentialClient(FailingRedisClient())
    )

    with pytest.raises(redis.exceptions.ConnectionError):
        adapter.get("bundle")
