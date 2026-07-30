from __future__ import annotations

import json
import logging
import os

import redis

from . import no_sql_database


GENERAL_CREDENTIALS_KEY = "devos:credentials:general"
PROJECT_CREDENTIALS_KEY_PREFIX = "devos:credentials:project:"
BOOTSTRAP_VARIABLE_PREFIX = "DEVOS_CREDENTIALS_"


class LoadCredentialsUseCase:
    def __init__(
        self,
        project_name: str,
        database: no_sql_database.NoSQLDatabasePort | None,
    ) -> None:
        self.__project_name = project_name
        self.__database = database

    @classmethod
    def from_environment(cls, project_name: str) -> LoadCredentialsUseCase:
        return cls(
            project_name=project_name,
            database=no_sql_database.RedisKeyValueAdapter.from_environment(),
        )

    def __load_bundle(
        self, storage_key: str
    ) -> dict[str, no_sql_database.JSONValue]:
        if self.__database is None:
            return {}
        stored_value = self.__database.get(storage_key)
        if stored_value is None:
            return {}
        if not isinstance(stored_value, dict):
            raise ValueError(f"Credential bundle '{storage_key}' is not a JSON object.")
        return stored_value

    def __environment_value(
        self, value: no_sql_database.JSONValue
    ) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, int | float):
            return str(value)
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    def execute(self) -> bool:
        if self.__database is None:
            logging.warning(
                "Redis credential storage is not configured. Using local environment values."
            )
            return False

        try:
            general_bundle = self.__load_bundle(GENERAL_CREDENTIALS_KEY)
            project_bundle = self.__load_bundle(
                f"{PROJECT_CREDENTIALS_KEY_PREFIX}{self.__project_name}"
            )
        except redis.exceptions.RedisError as error:
            logging.warning(
                "Redis credential storage is unavailable. Using local environment values. %s",
                error,
            )
            return False

        effective_bundle = {**general_bundle, **project_bundle}
        for key, value in effective_bundle.items():
            if key.startswith(BOOTSTRAP_VARIABLE_PREFIX):
                continue
            environment_value = self.__environment_value(value)
            if environment_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = environment_value
        return True
