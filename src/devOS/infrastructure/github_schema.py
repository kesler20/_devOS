import pydantic


class JsonObjectResponse(pydantic.RootModel[dict[str, pydantic.JsonValue]]):
    pass


class RepositoryResponse(pydantic.BaseModel):
    description: str | None = None


class UserResponse(pydantic.BaseModel):
    login: str


class RepositoryRequest(pydantic.BaseModel):
    name: str
    description: str
    private: bool = True
    auto_init: bool = False


class DescriptionRequest(pydantic.BaseModel):
    description: str


class PublicKeyResponse(pydantic.BaseModel):
    key: str
    key_id: str


class SecretRequest(pydantic.BaseModel):
    encrypted_value: str
    key_id: str


class SecretMetadata(pydantic.BaseModel):
    name: str


class SecretListResponse(pydantic.BaseModel):
    secrets: list[SecretMetadata]
