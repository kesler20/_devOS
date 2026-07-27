from adapters_clients.oauth.server import OAuthProviderConfig, OAuthTokenClient


class FakeResponse:
    status_code = 200
    text = "OK"

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class FakeTokenStore:
    def __init__(self) -> None:
        self.values = {}

    def put(self, key, value):
        self.values[key] = value

    def get(self, key):
        return self.values.get(key)


def test_build_authorization_url_includes_state_and_scopes() -> None:
    store = FakeTokenStore()
    client = OAuthTokenClient(
        OAuthProviderConfig(
            authorization_url="https://example.com/oauth/authorize",
            token_url="https://example.com/oauth/token",
            client_id="client",
            client_secret="secret",
            redirect_uri="http://localhost/callback",
            scopes=("read", "write"),
        ),
        http_post=lambda *_args, **_kwargs: FakeResponse({}),
        token_store=store,
        token_store_key="provider:token",
    )

    authorization_url = client.build_authorization_url("state-value")

    assert "client_id=client" in authorization_url
    assert "state=state-value" in authorization_url
    assert "scope=read+write" in authorization_url


def test_exchange_and_refresh_store_tokens() -> None:
    store = FakeTokenStore()
    requests = []

    def fake_post(url, data):
        requests.append((url, data))
        return FakeResponse(
            {"access_token": data["grant_type"], "refresh_token": "refresh"}
        )

    client = OAuthTokenClient(
        OAuthProviderConfig(
            authorization_url="https://example.com/oauth/authorize",
            token_url="https://example.com/oauth/token",
            client_id="client",
            client_secret="secret",
            redirect_uri="http://localhost/callback",
        ),
        http_post=fake_post,
        token_store=store,
        token_store_key="provider:token",
    )

    assert client.exchange_code("code")["access_token"] == "authorization_code"
    assert store.get("provider:token")["refresh_token"] == "refresh"
    assert client.refresh()["access_token"] == "refresh_token"
    assert requests[0][1]["code"] == "code"
    assert requests[1][1]["refresh_token"] == "refresh"
