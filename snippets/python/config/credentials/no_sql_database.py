from __future__ import annotations

import abc
import json
import os
import typing

import redis


JSONValue: typing.TypeAlias = (
    None
    | bool
    | int
    | float
    | str
    | list["JSONValue"]
    | dict[str, "JSONValue"]
)

REDIS_URL_VARIABLE = "DEVOS_CREDENTIALS_REDIS_URL"
REDIS_HOST_VARIABLE = "DEVOS_CREDENTIALS_REDIS_HOST"
REDIS_PORT_VARIABLE = "DEVOS_CREDENTIALS_REDIS_PORT"
REDIS_USERNAME_VARIABLE = "DEVOS_CREDENTIALS_REDIS_USERNAME"
REDIS_PASSWORD_VARIABLE = "DEVOS_CREDENTIALS_REDIS_PASSWORD"
REDIS_DATABASE_VARIABLE = "DEVOS_CREDENTIALS_REDIS_DB"
REDIS_SSL_VARIABLE = "DEVOS_CREDENTIALS_REDIS_SSL"


class NoSQLDatabasePort(abc.ABC):
    @abc.abstractmethod
    def put(self, key: str, value: JSONValue) -> bool:
        """Store a JSON-compatible value under a key."""

    @abc.abstractmethod
    def get(self, key: str) -> JSONValue:
        """Return the JSON-compatible value stored under a key."""

    @abc.abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a stored key."""


class RedisClient:
    def __init__(self, redis_client: typing.Any) -> None:
        self.__redis_client = redis_client

    @classmethod
    def from_environment(
        cls, environment: typing.Mapping[str, str] | None = None
    ) -> RedisClient | None:
        resolved_environment = os.environ if environment is None else environment
        redis_url = resolved_environment.get(REDIS_URL_VARIABLE)
        if redis_url:
            return cls(redis.Redis.from_url(redis_url, decode_responses=True))

        redis_host = resolved_environment.get(REDIS_HOST_VARIABLE)
        if not redis_host:
            return None

        ssl_value = resolved_environment.get(REDIS_SSL_VARIABLE, "false")
        redis_ssl_enabled = ssl_value.strip().lower() in {"1", "true", "yes", "on"}
        return cls(
            redis.Redis(
                host=redis_host,
                port=int(resolved_environment.get(REDIS_PORT_VARIABLE, "6379")),
                username=resolved_environment.get(REDIS_USERNAME_VARIABLE),
                password=resolved_environment.get(REDIS_PASSWORD_VARIABLE),
                db=int(resolved_environment.get(REDIS_DATABASE_VARIABLE, "0")),
                ssl=redis_ssl_enabled,
                decode_responses=True,
            )
        )

    def ping(self) -> bool:
        return bool(self.__redis_client.ping())

    def set(self, key: str, value: str) -> bool:
        return bool(self.__redis_client.set(key, value))

    def get(self, key: str) -> str | bytes | None:
        return typing.cast(str | bytes | None, self.__redis_client.get(key))

    def delete(self, key: str) -> int:
        return int(self.__redis_client.delete(key))



class RedisKeyValueAdapter(NoSQLDatabasePort):
    def __init__(self, redis_client: RedisClient) -> None:
        self.__redis_client = redis_client

    @classmethod
    def from_environment(
        cls, environment: typing.Mapping[str, str] | None = None
    ) -> RedisKeyValueAdapter | None:
        redis_client = RedisClient.from_environment(environment)
        if redis_client is None:
            return None
        return cls(redis_client)

    def is_available(self) -> bool:
        return self.__redis_client.ping()

    def put(self, key: str, value: JSONValue) -> bool:
        if not key:
            raise ValueError("Credential database keys cannot be empty.")
        return self.__redis_client.set(
            key, json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        )

    def get(self, key: str) -> JSONValue:
        if not key:
            raise ValueError("Credential database keys cannot be empty.")
        stored_value = self.__redis_client.get(key)
        if stored_value is None:
            return None
        if isinstance(stored_value, bytes):
            stored_value = stored_value.decode("utf-8")
        return typing.cast(JSONValue, json.loads(stored_value))

    def delete(self, key: str) -> bool:
        if not key:
            raise ValueError("Credential database keys cannot be empty.")
        return self.__redis_client.delete(key) > 0
