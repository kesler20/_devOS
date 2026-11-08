from pathlib import Path
import dotenv
import pytest
from devOS.infrastructure.credential_vault import JSONCredentialVaultAdapter, VaultError
from devOS.use_cases import migrate_credential_store as migration


class Client:
    connection_pool = type("Pool", (), {"connection_kwargs": {}})()


class Remote:
    def __init__(self, client):
        pass

    def keys(self, pattern):
        return ["devos:projects:sample"]

    def get(self, key):
        return {"ROOT": "root-value"} if key == "devos:general" else {"TOKEN": "remote"}


def test_verified_migration_and_explicit_conflict_choice(tmp_path, monkeypatch):
    root = tmp_path / "sample"
    root.mkdir()
    (root / ".env").write_text("devos_redis_host=fake\nTOKEN=local\n")
    monkeypatch.setattr(
        migration.credential_cli, "get_project_name", lambda root: "sample"
    )
    monkeypatch.setattr(migration.adapters, "build_redis_client", lambda e: Client())
    monkeypatch.setattr(migration.adapters, "RedisNoSQLAdapter", Remote)
    vault = JSONCredentialVaultAdapter(tmp_path / "vault")
    with pytest.raises(VaultError, match="Conflicting"):
        migration.MigrateCredentialStoreUseCase(
            vault, lambda _: Client(), Remote
        ).execute([root])
    assert not vault.path.exists()
    result = migration.MigrateCredentialStoreUseCase(
        vault, lambda _: Client(), Remote
    ).execute([root], {"sample": {"TOKEN"}})
    assert result.redis_verified == ["sample"]
    assert vault.read() == {"ROOT": "root-value", "project_sample": {"TOKEN": "local"}}
    assert dotenv.dotenv_values(root / ".env")["TOKEN"] == "local"
