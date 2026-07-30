import os
import typing
from enum import Enum

from dotenv import load_dotenv
from pydantic import SecretStr

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings  # type: ignore

from .credentials import runtime_loader


PROJECT_NAME = "__DEVOS_PROJECT_NAME__"

load_dotenv()
runtime_loader.LoadCredentialsUseCase.from_environment(PROJECT_NAME).execute()


class EnvironmentVariables(BaseSettings):
    PREFECT_API_URL: str = "https://prefect-production.up.railway.app/api"

    GITHUB_USERNAME: str = "kesler20"
    PAT: SecretStr | None = None

    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: SecretStr | None = None
    AWS_REGION: str = "eu-west-2"

    DATA_LAKE_NAME: str = "process-data-lake"
    MLFLOW_ARTIFACTS_BUCKET_NAME: str = "mlflow-artifacts8902"
    MLFLOW_TRACKING_URI: str = "https://mlflow-production-ed2d.up.railway.app"
    MLFLOW_S3_ENDPOINT_URL: str | None = None

    MINIO_PUBLIC_ENDPOINT: str = "https://bucket-production-d128.up.railway.app:443"
    MINIO_ROOT_PASSWORD: SecretStr | None = None
    MINIO_ROOT_USER: SecretStr | None = None
    MINIO_BUCKET: str | None = None
    MINIO_SECURE: bool = True
    AWS_S3_ADDRESSING_STYLE: str = "path"
    MINIO_BROWSER_REDIRECT_URL: str = "https://console-production-255d.up.railway.app"

    MQTT_MOSQUITTO_BROKER: str | None = None
    MQTT_MOSQUITTO_PORT: int = 1883
    MQTT_MOSQUITTO_USERNAME: str | None = None
    MQTT_MOSQUITTO_PASSWORD: SecretStr | None = None

    REDIS_HOST: str | None = None
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: SecretStr | None = None
    REDIS_DB: int = 0
    REDIS_SSL: bool = False

    EMAIL_BLOCK_NAME: str = "email-alert-block"
    EMAIL_HOST_USER: str | None = None
    EMAIL_HOST_PASSWORD: SecretStr | None = None
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_TYPE: str = "STARTTLS"
    EMAIL_FROM: str | None = None

    DOCKER_HUB_USERNAME: str | None = None
    DOCKER_HUB_PASSWORD: SecretStr | None = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @classmethod
    def mlflow_artifacts_bucket(cls) -> str:
        return f"s3://{cls().MLFLOW_ARTIFACTS_BUCKET_NAME}/mlartifacts/"

    @classmethod
    def root_path(cls, *parts: str) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts)


def unwrap_secret(value: typing.Any) -> typing.Any:
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    return value


dotenv_var = EnvironmentVariables()


class GithubConfigsCreds(Enum):
    GITHUB_USERNAME = dotenv_var.GITHUB_USERNAME
    PAT = unwrap_secret(dotenv_var.PAT)


class AwsConfigsCreds(Enum):
    AWS_ACCESS_KEY_ID = dotenv_var.AWS_ACCESS_KEY_ID
    AWS_SECRET_ACCESS_KEY = unwrap_secret(dotenv_var.AWS_SECRET_ACCESS_KEY)
    AWS_REGION = dotenv_var.AWS_REGION
    DATA_LAKE_NAME = dotenv_var.DATA_LAKE_NAME


class RedisConfigsCreds(Enum):
    REDIS_HOST = dotenv_var.REDIS_HOST
    REDIS_PORT = dotenv_var.REDIS_PORT
    REDIS_PASSWORD = unwrap_secret(dotenv_var.REDIS_PASSWORD)
    REDIS_DB = dotenv_var.REDIS_DB
    REDIS_SSL = dotenv_var.REDIS_SSL


class MinioConfigsCreds(Enum):
    MINIO_PUBLIC_ENDPOINT = dotenv_var.MINIO_PUBLIC_ENDPOINT
    MINIO_ROOT_USER = unwrap_secret(dotenv_var.MINIO_ROOT_USER)
    MINIO_ROOT_PASSWORD = unwrap_secret(dotenv_var.MINIO_ROOT_PASSWORD)
    MINIO_BUCKET = dotenv_var.MINIO_BUCKET or dotenv_var.DATA_LAKE_NAME
    MINIO_SECURE = dotenv_var.MINIO_SECURE
    AWS_S3_ADDRESSING_STYLE = dotenv_var.AWS_S3_ADDRESSING_STYLE
    MLFLOW_S3_ENDPOINT_URL = dotenv_var.MLFLOW_S3_ENDPOINT_URL
    MINIO_BROWSER_REDIRECT_URL = dotenv_var.MINIO_BROWSER_REDIRECT_URL


class MqttMosquittoConfigsCreds(Enum):
    MQTT_MOSQUITTO_BROKER = dotenv_var.MQTT_MOSQUITTO_BROKER
    MQTT_MOSQUITTO_PORT = dotenv_var.MQTT_MOSQUITTO_PORT
    MQTT_MOSQUITTO_USERNAME = dotenv_var.MQTT_MOSQUITTO_USERNAME
    MQTT_MOSQUITTO_PASSWORD = unwrap_secret(dotenv_var.MQTT_MOSQUITTO_PASSWORD)


class MlflowConfigsCreds(Enum):
    MLFLOW_TRACKING_URI = dotenv_var.MLFLOW_TRACKING_URI
    MLFLOW_ARTIFACTS_BUCKET_NAME = dotenv_var.MLFLOW_ARTIFACTS_BUCKET_NAME
    MLFLOW_ARTIFACTS_BUCKET = dotenv_var.mlflow_artifacts_bucket()
    MLFLOW_S3_ENDPOINT_URL = dotenv_var.MLFLOW_S3_ENDPOINT_URL
    MINIO_BROWSER_REDIRECT_URL = dotenv_var.MINIO_BROWSER_REDIRECT_URL


class EmailConfigsCreds(Enum):
    EMAIL_BLOCK_NAME = dotenv_var.EMAIL_BLOCK_NAME
    EMAIL_HOST_USER = dotenv_var.EMAIL_HOST_USER
    EMAIL_HOST_PASSWORD = unwrap_secret(dotenv_var.EMAIL_HOST_PASSWORD)
    SMTP_SERVER = dotenv_var.SMTP_SERVER
    SMTP_PORT = dotenv_var.SMTP_PORT
    SMTP_TYPE = dotenv_var.SMTP_TYPE
    EMAIL_FROM = dotenv_var.EMAIL_FROM


class DockerConfigsCreds(Enum):
    DOCKER_HUB_USERNAME = dotenv_var.DOCKER_HUB_USERNAME
    DOCKER_HUB_PASSWORD = unwrap_secret(dotenv_var.DOCKER_HUB_PASSWORD)


class PrefectConfigsCreds(Enum):
    PREFECT_API_URL = dotenv_var.PREFECT_API_URL
