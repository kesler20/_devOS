from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class RESTClientConfig:
    """Configuration for a bearer-token REST client.

    Parameters
    ----------
    base_url
        API base URL.
    """

    base_url: str


class BearerTokenRESTClient:
    """Small reusable client for JSON REST APIs using bearer tokens.

    Parameters
    ----------
    http_client
        Requests-like client.
    token_provider
        Callable returning a bearer token.
    config
        REST client configuration.
    """

    def __init__(
        self,
        http_client: Any,
        token_provider: Callable[[], str],
        config: RESTClientConfig,
    ) -> None:
        self._http_client = http_client
        self._token_provider = token_provider
        self._config = config

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token_provider()}"}

    def get_json(self, path: str, **params: Any) -> dict[str, Any]:
        """Run a GET request and parse JSON.

        Parameters
        ----------
        path
            API path.
        **params
            Query parameters.

        Returns
        -------
        dict[str, Any]
            JSON response.
        """

        response = self._http_client.get(
            f"{self._config.base_url}{path}",
            headers=self._headers(),
            params=params or None,
        )
        response.raise_for_status()
        return dict(response.json())

    def post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Run a POST request and parse JSON.

        Parameters
        ----------
        path
            API path.
        payload
            JSON request body.

        Returns
        -------
        dict[str, Any]
            JSON response.
        """

        response = self._http_client.post(
            f"{self._config.base_url}{path}",
            headers={**self._headers(), "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        return dict(response.json())

    def patch_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Run a PATCH request and parse JSON.

        Parameters
        ----------
        path
            API path.
        payload
            JSON request body.

        Returns
        -------
        dict[str, Any]
            JSON response.
        """

        response = self._http_client.patch(
            f"{self._config.base_url}{path}",
            headers={**self._headers(), "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        return dict(response.json())

    def delete(self, path: str) -> None:
        """Run a DELETE request.

        Parameters
        ----------
        path
            API path.
        """

        response = self._http_client.delete(
            f"{self._config.base_url}{path}",
            headers=self._headers(),
        )
        response.raise_for_status()


class TickTickRESTClient(BearerTokenRESTClient):
    """Reusable TickTick REST client."""

    def list_projects(self) -> dict[str, Any]:
        """List TickTick projects.

        Returns
        -------
        dict[str, Any]
            TickTick project response.
        """

        return self.get_json("/open/v1/project")

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a TickTick task.

        Parameters
        ----------
        payload
            TickTick task payload.

        Returns
        -------
        dict[str, Any]
            Created task response.
        """

        return self.post_json("/open/v1/task", payload)


class MendeleyRESTClient(BearerTokenRESTClient):
    """Reusable Mendeley REST client."""

    def create_document(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a Mendeley document.

        Parameters
        ----------
        payload
            Mendeley document payload.

        Returns
        -------
        dict[str, Any]
            Created document response.
        """

        return self.post_json("/documents", payload)


class MonzoRESTClient(BearerTokenRESTClient):
    """Reusable Monzo REST client."""

    def fetch_transactions(self, account_id: str, **params: Any) -> dict[str, Any]:
        """Fetch Monzo transactions.

        Parameters
        ----------
        account_id
            Monzo account ID.
        **params
            Optional Monzo query parameters.

        Returns
        -------
        dict[str, Any]
            Transaction response.
        """

        return self.get_json("/transactions", account_id=account_id, **params)
