from adapters_clients.aws.clients import AWSClient, AWSClientConfig


class FakeSession:
    def __init__(self) -> None:
        self.requested_services: list[str] = []

    def resource(self, service_name: str):
        self.requested_services.append(service_name)
        return FakeResource(service_name)


class FakeResource:
    def __init__(self, service_name: str) -> None:
        self.service_name = service_name

    def Bucket(self, bucket_name: str) -> tuple[str, str]:
        return self.service_name, bucket_name

    def Table(self, table_name: str) -> tuple[str, str]:
        return self.service_name, table_name


def test_get_s3_bucket_uses_injected_session() -> None:
    session = FakeSession()
    client = AWSClient(
        AWSClientConfig("access", "secret", "eu-west-2"),
        session=session,
    )

    assert client.get_s3_bucket("documents") == ("s3", "documents")
    assert session.requested_services == ["s3"]


def test_get_dynamodb_table_uses_injected_session() -> None:
    session = FakeSession()
    client = AWSClient(
        AWSClientConfig("access", "secret", "eu-west-2"),
        session=session,
    )

    assert client.get_dynamodb_table("items") == ("dynamodb", "items")
    assert session.requested_services == ["dynamodb"]
