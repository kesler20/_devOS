import json

from adapters_clients.redis.key_value_adapters import (
    DynamoKeyValueAdapter,
    FileNoSQLAdapter,
    FileKeyValueAdapter,
    JSONFileCacheAdapter,
    RedisHashNoSQLAdapter,
    RedisKeyValueAdapter,
    RedisTimeSeriesAdapter,
)


class FakeDynamoTable:
    def __init__(self) -> None:
        self.items: dict[tuple[str, int], dict] = {}

    def put_item(self, Item):
        self.items[(Item["category"], Item["date"])] = Item
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def query(self, Key):
        item = self.items.get((Key["category"], Key["date"]))
        return {"Items": [item] if item else []}

    def delete_item(self, Key):
        self.items.pop((Key["category"], Key["date"]), None)
        return {"ResponseMetadata": {"HTTPStatusCode": 204}}


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.time_series = FakeRedisTimeSeries()

    def ping(self) -> bool:
        return True

    def set(self, key: str, value: str) -> bool:
        self.values[key] = value
        return True

    def get(self, key: str):
        value = self.values.get(key)
        return value.encode("utf-8") if value is not None else None

    def delete(self, key: str) -> int:
        existed = key in self.values or key in self.hashes
        self.values.pop(key, None)
        self.hashes.pop(key, None)
        return int(existed)

    def hset(self, key: str, mapping: dict[str, str]) -> None:
        self.hashes[key] = mapping

    def hgetall(self, key: str) -> dict[str, str]:
        return self.hashes.get(key, {})

    def ts(self):
        return self.time_series


class FakeRedisTimeSeries:
    def __init__(self) -> None:
        self.created = []
        self.samples = {}

    def create(self, key: str, labels: dict[str, str]):
        self.created.append((key, labels))
        self.samples.setdefault(key, [])

    def add(self, key: str, timestamp_ms, value: float):
        self.samples.setdefault(key, []).append((timestamp_ms, value))

    def range(self, key: str, start_ms, end_ms):
        return self.samples.get(key, [])


def test_dynamo_key_value_adapter() -> None:
    adapter = DynamoKeyValueAdapter(FakeDynamoTable())

    assert adapter.put("invoice", 123, {"amount": 10.5}) is True
    assert adapter.get("invoice", 123) == {
        "category": "invoice",
        "date": 123,
        "amount": 10,
    }
    assert adapter.delete("invoice", 123) is True
    assert adapter.get("invoice", 123) is None


def test_redis_key_value_adapter() -> None:
    redis = FakeRedis()
    adapter = RedisKeyValueAdapter(redis)

    assert adapter.put("settings", {"theme": "dark"}) is True
    assert json.loads(redis.values["settings"]) == {"theme": "dark"}
    assert adapter.get("settings") == {"theme": "dark"}
    assert adapter.delete("settings") is True


def test_redis_hash_no_sql_adapter() -> None:
    adapter = RedisHashNoSQLAdapter(FakeRedis())

    assert adapter.is_available() is True
    assert adapter.put("profile", {"name": "Kesler", "count": 2}) is True
    assert adapter.get("profile") == {"name": "Kesler", "count": 2}
    assert adapter.delete("profile") is True


def test_redis_time_series_adapter() -> None:
    redis = FakeRedis()
    adapter = RedisTimeSeriesAdapter(redis)

    assert adapter.create_series("metrics:weight", {"unit": "kg"}) is True
    assert adapter.add_sample("metrics:weight", 1, 80.5) is True
    assert adapter.range("metrics:weight") == [(1, 80.5)]


def test_file_key_value_adapter(tmp_path) -> None:
    adapter = FileKeyValueAdapter(tmp_path / "store.json")

    assert adapter.put("settings", {"theme": "dark"}) is True
    assert adapter.get("settings") == {"theme": "dark"}
    assert adapter.delete("settings") is True
    assert adapter.get("settings") is None


def test_file_no_sql_adapter(tmp_path) -> None:
    adapter = FileNoSQLAdapter(tmp_path)

    assert adapter.put("records/item", {"value": 1}) is True
    assert adapter.get("records/item") == {"value": 1}
    assert adapter.delete("records/item") is True
    assert adapter.get("records/item") == {}


def test_json_file_cache_adapter(tmp_path) -> None:
    adapter = JSONFileCacheAdapter(tmp_path / "cache.json")
    cache = {"email": {"last_id": "abc"}}

    adapter.write_processed_cache(cache)

    assert adapter.load_processed_cache() == cache
