from __future__ import annotations

from typing import Any

from adapters_clients.aws.object_storage_adapter import S3ObjectStorageAdapter


class MinIOObjectStorageAdapter(S3ObjectStorageAdapter):
    """Store objects in MinIO through an S3-compatible client.

    Parameters
    ----------
    bucket
        MinIO bucket object with ``put_object``.
    object_resource
        S3-compatible MinIO resource with ``Object(bucket_name, key)``.
    bucket_name
        Name of the MinIO bucket.
    """

    def __init__(self, bucket: Any, object_resource: Any, bucket_name: str) -> None:
        super().__init__(
            bucket=bucket,
            object_resource=object_resource,
            bucket_name=bucket_name,
        )
