import keyword
import re
import typing

import pydantic


class ResourceApiImports(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    dao_module: str
    dto_module: str
    crud_module: str
    session_module: str
    session_provider: str = "get_session"

    @pydantic.field_validator(
        "dao_module", "dto_module", "crud_module", "session_module"
    )
    @classmethod
    def validate_module(cls, value: str) -> str:
        if any(
            not part.isidentifier() or keyword.iskeyword(part)
            for part in value.split(".")
        ):
            raise ValueError("Imports must be dotted Python module names")
        return value

    @pydantic.field_validator("session_provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        if not value.isidentifier() or keyword.iskeyword(value):
            raise ValueError("Session provider must be a Python function name")
        return value


def get_resource_path(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


class ResourceOperation(typing.NamedTuple):
    method: typing.Literal["get", "post", "patch", "delete"]
    url: str
    name: typing.Literal["create", "list", "read", "patch", "delete", "expanded"]
    arguments: str
    response: str
    body: str
    status: typing.Literal[200, 201]
