"""Verified, non-destructive migration of Redis and local dotenv assignments."""

from __future__ import annotations

import pathlib
import json
import logging
import redis
import typing

import dotenv
import redis.exceptions

import devOS.credential_cli as credential_cli
from devOS.domain import entities
from devOS.domain import credential_migration
from devOS.infrastructure import adapters
import devOS.infrastructure.credential_vault as credential_vault


class MigrateCredentialStoreUseCase:
    def __init__(
        self,
        vault: credential_vault.JSONCredentialVaultAdapter,
        redis_client_factory: typing.Callable[
            [typing.Mapping[str, str]], redis.Redis | None
        ],
        database_factory: typing.Callable[[redis.Redis], adapters.RedisNoSQLAdapter],
    ) -> None:
        self.__vault = vault
        self.__redis_client_factory = redis_client_factory
        self.__database_factory = database_factory

    def execute(
        self,
        projects: list[pathlib.Path],
        keep_local: dict[str, set[str]] | None = None,
    ) -> credential_migration.CredentialMigrationResult:
        logging.info("Migrating configured credential sources")
        keep_local = keep_local or {}
        document = self.__vault.read()
        sources: dict[str, dict[str, str]] = {}
        unavailable: list[str] = []
        imported: list[str] = []
        for root in projects:
            if not (root / ".env").is_file():
                continue
            values = dotenv.dotenv_values(root / ".env", interpolate=False)
            bootstrap = {
                key.lower(): value
                for key, value in values.items()
                if entities.is_bootstrap_variable(key) and value is not None
            }
            if bootstrap.get("devos_redis_url") or bootstrap.get("devos_redis_host"):
                sources[root.name] = bootstrap
        seen: set[str] = set()
        for name, bootstrap in sources.items():
            identity = json.dumps(bootstrap, sort_keys=True)
            if identity in seen:
                continue
            seen.add(identity)
            client = self.__redis_client_factory(bootstrap)
            if client is None:
                continue
            client.connection_pool.connection_kwargs.update(
                socket_connect_timeout=2, socket_timeout=2
            )
            remote = self.__database_factory(client)
            try:
                general = remote.get("devos:general")
                project_keys = remote.keys("devos:projects:*")
                bundles = {key: remote.get(key) for key in project_keys}
            except redis.exceptions.RedisError:
                unavailable.append(name)
                continue
            root_values = {
                key: value
                for key, value in document.items()
                if not key.startswith(credential_vault.PROJECT_PREFIX)
            }
            if general is not None:
                root_values = credential_cli.merge_bundle(
                    root_values,
                    entities.CredentialBundle.from_json_value(
                        general, "Redis root"
                    ).values(),
                )
            document.update(root_values)
            for key, value in bundles.items():
                scope = credential_vault.PROJECT_PREFIX + key.removeprefix(
                    "devos:projects:"
                )
                incoming = entities.CredentialBundle.from_json_value(
                    value, "Redis project"
                ).values()
                incoming = {
                    name: value
                    for name, value in incoming.items()
                    if name
                    not in keep_local.get(
                        scope.removeprefix(credential_vault.PROJECT_PREFIX), set()
                    )
                }
                document[scope] = credential_cli.merge_bundle(
                    typing.cast(dict[str, entities.JSONValue], document.get(scope, {})),
                    incoming,
                )
            imported.append(name)
        for root in projects:
            if not (root / ".env").is_file():
                continue
            local_name = credential_cli.get_project_name(root)
            if local_name is None:
                continue
            incoming = {
                key: value
                for key, value in dotenv.dotenv_values(
                    root / ".env", interpolate=False
                ).items()
                if not entities.is_bootstrap_variable(key) and value is not None
            }
            if not incoming:
                continue
            scope = credential_vault.PROJECT_PREFIX + local_name
            previous = typing.cast(
                dict[str, entities.JSONValue], document.get(scope, {})
            ).copy()
            for key in keep_local.get(local_name, set()):
                if key in incoming:
                    previous.pop(key, None)
            document[scope] = credential_cli.merge_bundle(previous, incoming)
        self.__vault.write(document)
        if self.__vault.read() != document:
            raise credential_vault.VaultError("Migration readback failed.")
        result = credential_migration.CredentialMigrationResult(
            redis_verified=imported,
            redis_unavailable=unavailable,
            projects=sorted(
                key.removeprefix(credential_vault.PROJECT_PREFIX)
                for key in document
                if key.startswith(credential_vault.PROJECT_PREFIX)
            ),
        )
        logging.info("Migrated credentials from %s available sources", len(imported))
        return result
