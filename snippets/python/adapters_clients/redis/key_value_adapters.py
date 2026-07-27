from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DynamoKeyValueAdapter:
    """Store JSON-like values in a DynamoDB-style table.

    Parameters
    ----------
    table
        DynamoDB table-like object with ``put_item``, ``query``, and
        ``delete_item``.
    partition_key
        Partition key column name.
    sort_key
        Sort key column name.
    key_builder
        Callable that builds a key condition expression for the underlying SDK.
    """

    def __init__(
        self,
        table: Any,
        partition_key: str = "category",
        sort_key: str = "date",
        key_builder: Any | None = None,
    ) -> None:
        self.__table = table
        self.__partition_key = partition_key
        self.__sort_key = sort_key
        self.__key_builder = key_builder

    def put(self, category: str, date: int, value: dict[str, Any]) -> bool:
        """Write a value by category and date.

        Parameters
        ----------
        category
            Partition key value.
        date
            Sort key value.
        value
            Data to store.

        Returns
        -------
        bool
            ``True`` for any 2xx SDK response.
        """

        if not category or not isinstance(date, int) or date <= 0 or not value:
            return False

        item = {self.__partition_key: category, self.__sort_key: date, **value}
        response = self.__table.put_item(Item=self.__convert_floats_to_ints(item))
        status_code = response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
        return 199 < status_code < 300

    def get(self, category: str, date: int) -> dict[str, Any] | None:
        """Read a value by category and date.

        Parameters
        ----------
        category
            Partition key value.
        date
            Sort key value.

        Returns
        -------
        dict[str, Any] | None
            Stored item, or ``None``.
        """

        if not category or not isinstance(date, int) or date <= 0:
            return None

        if self.__key_builder is None:
            response = self.__table.query(
                Key={
                    self.__partition_key: category,
                    self.__sort_key: date,
                }
            )
        else:
            response = self.__table.query(
                KeyConditionExpression=self.__key_builder(category, date)
            )
        items = response.get("Items", [])
        return items[0] if items else None

    def delete(self, category: str, date: int) -> bool:
        """Delete a value by category and date.

        Parameters
        ----------
        category
            Partition key value.
        date
            Sort key value.

        Returns
        -------
        bool
            ``True`` for any 2xx SDK response.
        """

        if not category or not isinstance(date, int) or date <= 0:
            return False

        response = self.__table.delete_item(
            Key={self.__partition_key: category, self.__sort_key: date}
        )
        status_code = response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
        return 199 < status_code < 300

    def __convert_floats_to_ints(self, data: Any) -> Any:
        if isinstance(data, float):
            return int(data)
        if isinstance(data, dict):
            return {
                self.__convert_floats_to_ints(key): self.__convert_floats_to_ints(value)
                for key, value in data.items()
            }
        if isinstance(data, list):
            return [self.__convert_floats_to_ints(item) for item in data]
        return data


class RedisKeyValueAdapter:
    """Store JSON values in a Redis-like client.

    Parameters
    ----------
    redis_client
        Object with ``set``, ``get``, and ``delete`` methods.
    """

    def __init__(self, redis_client: Any) -> None:
        self.__redis_client = redis_client

    def put(self, key: str, value: Any) -> bool:
        """Write a JSON-encoded value.

        Parameters
        ----------
        key
            Storage key.
        value
            JSON-compatible value.

        Returns
        -------
        bool
            ``True`` when Redis accepts the value.
        """

        if not key:
            return False
        return bool(self.__redis_client.set(key, json.dumps(value)))

    def get(self, key: str) -> Any | None:
        """Read and JSON-decode a value.

        Parameters
        ----------
        key
            Storage key.

        Returns
        -------
        Any | None
            Decoded value, or ``None``.
        """

        if not key:
            return None
        value = self.__redis_client.get(key)
        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return json.loads(value)

    def delete(self, key: str) -> bool:
        """Delete a value.

        Parameters
        ----------
        key
            Storage key.

        Returns
        -------
        bool
            ``True`` when Redis reports a deletion.
        """

        if not key:
            return False
        return bool(self.__redis_client.delete(key))


class RedisHashNoSQLAdapter:
    """Store dictionary values in Redis hashes.

    Parameters
    ----------
    redis_client
        Redis-like client with ``ping``, ``hset``, ``hgetall``, and ``delete``.
    """

    def __init__(self, redis_client: Any) -> None:
        self.__redis_client = redis_client

    def is_available(self) -> bool:
        """Check whether Redis responds to ping.

        Returns
        -------
        bool
            ``True`` when Redis responds successfully.
        """

        try:
            return bool(self.__redis_client.ping())
        except Exception:
            return False

    def put(self, key: str, value: dict[str, Any]) -> bool:
        """Write a dictionary into a Redis hash.

        Parameters
        ----------
        key
            Redis hash key.
        value
            JSON-compatible dictionary.

        Returns
        -------
        bool
            ``True`` when the write succeeds.
        """

        if not key:
            return False
        try:
            serialised = {name: json.dumps(item) for name, item in value.items()}
            self.__redis_client.hset(key, mapping=serialised)
            return True
        except Exception:
            return False

    def get(self, key: str) -> dict[str, Any]:
        """Read a Redis hash into a dictionary.

        Parameters
        ----------
        key
            Redis hash key.

        Returns
        -------
        dict[str, Any]
            Decoded dictionary, or an empty dictionary.
        """

        if not key:
            return {}
        try:
            data = self.__redis_client.hgetall(key)
        except Exception:
            return {}
        if not data:
            return {}
        decoded_data = {}
        for name, value in data.items():
            decoded_name = name.decode("utf-8") if isinstance(name, bytes) else name
            decoded_value = value.decode("utf-8") if isinstance(value, bytes) else value
            decoded_data[decoded_name] = json.loads(decoded_value)
        return decoded_data

    def delete(self, key: str) -> bool:
        """Delete a Redis hash.

        Parameters
        ----------
        key
            Redis hash key.

        Returns
        -------
        bool
            ``True`` when Redis reports a deletion.
        """

        if not key:
            return False
        return bool(self.__redis_client.delete(key))


class RedisTimeSeriesAdapter:
    """Store and query RedisTimeSeries samples.

    Parameters
    ----------
    redis_client
        Redis client exposing ``ts()`` with RedisTimeSeries commands.
    """

    def __init__(self, redis_client: Any) -> None:
        self.__redis_client = redis_client

    def create_series(self, key: str, labels: dict[str, str] | None = None) -> bool:
        """Create a time-series key.

        Parameters
        ----------
        key
            Series key.
        labels
            Optional RedisTimeSeries labels.

        Returns
        -------
        bool
            ``True`` when the create command succeeds.
        """

        if not key:
            return False
        self.__redis_client.ts().create(key, labels=labels or {})
        return True

    def add_sample(self, key: str, timestamp_ms: int | str, value: float) -> bool:
        """Add one sample.

        Parameters
        ----------
        key
            Series key.
        timestamp_ms
            Millisecond timestamp or ``"*"``.
        value
            Numeric sample value.

        Returns
        -------
        bool
            ``True`` when the add command succeeds.
        """

        if not key:
            return False
        self.__redis_client.ts().add(key, timestamp_ms, value)
        return True

    def range(
        self, key: str, start_ms: int | str = "-", end_ms: int | str = "+"
    ) -> list[Any]:
        """Read samples in a time range.

        Parameters
        ----------
        key
            Series key.
        start_ms
            Inclusive start timestamp.
        end_ms
            Inclusive end timestamp.

        Returns
        -------
        list[Any]
            RedisTimeSeries samples.
        """

        if not key:
            return []
        return list(self.__redis_client.ts().range(key, start_ms, end_ms))


class FileKeyValueAdapter:
    """Store JSON values in one local JSON file.

    Parameters
    ----------
    file_path
        JSON file path.
    """

    def __init__(self, file_path: str | Path) -> None:
        self.__file_path = Path(file_path)
        self.__file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.__file_path.exists():
            self.__file_path.write_text("{}", encoding="utf-8")

    def __read_store(self) -> dict[str, Any]:
        return json.loads(self.__file_path.read_text(encoding="utf-8"))

    def __write_store(self, store: dict[str, Any]) -> None:
        self.__file_path.write_text(json.dumps(store, indent=2), encoding="utf-8")

    def put(self, key: str, value: Any) -> bool:
        """Write a value.

        Parameters
        ----------
        key
            Storage key.
        value
            JSON-compatible value.

        Returns
        -------
        bool
            ``True`` after the value is written.
        """

        if not key:
            return False
        store = self.__read_store()
        store[key] = value
        self.__write_store(store)
        return True

    def get(self, key: str) -> Any | None:
        """Read a value.

        Parameters
        ----------
        key
            Storage key.

        Returns
        -------
        Any | None
            Stored value, or ``None``.
        """

        if not key:
            return None
        return self.__read_store().get(key)

    def delete(self, key: str) -> bool:
        """Delete a value.

        Parameters
        ----------
        key
            Storage key.

        Returns
        -------
        bool
            ``True`` when a value was removed.
        """

        if not key:
            return False
        store = self.__read_store()
        existed = key in store
        store.pop(key, None)
        self.__write_store(store)
        return existed


class FileNoSQLAdapter:
    """Store one JSON document per key under a directory.

    Parameters
    ----------
    root_directory
        Root folder for JSON documents.
    """

    def __init__(self, root_directory: str | Path) -> None:
        self.__root_directory = Path(root_directory)
        self.__root_directory.mkdir(parents=True, exist_ok=True)

    def __resolve_path(self, key: str) -> Path:
        document_path = (self.__root_directory / f"{key}.json").resolve()
        root_path = self.__root_directory.resolve()
        if root_path not in [document_path, *document_path.parents]:
            raise ValueError("key must stay inside root_directory.")
        return document_path

    def put(self, key: str, value: dict[str, Any]) -> bool:
        """Write a JSON document.

        Parameters
        ----------
        key
            Document key.
        value
            JSON-compatible dictionary.

        Returns
        -------
        bool
            ``True`` when the document is written.
        """

        if not key:
            return False
        path = self.__resolve_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2), encoding="utf-8")
        return True

    def get(self, key: str) -> dict[str, Any]:
        """Read a JSON document.

        Parameters
        ----------
        key
            Document key.

        Returns
        -------
        dict[str, Any]
            Document content, or an empty dictionary.
        """

        if not key:
            return {}
        path = self.__resolve_path(key)
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def delete(self, key: str) -> bool:
        """Delete a JSON document.

        Parameters
        ----------
        key
            Document key.

        Returns
        -------
        bool
            ``True`` when the file existed and was deleted.
        """

        if not key:
            return False
        path = self.__resolve_path(key)
        if not path.exists():
            return False
        path.unlink()
        return True


class JSONFileCacheAdapter:
    """Read and write a JSON cache file.

    Parameters
    ----------
    cache_file_path
        Path to the cache file.
    """

    def __init__(self, cache_file_path: str | Path) -> None:
        self.__cache_file_path = Path(cache_file_path)

    def load_processed_cache(self) -> dict[str, dict[str, str]]:
        """Load the processed cache.

        Returns
        -------
        dict[str, dict[str, str]]
            Parsed cache dictionary, or an empty dictionary.
        """

        if not self.__cache_file_path.exists():
            return {}
        try:
            parsed_json = json.loads(self.__cache_file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return parsed_json if isinstance(parsed_json, dict) else {}

    def write_processed_cache(self, processed_cache: dict[str, dict[str, str]]) -> None:
        """Write the processed cache.

        Parameters
        ----------
        processed_cache
            Cache dictionary to persist.

        Side Effects
        ------------
        Creates parent directories and writes the cache file.
        """

        self.__cache_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.__cache_file_path.write_text(
            json.dumps(processed_cache, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
