from __future__ import annotations
import dataclasses
import json
import re
import pydantic
import typing
import enum


class SupportedLanguages(enum.Enum):
    TYPESCRIPT = "typescript"
    PYTHON = "python"


SupportedLanguagesValues = typing.Literal["typescript", "python"]


class CodeGenOutputConfig(pydantic.BaseModel):
    """
    Specify code generation output settings for a project.

    Parameters
    ----------
    directory : list[str]
        Path to the output directory, relative to the project root, as a list of path components.
    language : SupportedLanguagesValues
        Programming language to use for generated code.
    """

    directory: list[str]
    language: SupportedLanguagesValues


class ContractSyncOutputConfig(pydantic.BaseModel):
    """
    Specify output settings for `@contract` synchronization.

    Parameters
    ----------
    source_language : SupportedLanguagesValues
        Source language to scan for files marked with ``@contract``.
    output_directory : list[str]
        Destination directory (relative to project root) where translated
        contracts are written using the same base filename.
    """

    source_language: SupportedLanguagesValues
    output_directory: list[str]


class ProjectSpecificConfig(pydantic.BaseModel):
    """
    Project-specific configuration for code generation outputs.

    Parameters
    ----------
    dao_output_config : CodeGenOutputConfig
        Output configuration for DAO code.
    dto_output_config : CodeGenOutputConfig
        Output configuration for DTO code.
    api_output_config : CodeGenOutputConfig
        Output configuration for API code.
    test_api_output_config : list[CodeGenOutputConfig]
        Output configuration for API test code.
    test_services_output_directory : list[str]
        Output configuration for service test code.
    adapters_output_directory : list[str]
        Output directory for adapter code, relative to the project root, as a list of path components
    use_cases_output_directory : list[str]
        Output directory for use case code, relative to the project root, as a list of path components.
    app_definition_directory : list[str]
        Output directory for fastapi app definition code and `get_db`, relative to the project root, as a list of path components.
    contract_sync_output_config : list[ContractSyncOutputConfig]
        Configuration for `@contract` file synchronization between Python and
        TypeScript.
    """

    dao_output_config: list[CodeGenOutputConfig]
    dto_output_config: list[CodeGenOutputConfig]
    api_output_config: list[CodeGenOutputConfig]
    test_api_output_config: list[CodeGenOutputConfig]
    test_services_output_directory: list[str]
    adapters_output_directory: list[str] = []
    use_cases_output_directory: list[str] = []
    app_definition_directory: list[str] = []
    contract_sync_output_config: list[ContractSyncOutputConfig] = []


class HomeRootConfig(pydantic.BaseModel):
    """
    Global configuration using the user's home directory as the root.

    Parameters
    ----------
    snippets : list[str]
        Paths to snippet directories, specified as lists of path components, relative to the user's home directory.
    """

    snippets: list[str]


class ProjectConfigSchema(pydantic.BaseModel):
    """
    Overall project configuration schema.

    Parameters
    ----------
    project_name : str
        Git repository name persisted for deployed runtimes.
    home_root : HomeRootConfig
        Global configuration rooted at the user's home directory.
    project_root : ProjectSpecificConfig
        Project-specific configuration, with paths relative to the project root.
    """

    project_name: str
    home_root: HomeRootConfig
    project_root: ProjectSpecificConfig

    @classmethod
    def create_default(cls, project_name: str) -> ProjectConfigSchema:
        """
        Generate a default project configuration.

        Parameters
        ----------
        project_name : str
            Name of the project to use in the configuration.

        Returns
        -------
        ProjectConfigSchema
            Default project configuration.
        """
        return cls(
            project_name=project_name,
            home_root=HomeRootConfig(
                snippets=["protocol", "automation_engine", "wiki", "Snippets"],
            ),
            project_root=ProjectSpecificConfig(
                dao_output_config=[
                    CodeGenOutputConfig(
                        directory=["src", project_name, "domain", "dao.py"],
                        language="python",
                    )
                ],
                dto_output_config=[
                    CodeGenOutputConfig(
                        directory=["src", project_name, "use_cases", "dto.py"],
                        language="python",
                    )
                ],
                api_output_config=[
                    CodeGenOutputConfig(
                        directory=["src", project_name, "infrastructure", "routes.py"],
                        language="python",
                    )
                ],
                test_services_output_directory=["tests"],
                test_api_output_config=[
                    CodeGenOutputConfig(
                        directory=["tests", "test_crud_routes.py"],
                        language="python",
                    )
                ],
                adapters_output_directory=[
                    "src",
                    project_name,
                    "infrastructure",
                    "sqlalchemy_db_adapter.py",
                ],
                use_cases_output_directory=[
                    "src",
                    project_name,
                    "use_cases",
                    "crud_use_cases.py",
                ],
                app_definition_directory=[
                    "src",
                    project_name,
                    "infrastructure",
                    "app.py",
                ],
                contract_sync_output_config=[
                    ContractSyncOutputConfig(
                        source_language="python",
                        output_directory=["src", project_name, "schema", "typescript"],
                    ),
                    ContractSyncOutputConfig(
                        source_language="typescript",
                        output_directory=["src", project_name, "schema", "python"],
                    ),
                ],
            ),
        )


# ================================= #
#                                   #
#   CREDENTIALS MANAGER ENTITIES    #
#                                   #
# ================================= #


JSONValue: typing.TypeAlias = (
    None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
)

BOOTSTRAP_VARIABLE_PREFIX = "devos_"


def is_bootstrap_variable(key: str) -> bool:
    """Check whether a name addresses the credential database's own connection.

    The comparison ignores case so that `devos_redis_host` and
    `DEVOS_REDIS_HOST` are the same reserved name, since Windows treats
    environment variables case-insensitively while Linux does not.
    """
    return key.lower().startswith(BOOTSTRAP_VARIABLE_PREFIX)


ENVIRONMENT_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclasses.dataclass
class CredentialBundle:
    """Own one validated group of credential values."""

    __values: dict[str, JSONValue]

    @classmethod
    def empty(cls) -> CredentialBundle:
        """Create an empty credential bundle."""
        return cls({})

    @classmethod
    def from_json_value(cls, value: JSONValue, storage_key: str) -> CredentialBundle:
        """Validate a Redis JSON document as a credential bundle."""
        if not isinstance(value, dict):
            raise ValueError(f"Credential bundle '{storage_key}' is not a JSON object.")

        validated_values: dict[str, JSONValue] = {}
        for key, credential_value in value.items():
            cls.validate_key(key)
            validated_values[key] = credential_value
        return cls(validated_values)

    @staticmethod
    def validate_key(key: str) -> None:
        """Validate one non-bootstrap environment variable name."""
        if not ENVIRONMENT_KEY_PATTERN.fullmatch(key):
            raise ValueError(f"Invalid environment variable name: {key}")
        if is_bootstrap_variable(key):
            raise ValueError(
                "devOS credential database bootstrap variables are reserved."
            )

    def merge(self, incoming_values: dict[str, JSONValue]) -> None:
        """Merge validated values while retaining values not mentioned by the caller."""
        for key, value in incoming_values.items():
            self.validate_key(key)
            self.__values[key] = value

    def remove(self, key: str) -> None:
        """Remove one known credential value."""
        self.validate_key(key)
        if key not in self.__values:
            raise KeyError(f"Credential key '{key}' was not found.")
        del self.__values[key]

    def get(self, key: str) -> JSONValue:
        """Return one known credential value."""
        self.validate_key(key)
        if key not in self.__values:
            raise KeyError(f"Credential key '{key}' was not found.")
        return self.__values[key]

    def combine(self, override_bundle: CredentialBundle) -> CredentialBundle:
        """Return a bundle where the supplied bundle has precedence."""
        return CredentialBundle({**self.__values, **override_bundle.__values})

    def values(self) -> dict[str, JSONValue]:
        """Return a JSON-safe copy suitable for a storage boundary."""
        return json.loads(json.dumps(self.__values, ensure_ascii=False))

    def keys(self) -> list[str]:
        """Return sorted credential names without their values."""
        return sorted(self.__values)

    def dotenv_values(self) -> dict[str, str]:
        """Render each credential as the right-hand side of an environment line."""
        rendered_values: dict[str, str] = {}
        for key in self.keys():
            value = self.__values[key]
            if value is None:
                continue
            if isinstance(value, str):
                rendered_value = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, bool):
                rendered_value = "true" if value else "false"
            elif isinstance(value, int | float):
                rendered_value = str(value)
            else:
                # Encode non-primitive values to JSON, then quote that JSON as a
                # dotenv string so the line stays on one line and re-parses back
                # to the original value (not just its string form).
                serialized_json = json.dumps(
                    value, ensure_ascii=False, separators=(",", ":")
                )
                rendered_value = json.dumps(serialized_json, ensure_ascii=False)
            rendered_values[key] = rendered_value
        return rendered_values

    def dotenv_content(self) -> str:
        """Render credential values as an environment file without explicit unsets."""
        rendered_lines = [
            f"{key}={value}" for key, value in self.dotenv_values().items()
        ]
        return "\n".join(rendered_lines) + ("\n" if rendered_lines else "")

    def dotenv_example_content(self) -> str:
        """Render a credential-name-only environment example."""
        rendered_lines = [
            f"{key}=" for key in self.keys() if self.__values[key] is not None
        ]
        return "\n".join(rendered_lines) + ("\n" if rendered_lines else "")


@dataclasses.dataclass
class CredentialProjectRegistry:
    """Own the known credential project names."""

    __project_names: set[str]

    @classmethod
    def empty(cls) -> CredentialProjectRegistry:
        """Create an empty project registry."""
        return cls(set())

    @classmethod
    def from_json_value(
        cls, value: JSONValue, storage_key: str
    ) -> CredentialProjectRegistry:
        """Validate a Redis JSON document as a project-name registry."""
        if not isinstance(value, list) or not all(
            isinstance(project_name, str) for project_name in value
        ):
            raise ValueError(
                f"The credential project registry '{storage_key}' is not a JSON string list."
            )
        return cls(set(typing.cast(list[str], value)))

    def register(self, project_name: str) -> None:
        """Record a project as owning a project credential bundle."""
        self.__project_names.add(project_name)

    def names(self) -> list[str]:
        """Return project names in deterministic order."""
        return sorted(self.__project_names)


WHOLE_DOCUMENT_NAME = "(whole document)"


@dataclasses.dataclass
class DocumentMerge:
    """Own the outcome of merging one stored document into another."""

    written: list[str]
    skipped: list[str]

    def changed(self) -> bool:
        """Report whether the destination document gained anything."""
        return bool(self.written)


@dataclasses.dataclass
class CredentialDocument:
    """Own one document held under a single credential database key.

    The document is kept as the raw JSON value the store returned, so a
    transfer preserves values the dotenv rendering would flatten.
    """

    __value: JSONValue

    @classmethod
    def from_json_value(cls, value: JSONValue) -> CredentialDocument:
        """Wrap a value read from the credential database."""
        return cls(value)

    def value(self) -> JSONValue:
        """Return a JSON-safe copy suitable for a storage boundary."""
        return json.loads(json.dumps(self.__value, ensure_ascii=False))

    def merge_without_overwriting(self, incoming: CredentialDocument) -> DocumentMerge:
        """Take everything from another document that this one does not hold.

        An object gains the fields it is missing and keeps every value it
        already has. A list gains the members it is missing. Any other pair of
        present documents is left alone, since there is no field to merge and
        replacing one would overwrite a stored value.

        Parameters
        ----------
        incoming
            Document supplied by the caller.

        Returns
        -------
        DocumentMerge
            Names written and names skipped, both in sorted order.
        """

        incoming_value = incoming.value()
        if self.__value is None:
            self.__value = incoming_value
            # An adopted key is always a change, even when the document it
            # carries is empty and so names nothing.
            adopted_names = self.__written_names(incoming_value)
            return DocumentMerge(adopted_names or [WHOLE_DOCUMENT_NAME], [])

        if isinstance(self.__value, dict) and isinstance(incoming_value, dict):
            written: list[str] = []
            skipped: list[str] = []
            for key, value in incoming_value.items():
                if key in self.__value:
                    skipped.append(key)
                    continue
                self.__value[key] = value
                written.append(key)
            return DocumentMerge(sorted(written), sorted(skipped))

        if isinstance(self.__value, list) and isinstance(incoming_value, list):
            missing_members = [
                member for member in incoming_value if member not in self.__value
            ]
            self.__value = sorted(
                self.__value + missing_members,
                key=lambda member: json.dumps(member, sort_keys=True),
            )
            return DocumentMerge(self.__written_names(missing_members), [])

        return DocumentMerge([], [WHOLE_DOCUMENT_NAME])

    @staticmethod
    def __written_names(value: JSONValue) -> list[str]:
        """Name what a freshly adopted value contributed."""
        if isinstance(value, dict):
            return sorted(value)
        if isinstance(value, list):
            return sorted(
                (
                    json.dumps(member, sort_keys=True)
                    if not isinstance(member, str)
                    else member
                )
                for member in value
            )
        return [WHOLE_DOCUMENT_NAME]
