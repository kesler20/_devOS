"""Inspect, configure, and stage an agreed project without publishing code."""

from __future__ import annotations

import ast
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import typing
import urllib.parse
from datetime import date

import dotenv
import pydantic
import redis.exceptions
import tomlkit
import yaml

from devOS.domain import entities
from devOS.domain.scaffold import (
    CredentialSetupResult, GitHubSecretSetupResult, ScaffoldError,
    ScaffoldInspection, ScaffoldResult, ScaffoldSpec, Stack,
)
from devOS.infrastructure.adapters import RedisNoSQLAdapter
from devOS.infrastructure.github_repository_client import GitHubRepositoryClient
from devOS.infrastructure.scaffold_adapters import (
    BOOTSTRAP_NAMES, BootstrapSourceAdapter, DevOSSecretClient,
    GitProjectAdapter, ProjectFilesAdapter,
)
from devOS.use_cases.manage_credentials import ManageCredentialsUseCase
import devOS.use_cases.manage_credentials as manage_credentials


RUNTIME_DEPENDENCIES = ["redis>=6.4.0", "python-dotenv>=1.1.0", "pydantic>=2.0", "pydantic-settings>=2.0"]


def validate_config_loading(content: str) -> None:
    """Require executable credential loading before typed settings construction."""
    tree = ast.parse(content)
    calls = [node for node in tree.body if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
             and ast.unparse(node.value) == "credentials.LoadCredentialsUseCase.from_environment().execute()"]
    if not calls:
        raise ScaffoldError("preflight", "Config must execute credential loading at module scope before constructing settings")
    settings = {node.name for node in tree.body if isinstance(node, ast.ClassDef)
                and any(ast.unparse(base).endswith("BaseSettings") for base in node.bases)}
    if any(node.lineno < calls[0].lineno and isinstance(node.func, ast.Name) and node.func.id in settings
           for node in ast.walk(tree) if isinstance(node, ast.Call)):
        raise ScaffoldError("preflight", "Config constructs settings before loading credentials")


def environment_values(root: pathlib.Path) -> dict[str, entities.JSONValue]:
    """Keep literal dotenv values and exclude the reserved bootstrap namespace."""
    path = root / ".env"
    return {key: value for key, value in dotenv.dotenv_values(path, interpolate=False).items()
            if value is not None and not entities.is_bootstrap_variable(key)} if path.is_file() else {}


def python_manifest(spec: ScaffoldSpec, files: ProjectFilesAdapter) -> str:
    """Preserve TOML formatting while updating description and runtime dependencies."""
    current = files.read(files.path(spec.root(), "pyproject.toml"))
    document = tomlkit.parse(current) if current else tomlkit.document()
    if "project" not in document:
        if current:
            raise ScaffoldError("preflight", "Existing package metadata is not PEP 621. Supply an agreed targeted migration")
        document["project"] = {"name": spec.project_name, "version": "0.1.0",
                               "requires-python": ">=" + spec.python_version, "readme": "README.md"}
        document["build-system"] = {"requires": ["uv_build>=0.9.0,<0.10.0"], "build-backend": "uv_build"}
        document["tool"] = {"uv": {"build-backend": {"module-name": spec.package()}}}
    project = typing.cast(typing.Any, document["project"])
    project["description"] = spec.description
    dependencies = project.get("dependencies", [])
    names = {re.split(r"[\[<>=!~ ;]", item.strip())[0].lower().replace("_", "-") for item in dependencies}
    for dependency in RUNTIME_DEPENDENCIES:
        if re.split(r"[<>=]", dependency)[0] not in names:
            dependencies.append(dependency)
    project["dependencies"] = dependencies
    optional = project.get("optional-dependencies", {})
    test_dependencies = optional.get("dev", [])
    if not any(re.split(r"[\[<>=!~ ;]", item)[0].lower() == "pytest" for item in test_dependencies):
        test_dependencies.append("pytest>=8.0")
    optional["dev"] = test_dependencies
    project["optional-dependencies"] = optional
    return tomlkit.dumps(document)


def credential_files(spec: ScaffoldSpec, files: ProjectFilesAdapter,
                     bootstrap: dict[str, str]) -> dict[str, str]:
    """Render bootstrap documentation and project-specific Python configuration."""
    root = spec.root()
    ignored = files.read(files.path(root, ".gitignore"))
    for pattern in [".env", ".env.*", "!.env.example", ".devos_backup/", ".venv/", "__pycache__/", "node_modules/"]:
        if pattern not in ignored.splitlines():
            ignored = ignored.rstrip("\r\n") + ("\n" if ignored else "") + pattern + "\n"
    rendered = {".gitignore": ignored,
                ".env.example": "".join(f"{key}=\n" for key in sorted([*bootstrap, "devos_project_name"]))}
    if spec.has_python():
        directory = spec.config_directory()
        files.path(root, directory + "/configs.py")
        current = files.read(files.path(root, directory + "/configs.py"))
        if current and spec.config_content is None:
            if "credentials.LoadCredentialsUseCase.from_environment().execute()" not in current:
                raise ScaffoldError("preflight", "Provide reviewed config_content integrating the existing settings file")
            config = current
        elif spec.config_content is not None:
            config = spec.config_content
            if "credentials.LoadCredentialsUseCase.from_environment().execute()" not in config:
                raise ScaffoldError("preflight", "Config must load devOS credentials before constructing settings")
        else:
            depth = len(pathlib.PurePosixPath(directory).parts)
            config = (
                '"""Project settings loaded from the devOS project bundle."""\n\n'
                "from pathlib import Path\nimport dotenv\nimport pydantic_settings\nfrom . import credentials\n\n"
                f"dotenv.load_dotenv(Path(__file__).resolve().parents[{depth}] / '.env')\n"
                "credentials.LoadCredentialsUseCase.from_environment().execute()\n\n\n"
                "class EnvironmentVariables(pydantic_settings.BaseSettings):\n"
                '    """Typed project settings."""\n\n'
                "    model_config = pydantic_settings.SettingsConfigDict(extra='ignore')\n\n\n"
                "environment_variables = EnvironmentVariables()\n"
            )
        rendered[directory + "/configs.py"] = config
        validate_config_loading(config)
        bundle = spec.engine_root() / "wiki/Snippets/python/config"
        rendered[directory + "/credentials.py"] = (bundle / "credentials.py").read_bytes().decode("utf-8")
        import_parts = pathlib.PurePosixPath(directory).parts
        if import_parts and import_parts[0] == "src":
            import_parts = import_parts[1:]
        rendered.update(manage_credentials.configuration_bundle_support(bundle, ".".join(import_parts)))
        parts = pathlib.PurePosixPath(directory).parts
        for length in range(1, len(parts) + 1):
            prefix = pathlib.PurePosixPath(*parts[:length]).as_posix()
            if prefix == "src":
                continue
            name = prefix + "/__init__.py"
            if not files.path(root, name).exists():
                rendered[name] = ""
        rendered["pyproject.toml"] = python_manifest(spec, files)
    return rendered


def project_files(spec: ScaffoldSpec, files: ProjectFilesAdapter,
                  bootstrap: dict[str, str]) -> dict[str, str]:
    """Render approved prose plus deterministic package and setup metadata."""
    if not spec.prd.strip() or not spec.decision_log.strip() or not spec.readme_body.strip():
        raise ScaffoldError("preflight", "Provide the agreed PRD, decision log, and detailed README body")
    root = spec.root()
    rendered = credential_files(spec, files, bootstrap)
    rendered.update({"README.md": f"# {spec.project_name}\n\n{spec.description}\n\n{spec.readme_body.rstrip()}\n",
                     "docs/product/prd.md": spec.prd, "docs/product/decision-log.md": spec.decision_log})
    for directory in ["scripts", *(["notebooks/kpis", "notebooks/eda", "notebooks/experiments/src"] if spec.data_project else [])]:
        placeholder = directory + "/.gitkeep"
        if not files.path(root, placeholder).exists():
            rendered[placeholder] = ""
    design_path = files.path(root, "docs/product/design.md")
    if not design_path.exists():
        rendered["docs/product/design.md"] = ""
    if spec.source_tables is not None:
        original = files.read(design_path)
        newline = "\r\n" if "\r\n" in original else "\n"
        inventory = "## Source Tables" + newline + newline + spec.source_tables.rstrip() + newline
        match = re.search(r"^## Source Tables\r?\n.*?(?=^## |\Z)", original, re.MULTILINE | re.DOTALL)
        rendered["docs/product/design.md"] = (
            original[:match.start()] + inventory + original[match.end():]
            if match else original + (newline if original and not original.endswith(newline) else "") + inventory
        )
    if spec.stack != Stack.PYTHON:
        name = "package.json" if spec.stack == Stack.REACT else spec.frontend_path.rstrip("/") + "/package.json"
        existing = files.read(files.path(root, name))
        package = json.loads(existing) if existing else {"name": spec.project_name.lower(), "version": "0.1.0", "private": True}
        package["description"] = spec.description
        if not existing:
            package["dependencies"] = {"react": "^19.0.0", "react-dom": "^19.0.0"}
        rendered[name] = json.dumps(package, indent=2, ensure_ascii=False) + "\n"
    reserved = {name.casefold() for name in rendered} | {".env", "docs/product/design.md"}
    for change in spec.files:
        name = pathlib.PurePosixPath(change.path).as_posix()
        if name.casefold() in reserved or pathlib.PurePosixPath(name).name.lower().startswith(".env") or any(part.lower() in {".git", ".devos_backup"} for part in pathlib.PurePosixPath(name).parts):
            raise ScaffoldError("preflight", "Use dedicated fields for generated metadata, design, and environment files")
        if name.casefold() in {path.casefold() for path in rendered}:
            raise ScaffoldError("preflight", "Duplicate approved file change")
        rendered[name] = change.content
    ci_path = files.path(root, ".github/workflows/ci.yml")
    if ".github/workflows/ci.yml" not in rendered and not ci_path.exists():
        python_steps = (
            f"      - uses: actions/setup-python@v5\n        with:\n          python-version: '{spec.python_version}'\n"
            "      - run: python -m pip install -e .\n"
            f"      - run: python -m compileall -q {spec.config_directory()}\n"
        ) if spec.has_python() else ""
        if spec.has_python() and ((root / "tests").is_dir() or any(name.startswith("tests/") for name in rendered)):
            python_steps += "      - run: python -m pip install pytest\n      - run: python -m pytest\n"
        frontend_steps = ""
        if spec.stack != Stack.PYTHON:
            location = "." if spec.stack == Stack.REACT else spec.frontend_path
            package = json.loads(rendered["package.json" if spec.stack == Stack.REACT else location + "/package.json"])
            manager = "pnpm" if spec.package_manager == "pnpm" else "npm"
            frontend_steps = "      - uses: actions/setup-node@v4\n        with:\n          node-version: '22'\n"
            if manager == "pnpm":
                frontend_steps += "      - run: corepack enable\n"
            frontend_steps += f"      - run: {manager} install\n        working-directory: {location}\n"
            for check in ("lint", "typecheck", "test", "build"):
                if check in package.get("scripts", {}):
                    frontend_steps += f"      - run: {manager} run {check}\n        working-directory: {location}\n"
        # Secret keys depend on the separately selected CI connection, not local bootstrap.
        ci_keys = set(spec.ci_store.bootstrap.secret_keys)
        if spec.ci_store.bootstrap.env_file:
            from devOS.infrastructure.scaffold_adapters import read_bootstrap_file
            ci_keys.update(read_bootstrap_file(spec.ci_store.bootstrap.env_file))
        environment = "    env:\n" + "".join(f"      {key}: ${{{{ secrets.{key.upper()} }}}}\n" for key in sorted([*ci_keys, "devos_project_name"])) if spec.has_python() else ""
        rendered[".github/workflows/ci.yml"] = (
            "name: CI\non: [push, pull_request]\npermissions:\n  contents: read\njobs:\n"
            "  checks:\n    runs-on: " + json.dumps(spec.ci_runner) + "\n" + environment + "    steps:\n      - uses: actions/checkout@v4\n" + python_steps + frontend_steps
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
                if name.startswith(".github/workflows/") and (not isinstance(payload, dict) or not payload.get("jobs")):
                    raise ScaffoldError("preflight", f"Workflow must define jobs at {name}")
        except (SyntaxError, ValueError, yaml.YAMLError, tomlkit.exceptions.ParseError):
            raise ScaffoldError("preflight", f"Generated file has invalid syntax at {name}") from None


def registered_project_page(engine: pathlib.Path, root: pathlib.Path, project_name: str,
                            files: ProjectFilesAdapter) -> pathlib.Path:
    """Find the owning registry page by repository path, irrespective of its title."""
    matches: list[pathlib.Path] = []
    proposed = engine / "wiki/Projects" / (project_name + ".md")
    for page in (engine / "wiki/Projects").glob("*.md"):
        content = files.read(page)
        frontmatter = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", content, re.DOTALL)
        if frontmatter is None:
            raise ScaffoldError("registration", "A project registry page has invalid frontmatter")
        try:
            metadata = yaml.safe_load(frontmatter.group(1))
        except yaml.YAMLError:
            raise ScaffoldError("registration", "A project registry page has invalid YAML") from None
        registered_path = metadata.get("repository_path") if isinstance(metadata, dict) else None
        if registered_path and pathlib.Path(str(registered_path)).expanduser().resolve() == root:
            matches.append(page)
        elif page == proposed and registered_path:
            raise ScaffoldError("registration", "The project title registers a different repository", "conflict")
    if len(matches) > 1:
        raise ScaffoldError("registration", "More than one project page registers this repository", "conflict")
    return matches[0] if matches else proposed


class InspectProjectScaffoldUseCase:
    """Inspect public files and local credential key differences without mutation."""

    def __init__(self, files: ProjectFilesAdapter, git: GitProjectAdapter,
                 database_factory: typing.Callable[..., typing.Any] = RedisNoSQLAdapter.from_environment):
        self.__files, self.__git, self.__database_factory = files, git, database_factory

    def execute(self, request: pathlib.Path) -> ScaffoldInspection:
        root = request.expanduser().resolve()
        values = dotenv.dotenv_values(root / ".env", interpolate=False) if (root / ".env").is_file() else {}
        configured = {key.lower(): value for key, value in values.items() if key.lower() in BOOTSTRAP_NAMES and value is not None}
        git_repository = self.__git.is_repository(root)
        result = ScaffoldInspection(project_path=str(root), exists=root.exists(), git_repository=git_repository,
                                    staged_files=self.__git.staged(root) if git_repository else [],
                                    environment_keys=sorted(key for key in values if not entities.is_bootstrap_variable(key)),
                                    bootstrap_keys=sorted(configured), files=self.__files.inventory(root))
        result.setup_requirements = [name for name in ["docs/product/prd.md", "docs/product/decision-log.md", "docs/product/design.md", "README.md", ".env.example", ".gitignore"] if not (root / name).is_file()]
        if not git_repository:
            result.setup_requirements.append("Git repository")
        if not configured:
            result.setup_requirements.append("local Redis bootstrap")
        if configured.get("devos_redis_url") or configured.get("devos_redis_host"):
            try:
                database = self.__database_factory(configured)
            except ValueError:
                raise ScaffoldError("bootstrap", "Local connection settings are invalid") from None
            project_name = values.get("devos_project_name") or root.name
            manager = ManageCredentialsUseCase(database, project_name, root)
            try:
                result.credential_comparison = manager.compare_project_credentials(environment_values(root))
            except redis.exceptions.RedisError:
                raise ScaffoldError("inspect", "Local Redis could not be read", "service") from None
            result.store_state = "read"
        return result


class ConfigureProjectCredentialsUseCase:
    """Verify selected store imports before replacing the local environment file."""

    def __init__(self, bootstrap: BootstrapSourceAdapter, files: ProjectFilesAdapter, git: GitProjectAdapter,
                 database_factory: typing.Callable[..., typing.Any] = RedisNoSQLAdapter.from_environment):
        self.__bootstrap, self.__files, self.__git = bootstrap, files, git
        self.__database_factory = database_factory

    def execute(self, spec: ScaffoldSpec) -> CredentialSetupResult:
        root = spec.root()
        incoming = environment_values(root)
        local_values = self.__bootstrap.resolve(spec.local_store.bootstrap)
        ci_values = self.__bootstrap.resolve(spec.ci_store.bootstrap)
        selections = [("local", local_values, spec.local_store), ("ci", ci_values, spec.ci_store)]
        managers: list[tuple[str, ManageCredentialsUseCase, dict[str, str]]] = []
        for name, values, selection in selections:
            try:
                database = self.__database_factory(values)
            except ValueError:
                raise ScaffoldError("bootstrap", f"Connection settings are invalid for {name}") from None
            if database is None:
                raise ScaffoldError("credentials", f"No database configured for {name}")
            manager = ManageCredentialsUseCase(database, spec.project_name, root)
            try:
                comparison = manager.compare_project_credentials(incoming)
            except redis.exceptions.RedisError:
                raise ScaffoldError("credentials", f"Could not read {name} Redis", "service") from None
            unresolved = [key for key in comparison["conflicting"] if key not in selection.resolutions]
            if unresolved:
                raise ScaffoldError("credentials", f"Choose local or stored in {name} for keys {', '.join(unresolved)}", "conflict")
            managers.append((name, manager, dict[str, str](selection.resolutions)))
        if local_values == ci_values and spec.local_store.resolutions != spec.ci_store.resolutions:
            raise ScaffoldError("credentials", "The same store cannot have different conflict resolutions", "conflict")
        rendered = credential_files(spec, self.__files, local_values)
        validate_rendered(rendered)
        self.__files.preflight(root, rendered, spec.expected_files, self.__git)
        self.__files.path(root, ".env")
        self.__files.path(root, ".env.scaffold.tmp")
        original_environment = self.__files.read(root / ".env")
        if (root / ".env").exists() and spec.expected_files.get(".env") != hashlib.sha256((root / ".env").read_bytes()).hexdigest():
            raise ScaffoldError("credentials", "Reinspect and approve the current .env before importing", "conflict")
        if self.__git.is_repository(root) and self.__git.run(root, ["ls-files", "--error-unmatch", ".env"], allow_failure=True).returncode == 0:
            raise ScaffoldError("credentials", "Remove the tracked .env from the index before credential setup", "conflict")
        verified: list[str] = []
        for name, manager, resolutions in managers:
            try:
                manager.import_project_credentials(incoming, resolutions)
            except redis.exceptions.RedisError:
                error = ScaffoldError("credentials", f"Import into {name} Redis failed. Original .env retained", "service")
                error.completed = verified.copy()
                raise error from None
            except (ValueError, RuntimeError):
                error = ScaffoldError("credentials", f"Import or readback failed in {name}. Reinspect its bundle and registry. Original .env retained", "verification")
                error.completed = verified.copy()
                raise error from None
            verified.append(name + " credential bundle verified")
        if self.__files.read(root / ".env") != original_environment:
            failure = ScaffoldError("credentials", ".env changed during import. Reinspect before rewriting it", "conflict")
            failure.completed = verified
            raise failure
        try:
            root.mkdir(parents=True, exist_ok=True)
            written = self.__files.write(root, rendered)
            self.__files.write_environment(root, local_values, spec.project_name)
        except OSError:
            error = ScaffoldError("credential-files", "Credential file write failed. Reinspect files before retrying", "tooling")
            error.completed = verified
            raise error from None
        return CredentialSetupResult(stores_verified=verified, files=written)


class ConfigureGitHubSecretsUseCase:
    """Configure only selected repository bootstrap secrets, with metadata verification."""

    def __init__(self, bootstrap: BootstrapSourceAdapter, github: GitHubRepositoryClient):
        self.__bootstrap, self.__github = bootstrap, github

    def execute(self, spec: ScaffoldSpec) -> GitHubSecretSetupResult:
        if spec.github is None:
            raise ScaffoldError("github-secrets", "Select the GitHub repository")
        values = self.__bootstrap.resolve(spec.ci_store.bootstrap)
        url = values.get("devos_redis_url")
        host = urllib.parse.urlparse(url).hostname if url else values.get("devos_redis_host")
        if spec.ci_runner != "self-hosted" and host in {"localhost", "127.0.0.1", "::1"}:
            raise ScaffoldError("github-secrets", "Hosted Actions cannot use a loopback Redis endpoint")
        values["devos_project_name"] = spec.project_name
        repository = f"{spec.github.owner}/{spec.github.repository}"
        completed: list[str] = []
        for name, value in sorted(values.items()):
            try:
                self.__github.set_actions_secret(repository, name.upper(), pydantic.SecretStr(value))
            except ScaffoldError as error:
                error.completed.extend(completed)
                raise
            completed.append(name.upper())
        try:
            available = set(self.__github.secret_names(repository))
        except ScaffoldError as error:
            error.completed.extend(completed)
            raise
        if not set(completed).issubset(available):
            failure = ScaffoldError("github-secrets", "Uploaded secret metadata was not found", "verification")
            failure.completed = completed
            raise failure
        return GitHubSecretSetupResult(repository=repository, secret_names=completed)


class ScaffoldProjectUseCase:
    """Apply reviewed setup and stage exact paths while retaining user-owned design."""

    def __init__(self, credentials: ConfigureProjectCredentialsUseCase, secrets: ConfigureGitHubSecretsUseCase,
                 bootstrap: BootstrapSourceAdapter, github: GitHubRepositoryClient,
                 files: ProjectFilesAdapter, git: GitProjectAdapter):
        self.__credentials, self.__secrets, self.__bootstrap = credentials, secrets, bootstrap
        self.__github, self.__files, self.__git = github, files, git

    def execute(self, spec: ScaffoldSpec) -> ScaffoldResult:
        root = spec.root()
        if spec.github is None:
            raise ScaffoldError("preflight", "Complete scaffolding requires a selected GitHub repository")
        local_values = self.__bootstrap.resolve(spec.local_store.bootstrap)
        rendered = project_files(spec, self.__files, local_values)
        validate_rendered(rendered)
        self.__files.preflight(root, rendered, spec.expected_files, self.__git)
        if self.__git.is_repository(root):
            # Check an existing remote before changing files or creating another repo.
            origin = self.__git.run(root, ["remote", "get-url", "origin"], allow_failure=True)
            repository = f"{spec.github.owner}/{spec.github.repository}"
            if origin.returncode == 0 and origin.stdout.strip().rstrip("/").removesuffix(".git") not in {
                f"https://github.com/{repository}", f"git@github.com:{repository}"
            }:
                raise ScaffoldError("preflight", "Existing origin differs from the selected repository", "conflict")
        engine = spec.engine_root()
        guides = spec.agent_guides or (["Python Development"] if spec.stack == Stack.PYTHON else
                                     ["Frontend Development"] if spec.stack == Stack.REACT else
                                     ["Python Development", "Frontend Development", "Backend Development"])
        for guide in guides:
            if guide not in {"Python Development", "Frontend Development", "Backend Development"} or not (engine / "wiki/SOPs" / (guide + ".md")).is_file():
                raise ScaffoldError("preflight", "Selected canonical engineering guide is unavailable")
        sync_script = engine / "scripts/sync_project_agents.py"
        if not sync_script.is_file():
            raise ScaffoldError("preflight", "Project guide synchronisation tool is unavailable")
        page = registered_project_page(engine, root, spec.project_name, self.__files)
        original_registration = self.__files.read(page)
        agents_content = "\n\n".join((engine / "wiki/SOPs" / (guide + ".md")).read_text(encoding="utf-8").strip() for guide in guides) + "\n"
        self.__files.preflight(root, {"AGENTS.md": agents_content}, spec.expected_files, self.__git)
        for directory in ["scripts", *(["notebooks/kpis", "notebooks/eda", "notebooks/experiments/src"] if spec.data_project else [])]:
            self.__files.path(root, directory)
        before_validation = self.__files.inventory(root)
        completed: list[str] = []
        try:
            credentials = self.__credentials.execute(spec)
            completed.extend(credentials.stores_verified)
            completed.append("bootstrap environment written")
            written = self.__files.write(root, rendered)
            (root / "scripts").mkdir(exist_ok=True)
            if spec.data_project:
                for directory in ["notebooks/kpis", "notebooks/eda", "notebooks/experiments/src"]:
                    (root / directory).mkdir(parents=True, exist_ok=True)
            completed.append("approved project files written")
            for command in spec.validation_commands:
                result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
                if result.returncode:
                    raise ScaffoldError("validation", "An agreed validation command failed. Review output locally", "verification")
            completed.append("local validation completed")
            self.__git.initialise(root)
            repository = self.__github.ensure_repository(spec.github.owner, spec.github.repository, spec.description)
            completed.append("GitHub repository configured")
            self.__git.configure_origin(root, repository)
            secret_result = self.__secrets.execute(spec)
            completed.extend("GitHub secret configured " + name for name in secret_result.secret_names)
            existing = self.__files.read(page)
            if existing != original_registration:
                raise ScaffoldError("registration", "Project registration changed during setup. Reinspect it", "conflict")
            if existing:
                frontmatter = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", existing, re.DOTALL)
                if frontmatter is None:
                    raise ScaffoldError("registration", "Project frontmatter was not closed")
                header = frontmatter.group(1).replace("\r\n", "\n")
                for key, value in [("repository_path", root.as_posix()), ("agent_guides", "[" + ", ".join(guides) + "]"), ("updated", date.today().isoformat())]:
                    line = key + ": " + value
                    header = re.sub(r"^" + key + r":.*$", line, header, flags=re.MULTILINE) if re.search(r"^" + key + ":", header, re.MULTILINE) else header + "\n" + line
                registration = "---\n" + header + "\n---\n" + existing[frontmatter.end():]
            else:
                today = date.today().isoformat()
                registration = (f"---\ntype: project\ncreated: {today}\nupdated: {today}\ntags: [software]\n"
                                f"repository_path: {root.as_posix()}\nagent_guides: [{', '.join(guides)}]\n---\n\n"
                                f"{spec.description}\n\nProduct context lives in `{root.as_posix()}/docs/product/`.\n")
            metadata = yaml.safe_load(registration.split("---\n", 2)[1])
            if metadata.get("repository_path") != root.as_posix():
                raise ScaffoldError("registration", "Repository path cannot be represented in registry frontmatter")
            page.parent.mkdir(parents=True, exist_ok=True)
            page.write_bytes(registration.encode())
            result = subprocess.run([sys.executable, str(sync_script), str(root)], cwd=engine, capture_output=True, text=True, check=False)
            if result.returncode:
                raise ScaffoldError("registration", "Project guide synchronisation failed", "tooling")
            completed.append("project guide registered and generated")
            index = engine / "wiki/INDEX.md"
            if index.exists():
                index_content = self.__files.read(index)
                reference = f"[[Projects/{page.stem}]]"
                if reference not in index_content:
                    index.write_bytes((index_content.rstrip() + f"\n- {reference} - {spec.description}\n").encode())
            staged_paths = sorted(set(written + ["AGENTS.md"] + credentials.files))
            after_validation = self.__files.inventory(root)
            for lock in ["uv.lock", "package-lock.json", "pnpm-lock.yaml", spec.frontend_path + "/package-lock.json", spec.frontend_path + "/pnpm-lock.yaml"]:
                if lock in after_validation and after_validation.get(lock) != before_validation.get(lock):
                    self.__git.validate_target(root, lock, self.__files.read(root / lock), before_validation.get(lock))
                    staged_paths.append(lock)
            staged = self.__git.stage(root, staged_paths)
            completed.append("scaffold files staged")
            return ScaffoldResult(project_path=str(root), files=staged_paths, staged_files=staged, completed=completed)
        except ScaffoldError as error:
            error.completed = completed + error.completed
            raise
        except OSError:
            failure = ScaffoldError("scaffold-files", "File or process operation failed. Reinspect partial changes", "tooling")
            failure.completed = completed
            raise failure from None
