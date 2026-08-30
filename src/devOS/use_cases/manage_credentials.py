from __future__ import annotations

import json
import pathlib
import re
import shutil
import typing
import dotenv
import pyperclip  # type: ignore
import devOS.domain.entities as entities
from devOS.infrastructure.adapters import RedisNoSQLAdapter


GENERAL_CREDENTIALS_KEY = "devos:general"
PROJECT_CREDENTIALS_KEY_PREFIX = "devos:projects:"
PROJECT_REGISTRY_KEY = "devos:projects"

CONFIG_SNIPPET_FILE_NAMES = ("configs.py", "credentials.py")

# Matches one environment assignment. The prefix captures everything up to
# and including the equals sign and any padding, so indentation, "export ",
# and spacing around the sign all survive a value being swapped in.
ASSIGNMENT_PATTERN = re.compile(
    r"^(?P<prefix>\s*(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*)"
)


class ManageCredentialsUseCase:
    """Own every credential operation against the credential database.

    Parameters
    ----------
    database
        Key-value store holding the credential bundles.
    project_name
        Name of the project whose bundle is being managed.
    project_root
        Directory holding the project's ``.env`` and ``.env.example``.
    """

    def __init__(
        self,
        database: RedisNoSQLAdapter | None,
        project_name: str,
        project_root: pathlib.Path,
    ) -> None:
        self.__database = database
        self.__project_name = project_name
        self.__project_root = pathlib.Path(project_root)

    @property
    def __credential_database(self) -> RedisNoSQLAdapter:
        # Copying the configuration bundle needs no store, so the database is
        # only demanded by the operations that actually read or write it.
        if self.__database is None:
            raise RuntimeError(
                "No credential database is configured. Set devos_redis_url, "
                "or devos_redis_host with its companion variables."
            )
        return self.__database

    # ------------------------ #
    #                          #
    #   BUNDLE ACCESS          #
    #                          #
    # ------------------------ #

    def __project_key(self, project_name: str | None = None) -> str:
        resolved_name = self.__project_name if project_name is None else project_name
        return f"{PROJECT_CREDENTIALS_KEY_PREFIX}{resolved_name}"

    def __load_bundle(self, storage_key: str) -> entities.CredentialBundle:
        stored_value = self.__credential_database.get(storage_key)
        if stored_value is None:
            return entities.CredentialBundle.empty()
        return entities.CredentialBundle.from_json_value(stored_value, storage_key)

    def __store_bundle(
        self, storage_key: str, bundle: entities.CredentialBundle
    ) -> None:
        if not self.__credential_database.put(storage_key, bundle.values()):
            raise RuntimeError(f"Credential bundle '{storage_key}' was not stored.")

    def __load_registry(self) -> entities.CredentialProjectRegistry:
        stored_value = self.__credential_database.get(PROJECT_REGISTRY_KEY)
        if stored_value is None:
            return entities.CredentialProjectRegistry.empty()
        return entities.CredentialProjectRegistry.from_json_value(
            stored_value, PROJECT_REGISTRY_KEY
        )

    def __register_project(self, project_name: str) -> None:
        registry = self.__load_registry()
        registry.register(project_name)
        if not self.__credential_database.put(
            PROJECT_REGISTRY_KEY, typing.cast(entities.JSONValue, registry.names())
        ):
            raise RuntimeError("The credential project registry was not stored.")

    # ================================= #
    #                                   #
    #   MATERIALIZATION                 #
    #                                   #
    # ================================= #

    def get_credentials(self) -> None:
        """Update the project's ``.env`` in place from its credential bundle.

        Existing assignments have only their values replaced, so comments,
        blank lines, ordering, and any key the store does not carry all survive.
        Credentials the file does not mention yet are appended at the end. The
        previous file is copied to ``.devos_backup/.env`` first.
        """

        environment_path = self.__project_root / ".env"
        rendered_values = self.__load_bundle(self.__project_key()).dotenv_values()

        original_lines: list[str] = []
        if environment_path.is_file():
            backup_path = self.__project_root / ".devos_backup" / ".env"
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(environment_path, backup_path)
            original_lines = environment_path.read_text(encoding="utf-8").splitlines()

        replaced_keys: set[str] = set()
        updated_lines: list[str] = []
        for line in original_lines:
            match = ASSIGNMENT_PATTERN.match(line)
            if match is None:
                updated_lines.append(line)
                continue
            key = match.group("key")
            if key not in rendered_values:
                updated_lines.append(line)
                continue
            updated_lines.append(f"{match.group('prefix')}{rendered_values[key]}")
            replaced_keys.add(key)

        appended_keys = [key for key in rendered_values if key not in replaced_keys]
        if appended_keys:
            # Two blank lines separate the appended block from whatever the file
            # already ended with.
            while updated_lines and not updated_lines[-1].strip():
                updated_lines.pop()
            if updated_lines:
                updated_lines += ["", ""]
            updated_lines += [
                f"{key}={rendered_values[key]}" for key in appended_keys
            ]

        environment_path.write_text(
            "\n".join(updated_lines) + ("\n" if updated_lines else ""),
            encoding="utf-8",
        )
        # The example masks whatever the resulting file holds, so a local-only
        # key is documented too rather than silently missing.
        example_keys = [
            match.group("key")
            for match in (ASSIGNMENT_PATTERN.match(line) for line in updated_lines)
            if match is not None
        ]
        (self.__project_root / ".env.example").write_text(
            "".join(f"{key}=\n" for key in example_keys), encoding="utf-8"
        )
        print(
            f"Updated {len(replaced_keys)} credentials in .env and appended "
            f"{len(appended_keys)}"
        )

    def set_credentials(self, *flags: str) -> None:
        """Merge the project's ``.env`` into its stored credential bundle.

        Parameters
        ----------
        *flags
            Pass ``--force`` to overwrite credentials the bundle already holds.
            Without it, an overlapping key aborts the whole push so that a stale
            local ``.env`` cannot silently replace a rotated stored value.
        """

        environment_path = self.__project_root / ".env"
        if not environment_path.is_file():
            raise FileNotFoundError(f"No .env file was found at {environment_path}.")

        incoming_values: dict[str, entities.JSONValue] = {
            key: value
            for key, value in dotenv.dotenv_values(environment_path).items()
            if value is not None and not entities.is_bootstrap_variable(key)
        }

        project_bundle = self.__load_bundle(self.__project_key())
        conflicting_keys = sorted(set(project_bundle.keys()) & set(incoming_values))
        if conflicting_keys and "--force" not in flags:
            raise ValueError(
                f"{len(conflicting_keys)} credentials already exist for "
                f"'{self.__project_name}': {', '.join(conflicting_keys)}. "
                "Re-run with --force to overwrite them."
            )

        project_bundle.merge(incoming_values)
        self.__store_bundle(self.__project_key(), project_bundle)
        self.__register_project(self.__project_name)
        print(
            f"Stored {len(incoming_values)} credentials for '{self.__project_name}', "
            f"overwriting {len(conflicting_keys)}"
        )

    def store_general_credentials(self, values: dict[str, entities.JSONValue]) -> None:
        """Merge values into the general bundle."""
        general_bundle = self.__load_bundle(GENERAL_CREDENTIALS_KEY)
        general_bundle.merge(values)
        self.__store_bundle(GENERAL_CREDENTIALS_KEY, general_bundle)

    def store_project_credentials(
        self, project_name: str, values: dict[str, entities.JSONValue]
    ) -> None:
        """Merge values into one project's bundle and register the project."""
        project_bundle = self.__load_bundle(self.__project_key(project_name))
        project_bundle.merge(values)
        self.__store_bundle(self.__project_key(project_name), project_bundle)
        self.__register_project(project_name)

    # ================================= #
    #                                   #
    #   OPERATIONS ON A SINGLE VALUE    #
    #                                   #
    # ================================= #

    def __set_value(self, storage_key: str, key: str, value: str) -> None:
        bundle = self.__load_bundle(storage_key)
        bundle.merge({key: value})
        self.__store_bundle(storage_key, bundle)

    def __delete_value(self, storage_key: str, key: str) -> None:
        bundle = self.__load_bundle(storage_key)
        bundle.remove(key)
        self.__store_bundle(storage_key, bundle)

    def set_credential(self, key: str, value: str) -> None:
        """Store one credential in the project bundle."""
        self.__set_value(self.__project_key(), key, value)
        self.__register_project(self.__project_name)
        print(f"Stored {key} for project '{self.__project_name}'")

    def delete_credential(self, key: str) -> None:
        """Remove one credential from the project bundle."""
        self.__delete_value(self.__project_key(), key)
        print(f"Deleted {key} from project '{self.__project_name}'")

    def set_global_secret(self, key: str, value: str) -> None:
        """Store one credential in the general bundle."""
        self.__set_value(GENERAL_CREDENTIALS_KEY, key, value)
        print(f"Stored {key} in the general credentials")

    def get_global_secret(self, key: str) -> None:
        """Copy one general credential to the clipboard without printing it."""
        value = self.__load_bundle(GENERAL_CREDENTIALS_KEY).get(key)
        pyperclip.copy(value if isinstance(value, str) else json.dumps(value))
        print(f"Copied {key} to the clipboard")

    def delete_global_secret(self, key: str) -> None:
        """Remove one credential from the general bundle."""
        self.__delete_value(GENERAL_CREDENTIALS_KEY, key)
        print(f"Deleted {key} from the general credentials")

    def list_credentials(self, project_name: str | None = None) -> None:
        """Print the credential overview or one project's names without values."""
        if project_name is None:
            general_keys = self.__load_bundle(GENERAL_CREDENTIALS_KEY).keys()
            current_project_keys = self.__load_bundle(self.__project_key()).keys()

            print(f"Project credentials ({self.__project_name}):")
            for key in current_project_keys:
                print(f"  {key}")
            print("Projects Registered:")
            for known_project_name in self.__load_registry().names():
                print(f"  {known_project_name}")
            print("Global Secrets:")
            for key in general_keys:
                print(f"  {key}")
            return

        project_keys = self.__load_bundle(self.__project_key(project_name)).keys()
        print(f"Project credentials ({project_name}):")
        for key in project_keys:
            print(f"  {key}")

    # =================== #
    #                     #
    #   TRANSFER          #
    #                     #
    # =================== #

    def export_credentials(self, home_relative_directory: str) -> None:
        """Materialize every stored bundle as ``.env`` files in a directory.

        Parameters
        ----------
        home_relative_directory
            Destination directory, given relative to the home directory. It
            holds the whole store in plaintext, so keep it out of any synced or
            version-controlled location.
        """

        export_root = pathlib.Path.home() / home_relative_directory
        export_root.mkdir(parents=True, exist_ok=True)

        general_bundle = self.__load_bundle(GENERAL_CREDENTIALS_KEY)
        (export_root / "general.env").write_text(
            general_bundle.dotenv_content(), encoding="utf-8"
        )

        exported_projects = self.__load_registry().names()
        exported_keys = len(general_bundle.keys())
        for project_name in exported_projects:
            project_bundle = self.__load_bundle(self.__project_key(project_name))
            exported_keys += len(project_bundle.keys())
            (export_root / f"{project_name}.env").write_text(
                project_bundle.dotenv_content(), encoding="utf-8"
            )

        print(
            f"Exported {exported_keys} credentials across "
            f"{len(exported_projects) + 1} files to {export_root}"
        )

    # ================================= #
    #                                   #
    #   PROJECT BUNDLE SETUP            #
    #                                   #
    # ================================= #

    def setup_credentials(
        self,
        snippets_root: pathlib.Path,
        project_config: entities.ProjectConfigSchema,
    ) -> None:
        """Copy the project-owned configuration bundle, refusing to overwrite.

        Parameters
        ----------
        snippets_root
            Root of the devOS snippets directory.
        project_config
            Configuration naming where the project keeps its infrastructure code.
        """

        adapters_directory = project_config.project_root.adapters_output_directory
        destination_directory = self.__project_root.joinpath(*adapters_directory[:-1])

        source_directory = pathlib.Path(snippets_root) / "python" / "config"
        destinations = [
            destination_directory / file_name for file_name in CONFIG_SNIPPET_FILE_NAMES
        ]
        for destination in destinations:
            if destination.exists():
                raise FileExistsError(
                    f"{destination} already exists. Remove it before running setup again."
                )

        destination_directory.mkdir(parents=True, exist_ok=True)
        for file_name, destination in zip(CONFIG_SNIPPET_FILE_NAMES, destinations):
            shutil.copyfile(source_directory / file_name, destination)
        print(
            f"Copied the credential configuration bundle into {destination_directory}"
        )
