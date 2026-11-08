"""GitHub repository metadata and encrypted Actions-secret operations."""

from __future__ import annotations

import base64
import typing
import logging

import nacl.public
import pydantic
import requests

import devOS.domain.scaffold as scaffold
from devOS.domain import entities
from devOS.infrastructure import github_schema


class GitHubRepositoryClient:
    """Keep access tokens and request bodies out of diagnostic output."""

    def __init__(
        self,
        token: pydantic.SecretStr,
        session: requests.Session | None = None,
        base_url: str = "https://api.github.com",
    ):
        self.__token = token
        self.__session = session or requests.Session()
        self.base_url = base_url.rstrip("/")

    def __request(
        self,
        method: typing.Literal["GET", "POST", "PATCH", "PUT"],
        path: str,
        body: pydantic.BaseModel | None = None,
        allow_missing: bool = False,
    ) -> dict[str, entities.JSONValue] | None:
        logging.info("Calling GitHub repository API with %s", method)
        try:
            response = self.__session.request(
                method,
                self.base_url + path,
                json=body.model_dump() if body is not None else None,
                timeout=30,
                headers={
                    "Authorization": "Bearer " + self.__token.get_secret_value(),
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2026-03-10",
                },
            )
        except requests.RequestException:
            raise scaffold.ScaffoldError(
                "github", "GitHub connection failed", "service"
            ) from None
        if allow_missing and response.status_code == 404:
            logging.info("GitHub repository API reports missing resource")
            return None
        if response.status_code not in {200, 201, 204}:
            category: scaffold.FailureCategory = (
                "permission"
                if response.status_code in {401, 403}
                else (
                    "service"
                    if response.status_code >= 500 or response.status_code == 429
                    else "configuration"
                )
            )
            raise scaffold.ScaffoldError(
                "github", f"GitHub returned HTTP {response.status_code}", category
            )
        if response.status_code == 204:
            logging.info("GitHub repository API call completed")
            return {}
        try:
            result = typing.cast(
                dict[str, entities.JSONValue],
                github_schema.JsonObjectResponse.model_validate(response.json()).root,
            )
            logging.info("GitHub repository API call completed")
            return result
        except (requests.exceptions.JSONDecodeError, pydantic.ValidationError):
            raise scaffold.ScaffoldError(
                "github", "GitHub returned invalid JSON", "service"
            ) from None

    def ensure_repository(self, owner: str, name: str, description: str) -> str:
        """Preserve existing visibility and create new repositories as private."""
        repository = f"{owner}/{name}"
        current = self.__request("GET", f"/repos/{repository}", allow_missing=True)
        if current is None:
            user = github_schema.UserResponse.model_validate(
                self.__request("GET", "/user")
            )
            path = (
                "/user/repos"
                if user.login.lower() == owner.lower()
                else f"/orgs/{owner}/repos"
            )
            self.__request(
                "POST",
                path,
                github_schema.RepositoryRequest(name=name, description=description),
            )
        elif (
            github_schema.RepositoryResponse.model_validate(current).description
            != description
        ):
            self.update_description(repository, description)
        return repository

    def update_description(self, repository: str, description: str) -> None:
        self.__request(
            "PATCH",
            f"/repos/{repository}",
            github_schema.DescriptionRequest(description=description),
        )

    def set_actions_secret(
        self, repository: str, name: str, value: pydantic.SecretStr
    ) -> None:
        """Encrypt each value with the repository public key before upload."""
        public_key_payload = (
            self.__request("GET", f"/repos/{repository}/actions/secrets/public-key")
            or {}
        )
        if "key" not in public_key_payload or "key_id" not in public_key_payload:
            raise scaffold.ScaffoldError(
                "github-secrets", "Repository public key was missing", "service"
            )
        try:
            public_key = github_schema.PublicKeyResponse.model_validate(
                public_key_payload
            )
            box = nacl.public.SealedBox(
                nacl.public.PublicKey(base64.b64decode(public_key.key, validate=True))
            )
        except (ValueError, TypeError):
            raise scaffold.ScaffoldError(
                "github-secrets", "Repository public key was invalid", "service"
            ) from None
        encrypted = base64.b64encode(
            box.encrypt(value.get_secret_value().encode())
        ).decode()
        self.__request(
            "PUT",
            f"/repos/{repository}/actions/secrets/{name}",
            github_schema.SecretRequest(
                encrypted_value=encrypted, key_id=public_key.key_id
            ),
        )

    def secret_names(self, repository: str) -> list[str]:
        """Verify names and metadata without attempting to read secret values."""
        names: list[str] = []
        page = 1
        while True:
            payload = (
                self.__request(
                    "GET",
                    f"/repos/{repository}/actions/secrets?per_page=100&page={page}",
                )
                or {}
            )
            items = github_schema.SecretListResponse.model_validate(payload).secrets
            names.extend(item.name for item in items)
            if len(items) < 100:
                return sorted(names)
            page += 1
