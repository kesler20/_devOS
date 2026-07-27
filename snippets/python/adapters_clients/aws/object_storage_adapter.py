from __future__ import annotations

import json
from typing import Any


class S3ObjectStorageAdapter:
    """Store JSON-compatible objects in an AWS S3 bucket.

    Parameters
    ----------
    bucket
        S3 bucket object with ``put_object``.
    object_resource
        S3 resource object with ``Object(bucket_name, key)``.
    bucket_name
        Name of the bucket used by ``object_resource`` reads and deletes.
    """

    def __init__(self, bucket: Any, object_resource: Any, bucket_name: str) -> None:
        self.__bucket = bucket
        self.__object_resource = object_resource
        self.__bucket_name = bucket_name

    def write_object(self, resource_locator: str, content: Any) -> bool:
        """Write an object to S3.

        Parameters
        ----------
        resource_locator
            Object key.
        content
            JSON-compatible content or raw string.

        Returns
        -------
        bool
            ``True`` when the SDK confirms the key.
        """

        if not resource_locator or content is None:
            return False

        body = content if isinstance(content, str) else json.dumps(content)
        response = self.__bucket.put_object(Key=resource_locator, Body=body)
        return getattr(response, "key", None) == resource_locator

    def read_object(self, resource_locator: str) -> Any | None:
        """Read and JSON-decode an object from S3.

        Parameters
        ----------
        resource_locator
            Object key.

        Returns
        -------
        Any | None
            Decoded object content, or ``None`` when it cannot be read.
        """

        if not resource_locator:
            return None
        try:
            raw_body = (
                self.__object_resource.Object(self.__bucket_name, resource_locator)
                .get()["Body"]
                .read()
                .decode("utf-8")
            )
            return json.loads(raw_body)
        except Exception:
            return None

    def delete_object(self, resource_locator: str) -> bool:
        """Delete an S3 object.

        Parameters
        ----------
        resource_locator
            Object key.

        Returns
        -------
        bool
            ``True`` for any 2xx SDK response.
        """

        if not resource_locator:
            return False
        try:
            response = self.__object_resource.Object(
                self.__bucket_name,
                resource_locator,
            ).delete()
        except Exception:
            return False
        status_code = response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
        return 199 < status_code < 300
