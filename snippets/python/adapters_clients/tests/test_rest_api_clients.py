from adapters_clients.rest.api_clients import (
    BearerTokenRESTClient,
    MendeleyRESTClient,
    MonzoRESTClient,
    RESTClientConfig,
    TickTickRESTClient,
)


class FakeResponse:
    def __init__(self, payload) -> None:
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


class FakeHTTPClient:
    def __init__(self) -> None:
        self.calls = []

    def get(self, url, headers=None, params=None):
        self.calls.append(("GET", url, headers, params))
        return FakeResponse({"url": url, "params": params})

    def post(self, url, headers=None, json=None):
        self.calls.append(("POST", url, headers, json))
        return FakeResponse({"url": url, "json": json})

    def patch(self, url, headers=None, json=None):
        self.calls.append(("PATCH", url, headers, json))
        return FakeResponse({"url": url, "json": json})

    def delete(self, url, headers=None):
        self.calls.append(("DELETE", url, headers, None))
        return FakeResponse({})


def test_bearer_token_rest_client_methods() -> None:
    http_client = FakeHTTPClient()
    client = BearerTokenRESTClient(
        http_client,
        lambda: "token",
        RESTClientConfig("https://api.example.com"),
    )

    assert client.get_json("/items")["url"] == "https://api.example.com/items"
    assert client.post_json("/items", {"name": "demo"})["json"] == {"name": "demo"}
    assert client.patch_json("/items/1", {"name": "updated"})["json"] == {
        "name": "updated"
    }
    client.delete("/items/1")

    assert http_client.calls[-1][0] == "DELETE"


def test_specific_rest_clients() -> None:
    http_client = FakeHTTPClient()

    ticktick = TickTickRESTClient(
        http_client,
        lambda: "token",
        RESTClientConfig("https://api.ticktick.com"),
    )
    mendeley = MendeleyRESTClient(
        http_client,
        lambda: "token",
        RESTClientConfig("https://api.mendeley.com"),
    )
    monzo = MonzoRESTClient(
        http_client,
        lambda: "token",
        RESTClientConfig("https://api.monzo.com"),
    )

    assert ticktick.list_projects()["url"].endswith("/open/v1/project")
    assert ticktick.create_task({"title": "Demo"})["json"] == {"title": "Demo"}
    assert mendeley.create_document({"title": "Paper"})["json"] == {"title": "Paper"}
    assert monzo.fetch_transactions("account-1")["params"] == {
        "account_id": "account-1"
    }
