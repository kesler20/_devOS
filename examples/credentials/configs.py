"""Explicit remote-loading example, independent of automation_engine."""
from pathlib import Path
import dotenv
import pydantic_settings
from .loading_creds import LoadingCredsUseCase

dotenv.load_dotenv(Path(__file__).with_name(".env"), interpolate=False)
LoadingCredsUseCase.from_environment().execute()

class EnvironmentVariables(pydantic_settings.BaseSettings):
    model_config = pydantic_settings.SettingsConfigDict(extra="ignore")

settings = EnvironmentVariables()
