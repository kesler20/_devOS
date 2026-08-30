from __future__ import annotations

import devOS.domain.entities as entities
import devOS.use_cases.manage_credentials as manage_credentials

from snippets.python.config import credentials as snippet_credentials


def test_snippet_and_devos_agree_on_the_storage_contract() -> None:
    """The copied snippet must address the same keys devOS writes."""
    assert (
        snippet_credentials.PROJECT_CREDENTIALS_KEY_PREFIX
        == manage_credentials.PROJECT_CREDENTIALS_KEY_PREFIX
    )
    assert not hasattr(snippet_credentials, "GENERAL_CREDENTIALS_KEY")
    assert (
        snippet_credentials.RESERVED_VARIABLE_PREFIX
        == entities.BOOTSTRAP_VARIABLE_PREFIX
    )


def test_snippet_and_devos_agree_on_the_bootstrap_variables() -> None:
    """Both sides must read the same Redis bootstrap variables."""
    import devOS.infrastructure.adapters as adapters

    bootstrap_variable_names = [
        "REDIS_URL_VARIABLE",
        "REDIS_HOST_VARIABLE",
        "REDIS_PORT_VARIABLE",
        "REDIS_USERNAME_VARIABLE",
        "REDIS_PASSWORD_VARIABLE",
        "REDIS_DATABASE_VARIABLE",
        "REDIS_SSL_VARIABLE",
    ]

    for variable_name in bootstrap_variable_names:
        assert getattr(snippet_credentials, variable_name) == getattr(
            adapters, variable_name
        )


def test_snippet_carries_only_the_read_path() -> None:
    """The copied snippet must not ship write operations."""
    adapter_methods = set(vars(snippet_credentials.RedisNoSQLAdapter))

    assert "get" in adapter_methods
    assert "put" not in adapter_methods
    assert "delete" not in adapter_methods
