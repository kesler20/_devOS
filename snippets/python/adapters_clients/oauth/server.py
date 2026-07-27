from __future__ import annotations

import http.server
import secrets
import urllib.parse
import webbrowser
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class OAuthProviderConfig:
    """Configuration for an OAuth authorization-code provider.

    Parameters
    ----------
    authorization_url
        Provider authorization endpoint.
    token_url
        Provider token endpoint.
    client_id
        OAuth client ID.
    client_secret
        OAuth client secret.
    redirect_uri
        Redirect URI registered with the provider.
    scopes
        OAuth scopes.
    """

    authorization_url: str
    token_url: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: tuple[str, ...] = ()


class OAuthTokenClient:
    """Exchange and refresh OAuth authorization-code tokens.

    Parameters
    ----------
    config
        OAuth provider configuration.
    http_post
        Callable compatible with ``requests.post``.
    token_store
        Object with ``put`` and ``get`` methods.
    token_store_key
        Storage key for persisted token payloads.
    """

    def __init__(
        self,
        config: OAuthProviderConfig,
        http_post: Callable[..., Any],
        token_store: Any,
        token_store_key: str,
    ) -> None:
        self.__config = config
        self.__http_post = http_post
        self.__token_store = token_store
        self.__token_store_key = token_store_key

    def build_authorization_url(self, state: str) -> str:
        """Build the provider authorization URL.

        Parameters
        ----------
        state
            CSRF state token.

        Returns
        -------
        str
            Authorization URL.
        """

        query = {
            "client_id": self.__config.client_id,
            "redirect_uri": self.__config.redirect_uri,
            "response_type": "code",
            "state": state,
        }
        if self.__config.scopes:
            query["scope"] = " ".join(self.__config.scopes)
        return f"{self.__config.authorization_url}?{urllib.parse.urlencode(query)}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        """Exchange an authorization code for tokens.

        Parameters
        ----------
        code
            Authorization code received at the callback.

        Returns
        -------
        dict[str, Any]
            Token response payload.
        """

        token = self.__request_token(
            {
                "grant_type": "authorization_code",
                "client_id": self.__config.client_id,
                "client_secret": self.__config.client_secret,
                "redirect_uri": self.__config.redirect_uri,
                "code": code,
            }
        )
        self.__token_store.put(self.__token_store_key, token)
        return token

    def refresh(self) -> dict[str, Any]:
        """Refresh a stored OAuth token.

        Returns
        -------
        dict[str, Any]
            Refreshed token response payload.
        """

        stored_token = self.__token_store.get(self.__token_store_key)
        if not stored_token or not stored_token.get("refresh_token"):
            raise RuntimeError("No stored refresh token is available.")
        token = self.__request_token(
            {
                "grant_type": "refresh_token",
                "client_id": self.__config.client_id,
                "client_secret": self.__config.client_secret,
                "refresh_token": stored_token["refresh_token"],
            }
        )
        self.__token_store.put(self.__token_store_key, token)
        return token

    def __request_token(self, data: dict[str, str]) -> dict[str, Any]:
        response = self.__http_post(self.__config.token_url, data=data)
        if response.status_code != 200:
            raise RuntimeError(
                f"OAuth token request failed with {response.status_code}: "
                f"{response.text}"
            )
        return dict(response.json())


class OAuthCallbackServer:
    """Capture one OAuth callback on a local HTTP server.

    Parameters
    ----------
    host
        Callback host.
    port
        Callback port.
    callback_path
        Callback path.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
        callback_path: str = "/callback",
    ) -> None:
        self.__host = host
        self.__port = port
        self.__callback_path = callback_path

    def capture_code(self, authorization_url: str, expected_state: str) -> str:
        """Open a browser and wait for one OAuth callback.

        Parameters
        ----------
        authorization_url
            URL opened in the default browser.
        expected_state
            State token that must be echoed by the provider.

        Returns
        -------
        str
            Authorization code.
        """

        captured: dict[str, str] = {}
        callback_path = self.__callback_path

        class CallbackRequestHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed_url = urllib.parse.urlparse(self.path)
                if parsed_url.path != callback_path:
                    self.send_response(404)
                    self.end_headers()
                    return

                query = urllib.parse.parse_qs(parsed_url.query)
                captured["code"] = query.get("code", [""])[0]
                captured["state"] = query.get("state", [""])[0]

                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Authorization received. You can close this tab.")

            def log_message(self, *args: Any) -> None:
                return

        webbrowser.open(authorization_url)
        server = http.server.HTTPServer(
            (self.__host, self.__port), CallbackRequestHandler
        )
        try:
            while "code" not in captured:
                server.handle_request()
        finally:
            server.server_close()

        if captured.get("state") != expected_state:
            raise RuntimeError("OAuth state mismatch.")
        return captured["code"]


def run_local_authorization(
    token_client: OAuthTokenClient,
    callback_server: OAuthCallbackServer,
) -> dict[str, Any]:
    """Run a one-shot local OAuth authorization-code flow.

    Parameters
    ----------
    token_client
        Token client used to build the URL and exchange the code.
    callback_server
        Callback server used to capture the authorization code.

    Returns
    -------
    dict[str, Any]
        Token payload.
    """

    state = secrets.token_urlsafe(16)
    authorization_url = token_client.build_authorization_url(state)
    code = callback_server.capture_code(authorization_url, expected_state=state)
    return token_client.exchange_code(code)
