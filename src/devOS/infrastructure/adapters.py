from __future__ import annotations

import json
import logging
import os
import typing
import redis
from devOS.domain import entities


REDIS_URL_VARIABLE = "devos_redis_url"
REDIS_HOST_VARIABLE = "devos_redis_host"
REDIS_PORT_VARIABLE = "devos_redis_port"
REDIS_USERNAME_VARIABLE = "devos_redis_username"
REDIS_PASSWORD_VARIABLE = "devos_redis_password"
REDIS_DATABASE_VARIABLE = "devos_redis_db"
REDIS_SSL_VARIABLE = "devos_redis_ssl"


def build_redis_client(
    environment: typing.Mapping[str, str] | None = None,
) -> redis.Redis | None:
    """Build a Redis client from the devOS bootstrap variables."""
    resolved_environment = os.environ if environment is None else environment
    redis_url = resolved_environment.get(REDIS_URL_VARIABLE)
    if redis_url:
        return redis.Redis.from_url(redis_url, decode_responses=True)

    redis_host = resolved_environment.get(REDIS_HOST_VARIABLE)
    if not redis_host:
        return None

    ssl_value = resolved_environment.get(REDIS_SSL_VARIABLE, "false")
    return redis.Redis(
        host=redis_host,
        port=int(resolved_environment.get(REDIS_PORT_VARIABLE, "6379")),
        username=resolved_environment.get(REDIS_USERNAME_VARIABLE),
        password=resolved_environment.get(REDIS_PASSWORD_VARIABLE),
        db=int(resolved_environment.get(REDIS_DATABASE_VARIABLE, "0")),
        ssl=ssl_value.strip().lower() in {"1", "true", "yes", "on"},
        decode_responses=True,
    )


class RedisNoSQLAdapter:
    """Store JSON values in a Redis-like client.

    Parameters
    ----------
    redis_client
        Object with ``set``, ``get``, and ``delete`` methods.
    """

    def __init__(self, redis_client: typing.Any) -> None:
        self.__redis_client = redis_client

    @classmethod
    def from_environment(
        cls, environment: typing.Mapping[str, str] | None = None
    ) -> RedisNoSQLAdapter | None:
        """Build the adapter from the devOS bootstrap variables.

        Returns
        -------
        RedisNoSQLAdapter | None
            ``None`` when no bootstrap connection is configured.
        """

        redis_client = build_redis_client(environment)
        if redis_client is None:
            return None
        return cls(redis_client)

    def put(self, key: str, value: entities.JSONValue) -> bool:
        """Write a JSON-encoded value.

        Parameters
        ----------
        key
            Storage key.
        value
            JSON-compatible value.

        Returns
        -------
        bool
            ``True`` when Redis accepts the value.
        """

        if not key:
            return False
        logging.info("Writing credential document to Redis for key %s.", key)
        return bool(self.__redis_client.set(key, json.dumps(value)))

    def get(self, key: str) -> entities.JSONValue:
        """Read and JSON-decode a value.

        Parameters
        ----------
        key
            Storage key.

        Returns
        -------
        JSONValue
            Decoded value, or ``None``.
        """

        if not key:
            return None
        logging.info("Reading credential document from Redis for key %s.", key)
        value = self.__redis_client.get(key)
        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return typing.cast(entities.JSONValue, json.loads(value))

    def delete(self, key: str) -> bool:
        """Delete a value.

        Parameters
        ----------
        key
            Storage key.

        Returns
        -------
        bool
            ``True`` when Redis reports a deletion.
        """

        if not key:
            return False
        logging.info("Deleting credential document from Redis for key %s.", key)
        return bool(self.__redis_client.delete(key))
