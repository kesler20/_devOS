import typing
from enum import Enum
from dotenv import load_dotenv
import typing

# Use pydantic-settings for v2, fall back to pydantic v1
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict  # pydantic v2

    V2_SETTINGS = True
except ImportError:  # fall back to v1
    from pydantic import BaseSettings  # type: ignore

    SettingsConfigDict = None  # type: ignore
    V2_SETTINGS = False
from pydantic import SecretStr

# -----------------------------------------------------------------------------
# Load .env into process env, then let Pydantic read from env
# -----------------------------------------------------------------------------
load_dotenv()


class EnvironmentVariables(BaseSettings):  # type: ignore
    # --- TickTick -------------------------------------------------------------
    ticktick_client_id: str | None = None
    ticktick_client_secret: SecretStr | None = None
    ticktick_access_token: SecretStr | None = None
    ticktick_username: str | None = None
    ticktick_password: str | None = None

    # GitHub API
    github_token: SecretStr | None = None
    github_username: str | None = None

    # Pydantic v1/v2 config (mutually exclusive)
    if not V2_SETTINGS:

        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            extra = "allow"

    else:
        model_config = SettingsConfigDict(  # type: ignore[name-defined]
            env_file=".env", env_file_encoding="utf-8", extra="allow"
        )


env = EnvironmentVariables()


def _unwrap_secret(v: typing.Any) -> typing.Any:
    if isinstance(v, SecretStr):
        return v.get_secret_value()
    return v


def _require(v: typing.Any, name: str) -> typing.Any:
    value = _unwrap_secret(v)
    if value is None or (isinstance(value, str) and value.strip() == ""):
        print(f"Warning: Missing required environment variable: {name}")
    return value


class TickTickCreds(Enum):
    CLIENT_ID = _require(env.ticktick_client_id, "ticktick_client_id")
    CLIENT_SECRET = _require(env.ticktick_client_secret, "ticktick_client_secret")
    ACCESS_TOKEN = _require(env.ticktick_access_token, "ticktick_access_token")
    USERNAME = _require(env.ticktick_username, "ticktick_username")
    PASSWORD = _require(env.ticktick_password, "ticktick_password")


class GitHubAPICreds(Enum):
    GITHUB_TOKEN = _require(env.github_token, "github_token")
    USERNAME = _require(env.github_username, "github_username")
