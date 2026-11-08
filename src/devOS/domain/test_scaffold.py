import dataclasses
import typing

HttpMethod = typing.Literal["get", "post", "put", "patch", "delete", "options", "head"]


@dataclasses.dataclass(frozen=True)
class EndpointScaffold:
    name: str
    method: HttpMethod
    path: str
    parameters: list[str]


@dataclasses.dataclass(frozen=True)
class UseCaseScaffold:
    name: str
    dependencies: list[str]
    inputs: list[str]
    asynchronous: bool
