import os
from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv

# Load .env into process environment
load_dotenv()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return int(value)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class EnvironmentVariables:
    """Minimal runtime configuration loaded from environment variables."""

    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = _env_int("REDIS_PORT", 6379)
    REDIS_PASSWORD: str | None = os.getenv("REDIS_PASSWORD")
    REDIS_DB: int = _env_int("REDIS_DB", 0)
    REDIS_SSL: bool = _env_bool("REDIS_SSL", False)

    MQTT_MOSQUITTO_BROKER: str = os.getenv("MQTT_MOSQUITTO_BROKER", "localhost")
    MQTT_MOSQUITTO_PORT: int = _env_int("MQTT_MOSQUITTO_PORT", 1883)
    MQTT_MOSQUITTO_USERNAME: str | None = os.getenv("MQTT_MOSQUITTO_USERNAME")
    MQTT_MOSQUITTO_PASSWORD: str | None = os.getenv("MQTT_MOSQUITTO_PASSWORD")

    EMAIL_HOST_USER: str | None = os.getenv("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD: str | None = os.getenv("EMAIL_HOST_PASSWORD")
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = _env_int("SMTP_PORT", 587)
    SMTP_USE_TLS: bool = _env_bool("SMTP_USE_TLS", True)


dotenv_var = EnvironmentVariables()


class RedisConfigsCreds(Enum):
    REDIS_HOST = dotenv_var.REDIS_HOST
    REDIS_PORT = dotenv_var.REDIS_PORT
    REDIS_PASSWORD = dotenv_var.REDIS_PASSWORD
    REDIS_DB = dotenv_var.REDIS_DB
    REDIS_SSL = dotenv_var.REDIS_SSL


class MqttMosquittoConfigsCreds(Enum):
    MQTT_MOSQUITTO_BROKER = dotenv_var.MQTT_MOSQUITTO_BROKER
    MQTT_MOSQUITTO_PORT = dotenv_var.MQTT_MOSQUITTO_PORT
    MQTT_MOSQUITTO_USERNAME = dotenv_var.MQTT_MOSQUITTO_USERNAME
    MQTT_MOSQUITTO_PASSWORD = dotenv_var.MQTT_MOSQUITTO_PASSWORD


class EmailConfigsCreds(Enum):
    EMAIL_HOST_USER = dotenv_var.EMAIL_HOST_USER
    EMAIL_HOST_PASSWORD = dotenv_var.EMAIL_HOST_PASSWORD
    SMTP_SERVER = dotenv_var.SMTP_SERVER
    SMTP_PORT = dotenv_var.SMTP_PORT
    SMTP_USE_TLS = dotenv_var.SMTP_USE_TLS
