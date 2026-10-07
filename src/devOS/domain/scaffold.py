"""Approved project setup inputs and value-free operation results."""

from __future__ import annotations

import enum
import pathlib
import re
import typing

import pydantic


class ScaffoldError(RuntimeError):
    """Report a safe failure and any operations completed before it."""

    def __init__(self, operation: str, reason: str, category: str = "configuration"):
        self.operation = operation
        self.reason = reason
        self.category = category
        self.completed: list[str] = []
        super().__init__(f"{operation} failed. {reason}")


class Stack(str, enum.Enum):
    PYTHON = "python"
    REACT = "react"
    FULLSTACK = "fullstack"


class InputModel(pydantic.BaseModel):
    """Reject misspelled fields rather than silently dropping approved choices."""

    model_config = pydantic.ConfigDict(extra="forbid")


class BootstrapSource(InputModel):
    """Locate bootstrap values without placing them in an execution specification."""

    env_file: pathlib.Path | None = None
    secret_keys: dict[str, str] = pydantic.Field(default_factory=dict)

    @pydantic.field_validator("secret_keys")
    @classmethod
    def validate_keys(cls, value: dict[str, str]) -> dict[str, str]:
        allowed = {f"devos_redis_{key}" for key in
                   ("url", "host", "port", "username", "password", "db", "ssl")}
        if set(value) - allowed or any(not key for key in value.values()):
            raise ValueError("Bootstrap references must name canonical Redis variables")
        return value


class StoreSelection(InputModel):
    """Select a store and the source chosen for each differing credential key."""

    bootstrap: BootstrapSource
    resolutions: dict[str, typing.Literal["local", "stored"]] = pydantic.Field(default_factory=dict)


class GitHubSelection(InputModel):
    owner: str
    repository: str
    token_secret_key: str = "github_token"

    @pydantic.field_validator("owner", "repository", "token_secret_key")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", value):
            raise ValueError("Use a repository or secret name, not a URL or value")
        return value


class FileChange(InputModel):
    path: str
    content: str

    @pydantic.field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        if "\\" in value or ":" in value:
            raise ValueError("Use relative paths with forward slashes")
        return value


class ScaffoldSpec(InputModel):
    """Reviewed content and setup choices, never raw credential values."""

    protocol_root: pathlib.Path
    project_name: str
    description: str
    stack: Stack
    local_store: StoreSelection
    ci_store: StoreSelection
    project_path: pathlib.Path | None = None
    secret_source_env_file: pathlib.Path | None = None
    github: GitHubSelection | None = None
    automation_engine_root: pathlib.Path | None = None
    agent_guides: list[str] = pydantic.Field(default_factory=list)
    data_project: bool = False
    python_package: str | None = None
    python_version: str = "3.12"
    package_manager: typing.Literal["uv", "pip", "npm", "pnpm"] = "uv"
    ci_runner: str = "ubuntu-latest"
    frontend_path: str = "frontend"
    config_path: str | None = None
    config_content: str | None = None
    readme_body: str = ""
    prd: str = ""
    decision_log: str = ""
    source_tables: str | None = None
    files: list[FileChange] = pydantic.Field(default_factory=list)
    expected_files: dict[str, str] = pydantic.Field(default_factory=dict)
    validation_commands: list[list[str]] = pydantic.Field(default_factory=list)

    @pydantic.field_validator("validation_commands")
    @classmethod
    def validate_commands(cls, value: list[list[str]]) -> list[list[str]]:
        if any(not command or not all(command) for command in value):
            raise ValueError("Validation commands must be nonempty argument arrays")
        # Publishing is deliberately outside this workflow, including validation.
        for command in value:
            if command[0] in {"git", "gh"}:
                raise ValueError("Validation commands cannot perform Git or GitHub operations")
        return value

    @pydantic.field_validator("project_name")
    @classmethod
    def validate_project(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
            raise ValueError("Project names must be a single safe directory name")
        return value

    @pydantic.field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        if not value.strip() or "\n" in value or "\r" in value:
            raise ValueError("Provide an agreed, single-line project description")
        return value.strip()

    @pydantic.field_validator("python_package")
    @classmethod
    def validate_package(cls, value: str | None) -> str | None:
        if value is not None and not value.isidentifier():
            raise ValueError("Python package names must be identifiers")
        return value

    def root(self) -> pathlib.Path:
        """Resolve the explicitly selected Protocol project."""
        protocol = self.protocol_root.expanduser().resolve()
        root = (self.project_path or protocol / self.project_name).expanduser().resolve()
        if root == protocol or not root.is_relative_to(protocol):
            raise ScaffoldError("preflight", "Project must be inside the selected Protocol root")
        return root

    def engine_root(self) -> pathlib.Path:
        return (self.automation_engine_root or self.protocol_root / "automation_engine").expanduser().resolve()

    def package(self) -> str:
        value = self.python_package or self.project_name.replace("-", "_").replace(".", "_")
        if not value.isidentifier():
            raise ScaffoldError("preflight", "Choose a valid Python package name")
        return value

    def config_directory(self) -> str:
        directory = self.config_path or f"src/{self.package()}/infrastructure"
        if "\\" in directory or ":" in directory:
            raise ScaffoldError("preflight", "Use forward slashes in config paths")
        if self.stack == Stack.FULLSTACK and pathlib.PurePosixPath(directory).is_relative_to(self.frontend_path):
            raise ScaffoldError("preflight", "Credential loading cannot be placed in the frontend")
        return directory

    def has_python(self) -> bool:
        return self.stack != Stack.REACT


class ScaffoldInspection(pydantic.BaseModel):
    project_path: str
    exists: bool
    git_repository: bool
    staged_files: list[str] = pydantic.Field(default_factory=list)
    environment_keys: list[str] = pydantic.Field(default_factory=list)
    bootstrap_keys: list[str] = pydantic.Field(default_factory=list)
    files: dict[str, str] = pydantic.Field(default_factory=dict)
    credential_comparison: dict[str, list[str]] = pydantic.Field(default_factory=dict)
    store_state: str = "unconfigured"
    setup_requirements: list[str] = pydantic.Field(default_factory=list)


class CredentialSetupResult(pydantic.BaseModel):
    stores_verified: list[str]
    files: list[str]


class GitHubSecretSetupResult(pydantic.BaseModel):
    repository: str
    secret_names: list[str]


class ScaffoldResult(pydantic.BaseModel):
    project_path: str
    files: list[str]
    staged_files: list[str]
    completed: list[str]
    pending: list[str] = pydantic.Field(default_factory=lambda: ["Kesler commits and pushes", "Verify Actions after push"])
