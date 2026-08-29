from __future__ import annotations

import configparser
import json
import logging
import os
import pathlib
import typing

import redis
import redis.exceptions

JSONValue: typing.TypeAlias = (
    None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
)

GENERAL_CREDENTIALS_KEY = "devos:general"
PROJECT_CREDENTIALS_KEY_PREFIX = "devos:projects:"
RESERVED_VARIABLE_PREFIX = "devos_"

PROJECT_NAME_VARIABLE = "devos_project_name"
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


def resolve_project_name(
    environment: typing.Mapping[str, str] | None = None,
    start_directory: pathlib.Path | None = None,
) -> str:
    """Resolve the credential project name, warning when a fallback is used."""

    def git_remote_name(directory: pathlib.Path) -> str | None:
        for candidate in [directory, *directory.parents]:
            git_config_path = candidate / ".git" / "config"
            if not git_config_path.is_file():
                continue
            parser = configparser.ConfigParser()
            try:
                parser.read(git_config_path, encoding="utf-8")
            except configparser.Error:
                return None
            for section in parser.sections():
                if not section.startswith("remote "):
                    continue
                remote_url = parser[section].get("url", "").strip()
                if remote_url:
                    return remote_url.rstrip("/").split("/")[-1].removesuffix(".git")
            return None
        return None

    resolved_environment = os.environ if environment is None else environment
    configured_name = resolved_environment.get(PROJECT_NAME_VARIABLE)
    if configured_name:
        return configured_name

    resolved_directory = (
        pathlib.Path.cwd() if start_directory is None else start_directory
    )
    remote_name = git_remote_name(resolved_directory)
    if remote_name:
        logging.warning(
            "%s is not set. Using the git remote name '%s' as the credential project.",
            PROJECT_NAME_VARIABLE,
            remote_name,
        )
        return remote_name

    directory_name = resolved_directory.name
    logging.warning(
        "%s is not set and no git remote was found. Using the directory name '%s' "
        "as the credential project, which may not match any stored bundle.",
        PROJECT_NAME_VARIABLE,
        directory_name,
    )
    return directory_name


class RedisNoSQLAdapter:
    """Read JSON values from a Redis-like client."""

    def __init__(self, redis_client: typing.Any) -> None:
        self.__redis_client = redis_client

    def get(self, key: str) -> JSONValue:
        """Read and JSON-decode a value."""
        if not key:
            return None
        value = self.__redis_client.get(key)
        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return typing.cast(JSONValue, json.loads(value))


class LoadCredentialsUseCase:
    """Load stored credentials into the process environment."""

    def __init__(self, project_name: str, database: typing.Any | None) -> None:
        self.__project_name = project_name
        self.__database = database

    @classmethod
    def from_environment(cls) -> LoadCredentialsUseCase:
        """Build the use case from the devOS bootstrap variables."""
        redis_client = build_redis_client()
        database = None if redis_client is None else RedisNoSQLAdapter(redis_client)
        return cls(project_name=resolve_project_name(), database=database)

    def __load_bundle(
        self, database: typing.Any, storage_key: str
    ) -> dict[str, JSONValue]:
        stored_value = database.get(storage_key)
        if stored_value is None:
            return {}
        if not isinstance(stored_value, dict):
            raise ValueError(f"Credential bundle '{storage_key}' is not a JSON object.")
        return stored_value

    def __environment_value(self, value: JSONValue) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int | float):
            return str(value)
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    def execute(self) -> bool:
        """Overlay the general and project bundles onto the environment."""
        database = self.__database
        if database is None:
            logging.warning(
                "Redis credential storage is not configured. Using local environment values."
            )
            return False

        try:
            general_bundle = self.__load_bundle(database, GENERAL_CREDENTIALS_KEY)
            project_bundle = self.__load_bundle(
                database, f"{PROJECT_CREDENTIALS_KEY_PREFIX}{self.__project_name}"
            )
        except redis.exceptions.RedisError as error:
            logging.warning(
                "Redis credential storage is unavailable. Using local environment values. %s",
                error,
            )
            return False

        for key, value in {**general_bundle, **project_bundle}.items():
            # A null means the bundle does not specify the value, so whatever the
            # shell or .env already provided is left in place.
            if value is None or key.lower().startswith(RESERVED_VARIABLE_PREFIX):
                continue
            os.environ[key] = self.__environment_value(value)
        return True
