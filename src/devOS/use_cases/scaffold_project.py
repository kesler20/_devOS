"""Inspect, configure, and stage an agreed project without publishing code."""

from __future__ import annotations
import logging

import ast
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import typing
import urllib.parse
import datetime as datetime

import dotenv
import pydantic
import redis.exceptions
import tomlkit
import yaml

from devOS.domain import entities
import devOS.domain.scaffold as scaffold
import devOS.infrastructure.adapters as adapters
import devOS.infrastructure.credential_vault as credential_vault
import devOS.infrastructure.github_repository_client as github_repository_client
import devOS.infrastructure.scaffold_adapters as scaffold_adapters

import devOS.use_cases.manage_credentials as manage_credentials
from devOS.use_cases import credential_ports

RUNTIME_DEPENDENCIES = [
    "redis>=6.4.0",
    "python-dotenv>=1.1.0",
    "pydantic>=2.0",
    "pydantic-settings>=2.0",
]


def validate_config_loading(content: str) -> None:
    """Require dotenv loading before settings are constructed."""
    tree = ast.parse(content)
    loads = [
        node.value
        for node in tree.body
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and ast.unparse(node.value.func).endswith("load_dotenv")
    ]
    if not loads:
        raise scaffold.ScaffoldError(
            "preflight",
            "Config must load .env at module scope before constructing settings",
        )
    settings = {
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and any(ast.unparse(base).endswith("BaseSettings") for base in node.bases)
    }
    if any(
        node.lineno < min(load.lineno for load in loads)
        and isinstance(node.func, ast.Name)
        and node.func.id in settings
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    ):
        raise scaffold.ScaffoldError(
            "preflight", "Config constructs settings before loading .env"
        )

    if any(
        not any(
            keyword.arg == "interpolate"
            and isinstance(keyword.value, ast.Constant)
            and keyword.value.value is False
            for keyword in load.keywords
        )
        for load in loads
    ):
        raise scaffold.ScaffoldError(
            "preflight", "Config must load dotenv with interpolate=False"
        )

    settings_classes = [
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name in settings
    ]
    if any(
        (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "env_file"
                for target in node.targets
            )
            and not (isinstance(node.value, ast.Constant) and node.value.value is None)
        )
        or (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "env_file"
            and node.value is not None
            and not (isinstance(node.value, ast.Constant) and node.value.value is None)
        )
        or (
            isinstance(node, ast.Dict)
            and any(
                isinstance(key, ast.Constant)
                and key.value == "env_file"
                and not (isinstance(value, ast.Constant) and value.value is None)
                for key, value in zip(node.keys, node.values)
            )
        )
        or (
            isinstance(node, ast.keyword)
            and node.arg == "env_file"
            and not (isinstance(node.value, ast.Constant) and node.value.value is None)
        )
        for settings_class in settings_classes
        for node in ast.walk(settings_class)
    ) or any(
        isinstance(node, ast.Call)
        and any(
            keyword.arg == "_env_file"
            and not (
                isinstance(keyword.value, ast.Constant) and keyword.value.value is None
            )
            for keyword in node.keywords
        )
        for node in ast.walk(tree)
    ):
        raise scaffold.ScaffoldError(
            "preflight",
            "Settings must use the literal environment loaded by dotenv without rereading env_file",
        )


def get_environment_values(root: pathlib.Path) -> dict[str, entities.JSONValue]:
    """Keep literal dotenv values and exclude the reserved bootstrap namespace."""
    path = root / ".env"
    return (
        {
            key: value
            for key, value in dotenv.dotenv_values(path, interpolate=False).items()
            if value is not None and not entities.is_bootstrap_variable(key)
        }
        if path.is_file()
        else {}
    )


def render_python_manifest(
    spec: scaffold.ScaffoldSpec, files: scaffold_adapters.ProjectFilesAdapter
) -> str:
    """Preserve TOML formatting while updating description and runtime dependencies."""
    current = files.read(files.path(spec.root(), "pyproject.toml"))
    document = tomlkit.parse(current) if current else tomlkit.document()
    if "project" not in document:
        if current:
            raise scaffold.ScaffoldError(
                "preflight",
                "Existing package metadata is not PEP 621. Supply an agreed targeted migration",
            )
        document["project"] = {
            "name": spec.project_name,
            "version": "0.1.0",
            "requires-python": ">=" + spec.python_version,
            "readme": "README.md",
        }
        document["build-system"] = {
            "requires": ["uv_build>=0.9.0,<0.10.0"],
            "build-backend": "uv_build",
        }
        document["tool"] = {"uv": {"build-backend": {"module-name": spec.package()}}}
    project = typing.cast(tomlkit.items.Table, document["project"])
    project["description"] = spec.description
    dependencies = project.get("dependencies", [])
    names = {
        re.split(r"[\[<>=!~ ;]", item.strip())[0].lower().replace("_", "-")
        for item in dependencies
    }
    for dependency in RUNTIME_DEPENDENCIES:
        if re.split(r"[<>=]", dependency)[0] not in names:
            dependencies.append(dependency)
    project["dependencies"] = dependencies
    optional = project.get("optional-dependencies", {})
    test_dependencies = optional.get("dev", [])
    if not any(
        re.split(r"[\[<>=!~ ;]", item)[0].lower() == "pytest"
        for item in test_dependencies
    ):
        test_dependencies.append("pytest>=8.0")
    optional["dev"] = test_dependencies
    project["optional-dependencies"] = optional
    return tomlkit.dumps(document)


def render_credential_files(
    spec: scaffold.ScaffoldSpec,
    files: scaffold_adapters.ProjectFilesAdapter,
    bootstrap: dict[str, str],
) -> dict[str, str]:
    """Render bootstrap documentation and project-specific Python configuration."""
    root = spec.root()
    ignored = files.read(files.path(root, ".gitignore"))
    for pattern in [
        ".env",
        ".env.*",
        "!.env.example",
        ".devos_backup/",
        ".venv/",
        "__pycache__/",
        "node_modules/",
    ]:
        if pattern not in ignored.splitlines():
            ignored = (
                ignored.rstrip("\r\n") + ("\n" if ignored else "") + pattern + "\n"
            )
    rendered = {
        ".gitignore": ignored,
        ".env.example": (
            files.read(root / ".env.example")
            if (root / ".env.example").is_file()
            else "".join(
                f"{key}=\n" for key in sorted([*bootstrap, "devos_project_name"])
            )
        ),
    }
    if spec.has_python():
        directory = spec.config_directory()
        files.path(root, directory + "/configs.py")
        current = files.read(files.path(root, directory + "/configs.py"))
        if current and spec.config_content is None:
            if "load_dotenv" not in current:
                raise scaffold.ScaffoldError(
                    "preflight",
                    "Provide reviewed config_content integrating the existing settings file",
                )
            config = current
        elif spec.config_content is not None:
            config = spec.config_content
            if "load_dotenv" not in config:
                raise scaffold.ScaffoldError(
                    "preflight",
                    "Config must load .env at module scope before constructing settings",
                )
        else:
            source = spec.engine_root() / "wiki/Snippets/python/config"
            depth = len(pathlib.PurePosixPath(directory).parts)
            config = files.read(source / "configs.py")
            if not config:
                raise scaffold.ScaffoldError(
                    "preflight", "Canonical configuration bundle is unavailable"
                )
            config = (
                config.replace("\r\n", "\n")
                .replace("import os\n", "import os\nimport pathlib\n", 1)
                .replace(
                    "dotenv.load_dotenv(interpolate=False)",
                    f"dotenv.load_dotenv(pathlib.Path(__file__).resolve().parents[{depth}] / '.env', interpolate=False)",
                    1,
                )
            )
            # Dotenv already materializes the literal environment before settings.
            # Pydantic must not reread and interpolate the same file.
            config = config.replace(
                '        env_file = ".env"', '        extra = "ignore"'
            ).replace('        env_file_encoding = "utf-8"\n', "")
        source = spec.engine_root() / "wiki/Snippets/python/config"
        import_parts = pathlib.PurePosixPath(directory).parts
        if import_parts and import_parts[0] == "src":
            import_parts = import_parts[1:]
        support = manage_credentials.get_configuration_bundle_support(
            source, ".".join(import_parts)
        )
        support.update(
            {
                directory + "/" + name: files.read(source / name)
                for name in manage_credentials.CONFIG_SNIPPET_FILE_NAMES
                if name != "configs.py"
            }
        )
        for name, content in support.items():
            # Existing project-owned support is retained on a reviewed rerun.
            if not files.path(root, name).exists():
                rendered[name] = content
        rendered[directory + "/configs.py"] = config
        validate_config_loading(config)
        parts = pathlib.PurePosixPath(directory).parts
        for length in range(1, len(parts) + 1):
            prefix = pathlib.PurePosixPath(*parts[:length]).as_posix()
            if prefix == "src":
                continue
            name = prefix + "/__init__.py"
            if not files.path(root, name).exists():
                rendered[name] = ""
        rendered["pyproject.toml"] = render_python_manifest(spec, files)
    return rendered


def render_project_files(
    spec: scaffold.ScaffoldSpec,
    files: scaffold_adapters.ProjectFilesAdapter,
    bootstrap: dict[str, str],
    vault_factory: typing.Callable[
        [], credential_ports.CredentialDatabasePort
    ] = credential_vault.get_local_vault,
) -> dict[str, str]:
    """Render approved prose plus deterministic package and setup metadata."""
    if (
        not spec.prd.strip()
        or not spec.decision_log.strip()
        or not spec.readme_body.strip()
    ):
        raise scaffold.ScaffoldError(
            "preflight",
            "Provide the agreed PRD, decision log, and detailed README body",
        )
    root = spec.root()
    rendered = render_credential_files(spec, files, bootstrap)
    rendered.update(
        {
            "README.md": f"# {spec.project_name}\n\n{spec.description}\n\n{spec.readme_body.rstrip()}\n",
            "docs/product/prd.md": spec.prd,
            "docs/product/decision-log.md": spec.decision_log,
        }
    )
    for directory in [
        "scripts",
        *(
            ["notebooks/kpis", "notebooks/eda", "notebooks/experiments/src"]
            if spec.data_project
            else []
        ),
    ]:
        placeholder = directory + "/.gitkeep"
        if not files.path(root, placeholder).exists():
            rendered[placeholder] = ""
    design_path = files.path(root, "docs/product/design.md")
    if not design_path.exists():
        rendered["docs/product/design.md"] = ""
    if spec.source_tables is not None:
        original = files.read(design_path)
        newline = "\r\n" if "\r\n" in original else "\n"
        inventory = (
            "## Source Tables"
            + newline
            + newline
            + spec.source_tables.rstrip()
            + newline
        )
        match = re.search(
            r"^## Source Tables\r?\n.*?(?=^## |\Z)", original, re.MULTILINE | re.DOTALL
        )
        rendered["docs/product/design.md"] = (
            original[: match.start()] + inventory + original[match.end() :]
            if match
            else original
            + (newline if original and not original.endswith(newline) else "")
            + inventory
        )
    if spec.stack != scaffold.Stack.PYTHON:
        name = (
            "package.json"
            if spec.stack == scaffold.Stack.REACT
            else spec.frontend_path.rstrip("/") + "/package.json"
        )
        existing = files.read(files.path(root, name))
        package = (
            json.loads(existing)
            if existing
            else {
                "name": spec.project_name.lower(),
                "version": "0.1.0",
                "private": True,
            }
        )
        package["description"] = spec.description
        if not existing:
            package["dependencies"] = {"react": "^19.0.0", "react-dom": "^19.0.0"}
        rendered[name] = json.dumps(package, indent=2, ensure_ascii=False) + "\n"
    reserved = {name.casefold() for name in rendered} | {
        ".env",
        "docs/product/design.md",
    }
    for change in spec.files:
        name = pathlib.PurePosixPath(change.path).as_posix()
        if (
            name.casefold() in reserved
            or pathlib.PurePosixPath(name).name.lower().startswith(".env")
            or any(
                part.lower() in {".git", ".devos_backup"}
                for part in pathlib.PurePosixPath(name).parts
            )
        ):
            raise scaffold.ScaffoldError(
                "preflight",
                "Use dedicated fields for generated metadata, design, and environment files",
            )
        if name.casefold() in {path.casefold() for path in rendered}:
            raise scaffold.ScaffoldError("preflight", "Duplicate approved file change")
        rendered[name] = change.content
    ci_path = files.path(root, ".github/workflows/ci.yml")
    if ".github/workflows/ci.yml" not in rendered and not ci_path.exists():
        python_steps = (
            (
                f"      - uses: actions/setup-python@v5\n        with:\n          python-version: '{spec.python_version}'\n"
                "      - run: python -m pip install -e .\n"
                f"      - run: python -m compileall -q {spec.config_directory()}\n"
            )
            if spec.has_python()
            else ""
        )
        if spec.has_python() and (
            (root / "tests").is_dir()
            or any(name.startswith("tests/") for name in rendered)
        ):
            python_steps += "      - run: python -m pip install pytest\n      - run: python -m pytest\n"
        frontend_steps = ""
        if spec.stack != scaffold.Stack.PYTHON:
            location = "." if spec.stack == scaffold.Stack.REACT else spec.frontend_path
            package = json.loads(
                rendered[
                    (
                        "package.json"
                        if spec.stack == scaffold.Stack.REACT
                        else location + "/package.json"
                    )
                ]
            )
            manager = "pnpm" if spec.package_manager == "pnpm" else "npm"
            frontend_steps = "      - uses: actions/setup-node@v4\n        with:\n          node-version: '22'\n"
            if manager == "pnpm":
                frontend_steps += "      - run: corepack enable\n"
            frontend_steps += f"      - run: {manager} install\n        working-directory: {location}\n"
            for check in ("lint", "typecheck", "test", "build"):
                if check in package.get("scripts", {}):
                    frontend_steps += f"      - run: {manager} run {check}\n        working-directory: {location}\n"
        # Secret keys depend on the separately selected CI connection, not local bootstrap.
        ci_keys = (
            set(spec.ci_store.bootstrap.secret_keys)
            if spec.ci_store
            else set(get_environment_values(root))
        )
        if spec.ci_store is None:
            vault = vault_factory()
            stored = vault.get("devos:projects:" + spec.project_name)
            if isinstance(stored, dict):
                ci_keys.update(
                    key for key, value in stored.items() if value is not None
                )
        if spec.ci_store and spec.ci_store.bootstrap.env_file:
            import devOS.infrastructure.scaffold_adapters as scaffold_adapters

            ci_keys.update(
                scaffold_adapters.read_bootstrap_file(spec.ci_store.bootstrap.env_file)
            )
        if spec.ci_store:
            ci_keys.add("devos_project_name")
        environment = (
            "    env:\n"
            + "".join(
                f"      {key}: ${{{{ secrets.{key.upper()} }}}}\n"
                for key in sorted(ci_keys)
            )
            if spec.has_python() and ci_keys
            else ""
        )
        rendered[".github/workflows/ci.yml"] = (
            "name: CI\non: [push, pull_request]\npermissions:\n  contents: read\njobs:\n"
            "  checks:\n    runs-on: "
            + json.dumps(spec.ci_runner)
            + "\n"
            + environment
            + "    steps:\n      - uses: actions/checkout@v4\n"
            + python_steps
            + frontend_steps
        )
    return rendered


def validate_rendered(rendered: dict[str, str]) -> None:
    """Validate syntax before any mutation without executing project modules."""
    for name, content in rendered.items():
        try:
            if name.endswith(".py"):
                ast.parse(content)
            elif name.endswith(".toml"):
                tomlkit.parse(content)
            elif name.endswith(".json"):
                json.loads(content)
            elif name.endswith((".yml", ".yaml")):
                payload = yaml.safe_load(content)
                if name.startswith(".github/workflows/") and (
                    not isinstance(payload, dict) or not payload.get("jobs")
                ):
                    raise scaffold.ScaffoldError(
                        "preflight", f"Workflow must define jobs at {name}"
                    )
        except (SyntaxError, ValueError, yaml.YAMLError, tomlkit.exceptions.ParseError):
            raise scaffold.ScaffoldError(
                "preflight", f"Generated file has invalid syntax at {name}"
            ) from None


def get_registered_project_page(
    engine: pathlib.Path,
    root: pathlib.Path,
    project_name: str,
    files: scaffold_adapters.ProjectFilesAdapter,
) -> pathlib.Path:
    """Find the owning registry page by repository path, irrespective of its title."""
    matches: list[pathlib.Path] = []
    proposed = engine / "wiki/Projects" / (project_name + ".md")
    for page in (engine / "wiki/Projects").glob("*.md"):
        content = files.read(page)
        frontmatter = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", content, re.DOTALL)
        if frontmatter is None:
            raise scaffold.ScaffoldError(
                "registration", "A project registry page has invalid frontmatter"
            )
        try:
            metadata = yaml.safe_load(frontmatter.group(1))
        except yaml.YAMLError:
            raise scaffold.ScaffoldError(
                "registration", "A project registry page has invalid YAML"
            ) from None
        registered_path = (
            metadata.get("repository_path") if isinstance(metadata, dict) else None
        )
        if (
            registered_path
            and pathlib.Path(str(registered_path)).expanduser().resolve() == root
        ):
            matches.append(page)
        elif page == proposed and registered_path:
            raise scaffold.ScaffoldError(
                "registration",
                "The project title registers a different repository",
                "conflict",
            )
    if len(matches) > 1:
        raise scaffold.ScaffoldError(
            "registration",
            "More than one project page registers this repository",
            "conflict",
        )
    return matches[0] if matches else proposed


class InspectProjectScaffoldUseCase:
    """Inspect public files and local credential key differences without mutation."""

    def __init__(
        self,
        files: scaffold_adapters.ProjectFilesAdapter,
        git: scaffold_adapters.GitProjectAdapter,
        vault_factory: typing.Callable[
            [], credential_ports.CredentialDatabasePort
        ] = credential_vault.get_local_vault,
        manager_factory: typing.Callable[
            [credential_ports.CredentialDatabasePort, str, pathlib.Path],
            manage_credentials.ManageCredentialsUseCase,
        ] = manage_credentials.ManageCredentialsUseCase,
    ) -> None:
        self.__files, self.__git = files, git
        self.__vault_factory, self.__manager_factory = vault_factory, manager_factory

    def execute(self, request: pathlib.Path) -> scaffold.ScaffoldInspection:
        logging.info("Starting execute")
        root = request.expanduser().resolve()
        values = (
            dotenv.dotenv_values(root / ".env", interpolate=False)
            if (root / ".env").is_file()
            else {}
        )
        configured = {
            key.lower(): value
            for key, value in values.items()
            if key.lower() in scaffold_adapters.BOOTSTRAP_NAMES and value is not None
        }
        git_repository = self.__git.is_repository(root)
        result = scaffold.ScaffoldInspection(
            project_path=str(root),
            exists=root.exists(),
            git_repository=git_repository,
            staged_files=self.__git.staged(root) if git_repository else [],
            environment_keys=sorted(
                key for key in values if not entities.is_bootstrap_variable(key)
            ),
            bootstrap_keys=sorted(configured),
            files=self.__files.inventory(root),
        )
        result.setup_requirements = [
            name
            for name in [
                "docs/product/prd.md",
                "docs/product/decision-log.md",
                "docs/product/design.md",
                "README.md",
                ".env.example",
                ".gitignore",
            ]
            if not (root / name).is_file()
        ]
        if not git_repository:
            result.setup_requirements.append("Git repository")
        try:
            database = self.__vault_factory()
            import devOS.credential_cli as credential_cli

            manager = self.__manager_factory(
                database, credential_cli.get_project_name(root) or root.name, root
            )
            result.credential_comparison = manager.compare_project_credentials(
                get_environment_values(root)
            )
            result.store_state = "read"
        except credential_vault.VaultNotConfigured:
            result.setup_requirements.append("local JSON credential vault")
        logging.info("Completed execute")
        return result


class ConfigureProjectCredentialsUseCase:
    """Verify selected store imports before replacing the local environment file."""

    def __init__(
        self,
        bootstrap: scaffold_adapters.BootstrapSourceAdapter,
        files: scaffold_adapters.ProjectFilesAdapter,
        git: scaffold_adapters.GitProjectAdapter,
        database_factory: typing.Callable[
            [typing.Mapping[str, str]], adapters.RedisNoSQLAdapter | None
        ] = adapters.RedisNoSQLAdapter.from_environment,
        vault_factory: typing.Callable[
            [], credential_ports.CredentialDatabasePort
        ] = credential_vault.get_local_vault,
        manager_factory: typing.Callable[
            [credential_ports.CredentialDatabasePort, str, pathlib.Path],
            manage_credentials.ManageCredentialsUseCase,
        ] = manage_credentials.ManageCredentialsUseCase,
    ):
        self.__bootstrap, self.__files, self.__git = bootstrap, files, git
        self.__database_factory = database_factory
        self.__vault_factory, self.__manager_factory = vault_factory, manager_factory

    def execute(self, spec: scaffold.ScaffoldSpec) -> scaffold.CredentialSetupResult:
        logging.info("Starting execute")
        root = spec.root()
        incoming = get_environment_values(root)
        local_values: dict[str, str] = {}
        vault = self.__vault_factory()
        manager = self.__manager_factory(vault, spec.project_name, root)
        resolutions = dict[str, str](spec.credential_resolutions)
        comparison = manager.compare_project_credentials(incoming)
        unresolved = [
            key for key in comparison["conflicting"] if key not in resolutions
        ]
        if unresolved:
            logging.warning("Failed execute")
            raise scaffold.ScaffoldError(
                "credentials",
                "Choose local or stored for keys " + ", ".join(unresolved),
                "conflict",
            )
        ci_manager = None
        if spec.ci_store is not None:
            connection = self.__bootstrap.resolve(spec.ci_store.bootstrap)
            database = self.__database_factory(connection)
            if database is None:
                logging.warning("Failed execute")
                raise scaffold.ScaffoldError(
                    "credentials", "Selected CI store requires a connection"
                )
            ci_manager = self.__manager_factory(database, spec.project_name, root)
            assigned = entities.CredentialBundle.from_json_value(
                vault.get("devos:projects:" + spec.project_name) or {}, "project"
            )
            selected = {
                key: value
                for key, value in incoming.items()
                if key not in assigned.keys()
                or assigned.get(key) == value
                or resolutions.get(key) == "local"
            }
            ci_values = assigned.combine(
                entities.CredentialBundle.from_json_value(selected, "project")
            ).values()
            ci_comparison = ci_manager.compare_project_credentials(ci_values)
            unresolved_ci = [
                key
                for key in ci_comparison["conflicting"]
                if key not in spec.ci_store.resolutions
            ]
            if unresolved_ci:
                logging.warning("Failed execute")
                raise scaffold.ScaffoldError(
                    "credentials",
                    "Choose local or stored for CI keys " + ", ".join(unresolved_ci),
                    "conflict",
                )

        rendered = render_credential_files(spec, self.__files, local_values)
        validate_rendered(rendered)
        self.__files.preflight(root, rendered, spec.expected_files, self.__git)
        self.__files.path(root, ".env")
        self.__files.path(root, ".env.scaffold.tmp")
        original_environment = self.__files.read(root / ".env")
        if (root / ".env").exists() and spec.expected_files.get(
            ".env"
        ) != hashlib.sha256((root / ".env").read_bytes()).hexdigest():
            logging.warning("Failed execute")
            raise scaffold.ScaffoldError(
                "credentials",
                "Reinspect and approve the current .env before importing",
                "conflict",
            )
        if (
            self.__git.is_repository(root)
            and self.__git.run(
                root, ["ls-files", "--error-unmatch", ".env"], allow_failure=True
            ).returncode
            == 0
        ):
            logging.warning("Failed execute")
            raise scaffold.ScaffoldError(
                "credentials",
                "Remove the tracked .env from the index before credential setup",
                "conflict",
            )
        verified: list[str] = []
        try:
            manager.import_project_credentials(incoming, resolutions)
            verified.append("vault credential bundle verified")
            if ci_manager is not None and spec.ci_store is not None:
                ci_manager.import_project_credentials(
                    ci_values, dict[str, str](spec.ci_store.resolutions)
                )
                verified.append("CI credential bundle verified")
        except redis.exceptions.RedisError:
            error = scaffold.ScaffoldError(
                "credentials",
                "CI store import failed. Original .env retained",
                "service",
            )
            error.completed = verified.copy()
            logging.warning("Failed execute")
            raise error from None
        except (ValueError, RuntimeError):
            error = scaffold.ScaffoldError(
                "credentials",
                "Import or readback failed. Reinspect the bundle and registry. Original .env retained",
                "verification",
            )
            error.completed = verified.copy()
            logging.warning("Failed execute")
            raise error from None
        if self.__files.read(root / ".env") != original_environment:
            failure = scaffold.ScaffoldError(
                "credentials",
                ".env changed during import. Reinspect before rewriting it",
                "conflict",
            )
            failure.completed = verified
            logging.warning("Failed execute")
            raise failure
        try:
            root.mkdir(parents=True, exist_ok=True)
            written = self.__files.write(root, rendered)
            manager.get_credentials()
        except OSError:
            error = scaffold.ScaffoldError(
                "credential-files",
                "Credential file write failed. Reinspect files before retrying",
                "tooling",
            )
            error.completed = verified
            logging.warning("Failed execute")
            raise error from None
        logging.info("Completed execute")
        return scaffold.CredentialSetupResult(stores_verified=verified, files=written)


class ConfigureGitHubSecretsUseCase:
    """Configure only selected repository bootstrap secrets, with metadata verification."""

    def __init__(
        self,
        bootstrap: scaffold_adapters.BootstrapSourceAdapter,
        github: github_repository_client.GitHubRepositoryClient,
        vault_factory: typing.Callable[
            [], credential_ports.CredentialDatabasePort
        ] = credential_vault.get_local_vault,
    ):
        self.__bootstrap, self.__github = bootstrap, github
        self.__vault_factory = vault_factory

    def execute(self, spec: scaffold.ScaffoldSpec) -> scaffold.GitHubSecretSetupResult:
        logging.info("Starting execute")
        if spec.github is None:
            logging.warning("Failed execute")
            raise scaffold.ScaffoldError(
                "github-secrets", "Select the GitHub repository"
            )
        if spec.ci_store:
            values = self.__bootstrap.resolve(spec.ci_store.bootstrap)
        else:
            vault = self.__vault_factory()
            bundle = entities.CredentialBundle.from_json_value(
                vault.get("devos:projects:" + spec.project_name) or {}, "project"
            )
            values = {
                key: value if isinstance(value, str) else json.dumps(value)
                for key, value in bundle.values().items()
                if value is not None
            }
        url = values.get("devos_redis_url")
        host = (
            urllib.parse.urlparse(url).hostname
            if url
            else values.get("devos_redis_host")
        )
        if spec.ci_runner != "self-hosted" and host in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            logging.warning("Failed execute")
            raise scaffold.ScaffoldError(
                "github-secrets", "Hosted Actions cannot use a loopback Redis endpoint"
            )
        if spec.ci_store:
            values["devos_project_name"] = spec.project_name
        repository = f"{spec.github.owner}/{spec.github.repository}"
        completed: list[str] = []
        for name, value in sorted(values.items()):
            try:
                self.__github.set_actions_secret(
                    repository, name.upper(), pydantic.SecretStr(value)
                )
            except scaffold.ScaffoldError as error:
                error.completed.extend(completed)
                logging.warning("Failed execute")
                raise
            completed.append(name.upper())
        try:
            available = set(self.__github.secret_names(repository))
        except scaffold.ScaffoldError as error:
            error.completed.extend(completed)
            logging.warning("Failed execute")
            raise
        if not set(completed).issubset(available):
            failure = scaffold.ScaffoldError(
                "github-secrets",
                "Uploaded secret metadata was not found",
                "verification",
            )
            failure.completed = completed
            logging.warning("Failed execute")
            raise failure
        logging.info("Completed execute")
        return scaffold.GitHubSecretSetupResult(
            repository=repository, secret_names=completed
        )


class ScaffoldProjectUseCase:
    """Apply reviewed setup and stage exact paths while retaining user-owned design."""

    def __init__(
        self,
        credentials: ConfigureProjectCredentialsUseCase,
        secrets: ConfigureGitHubSecretsUseCase,
        bootstrap: scaffold_adapters.BootstrapSourceAdapter,
        github: github_repository_client.GitHubRepositoryClient,
        files: scaffold_adapters.ProjectFilesAdapter,
        git: scaffold_adapters.GitProjectAdapter,
        vault_factory: typing.Callable[
            [], credential_ports.CredentialDatabasePort
        ] = credential_vault.get_local_vault,
    ):
        self.__vault_factory = vault_factory
        self.__credentials, self.__secrets, self.__bootstrap = (
            credentials,
            secrets,
            bootstrap,
        )
        self.__github, self.__files, self.__git = github, files, git

    def execute(self, spec: scaffold.ScaffoldSpec) -> scaffold.ScaffoldResult:
        logging.info("Starting execute")
        root = spec.root()
        if spec.github is None:
            logging.warning("Failed execute")
            raise scaffold.ScaffoldError(
                "preflight",
                "Complete scaffolding requires a selected GitHub repository",
            )
        local_values: dict[str, str] = {}
        rendered = render_project_files(
            spec, self.__files, local_values, self.__vault_factory
        )
        validate_rendered(rendered)
        self.__files.preflight(root, rendered, spec.expected_files, self.__git)
        if self.__git.is_repository(root):
            # Check an existing remote before changing files or creating another repo.
            origin = self.__git.run(
                root, ["remote", "get-url", "origin"], allow_failure=True
            )
            repository = f"{spec.github.owner}/{spec.github.repository}"
            if origin.returncode == 0 and origin.stdout.strip().rstrip(
                "/"
            ).removesuffix(".git") not in {
                f"https://github.com/{repository}",
                f"git@github.com:{repository}",
            }:
                logging.warning("Failed execute")
                raise scaffold.ScaffoldError(
                    "preflight",
                    "Existing origin differs from the selected repository",
                    "conflict",
                )
        engine = spec.engine_root()
        guides = spec.agent_guides or (
            ["Python Development"]
            if spec.stack == scaffold.Stack.PYTHON
            else (
                ["Frontend Development"]
                if spec.stack == scaffold.Stack.REACT
                else [
                    "Python Development",
                    "Frontend Development",
                    "Backend Development",
                ]
            )
        )
        for guide in guides:
            if (
                guide
                not in {
                    "Python Development",
                    "Frontend Development",
                    "Backend Development",
                }
                or not (engine / "wiki/SOPs" / (guide + ".md")).is_file()
            ):
                logging.warning("Failed execute")
                raise scaffold.ScaffoldError(
                    "preflight", "Selected canonical engineering guide is unavailable"
                )
        sync_script = engine / "scripts/sync_project_agents.py"
        if not sync_script.is_file():
            logging.warning("Failed execute")
            raise scaffold.ScaffoldError(
                "preflight", "Project guide synchronisation tool is unavailable"
            )
        page = get_registered_project_page(
            engine, root, spec.project_name, self.__files
        )
        original_registration = self.__files.read(page)
        agents_content = (
            "\n\n".join(
                (engine / "wiki/SOPs" / (guide + ".md"))
                .read_text(encoding="utf-8")
                .strip()
                for guide in guides
            )
            + "\n"
        )
        self.__files.preflight(
            root, {"AGENTS.md": agents_content}, spec.expected_files, self.__git
        )
        for directory in [
            "scripts",
            *(
                ["notebooks/kpis", "notebooks/eda", "notebooks/experiments/src"]
                if spec.data_project
                else []
            ),
        ]:
            self.__files.path(root, directory)
        before_validation = self.__files.inventory(root)
        completed: list[str] = []
        try:
            credentials = self.__credentials.execute(spec)
            completed.extend(credentials.stores_verified)
            completed.append("project environment materialized")
            rendered[".env.example"] = self.__files.read(root / ".env.example")
            written = self.__files.write(root, rendered)
            (root / "scripts").mkdir(exist_ok=True)
            if spec.data_project:
                for directory in [
                    "notebooks/kpis",
                    "notebooks/eda",
                    "notebooks/experiments/src",
                ]:
                    (root / directory).mkdir(parents=True, exist_ok=True)
            completed.append("approved project files written")
            for command in spec.validation_commands:
                result = subprocess.run(
                    command, cwd=root, capture_output=True, text=True, check=False
                )
                if result.returncode:
                    logging.warning("Failed execute")
                    raise scaffold.ScaffoldError(
                        "validation",
                        "An agreed validation command failed. Review output locally",
                        "verification",
                    )
            completed.append("local validation completed")
            self.__git.initialise(root)
            repository = self.__github.ensure_repository(
                spec.github.owner, spec.github.repository, spec.description
            )
            completed.append("GitHub repository configured")
            self.__git.configure_origin(root, repository)
            secret_result = self.__secrets.execute(spec)
            completed.extend(
                "GitHub secret configured " + name
                for name in secret_result.secret_names
            )
            existing = self.__files.read(page)
            if existing != original_registration:
                logging.warning("Failed execute")
                raise scaffold.ScaffoldError(
                    "registration",
                    "Project registration changed during setup. Reinspect it",
                    "conflict",
                )
            if existing:
                frontmatter = re.match(
                    r"\A---\r?\n(.*?)\r?\n---\r?\n", existing, re.DOTALL
                )
                if frontmatter is None:
                    logging.warning("Failed execute")
                    raise scaffold.ScaffoldError(
                        "registration", "Project frontmatter was not closed"
                    )
                header = frontmatter.group(1).replace("\r\n", "\n")
                for key, value in [
                    ("repository_path", root.as_posix()),
                    ("agent_guides", "[" + ", ".join(guides) + "]"),
                    ("updated", datetime.date.today().isoformat()),
                ]:
                    line = key + ": " + value
                    header = (
                        re.sub(r"^" + key + r":.*$", line, header, flags=re.MULTILINE)
                        if re.search(r"^" + key + ":", header, re.MULTILINE)
                        else header + "\n" + line
                    )
                registration = (
                    "---\n" + header + "\n---\n" + existing[frontmatter.end() :]
                )
            else:
                today = datetime.date.today().isoformat()
                registration = (
                    f"---\ntype: project\ncreated: {today}\nupdated: {today}\ntags: [software]\n"
                    f"repository_path: {root.as_posix()}\nagent_guides: [{', '.join(guides)}]\n---\n\n"
                    f"{spec.description}\n\nProduct context lives in `{root.as_posix()}/docs/product/`.\n"
                )
            metadata = yaml.safe_load(registration.split("---\n", 2)[1])
            if metadata.get("repository_path") != root.as_posix():
                logging.warning("Failed execute")
                raise scaffold.ScaffoldError(
                    "registration",
                    "Repository path cannot be represented in registry frontmatter",
                )
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_bytes(registration.encode())
            result = subprocess.run(
                [sys.executable, str(sync_script), str(root)],
                cwd=engine,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode:
                logging.warning("Failed execute")
                raise scaffold.ScaffoldError(
                    "registration", "Project guide synchronisation failed", "tooling"
                )
            completed.append("project guide registered and generated")
            index = engine / "wiki/INDEX.md"
            if index.exists():
                index_content = self.__files.read(index)
                reference = f"[[Projects/{page.stem}]]"
                if reference not in index_content:
                    index.write_bytes(
                        (
                            index_content.rstrip()
                            + f"\n- {reference} - {spec.description}\n"
                        ).encode()
                    )
            staged_paths = sorted(set(written + ["AGENTS.md"] + credentials.files))
            after_validation = self.__files.inventory(root)
            for lock in [
                "uv.lock",
                "package-lock.json",
                "pnpm-lock.yaml",
                spec.frontend_path + "/package-lock.json",
                spec.frontend_path + "/pnpm-lock.yaml",
            ]:
                if lock in after_validation and after_validation.get(
                    lock
                ) != before_validation.get(lock):
                    self.__git.validate_target(
                        root,
                        lock,
                        self.__files.read(root / lock),
                        before_validation.get(lock),
                    )
                    staged_paths.append(lock)
            staged = self.__git.stage(root, staged_paths)
            completed.append("scaffold files staged")
            logging.info("Completed execute")
            return scaffold.ScaffoldResult(
                project_path=str(root),
                files=staged_paths,
                staged_files=staged,
                completed=completed,
            )
        except scaffold.ScaffoldError as error:
            error.completed = completed + error.completed
            logging.warning("Failed execute")
            raise
        except OSError:
            failure = scaffold.ScaffoldError(
                "scaffold-files",
                "File or process operation failed. Reinspect partial changes",
                "tooling",
            )
            failure.completed = completed
            logging.warning("Failed execute")
            raise failure from None
        logging.info("Completed execute")
