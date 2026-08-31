from __future__ import annotations

import json

import pytest
import redis

import devOS.infrastructure.adapters as adapters


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
    adapter = adapters.RedisNoSQLAdapter(fake_client)
    value: adapters.JSONValue = {
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
    adapter = adapters.RedisNoSQLAdapter(fake_client)

    with pytest.raises(json.JSONDecodeError):
        adapter.get("bundle")


def test_redis_client_prefers_url_over_separate_variables(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_from_url(url: str, decode_responses: bool):
        captured["url"] = url
        captured["decode_responses"] = decode_responses
        return FakeRedisClient()

    monkeypatch.setattr(
        adapters.redis.Redis, "from_url", fake_from_url
    )

    client = adapters.build_redis_client(
        {
            "devos_redis_url": "rediss://user:pass@example.test:6379/0",
            "devos_redis_host": "ignored.test",
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

    monkeypatch.setattr(adapters.redis, "Redis", fake_redis)

    client = adapters.build_redis_client(
        {
            "devos_redis_host": "redis.test",
            "devos_redis_port": "6380",
            "devos_redis_username": "owner",
            "devos_redis_password": "password",
            "devos_redis_db": "4",
            "devos_redis_ssl": "true",
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

    adapter = adapters.RedisNoSQLAdapter(FailingRedisClient())

    with pytest.raises(redis.exceptions.ConnectionError):
        adapter.get("bundle")
