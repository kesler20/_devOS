import typing
from dotenv import load_dotenv

# Use pydantic-settings for v2, fall back to pydantic v1
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict  # pydantic v2

    V2_SETTINGS = True
except ImportError:  # fall back to v1
    from pydantic import BaseSettings  # type: ignore

    SettingsConfigDict = None  # type: ignore
    V2_SETTINGS = False

# -----------------------------------------------------------------------------
# Load .env into process env, then let Pydantic read from env
# -----------------------------------------------------------------------------
load_dotenv()


class EnvironmentVariables(BaseSettings):  # type: ignore
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
