"""GitHub repository metadata and encrypted Actions-secret operations."""

from __future__ import annotations

import base64
import typing

import nacl.public
import pydantic
import requests

from devOS.domain.scaffold import ScaffoldError


class GitHubRepositoryClient:
    """Keep access tokens and request bodies out of diagnostic output."""

    def __init__(self, token: pydantic.SecretStr, session: requests.Session | None = None):
        self.__token = token
        self.__session = session or requests.Session()

    def request(self, method: str, path: str, body: dict[str, typing.Any] | None = None,
                allow_missing: bool = False) -> dict[str, typing.Any] | None:
        """Return JSON, classifying dependency errors without their sensitive text."""
        try:
            response = self.__session.request(
                method, "https://api.github.com" + path, json=body, timeout=30,
                headers={"Authorization": "Bearer " + self.__token.get_secret_value(),
                         "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2026-03-10"},
            )
        except requests.RequestException:
            raise ScaffoldError("github", "GitHub connection failed", "service") from None
        if allow_missing and response.status_code == 404:
            return None
        if response.status_code not in {200, 201, 204}:
            category = "permission" if response.status_code in {401, 403} else "service" if response.status_code >= 500 or response.status_code == 429 else "configuration"
            raise ScaffoldError("github", f"GitHub returned HTTP {response.status_code}", category)
        if response.status_code == 204:
            return {}
        try:
            return typing.cast(dict[str, typing.Any], response.json())
        except requests.exceptions.JSONDecodeError:
            raise ScaffoldError("github", "GitHub returned invalid JSON", "service") from None

    def ensure_repository(self, owner: str, name: str, description: str) -> str:
        """Preserve existing visibility and create new repositories as private."""
        repository = f"{owner}/{name}"
        current = self.request("GET", f"/repos/{repository}", allow_missing=True)
        if current is None:
            user = self.request("GET", "/user") or {}
            path = "/user/repos" if str(user.get("login", "")).lower() == owner.lower() else f"/orgs/{owner}/repos"
            self.request("POST", path, {"name": name, "description": description, "private": True, "auto_init": False})
        elif current.get("description") != description:
            self.update_description(repository, description)
        return repository

    def update_description(self, repository: str, description: str) -> None:
        self.request("PATCH", f"/repos/{repository}", {"description": description})

    def set_actions_secret(self, repository: str, name: str, value: pydantic.SecretStr) -> None:
        """Encrypt each value with the repository public key before upload."""
        public_key = self.request("GET", f"/repos/{repository}/actions/secrets/public-key") or {}
        if "key" not in public_key or "key_id" not in public_key:
            raise ScaffoldError("github-secrets", "Repository public key was missing", "service")
        try:
            box = nacl.public.SealedBox(nacl.public.PublicKey(base64.b64decode(public_key["key"], validate=True)))
        except (ValueError, TypeError):
            raise ScaffoldError("github-secrets", "Repository public key was invalid", "service") from None
        encrypted = base64.b64encode(box.encrypt(value.get_secret_value().encode())).decode()
        self.request("PUT", f"/repos/{repository}/actions/secrets/{name}",
                     {"encrypted_value": encrypted, "key_id": public_key["key_id"]})

    def secret_names(self, repository: str) -> list[str]:
        """Verify names and metadata without attempting to read secret values."""
        names: list[str] = []
        page = 1
        while True:
            payload = self.request("GET", f"/repos/{repository}/actions/secrets?per_page=100&page={page}") or {}
            items = payload.get("secrets", [])
            names.extend(item["name"] for item in items)
            if len(items) < 100:
                return sorted(names)
            page += 1
