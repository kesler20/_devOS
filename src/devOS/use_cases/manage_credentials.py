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

STORE_KEY_PREFIX = "devos:"
STORE_KEY_PATTERN = "devos:*"
DOCUMENT_FILE_SUFFIX = ".json"
INVALID_PATH_CHARACTERS = frozenset('<>:"/\\|?*')

CONFIG_SNIPPET_FILE_NAMES = ("configs.py", "credentials.py")


def configuration_bundle_support(
    source_directory: pathlib.Path, config_import: str
) -> dict[str, str]:
    """Render the companion tests and setup files for an installed config package."""
    support = {
        "docs/snippets/config/" + name: (source_directory / name).read_text(encoding="utf-8")
        for name in ("README.md", "requirements.txt", "requirements-test.txt", ".env.example")
    }
    for test in sorted((source_directory / "tests").glob("test_*.py")):
        support["tests/snippets/config/" + test.name] = test.read_text(encoding="utf-8").replace(
            "from config import credentials", f"from {config_import} import credentials"
        )
    if not any(name.startswith("tests/") for name in support):
        raise ValueError("The configuration bundle must include offline tests.")
    return support

# Matches one environment assignment. The prefix captures everything up to
# and including the equals sign and any padding, so indentation, "export ",
# and spacing around the sign all survive a value being swapped in.
ASSIGNMENT_PATTERN = re.compile(
    r"^(?P<prefix>\s*(?:export\s+)?(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*)"
)


def document_relative_path(storage_key: str) -> pathlib.Path:
    """Translate a storage key into its path inside an exported store.

    The ``devos:`` prefix is dropped and every remaining segment becomes a
    directory, so ``devos:projects:devOS`` is written as ``projects/devOS.json``.
    A segment that would escape the export root or that no filesystem accepts
    stops the export instead of being rewritten into something else.
    """

    if not storage_key.startswith(STORE_KEY_PREFIX):
        raise ValueError(f"Storage key '{storage_key}' is outside the devOS store.")

    segments = storage_key[len(STORE_KEY_PREFIX) :].split(":")
    for segment in segments:
        if not segment or segment in {".", ".."}:
            raise ValueError(
                f"Storage key '{storage_key}' has an empty or relative segment."
            )
        if any(
            character in INVALID_PATH_CHARACTERS or ord(character) < 32
            for character in segment
        ):
            raise ValueError(f"Storage key '{storage_key}' cannot be written as a path.")

    # The last segment is joined by hand rather than through with_suffix, which
    # would treat a dot inside a key name as an extension and truncate it.
    return pathlib.Path(*segments[:-1]) / f"{segments[-1]}{DOCUMENT_FILE_SUFFIX}"


def storage_key_from_document_path(relative_path: pathlib.Path) -> str:
    """Translate a path inside an exported store back into its storage key."""
    segments = list(relative_path.parts)
    segments[-1] = segments[-1][: -len(DOCUMENT_FILE_SUFFIX)]
    return STORE_KEY_PREFIX + ":".join(segments)


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

        self.__write_environment_file(
            self.__load_bundle(self.__project_key()).dotenv_values()
        )

    def __write_environment_file(self, rendered_values: dict[str, str]) -> None:
        """Apply rendered values to ``.env`` without disturbing anything else."""
        environment_path = self.__project_root / ".env"

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
            updated_lines += [f"{key}={rendered_values[key]}" for key in appended_keys]

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

    def compare_project_credentials(
        self, values: dict[str, entities.JSONValue]
    ) -> dict[str, list[str]]:
        """Compare incoming values without exposing them or changing the store."""
        bundle = self.__load_bundle(self.__project_key())
        comparison: dict[str, list[str]] = {"missing": [], "identical": [], "conflicting": []}
        for key, value in sorted(values.items()):
            entities.CredentialBundle.validate_key(key)
            if key not in bundle.keys():
                comparison["missing"].append(key)
            elif bundle.get(key) == value:
                comparison["identical"].append(key)
            else:
                comparison["conflicting"].append(key)
        return comparison

    def import_project_credentials(
        self, values: dict[str, entities.JSONValue], resolutions: dict[str, str]
    ) -> None:
        """Merge agreed values and verify both the bundle and project registry."""
        bundle = self.__load_bundle(self.__project_key())
        for key, value in values.items():
            entities.CredentialBundle.validate_key(key)
            if key in bundle.keys() and bundle.get(key) != value:
                choice = resolutions.get(key)
                if choice not in {"local", "stored"}:
                    raise ValueError(f"Choose local or stored for credential key {key}")
        incoming = {
            key: value for key, value in values.items()
            if key not in bundle.keys() or bundle.get(key) == value or resolutions.get(key) == "local"
        }
        expected = bundle.combine(entities.CredentialBundle.from_json_value(incoming, self.__project_key()))
        if expected.values() != bundle.values() or self.__credential_database.get(self.__project_key()) is None:
            self.__store_bundle(self.__project_key(), expected)
        if self.__project_name not in self.__load_registry().names():
            self.__register_project(self.__project_name)
        if self.__load_bundle(self.__project_key()).values() != expected.values():
            raise RuntimeError("Credential bundle readback did not match the imported values")
        if self.__project_name not in self.__load_registry().names():
            raise RuntimeError("Credential project registry readback did not include the project")

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
        """Store one credential in the project bundle and in ``.env``."""
        self.__set_value(self.__project_key(), key, value)
        self.__register_project(self.__project_name)
        # Written straight to .env too, so the value is usable in this project
        # without a separate pull.
        rendered = entities.CredentialBundle.empty()
        rendered.merge({key: value})
        self.__write_environment_file(rendered.dotenv_values())
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
        if value is None:
            raise KeyError(f"General secret key {key} is absent")
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

    def export_store(self, home_relative_directory: str) -> None:
        """Mirror every stored document as a JSON file tree.

        The tree is a faithful copy of the store rather than a rendering of it,
        so values the environment format would flatten survive a round trip
        through ``import_store``.

        Parameters
        ----------
        home_relative_directory
            Destination directory, given relative to the home directory.
        """

        export_root = pathlib.Path.home() / home_relative_directory
        export_root.mkdir(parents=True, exist_ok=True)

        # Every key is translated before anything is written, so a key that
        # cannot become a path leaves no half-exported tree behind.
        storage_keys = self.__credential_database.keys(STORE_KEY_PATTERN)
        document_paths = {
            storage_key: export_root / document_relative_path(storage_key)
            for storage_key in storage_keys
        }

        for storage_key, document_path in document_paths.items():
            document_path.parent.mkdir(parents=True, exist_ok=True)
            document_path.write_text(
                json.dumps(
                    self.__credential_database.get(storage_key),
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

        print(f"Exported {len(document_paths)} documents to {export_root}")
        print(
            "These documents hold credentials in plaintext. Delete them once "
            "they have been imported."
        )

    def import_store(self, home_relative_directory: str) -> None:
        """Merge an exported JSON file tree into the current store.

        Only the credential database is written. Nothing already stored is
        replaced: an existing value is kept and reported as skipped, so the
        destination store is selected purely by the ``devos_redis_*`` connection
        the current ``.env`` describes.

        Parameters
        ----------
        home_relative_directory
            Directory holding an exported store, relative to the home directory.
        """

        import_root = pathlib.Path.home() / home_relative_directory
        if not import_root.is_dir():
            raise FileNotFoundError(
                f"No exported credential store was found at {import_root}."
            )

        written_documents = 0
        written_values = 0
        skipped_names_by_key: dict[str, list[str]] = {}
        for document_path in sorted(import_root.rglob(f"*{DOCUMENT_FILE_SUFFIX}")):
            storage_key = storage_key_from_document_path(
                document_path.relative_to(import_root)
            )
            incoming_document = entities.CredentialDocument.from_json_value(
                json.loads(document_path.read_text(encoding="utf-8"))
            )
            stored_document = entities.CredentialDocument.from_json_value(
                self.__credential_database.get(storage_key)
            )
            merge = stored_document.merge_without_overwriting(incoming_document)
            if merge.skipped:
                skipped_names_by_key[storage_key] = merge.skipped
            if not merge.changed():
                continue
            if not self.__credential_database.put(storage_key, stored_document.value()):
                raise RuntimeError(f"Credential document '{storage_key}' was not stored.")
            written_documents += 1
            written_values += len(merge.written)

        print(
            f"Imported {written_values} values across {written_documents} documents "
            f"from {import_root}"
        )
        for storage_key, skipped_names in skipped_names_by_key.items():
            print(f"  kept in {storage_key}: {', '.join(skipped_names)}")

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
            Root of automation_engine's wiki/Snippets library.
        project_config
            Configuration naming where the project keeps its infrastructure code.
        """

        adapters_directory = project_config.project_root.adapters_output_directory
        destination_directory = self.__project_root.joinpath(*adapters_directory[:-1])

        source_directory = pathlib.Path(snippets_root) / "python" / "config"
        relative_directory = destination_directory.relative_to(self.__project_root)
        import_parts = relative_directory.parts
        if import_parts and import_parts[0] == "src":
            import_parts = import_parts[1:]
        rendered = configuration_bundle_support(source_directory, ".".join(import_parts))
        rendered.update({
            (relative_directory / name).as_posix(): (source_directory / name).read_bytes().decode("utf-8")
            for name in CONFIG_SNIPPET_FILE_NAMES
        })
        for name in rendered:
            destination = self.__project_root / name
            if destination.exists():
                raise FileExistsError(
                    f"{destination} already exists. Remove it before running setup again."
                )

        for name, content in rendered.items():
            destination = self.__project_root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content.encode("utf-8"))
        print(
            f"Copied the credential configuration bundle into {destination_directory}"
        )
        print("Merge docs/snippets/config/requirements.txt into runtime dependencies and "
              "requirements-test.txt into test dependencies, then run the copied offline tests.")
