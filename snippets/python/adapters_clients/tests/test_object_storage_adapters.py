from io import BytesIO

from adapters_clients.aws.object_storage_adapter import S3ObjectStorageAdapter
from adapters_clients.minio.object_storage_adapter import MinIOObjectStorageAdapter
from adapters_clients.storage.object_storage_adapters import FileObjectStorageAdapter


class FakePutResponse:
    def __init__(self, key: str) -> None:
        self.key = key


class FakeBucket:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    def put_object(self, Key: str, Body: str):
        self.store[Key] = Body
        return FakePutResponse(Key)


class FakeS3Object:
    def __init__(self, store: dict[str, str], key: str) -> None:
        self.store = store
        self.key = key

    def get(self):
        return {"Body": BytesIO(self.store[self.key].encode("utf-8"))}

    def delete(self):
        self.store.pop(self.key, None)
        return {"ResponseMetadata": {"HTTPStatusCode": 204}}


class FakeS3Resource:
    def __init__(self, store: dict[str, str]) -> None:
        self.store = store

    def Object(self, bucket_name: str, key: str):
        return FakeS3Object(self.store, key)


def test_s3_object_storage_round_trip() -> None:
    bucket = FakeBucket()
    adapter = S3ObjectStorageAdapter(bucket, FakeS3Resource(bucket.store), "bucket")

    assert adapter.write_object("a/object.json", {"value": 1}) is True
    assert adapter.read_object("a/object.json") == {"value": 1}
    assert adapter.delete_object("a/object.json") is True
    assert adapter.read_object("a/object.json") is None


def test_file_object_storage_round_trip(tmp_path) -> None:
    adapter = FileObjectStorageAdapter(tmp_path)

    assert adapter.write_object("nested/object.json", {"value": 2}) is True
    assert adapter.read_object("nested/object.json") == {"value": 2}
    assert adapter.delete_object("nested/object.json") is True
    assert adapter.read_object("nested/object.json") is None


def test_minio_object_storage_uses_s3_compatible_behavior() -> None:
    bucket = FakeBucket()
    adapter = MinIOObjectStorageAdapter(bucket, FakeS3Resource(bucket.store), "bucket")

    assert adapter.write_object("model/artifact.json", {"metric": 0.9}) is True
    assert adapter.read_object("model/artifact.json") == {"metric": 0.9}
