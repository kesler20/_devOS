from __future__ import annotations

import argparse
import json
import pathlib
import tempfile

import dotenv

import devOS.infrastructure.credential_database as credential_database
import devOS.use_cases.manage_credentials as manage_credentials


class LegacyCredentialsMigrationUseCase:
    def __init__(
        self,
        legacy_vault: pathlib.Path,
        credentials_use_case: manage_credentials.ManageCredentialsUseCase,
    ) -> None:
        self.__legacy_vault = legacy_vault
        self.__credentials_use_case = credentials_use_case

    def __read_project_bundles(self) -> dict[str, dict[str, str]]:
        dotenv_root = self.__legacy_vault / "dotenv"
        project_bundles: dict[str, dict[str, str]] = {}
        if not dotenv_root.exists():
            return project_bundles

        for project_directory in sorted(
            path for path in dotenv_root.iterdir() if path.is_dir()
        ):
            credential_file = (
                project_directory / f"dotenv_{project_directory.name}.txt"
            )
            if not credential_file.is_file():
                continue
            parsed_values = dotenv.dotenv_values(credential_file)
            project_bundles[project_directory.name] = {
                key: "" if value is None else value
                for key, value in parsed_values.items()
                if not key.startswith(manage_credentials.BOOTSTRAP_VARIABLE_PREFIX)
            }
        return project_bundles

    def __read_general_bundle(self) -> dict[str, str]:
        secrets_root = self.__legacy_vault / "secrets"
        general_bundle: dict[str, str] = {}
        if not secrets_root.exists():
            return general_bundle

        for secret_file in sorted(secrets_root.glob("global_secret_*.txt")):
            secret_key = secret_file.stem.removeprefix("global_secret_")
            if not manage_credentials.ENVIRONMENT_KEY_PATTERN.fullmatch(secret_key):
                raise ValueError(f"Invalid legacy credential key: {secret_key}")
            general_bundle[secret_key] = secret_file.read_text(encoding="utf-8")
        return general_bundle

    def execute(self) -> None:
        if not self.__legacy_vault.is_dir():
            raise FileNotFoundError(
                f"Legacy credential vault was not found: {self.__legacy_vault}"
            )

        general_bundle = self.__read_general_bundle()
        project_bundles = self.__read_project_bundles()
        json.dumps(general_bundle)
        json.dumps(project_bundles)

        with tempfile.TemporaryDirectory() as temporary_directory:
            export_root = pathlib.Path(temporary_directory)
            general_destination = export_root / "general" / "credentials.json"
            general_destination.parent.mkdir(parents=True)
            general_destination.write_text(
                json.dumps(general_bundle, indent=2), encoding="utf-8"
            )
            for project_name, project_bundle in project_bundles.items():
                project_destination = (
                    export_root
                    / "projects"
                    / project_name
                    / "credentials.json"
                )
                project_destination.parent.mkdir(parents=True)
                project_destination.write_text(
                    json.dumps(project_bundle, indent=2), encoding="utf-8"
                )
            self.__credentials_use_case.import_credentials(str(export_root))

        print(f"General credential keys validated: {len(general_bundle)}")
        for project_name, project_bundle in sorted(project_bundles.items()):
            print(f"Project credential keys validated: {project_name} {len(project_bundle)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate devOS-managed filesystem credentials into Redis."
    )
    parser.add_argument(
        "legacy_vault",
        nargs="?",
        default=str(
            pathlib.Path.home()
            / "protocol"
            / "00 PKM"
            / "3 Resources"
            / "Vault"
        ),
    )
    arguments = parser.parse_args()

    database = credential_database.RedisKeyValueAdapter.from_environment()
    credentials_use_case = manage_credentials.ManageCredentialsUseCase(
        database=database,
        project_name="migration",
    )
    LegacyCredentialsMigrationUseCase(
        legacy_vault=pathlib.Path(arguments.legacy_vault).expanduser().resolve(),
        credentials_use_case=credentials_use_case,
    ).execute()


if __name__ == "__main__":
    main()
