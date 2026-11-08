import typing

from devOS.domain import entities


class CredentialStorePort(typing.Protocol):
    def get(self, key: str) -> entities.JSONValue: ...

    def put(self, key: str, value: entities.JSONValue) -> bool: ...

    def get_storage_identity(self, key: str) -> str: ...


class CredentialDatabasePort(CredentialStorePort, typing.Protocol):
    def keys(self, pattern: str) -> list[str]: ...
