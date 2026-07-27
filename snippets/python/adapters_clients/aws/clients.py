from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AWSClientConfig:
    """Configuration for an AWS SDK session.

    Parameters
    ----------
    access_key_id
        AWS access key ID.
    secret_access_key
        AWS secret access key.
    region_name
        AWS region used for all resources.
    """

    access_key_id: str
    secret_access_key: str
    region_name: str


class AWSClient:
    """Create AWS resources through an injected or lazily created boto3 session.

    Parameters
    ----------
    config
        Credentials and region for creating a boto3 session.
    session
        Optional prebuilt boto3-compatible session. Tests should pass a fake
        session here to avoid real AWS calls.
    """

    def __init__(self, config: AWSClientConfig, session: Any | None = None) -> None:
        self.__config = config
        self.__session = session

    def __get_session(self) -> Any:
        if self.__session is not None:
            return self.__session

        import boto3

        self.__session = boto3.Session(
            aws_access_key_id=self.__config.access_key_id,
            aws_secret_access_key=self.__config.secret_access_key,
            region_name=self.__config.region_name,
        )
        return self.__session

    def get_resource(self, service_name: str) -> Any:
        """Return an AWS resource object.

        Parameters
        ----------
        service_name
            AWS service name such as ``"s3"`` or ``"dynamodb"``.

        Returns
        -------
        Any
            SDK resource object returned by the configured session.
        """

        return self.__get_session().resource(service_name)

    def get_s3_resource(self) -> Any:
        """Return the S3 resource for object storage adapters.

        Returns
        -------
        Any
            S3 resource object.
        """

        return self.get_resource("s3")

    def get_dynamodb_resource(self) -> Any:
        """Return the DynamoDB resource for key-value adapters.

        Returns
        -------
        Any
            DynamoDB resource object.
        """

        return self.get_resource("dynamodb")

    def get_s3_bucket(self, bucket_name: str) -> Any:
        """Return an S3 bucket object by name.

        Parameters
        ----------
        bucket_name
            Name of the S3 bucket.

        Returns
        -------
        Any
            S3 bucket object.
        """

        if not bucket_name:
            raise ValueError("bucket_name must be provided.")
        return self.get_s3_resource().Bucket(bucket_name)

    def get_dynamodb_table(self, table_name: str) -> Any:
        """Return a DynamoDB table object by name.

        Parameters
        ----------
        table_name
            Name of the DynamoDB table.

        Returns
        -------
        Any
            DynamoDB table object.
        """

        if not table_name:
            raise ValueError("table_name must be provided.")
        return self.get_dynamodb_resource().Table(table_name)
