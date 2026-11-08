from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import json
import re
import typing

JSONValue: typing.TypeAlias = (
    None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
)

BLOCK_NAME_PATTERN = re.compile(r"[^a-z0-9]+")


class SecretBlockPort(typing.Protocol):
    """The slice of a Prefect Secret block the adapter depends on."""

    @classmethod
    def load(cls, name: str) -> typing.Any: ...

    def save(self, name: str, overwrite: bool = False) -> typing.Any: ...


def block_name(key: str) -> str:
    """Map a store key to a valid Prefect block name (lowercase, digits, dashes)."""
    return BLOCK_NAME_PATTERN.sub("-", key.lower()).strip("-")


def _run(value: typing.Any) -> typing.Any:
    """Resolve a Prefect call that is sync or async depending on the context."""
    if not inspect.isawaitable(value):
        return value

    async def await_value() -> typing.Any:
        return await value

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(await_value())
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(await_value())).result()


def _unwrap(value: typing.Any) -> typing.Any:
    getter = getattr(value, "get_secret_value", None)
    return getter() if callable(getter) else value


class PrefectVaultAdapter:
    """Read JSON bundles from Prefect Secret blocks, creating them on demand.

    Satisfies the same ``get(key)`` contract as the Redis adapter, so the load
    credentials use case takes either store. ``ensure`` is the one write path: it
    loads the block named after a key and, when it does not exist yet, seeds it from
    the values already present in the environment, so the first run creates the block
    and later runs only read it.
    """

    def __init__(self, secret_block: type[SecretBlockPort] | None = None) -> None:
        if secret_block is None:
            from prefect.blocks.system import Secret

            secret_block = typing.cast("type[SecretBlockPort]", Secret)
        self.__secret_block = secret_block

    def __load(self, name: str) -> typing.Any | None:
        try:
            return _run(self.__secret_block.load(name))
        except ValueError:
            # Prefect raises ValueError when no block document has this name.
            return None

    @staticmethod
    def __decode(block: typing.Any) -> dict[str, JSONValue]:
        value = _unwrap(block.value if hasattr(block, "value") else block.get())
        return typing.cast("dict[str, JSONValue]", json.loads(value))

    def get(self, key: str) -> JSONValue:
        """Read and JSON-decode the bundle stored under a key, or None."""
        if not key:
            return None
        block = self.__load(block_name(key))
        return None if block is None else self.__decode(block)

    def ensure(
        self, key: str, environment_payload: typing.Mapping[str, typing.Any]
    ) -> dict[str, JSONValue]:
        """Load the bundle for a key, creating its block from the environment first.

        Only values that are set are stored, secret wrappers are unwrapped, and
        a missing block with nothing to seed it from raises ``ValueError``.
        """
        name = block_name(key)
        block = self.__load(name)
        if block is None:
            seed = {
                field: _unwrap(value)
                for field, value in environment_payload.items()
                if value is not None
            }
            if not seed:
                raise ValueError(
                    f"Block '{name}' not found and no environment values to create it."
                )
            secret = self.__secret_block(value=json.dumps(seed))  # type: ignore[call-arg]
            _run(secret.save(name, overwrite=True))
            block = self.__load(name)
        return self.__decode(block)
