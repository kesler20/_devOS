from __future__ import annotations

import json
import pathlib

import devOS.infrastructure.credential_database as credential_database
import devOS.use_cases.manage_credentials as manage_credentials
import scripts.migrate_credentials_vault as migrate_credentials_vault


class FakeNoSQLDatabase:
    def __init__(self) -> None:
        self.values: dict[str, credential_database.JSONValue] = {}

    def put(self, key, value):
        self.values[key] = json.loads(json.dumps(value))
        return True

    def get(self, key):
        return self.values.get(key)

    def delete(self, key):
        return self.values.pop(key, None) is not None


def test_legacy_migration_imports_only_managed_records_and_is_idempotent(
    tmp_path: pathlib.Path, capsys
) -> None:
    legacy_vault = tmp_path / "legacy"
    project_directory = legacy_vault / "dotenv" / "sample"
    project_directory.mkdir(parents=True)
    (project_directory / "dotenv_sample.txt").write_text(
        "PROJECT_TOKEN=project-secret\n", encoding="utf-8"
    )
    (project_directory / "dotenv_example_sample.txt").write_text(
        "PROJECT_TOKEN=\n", encoding="utf-8"
    )
    secrets_directory = legacy_vault / "secrets"
    secrets_directory.mkdir()
    (secrets_directory / "global_secret_GENERAL_TOKEN.txt").write_text(
        "general-secret", encoding="utf-8"
    )
    unmanaged_directory = secrets_directory / "certificate_bundle"
    unmanaged_directory.mkdir()
    (unmanaged_directory / "private.pem").write_text(
        "private-file-value", encoding="utf-8"
    )
    (legacy_vault / "passwords.md").write_text(
        "unmanaged-password", encoding="utf-8"
    )

    database = FakeNoSQLDatabase()
    credentials_use_case = manage_credentials.ManageCredentialsUseCase(
        database=database,
        project_name="migration",
        project_root=tmp_path,
    )
    migration = migrate_credentials_vault.LegacyCredentialsMigrationUseCase(
        legacy_vault=legacy_vault,
        credentials_use_case=credentials_use_case,
    )

    migration.execute()
    migration.execute()

    assert database.values[manage_credentials.GENERAL_CREDENTIALS_KEY] == {
        "GENERAL_TOKEN": "general-secret"
    }
    assert database.values["devos:credentials:project:sample"] == {
        "PROJECT_TOKEN": "project-secret"
    }
    assert "private-file-value" not in json.dumps(database.values)
    assert "unmanaged-password" not in json.dumps(database.values)
    captured = capsys.readouterr()
    assert "project-secret" not in captured.out
    assert "general-secret" not in captured.out
