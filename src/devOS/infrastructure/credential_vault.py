"""Local JSON credential authority and independently configured remote targets."""

from __future__ import annotations

import json
import logging
import importlib
import contextlib
import pydantic
import os
import pathlib
import tempfile
import typing

from devOS.domain import entities
from devOS.use_cases import credential_ports

PrefectResult = typing.TypeVar("PrefectResult")


class PrefectStoreSettings(pydantic.BaseModel):
    api_url: str
    api_key: pydantic.SecretStr | None = None


class PrefectSecretBlockSchema(typing.Protocol):
    def get(self) -> str: ...

    def save(
        self, name: str, overwrite: bool = False
    ) -> object | typing.Awaitable[object]: ...


class PrefectSecretTypeSchema(typing.Protocol):
    def __call__(self, *, value: pydantic.SecretStr) -> PrefectSecretBlockSchema: ...

    def load(
        self, name: str
    ) -> PrefectSecretBlockSchema | typing.Awaitable[PrefectSecretBlockSchema]: ...


PROJECT_PREFIX = "project_"
REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[3]
CONFIG_PATH = REPOSITORY_ROOT / ".devos" / "config.json"


class VaultError(ValueError):
    """A value-free error suitable for displaying to the operator."""


class VaultNotConfigured(VaultError):
    """The operator has not selected a local vault directory."""


def read_document(path: pathlib.Path) -> dict[str, entities.JSONValue]:
    logging.info("Reading credential JSON document")
    if not path.exists():
        return {}
    try:

        def reject_constant(value: str) -> typing.NoReturn:
            raise VaultError("Vault JSON cannot contain non-finite numbers.")

        value = json.loads(
            path.read_text(encoding="utf-8"), parse_constant=reject_constant
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise VaultError(
            "Cannot read vault JSON. Repair the file before continuing."
        ) from None
    if not isinstance(value, dict):
        raise VaultError("Vault JSON must be an object.")
    logging.info("Read credential JSON document")
    return typing.cast(dict[str, entities.JSONValue], value)


def write_document(path: pathlib.Path, value: dict[str, entities.JSONValue]) -> None:
    logging.info("Writing credential JSON document")
    try:
        payload = (
            json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )
    except (TypeError, ValueError):
        raise VaultError("Vault contains an unsupported JSON value.") from None
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=".devos-", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        pathlib.Path(temporary).unlink(missing_ok=True)
    logging.info("Wrote credential JSON document")


def get_configured_vault(
    config_path: pathlib.Path | None = None, interactive: bool = False
) -> pathlib.Path:
    config_path = config_path or CONFIG_PATH
    config = read_document(config_path)
    directory = config.get("vault_directory")
    if not directory:
        if not interactive:
            raise VaultNotConfigured(
                "Vault is not configured. Run dev config creds in an interactive terminal."
            )
        directory = input("Credential vault directory: ").strip()
        if not directory:
            raise VaultError("A vault directory is required.")
        directory = str(pathlib.Path(directory).expanduser().resolve())
        config["vault_directory"] = directory
        write_document(config_path, config)
    if not isinstance(directory, str):
        raise VaultError("Configured vault directory must be a path string.")
    return pathlib.Path(directory).expanduser().resolve()


def validate_root_key(key: str) -> None:
    if not entities.ENVIRONMENT_KEY_PATTERN.fullmatch(key):
        raise VaultError("Invalid root credential key name.")
    if key.startswith(PROJECT_PREFIX):
        raise VaultError("Root credential names cannot start with project_.")


def validate_project(name: str) -> None:
    if not name or any(character in name for character in "\\/:\r\n"):
        raise VaultError("Invalid credential project identity.")


def get_local_vault() -> JSONCredentialVaultAdapter:
    return JSONCredentialVaultAdapter(get_configured_vault())


class JSONCredentialVaultAdapter:
    """Map project bundles onto a single validated JSON file."""

    def __init__(self, directory: pathlib.Path) -> None:
        self.directory = directory
        self.path = directory / "creds.json"

    def get_storage_identity(self, key: str) -> str:
        return key

    def read(self) -> dict[str, entities.JSONValue]:
        value = read_document(self.path)
        for key, item in value.items():
            if key.startswith(PROJECT_PREFIX):
                validate_project(key.removeprefix(PROJECT_PREFIX))
                entities.CredentialBundle.from_json_value(item, "project bundle")
            else:
                validate_root_key(key)
        return value

    def write(self, value: dict[str, entities.JSONValue]) -> None:
        for key, item in value.items():
            if key.startswith(PROJECT_PREFIX):
                validate_project(key.removeprefix(PROJECT_PREFIX))
                entities.CredentialBundle.from_json_value(item, "project bundle")
            else:
                validate_root_key(key)
        write_document(self.path, value)
        if self.read() != value:
            raise VaultError("Vault readback failed.")

    def get(self, key: str) -> entities.JSONValue:
        document = self.read()
        if key == "devos:general":
            return {
                name: value
                for name, value in document.items()
                if not name.startswith(PROJECT_PREFIX)
            }
        if key == "devos:projects":
            return typing.cast(
                entities.JSONValue,
                sorted(
                    name.removeprefix(PROJECT_PREFIX)
                    for name in document
                    if name.startswith(PROJECT_PREFIX)
                ),
            )
        if key.startswith("devos:projects:"):
            return document.get(PROJECT_PREFIX + key.removeprefix("devos:projects:"))
        raise VaultError("Unknown credential scope.")

    def put(self, key: str, value: entities.JSONValue) -> bool:
        document = self.read()
        if key == "devos:projects":
            return True  # The project registry is derived from the JSON objects.
        if key == "devos:general":
            bundle = entities.CredentialBundle.from_json_value(value, "root")
            for name in bundle.keys():
                validate_root_key(name)
            document = {
                name: item
                for name, item in document.items()
                if name.startswith(PROJECT_PREFIX)
            }
            document.update(bundle.values())
        elif key.startswith("devos:projects:"):
            name = key.removeprefix("devos:projects:")
            validate_project(name)
            document[PROJECT_PREFIX + name] = entities.CredentialBundle.from_json_value(
                value, "project"
            ).values()
        else:
            raise VaultError("Unknown credential scope.")
        self.write(document)
        return True

    def keys(self, pattern: str) -> list[str]:
        import fnmatch

        document = self.read()
        keys = [
            "devos:general",
            "devos:projects",
            *(
                "devos:projects:" + key.removeprefix(PROJECT_PREFIX)
                for key in document
                if key.startswith(PROJECT_PREFIX)
            ),
        ]
        return [key for key in keys if fnmatch.fnmatchcase(key, pattern)]


def get_remote_store(
    vault: JSONCredentialVaultAdapter, name: str
) -> credential_ports.CredentialStorePort:
    stores = read_document(vault.directory / "config.json").get("stores", {})
    if (
        not isinstance(stores, dict)
        or name not in stores
        or not isinstance(stores[name], dict)
    ):
        raise VaultError("Named store is not configured in the vault config.json.")
    target = typing.cast(dict[str, entities.JSONValue], stores[name])
    if target.get("type") == "redis":
        import devOS.infrastructure.adapters as adapters

        connection = target.get("connection", {})
        if not isinstance(connection, dict):
            raise VaultError("Redis connection must be an object.")
        allowed = {"url", "host", "port", "username", "password", "db", "ssl"}
        if set(connection) - allowed:
            raise VaultError("Unknown Redis connection field.")
        database = adapters.RedisNoSQLAdapter.from_environment(
            {
                "devos_redis_"
                + key: str(value).lower() if isinstance(value, bool) else str(value)
                for key, value in connection.items()
            }
        )
        if database is None:
            raise VaultError("Named Redis store requires a URL or host.")
        return database
    if target.get("type") == "prefect":
        if not isinstance(target.get("api_url"), str) or not target.get("api_url"):
            raise VaultError("Named Prefect store requires an api_url.")
        return PrefectCredentialStoreAdapter(target)
    raise VaultError("Named store type must be redis or prefect.")


class PrefectCredentialStoreAdapter:
    """Read and publish JSON Secret blocks under explicit Prefect settings."""

    def __init__(self, target: dict[str, entities.JSONValue]) -> None:
        self.__settings = PrefectStoreSettings.model_validate(target)

    def get_storage_identity(self, key: str) -> str:
        import re

        return re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")

    def get(self, key: str) -> entities.JSONValue:
        logging.info("Reading Prefect credential scope")
        blocks = importlib.import_module("prefect.blocks.system")
        settings = importlib.import_module("prefect.settings")
        secret_type = typing.cast(PrefectSecretTypeSchema, blocks.Secret)
        temporary_settings = typing.cast(
            typing.Callable[
                [dict[object, entities.JSONValue]],
                contextlib.AbstractContextManager[object],
            ],
            settings.temporary_settings,
        )

        with temporary_settings(
            {
                settings.PREFECT_API_URL: self.__settings.api_url,
                settings.PREFECT_API_KEY: (
                    self.__settings.api_key.get_secret_value()
                    if self.__settings.api_key is not None
                    else None
                ),
            }
        ):
            try:
                block = resolve_prefect_call(
                    secret_type.load(self.get_storage_identity(key))
                )
            except ValueError:
                logging.info("Prefect credential scope is absent")
                return None
            result = typing.cast(entities.JSONValue, json.loads(block.get()))
        logging.info("Read Prefect credential scope")
        return result

    def put(self, key: str, value: entities.JSONValue) -> bool:
        logging.info("Writing Prefect credential scope")
        blocks = importlib.import_module("prefect.blocks.system")
        settings = importlib.import_module("prefect.settings")
        secret_type = typing.cast(PrefectSecretTypeSchema, blocks.Secret)
        temporary_settings = typing.cast(
            typing.Callable[
                [dict[object, entities.JSONValue]],
                contextlib.AbstractContextManager[object],
            ],
            settings.temporary_settings,
        )

        with temporary_settings(
            {
                settings.PREFECT_API_URL: self.__settings.api_url,
                settings.PREFECT_API_KEY: (
                    self.__settings.api_key.get_secret_value()
                    if self.__settings.api_key is not None
                    else None
                ),
            }
        ):
            resolve_prefect_call(
                secret_type(
                    value=pydantic.SecretStr(json.dumps(value, ensure_ascii=False))
                ).save(self.get_storage_identity(key), overwrite=True)
            )
        logging.info("Wrote Prefect credential scope")
        return True


def resolve_prefect_call(
    value: PrefectResult | typing.Awaitable[PrefectResult],
) -> PrefectResult:
    """Resolve Prefect's sync and async method variants."""
    import asyncio
    import concurrent.futures
    import inspect

    if not inspect.isawaitable(value):
        return typing.cast(PrefectResult, value)

    async def await_value() -> PrefectResult:
        return await typing.cast(typing.Awaitable[PrefectResult], value)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(await_value())
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(await_value())).result()
