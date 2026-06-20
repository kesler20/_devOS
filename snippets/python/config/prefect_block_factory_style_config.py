import os
import json
import typing
import asyncio
import inspect
from dotenv import load_dotenv

# ---- Pydantic compatibility (v1/v2) -----------------------------------------
try:
    from pydantic_settings import BaseSettings  # pydantic v2
except ImportError:  # fall back to v1
    from pydantic import BaseSettings  # type: ignore

from pydantic import Field, SecretStr
from enum import Enum  # added

# ---- Prefect blocks ----------------------------------------------------------
from prefect_github import GitHubCredentials
from prefect_redis.blocks import RedisDatabase
from prefect_aws import AwsCredentials
from prefect.blocks.system import Secret as PrefectSecret
from prefect_email import EmailServerCredentials  # added

# -----------------------------------------------------------------------------
# Load .env into process env, then let Pydantic read from env
# -----------------------------------------------------------------------------
load_dotenv()


# =======================================================#
#                                                        #
#   CONSTANT DEFINITIONS AND PREFECT BLOCK LOADER        #
#                                                        #
# =======================================================#


class EnvironmentVariables(BaseSettings):
    # --- Prefect --------------------------------------------------------------
    PREFECT_API_URL: str = "https://prefect-production.up.railway.app/api"

    # --- GitHub ---------------------------------------------------------------
    GITHUB_USERNAME: str = "kesler20"
    PAT: SecretStr | None = None  # personal access token

    # --- AWS ------------------------------------------------------------------
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: SecretStr | None = None
    AWS_REGION: str = "eu-west-2"

    # AWS IoT (paths kept as constants, not used in blocks here)
    PATH_TO_ROOT_CA: str = Field(
        default_factory=lambda: EnvironmentVariables.root_path("AmazonRootCA1 (1).pem")
    )
    PATH_TO_PRIVATE_KEY: str = Field(
        default_factory=lambda: EnvironmentVariables.root_path(
            "9343eecbd39fc8666c2dceff21b308511388e4812042b6a58374f20885f45b57-private.pem.key"
        )
    )
    PATH_TO_CERTIFICATE: str = Field(
        default_factory=lambda: EnvironmentVariables.root_path(
            "9343eecbd39fc8666c2dceff21b308511388e4812042b6a58374f20885f45b57-certificate.pem.crt"
        )
    )
    AWS_IOT_ENDPOINT: str = "a2gac7ap3hk6n-ats.iot.eu-west-2.amazonaws.com"

    # --- S3 / Data lake / MLflow ---------------------------------------------
    DATA_LAKE_NAME: str = "process-data-lake"
    MLFLOW_ARTIFACTS_BUCKET_NAME: str = "mlflow-artifacts8902"
    MLFLOW_TRACKING_URI: str = "https://mlflow-production-ed2d.up.railway.app"
    MLFLOW_S3_ENDPOINT_URL: str | None = None

    # --- MinIO ----------------------------------------------------------------
    MINIO_ENDPOINT: str | None = None
    MINIO_ACCESS_KEY: SecretStr | None = None
    MINIO_SECRET_KEY: SecretStr | None = None
    MINIO_BUCKET: str | None = (
        None  # will fallback to DATA_LAKE_NAME when building payload
    )
    MINIO_SECURE: bool = True
    AWS_S3_ADDRESSING_STYLE: str = "path"
    MINIO_BROWSER_REDIRECT_URL: str = "https://minioconsole.up.railway.app"

    # --- MQTT Mosquitto -------------------------------------------------------
    MQTT_MOSQUITTO_BROKER: str | None = None
    MQTT_MOSQUITTO_PORT: int = 1883
    MQTT_MOSQUITTO_USERNAME: str | None = None
    MQTT_MOSQUITTO_PASSWORD: SecretStr | None = None

    # --- Redis ----------------------------------------------------------------
    REDIS_HOST: str | None = None
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: SecretStr | None = None
    REDIS_DB: int = 0
    REDIS_SSL: bool = False

    # --- Email / SMTP ---------------------------------------------------------
    EMAIL_BLOCK_NAME: str = "email-alert-block"
    EMAIL_HOST_USER: str | None = None
    EMAIL_HOST_PASSWORD: SecretStr | None = None
    SMTP_SERVER: str = "smtp.gmail.com"

    class Config:
        # pydantic v1 compatibility
        env_file = ".env"
        env_file_encoding = "utf-8"

    # --- Derived properties --------------------------------------
    @classmethod
    def mlflow_artifacts_bucket(cls) -> str:
        return f"s3://{cls().MLFLOW_ARTIFACTS_BUCKET_NAME}/mlartifacts/"

    @classmethod
    def root_path(self, *parts) -> str:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts)


class PrefectBlockFactory:
    @staticmethod
    async def _maybe_await(obj):
        if inspect.isawaitable(obj):
            return await obj
        return obj

    @staticmethod
    def _unwrap_secret(v: typing.Any) -> typing.Any:
        return v.get_secret_value() if isinstance(v, SecretStr) else v

    @staticmethod
    def _non_none_items(d: dict[str, typing.Any]) -> dict[str, typing.Any]:
        return {
            k: PrefectBlockFactory._unwrap_secret(v)
            for k, v in d.items()
            if v is not None
        }

    @staticmethod
    def _run_async(
        coro_fn: typing.Callable[[], typing.Awaitable[typing.Any]],
    ) -> typing.Any:
        """Run an async callable safely whether we're in an event loop or not."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro_fn())  # type: ignore
        else:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(lambda: asyncio.run(coro_fn())).result()  # type: ignore

    @staticmethod
    def _sync_to_os_environ(d: dict[str, typing.Any]) -> None:
        """Copy key/values into os.environ without overwriting existing vars."""
        for k, v in d.items():
            if v is None:
                continue
            os.environ.setdefault(k, str(v))

    @classmethod
    async def _ensure_block_as_dict_async(
        cls,
        block_cls: type,
        block_name: str,
        env_payload: dict[str, typing.Any],
        *,
        ctor_map: dict[str, str] | None = None,
        pack_as_secret_json: bool = False,
        sync_to_os_environ: bool = False,
    ) -> dict[str, typing.Any]:
        """
        Try to load a Prefect block. If not found:
          - Check env_payload for any non-None values (already read via Pydantic)
          - If present, create the block (mapping env keys -> ctor kwargs via ctor_map)
        Always return a dict whose keys are the ENV/CONSTANT names and values are the stored values
        (with SecretStr unwrapped). For Secret blocks with JSON payload, returns that JSON object.
        Optionally, when sync_to_os_environ=True, copy resolved values into os.environ without
        overwriting any existing process environment variables.
        """
        ctor_map = ctor_map or {}

        # 1) Try to load the block
        try:
            block = await cls._maybe_await(block_cls.load(block_name))  # type: ignore[attr-defined]
        except ValueError:
            # 2) Create if we have any material values
            filtered = cls._non_none_items(env_payload)

            if not filtered:
                # Nothing to create with
                raise ValueError(
                    f"Block '{block_name}' not found and no environment-backed values provided."
                )

            if pack_as_secret_json:
                # Store the env payload as a single JSON secret
                payload_json = json.dumps(filtered)
                await cls._maybe_await(
                    PrefectSecret(value=SecretStr(payload_json)).save(
                        name=block_name, overwrite=True
                    )
                )
                print(f"[{block_name}] created ✅ (Prefect Secret JSON)")
                block = await cls._maybe_await(PrefectSecret.load(block_name))
            else:
                # Map env keys -> ctor kwargs where needed
                ctor_kwargs = {ctor_map.get(k, k): v for k, v in filtered.items()}
                await cls._maybe_await(block_cls(**ctor_kwargs).save(block_name, overwrite=True))  # type: ignore[misc]
                print(f"[{block_name}] created ✅")
                block = await cls._maybe_await(block_cls.load(block_name))  # type: ignore[attr-defined]

        # 3) Convert loaded block to dict keyed by ENV/CONSTANT names
        #    - For Secret JSON blocks, parse and return that JSON as-is (already env-keyed)
        if isinstance(block, PrefectSecret):
            try:
                base = json.loads(block.value.get_secret_value())
            except Exception:
                base = {"value": block.value.get_secret_value()}
            # Enrich with env/config keys (prefer block values if present)
            enriched = {**env_payload, **base}
            # unwrap secrets
            result_secret = {k: cls._unwrap_secret(v) for k, v in enriched.items()}
            if sync_to_os_environ:
                cls._sync_to_os_environ(result_secret)
            return result_secret

        # Pydantic v2: model_dump, v1: dict()
        model_dict: dict[str, typing.Any]
        if hasattr(block, "model_dump"):
            model_dict = block.model_dump()  # type: ignore[attr-defined]
        elif hasattr(block, "dict"):
            model_dict = block.dict()  # type: ignore[attr-defined]
        else:
            model_dict = {k: v for k, v in vars(block).items() if not k.startswith("_")}

        # invert ctor_map to return env-constant keys
        inv_map = {v: k for k, v in (ctor_map or {}).items()}
        result: dict[str, typing.Any] = {}
        for k, v in model_dict.items():
            env_key = inv_map.get(k, k)  # return original const name if we mapped
            result[env_key] = cls._unwrap_secret(v)

        # Enrich with env/config keys that are not represented in the block
        for k, v in env_payload.items():
            if k not in result and v is not None:
                result[k] = cls._unwrap_secret(v)

        if sync_to_os_environ:
            cls._sync_to_os_environ(result)
        return result

    @classmethod
    def ensure_block_as_dict(
        cls,
        block_cls: type,
        block_name: str,
        env_payload: dict[str, typing.Any],
        *,
        ctor_map: dict[str, str] | None = None,
        pack_as_secret_json: bool = False,
        sync_to_os_environ: bool = False,
    ) -> dict[str, typing.Any]:
        """Sync wrapper for _ensure_block_as_dict_async."""
        block_dict: dict[str, typing.Any] = cls._run_async(
            lambda: cls._ensure_block_as_dict_async(
                block_cls,
                block_name,
                env_payload,
                ctor_map=ctor_map,
                pack_as_secret_json=pack_as_secret_json,
                sync_to_os_environ=sync_to_os_environ,
            )
        )
        return block_dict


dotenv_var = EnvironmentVariables()


class GithubConfigsCreds(Enum):
    @staticmethod
    def get_value(value: str) -> typing.Any:
        return PrefectBlockFactory.ensure_block_as_dict(
            block_cls=GitHubCredentials,
            block_name=f"{dotenv_var.GITHUB_USERNAME}-admin-creds",
            env_payload={
                "PAT": dotenv_var.PAT,
                "GITHUB_USERNAME": dotenv_var.GITHUB_USERNAME,
            },
            ctor_map={"PAT": "token"},
            sync_to_os_environ=True,
        ).get(value)

    GITHUB_USERNAME = dotenv_var.GITHUB_USERNAME
    PAT = get_value("PAT")


class AwsConfigsCreds(Enum):
    @staticmethod
    def get_value(value: str) -> typing.Any:
        return PrefectBlockFactory.ensure_block_as_dict(
            block_cls=AwsCredentials,
            block_name="aws-credentials",
            env_payload={
                "AWS_ACCESS_KEY_ID": dotenv_var.AWS_ACCESS_KEY_ID,
                "AWS_SECRET_ACCESS_KEY": dotenv_var.AWS_SECRET_ACCESS_KEY,
                "AWS_REGION": dotenv_var.AWS_REGION,
            },
            ctor_map={
                "AWS_ACCESS_KEY_ID": "aws_access_key_id",
                "AWS_SECRET_ACCESS_KEY": "aws_secret_access_key",
                "AWS_REGION": "region_name",
            },
            sync_to_os_environ=True,
        ).get(value)

    AWS_ACCESS_KEY_ID = get_value("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = get_value("AWS_SECRET_ACCESS_KEY")
    AWS_REGION = get_value("AWS_REGION")
    DATA_LAKE_NAME = dotenv_var.DATA_LAKE_NAME


class RedisConfigsCreds(Enum):
    @staticmethod
    def get_value(value: str) -> typing.Any:
        return PrefectBlockFactory.ensure_block_as_dict(
            block_cls=RedisDatabase,
            block_name="redis-database",
            env_payload={
                "REDIS_HOST": dotenv_var.REDIS_HOST,
                "REDIS_PORT": dotenv_var.REDIS_PORT,
                "REDIS_PASSWORD": dotenv_var.REDIS_PASSWORD,
                "REDIS_DB": dotenv_var.REDIS_DB,
                "REDIS_SSL": dotenv_var.REDIS_SSL,
            },
            ctor_map={
                "REDIS_HOST": "host",
                "REDIS_PORT": "port",
                "REDIS_PASSWORD": "password",
                "REDIS_DB": "db",
                "REDIS_SSL": "ssl",
            },
            sync_to_os_environ=True,
        ).get(value)

    REDIS_HOST = get_value("REDIS_HOST")
    REDIS_PORT = get_value("REDIS_PORT")
    REDIS_PASSWORD = get_value("REDIS_PASSWORD")
    REDIS_DB = get_value("REDIS_DB")
    REDIS_SSL = get_value("REDIS_SSL")


class MinioConfigsCreds(Enum):
    @staticmethod
    def get_value(value: str) -> typing.Any:
        return PrefectBlockFactory.ensure_block_as_dict(
            block_cls=PrefectSecret,
            block_name="minio-credentials",
            env_payload={
                "MINIO_ENDPOINT": dotenv_var.MINIO_ENDPOINT,
                "MINIO_ACCESS_KEY": dotenv_var.MINIO_ACCESS_KEY,
                "MINIO_SECRET_KEY": dotenv_var.MINIO_SECRET_KEY,
                "MINIO_BUCKET": dotenv_var.MINIO_BUCKET or dotenv_var.DATA_LAKE_NAME,
                "MINIO_SECURE": dotenv_var.MINIO_SECURE,
                "AWS_S3_ADDRESSING_STYLE": dotenv_var.AWS_S3_ADDRESSING_STYLE,
                "MLFLOW_S3_ENDPOINT_URL": dotenv_var.MLFLOW_S3_ENDPOINT_URL,
                "MINIO_BROWSER_REDIRECT_URL": dotenv_var.MINIO_BROWSER_REDIRECT_URL,
            },
            pack_as_secret_json=True,
            sync_to_os_environ=True,
        ).get(value)

    MINIO_ENDPOINT = get_value("MINIO_ENDPOINT")
    MINIO_ACCESS_KEY = get_value("MINIO_ACCESS_KEY")
    MINIO_SECRET_KEY = get_value("MINIO_SECRET_KEY")
    MINIO_BUCKET = get_value("MINIO_BUCKET")
    MINIO_SECURE = get_value("MINIO_SECURE")
    AWS_S3_ADDRESSING_STYLE = get_value("AWS_S3_ADDRESSING_STYLE")
    MLFLOW_S3_ENDPOINT_URL = get_value("MLFLOW_S3_ENDPOINT_URL")
    MINIO_BROWSER_REDIRECT_URL = get_value("MINIO_BROWSER_REDIRECT_URL")


class MqttMosquittoConfigsCreds(Enum):
    @staticmethod
    def get_value(value: str) -> typing.Any:
        return PrefectBlockFactory.ensure_block_as_dict(
            block_cls=PrefectSecret,
            block_name="mqtt-mosquitto-credentials",
            env_payload={
                "MQTT_MOSQUITTO_BROKER": dotenv_var.MQTT_MOSQUITTO_BROKER,
                "MQTT_MOSQUITTO_PORT": dotenv_var.MQTT_MOSQUITTO_PORT,
                "MQTT_MOSQUITTO_USERNAME": dotenv_var.MQTT_MOSQUITTO_USERNAME,
                "MQTT_MOSQUITTO_PASSWORD": dotenv_var.MQTT_MOSQUITTO_PASSWORD,
            },
            pack_as_secret_json=True,
            sync_to_os_environ=True,
        ).get(value)

    MQTT_MOSQUITTO_BROKER = get_value("MQTT_MOSQUITTO_BROKER")
    MQTT_MOSQUITTO_PORT = get_value("MQTT_MOSQUITTO_PORT")
    MQTT_MOSQUITTO_USERNAME = get_value("MQTT_MOSQUITTO_USERNAME")
    MQTT_MOSQUITTO_PASSWORD = get_value("MQTT_MOSQUITTO_PASSWORD")


class MlflowConfigsCreds(Enum):
    @staticmethod
    def get_value(value: str) -> typing.Any:
        return PrefectBlockFactory.ensure_block_as_dict(
            block_cls=PrefectSecret,
            block_name="mlflow-credentials",
            env_payload={
                "MLFLOW_TRACKING_URI": dotenv_var.MLFLOW_TRACKING_URI,
                "MLFLOW_ARTIFACTS_BUCKET_NAME": dotenv_var.MLFLOW_ARTIFACTS_BUCKET_NAME,
                "MLFLOW_S3_ENDPOINT_URL": dotenv_var.MLFLOW_S3_ENDPOINT_URL,
                "MINIO_BROWSER_REDIRECT_URL": dotenv_var.MINIO_BROWSER_REDIRECT_URL,
            },
            pack_as_secret_json=True,
            sync_to_os_environ=True,
        ).get(value)

    MLFLOW_TRACKING_URI = get_value("MLFLOW_TRACKING_URI")
    MLFLOW_ARTIFACTS_BUCKET_NAME = get_value("MLFLOW_ARTIFACTS_BUCKET_NAME")
    MLFLOW_ARTIFACTS_BUCKET = dotenv_var.mlflow_artifacts_bucket()
    MLFLOW_S3_ENDPOINT_URL = get_value("MLFLOW_S3_ENDPOINT_URL")
    MINIO_BROWSER_REDIRECT_URL = get_value("MINIO_BROWSER_REDIRECT_URL")


class EmailConfigsCreds(Enum):
    @staticmethod
    def get_value(value: str) -> typing.Any:
        return PrefectBlockFactory.ensure_block_as_dict(
            block_cls=EmailServerCredentials,
            block_name=dotenv_var.EMAIL_BLOCK_NAME,
            env_payload={
                "EMAIL_HOST_USER": dotenv_var.EMAIL_HOST_USER,
                "EMAIL_HOST_PASSWORD": dotenv_var.EMAIL_HOST_PASSWORD,
                "SMTP_SERVER": dotenv_var.SMTP_SERVER,
            },
            ctor_map={
                "EMAIL_HOST_USER": "username",
                "EMAIL_HOST_PASSWORD": "password",
                "SMTP_SERVER": "smtp_server",
            },
            sync_to_os_environ=True,
        ).get(value)

    EMAIL_BLOCK_NAME = dotenv_var.EMAIL_BLOCK_NAME
    EMAIL_HOST_USER = get_value("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = get_value("EMAIL_HOST_PASSWORD")
    SMTP_SERVER = get_value("SMTP_SERVER")
    SMTP_PORT = get_value("SMTP_PORT")
    SMTP_TYPE = get_value("SMTP_TYPE")
    EMAIL_FROM = get_value("EMAIL_FROM")


class AwsIotConfigsCreds(Enum):
    PATH_TO_ROOT_CA = dotenv_var.PATH_TO_ROOT_CA
    PATH_TO_PRIVATE_KEY = dotenv_var.PATH_TO_PRIVATE_KEY
    PATH_TO_CERTIFICATE = dotenv_var.PATH_TO_CERTIFICATE
    AWS_IOT_ENDPOINT = dotenv_var.AWS_IOT_ENDPOINT


class PrefectConfigsCreds(Enum):
    PREFECT_API_URL = dotenv_var.PREFECT_API_URL
