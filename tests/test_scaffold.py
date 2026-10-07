from __future__ import annotations

import base64
import json
import importlib
import os
import pathlib
import subprocess
import sys
from unittest.mock import Mock

import dotenv
import nacl.public
import pydantic
import pytest
import redis.exceptions

from devOS import scaffold_cli
from devOS.domain.scaffold import ScaffoldError, ScaffoldSpec
from devOS.infrastructure.github_repository_client import GitHubRepositoryClient
from devOS.infrastructure.scaffold_adapters import BootstrapSourceAdapter, DevOSSecretClient, GitProjectAdapter, ProjectFilesAdapter
from devOS.use_cases.scaffold_project import (
    ConfigureGitHubSecretsUseCase, ConfigureProjectCredentialsUseCase,
    InspectProjectScaffoldUseCase, ScaffoldProjectUseCase, project_files,
)
from test_manage_credentials import FakeNoSQLDatabase


class Store(FakeNoSQLDatabase):
    def __init__(self, fail=False):
        super().__init__()
        self.writes = []
        self.fail = fail

    def put(self, key, value):
        self.writes.append(key)
        if self.fail and key.startswith("devos:projects:"):
            return True  # Simulate a success acknowledgement without persistence.
        return super().put(key, value)


class GitHub:
    def __init__(self):
        self.names = []
        self.repositories = []

    def ensure_repository(self, owner, name, description):
        self.repositories.append((owner, name, description))
        return owner + "/" + name

    def set_actions_secret(self, repository, name, value):
        assert isinstance(value, pydantic.SecretStr)
        self.names.append(name)

    def secret_names(self, repository):
        return self.names


@pytest.fixture
def setup(tmp_path):
    protocol = tmp_path / "protocol"
    protocol.mkdir()
    local = tmp_path / "local.env"
    ci = tmp_path / "ci.env"
    local.write_text("devos_redis_host=local.test\ndevos_redis_password=bootstrap-local\n")
    ci.write_text("devos_redis_url=rediss://ci.test\n")
    engine = protocol / "automation_engine"
    (engine / "wiki/SOPs").mkdir(parents=True)
    (engine / "wiki/Projects").mkdir()
    (engine / "wiki/INDEX.md").write_text("# Index\n")
    (engine / "scripts").mkdir()
    import config
    import shutil
    shutil.copytree(pathlib.Path(config.__file__).parent, engine / "wiki/Snippets/python/config",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # Fake the existing synchronisation-tool boundary without a host checkout dependency.
    (engine / "scripts/sync_project_agents.py").write_text(
        "import pathlib, sys, yaml\n"
        "root = pathlib.Path(sys.argv[1])\n"
        "engine = pathlib.Path(__file__).parents[1]\n"
        "page = next(page for page in (engine / 'wiki/Projects').glob('*.md') if pathlib.Path(yaml.safe_load(page.read_text().split('---')[1]).get('repository_path', '.')).resolve() == root.resolve())\n"
        "metadata = yaml.safe_load(page.read_text().split('---')[1])\n"
        "content = '\\n\\n'.join((engine / 'wiki/SOPs' / (guide + '.md')).read_text().strip() for guide in metadata['agent_guides']) + '\\n'\n"
        "(root / 'AGENTS.md').write_text(content)\n"
    )
    for guide in ["Python Development", "Frontend Development", "Backend Development"]:
        (engine / "wiki/SOPs" / (guide + ".md")).write_text("# " + guide + "\n\nProject contract.\n")
    spec = ScaffoldSpec(protocol_root=protocol, project_name="sample", description="Inform a useful decision.",
                        stack="python", local_store={"bootstrap": {"env_file": local}},
                        ci_store={"bootstrap": {"env_file": ci}}, github={"owner": "kesler", "repository": "sample"},
                        data_project=True, prd="# Product\n", decision_log="# Requirements\n\n# Specifications\n",
                        readme_body="## Install\n\nRun `uv sync`.\n", validation_commands=[[sys.executable, "-m", "compileall", "-q", "src"]])
    files, git = ProjectFilesAdapter(), GitProjectAdapter()
    bootstrap = BootstrapSourceAdapter(Mock())
    stores = {"local.test": Store(), "rediss://ci.test": Store()}
    credentials = ConfigureProjectCredentialsUseCase(bootstrap, files, git, lambda values: stores[values.get("devos_redis_host") or values["devos_redis_url"]])
    github = GitHub()
    secrets = ConfigureGitHubSecretsUseCase(bootstrap, github)
    complete = ScaffoldProjectUseCase(credentials, secrets, bootstrap, github, files, git)
    return spec, stores, files, git, credentials, secrets, complete, github


def approve(spec, files):
    spec.expected_files = files.inventory(spec.root())


def seed_environment(spec, files, content='TOKEN="literal ${TOKEN} # value"\nEMPTY=\n'):
    spec.root().mkdir()
    (spec.root() / ".env").write_text(content)
    approve(spec, files)


def test_complete_new_project_and_rerun(setup):
    spec, stores, files, git, _, _, complete, github = setup
    result = complete.execute(spec)
    root = spec.root()
    assert git.is_repository(root)
    assert git.run(root, ["rev-parse", "HEAD"], allow_failure=True).returncode != 0
    assert (root / "src/sample/infrastructure/credentials.py").read_bytes() == (spec.engine_root() / "wiki/Snippets/python/config/credentials.py").read_bytes()
    assert (root / "docs/product/design.md").read_bytes() == b""
    test_environment = os.environ.copy()
    test_environment["PYTHONPATH"] = str(root / "src")
    result_tests = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/snippets/config"],
                                  cwd=root, env=test_environment, capture_output=True, text=True)
    assert result_tests.returncode == 0, result_tests.stdout + result_tests.stderr
    assert "pytest>=8.0" in (root / "pyproject.toml").read_text()
    assert "notebooks/experiments/src/.gitkeep" in result.staged_files
    assert "scripts/.gitkeep" in result.staged_files
    assert ".env" not in git.staged(root)
    assert "DEVOS_REDIS_URL" in github.names
    workflow = (root / ".github/workflows/ci.yml").read_text()
    assert "python -m pytest" in workflow
    assert "devos_redis_url: ${{ secrets.DEVOS_REDIS_URL }}" in workflow
    assert "bootstrap-local" not in result.model_dump_json()
    approve(spec, files)
    assert set(complete.execute(spec).staged_files).issubset(result.staged_files)
    assert git.staged(root) == result.staged_files
    assert len(stores["local.test"].writes) == 2  # Identical reruns verify without writes.


def test_both_store_import_preserves_literals_and_value_free_files(setup):
    spec, stores, files, _, credentials, *_ = setup
    seed_environment(spec, files)
    result = credentials.execute(spec)
    for store in stores.values():
        assert store.values["devos:projects:sample"] == {"TOKEN": "literal ${TOKEN} # value", "EMPTY": ""}
        assert store.values["devos:projects"] == ["sample"]
    environment = dotenv.dotenv_values(spec.root() / ".env", interpolate=False)
    assert environment == {"devos_redis_host": "local.test", "devos_redis_password": "bootstrap-local", "devos_project_name": "sample"}
    assert "TOKEN" not in (spec.root() / ".env.example").read_text()
    assert "literal" not in result.model_dump_json()


def test_conflicts_preflight_both_stores_and_independent_resolution(setup):
    spec, stores, files, _, credentials, *_ = setup
    seed_environment(spec, files, "TOKEN=local-value\nIDENTICAL=same\n")
    stores["rediss://ci.test"].values["devos:projects:sample"] = {"TOKEN": "stored-value", "IDENTICAL": "same"}
    with pytest.raises(ScaffoldError) as failure:
        credentials.execute(spec)
    assert failure.value.category == "conflict"
    assert all(not store.writes for store in stores.values())
    spec.ci_store.resolutions = {"TOKEN": "stored"}
    credentials.execute(spec)
    assert stores["local.test"].values["devos:projects:sample"]["TOKEN"] == "local-value"
    assert stores["rediss://ci.test"].values["devos:projects:sample"]["TOKEN"] == "stored-value"


def test_failed_second_import_keeps_original_env_and_reports_partial(setup):
    spec, stores, files, _, credentials, *_ = setup
    seed_environment(spec, files)
    original = (spec.root() / ".env").read_bytes()
    stores["rediss://ci.test"] = Store(fail=True)
    with pytest.raises(ScaffoldError) as failure:
        credentials.execute(spec)
    assert failure.value.category == "verification"
    assert failure.value.completed == ["local credential bundle verified"]
    assert (spec.root() / ".env").read_bytes() == original
    assert not (spec.root() / ".env.example").exists()
    stores["rediss://ci.test"].fail = False
    credentials.execute(spec)
    assert stores["local.test"].writes.count("devos:projects:sample") == 1


def test_read_only_inspection_does_not_mutate_or_disclose_values(setup):
    spec, stores, files, git, *_ = setup
    seed_environment(spec, files)
    result = InspectProjectScaffoldUseCase(files, git).execute(spec.root())
    assert result.environment_keys == ["EMPTY", "TOKEN"]
    assert ".env" in result.files
    assert "literal" not in result.model_dump_json()
    assert all(not store.writes for store in stores.values())


def test_existing_design_workflow_and_unrelated_changes_preserved(setup):
    spec, _, files, git, _, _, complete, _ = setup
    root = spec.root()
    root.mkdir()
    git.initialise(root)
    git.run(root, ["config", "user.name", "Test"])
    git.run(root, ["config", "user.email", "test@example.com"])
    (root / "unrelated.txt").write_text("initial\n")
    git.run(root, ["add", "unrelated.txt"])
    git.run(root, ["commit", "-m", "test baseline"])
    (root / "unrelated.txt").write_text("staged\n")
    git.run(root, ["add", "unrelated.txt"])
    (root / "unrelated.txt").write_text("working\n")
    (root / "uv.lock").write_text("unrelated lock")
    (root / "docs/product").mkdir(parents=True)
    original = "# Design\r\n\r\nUser architecture.\r\n\r\n## Source Tables\r\n\r\nOld schema\r\n\r\n## Constraints\r\n\r\nKeep immutable.\r\n"
    (root / "docs/product/design.md").write_bytes(original.encode())
    (root / ".github/workflows").mkdir(parents=True)
    (root / ".github/workflows/ci.yml").write_text("name: Existing\non: [push]\njobs:\n  old:\n    runs-on: ubuntu-latest\n    steps: []\n")
    spec.source_tables = "Orders table from the warehouse."
    approve(spec, files)
    result = complete.execute(spec)
    changed = (root / "docs/product/design.md").read_bytes().decode()
    assert changed.split("## Source Tables")[0] == original.split("## Source Tables")[0]
    assert changed.split("## Constraints")[1] == original.split("## Constraints")[1]
    assert "Existing" in (root / ".github/workflows/ci.yml").read_text()
    assert (root / "unrelated.txt").read_text() == "working\n"
    assert git.run(root, ["show", ":unrelated.txt"]).stdout == "staged\n"
    assert "uv.lock" not in result.staged_files
    assert "unrelated.txt" not in result.staged_files


def test_staged_overlap_rejected_before_credential_mutation(setup):
    spec, stores, files, git, _, _, complete, _ = setup
    spec.root().mkdir()
    git.initialise(spec.root())
    (spec.root() / "README.md").write_text("User staged readme\n")
    git.run(spec.root(), ["add", "README.md"])
    approve(spec, files)
    with pytest.raises(ScaffoldError, match="staged changes"):
        complete.execute(spec)
    assert all(not store.writes for store in stores.values())


def test_react_never_generates_credentials_in_browser(setup):
    spec, _, files, _, _, _, complete, _ = setup
    spec.stack = "react"
    spec.package_manager = "npm"
    spec.validation_commands = []
    result = complete.execute(spec)
    assert not any(name.endswith("credentials.py") for name in result.files)
    assert not (spec.root() / "src").exists()
    assert "DEVOS_REDIS" not in (spec.root() / ".github/workflows/ci.yml").read_text()
    assert json.loads((spec.root() / "package.json").read_text())["description"] == spec.description


@pytest.mark.parametrize("path", [".\\.env", "docs\\product\\design.md", "docs/product/design.md", ".env.local", "../outside.md"])
def test_protected_file_paths_cannot_bypass_preflight(setup, path):
    spec, _, files, *_ = setup
    if "\\" in path:
        with pytest.raises(pydantic.ValidationError):
            spec.files = []
            ScaffoldSpec.model_validate({**spec.model_dump(), "files": [{"path": path, "content": "bad"}]})
    else:
        from devOS.domain.scaffold import FileChange
        spec.files = [FileChange(path=path, content="bad")]
        with pytest.raises(ScaffoldError):
            rendered = project_files(spec, files, {})
            files.preflight(spec.root(), rendered, {}, GitProjectAdapter())


def test_secret_upload_failure_reports_names_and_metadata_failure(setup):
    spec, _, _, _, _, secrets, _, github = setup
    github.secret_names = Mock(side_effect=ScaffoldError("github", "Service unavailable", "service"))
    with pytest.raises(ScaffoldError) as failure:
        secrets.execute(spec)
    assert set(failure.value.completed) == {"DEVOS_PROJECT_NAME", "DEVOS_REDIS_URL"}
    assert "ci.test" not in str(failure.value)


def test_github_client_encrypts_and_preserves_visibility():
    private = nacl.public.PrivateKey.generate()
    responses = []
    def response(status, content):
        item = Mock(status_code=status)
        item.json.return_value = content
        responses.append(item)
    response(200, {"description": "old", "private": False})
    response(200, {})
    response(200, {"key": base64.b64encode(bytes(private.public_key)).decode(), "key_id": "id"})
    response(204, {})
    session = Mock()
    session.request.side_effect = responses
    client = GitHubRepositoryClient(pydantic.SecretStr("access-token"), session)
    assert client.ensure_repository("kesler", "sample", "description") == "kesler/sample"
    assert session.request.call_args_list[1].kwargs["json"] == {"description": "description"}
    client.set_actions_secret("kesler/sample", "DEVOS_REDIS_URL", pydantic.SecretStr("bootstrap-secret"))
    body = session.request.call_args.kwargs["json"]
    assert "bootstrap-secret" not in json.dumps(body)
    assert nacl.public.SealedBox(private).decrypt(base64.b64decode(body["encrypted_value"])) == b"bootstrap-secret"


def test_new_repository_private_without_initial_commit():
    session = Mock()
    session.request.side_effect = [Mock(status_code=404), Mock(status_code=200, json=lambda: {"login": "kesler"}), Mock(status_code=201, json=lambda: {})]
    GitHubRepositoryClient(pydantic.SecretStr("token"), session).ensure_repository("kesler", "sample", "description")
    assert session.request.call_args.kwargs["json"] == {"name": "sample", "description": "description", "private": True, "auto_init": False}


def test_cli_independent_commands_and_secret_free_errors(setup, monkeypatch, capsys):
    spec, _, files, _, credentials, secrets, *_ = setup
    seed_environment(spec, files)
    path = spec.protocol_root.parent / "approved.json"
    path.write_text(spec.model_dump_json())
    monkeypatch.setattr(scaffold_cli, "ConfigureProjectCredentialsUseCase", lambda *_: credentials)
    monkeypatch.setattr(scaffold_cli.DevOSSecretClient, "get", lambda *_: "secret-test-token")
    monkeypatch.setattr(scaffold_cli, "ConfigureGitHubSecretsUseCase", lambda *_: secrets)
    assert scaffold_cli.main(["credentials", "apply", str(path)]) == 0
    assert scaffold_cli.main(["secrets", "apply", str(path)]) == 0
    path.write_text('{"password": "must-not-print"}')
    assert scaffold_cli.main(["apply", str(path)]) == 2
    captured = capsys.readouterr()
    assert "must-not-print" not in captured.err
    assert "secret-test-token" not in captured.out + captured.err


def test_cli_inspect_dispatch_outside_git_is_lazy(tmp_path):
    result = subprocess.run([sys.executable, "-c", "import devOS,sys; sys.argv=['dev','scaffold','inspect',sys.argv[1]]; devOS.main()", str(tmp_path)], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["git_repository"] is False


def test_generated_settings_load_project_bundle_before_constructing_settings(setup, monkeypatch):
    spec, _, files, _, credentials, *_ = setup
    spec.config_content = (
        "from pathlib import Path\nimport dotenv\nimport pydantic_settings\nfrom . import credentials\n"
        "dotenv.load_dotenv(Path(__file__).resolve().parents[3] / '.env')\n"
        "credentials.LoadCredentialsUseCase.from_environment().execute()\n"
        "class EnvironmentVariables(pydantic_settings.BaseSettings):\n    token: str\n"
        "environment_variables = EnvironmentVariables()\n"
    )
    client = Mock()
    client.get.return_value = json.dumps({"TOKEN": "runtime-test-value"})
    for name in [*os.environ]:
        if name.lower().startswith("devos_") or name.upper() == "TOKEN":
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("redis.Redis", Mock(return_value=client))
    credentials.execute(spec)
    monkeypatch.syspath_prepend(str(spec.root() / "src"))
    try:
        configs = importlib.import_module("sample.infrastructure.configs")
        assert configs.environment_variables.token == "runtime-test-value"
        client.get.assert_called_once_with("devos:projects:sample")
    finally:
        for name in list(sys.modules):
            if name == "sample" or name.startswith("sample."):
                del sys.modules[name]
        for name in ["TOKEN", "devos_redis_host", "devos_redis_password", "devos_project_name"]:
            os.environ.pop(name, None)


def test_comment_loader_or_wrong_settings_order_rejected(setup):
    spec, _, files, _, credentials, *_ = setup
    spec.config_content = "# credentials.LoadCredentialsUseCase.from_environment().execute()\n"
    with pytest.raises(ScaffoldError, match="module scope"):
        credentials.execute(spec)
    spec.config_content = (
        "import pydantic_settings\nfrom . import credentials\n"
        "class Settings(pydantic_settings.BaseSettings):\n    pass\n"
        "settings = Settings()\ncredentials.LoadCredentialsUseCase.from_environment().execute()\n"
    )
    with pytest.raises(ScaffoldError, match="before loading"):
        credentials.execute(spec)


def test_tooling_failure_reports_imports_and_safe_remaining_completion(setup, monkeypatch):
    spec, stores, files, _, credentials, _, complete, _ = setup
    seed_environment(spec, files)
    actual_write = files.write
    def fail_docs(root, rendered):
        if "docs/product/prd.md" in rendered:
            raise OSError("must-not-print-secret")
        return actual_write(root, rendered)
    monkeypatch.setattr(files, "write", fail_docs)
    with pytest.raises(ScaffoldError) as failure:
        complete.execute(spec)
    assert failure.value.category == "tooling"
    assert "bootstrap environment written" in failure.value.completed
    assert "must-not-print-secret" not in str(failure.value)
    original_writes = {name: list(store.writes) for name, store in stores.items()}
    approve(spec, files)
    monkeypatch.setattr(files, "write", actual_write)
    # Equivalent direct file operation completes the outstanding authorised docs.
    rendered = project_files(spec, files, {"devos_redis_host": "local.test", "devos_redis_password": "bootstrap-local"})
    files.preflight(spec.root(), rendered, spec.expected_files, GitProjectAdapter())
    files.write(spec.root(), rendered)
    assert all(store.writes == original_writes[name] for name, store in stores.items())
    assert (spec.root() / "docs/product/prd.md").read_text() == spec.prd


def test_cli_failure_returns_safe_partial_operation(setup, monkeypatch, capsys):
    spec, _, _, _, _, secrets, _, github = setup
    path = spec.protocol_root.parent / "approved.json"
    path.write_text(spec.model_dump_json())
    monkeypatch.setattr(scaffold_cli.DevOSSecretClient, "get", lambda *_: "general-test-secret")
    monkeypatch.setattr(scaffold_cli, "ConfigureGitHubSecretsUseCase", lambda *_: secrets)
    original = github.set_actions_secret
    def fail_second(repository, name, value):
        if github.names:
            raise ScaffoldError("github", "Unavailable", "service")
        original(repository, name, value)
    github.set_actions_secret = fail_second
    assert scaffold_cli.main(["secrets", "apply", str(path)]) == 1
    report = json.loads(capsys.readouterr().err)
    assert report["completed"] == ["DEVOS_PROJECT_NAME"]
    assert report["category"] == "service"


def test_changed_env_and_tracked_env_rejected_before_import(setup):
    spec, stores, files, git, credentials, *_ = setup
    seed_environment(spec, files)
    (spec.root() / ".env").write_text("CHANGED=value\n")
    with pytest.raises(ScaffoldError, match="Reinspect"):
        credentials.execute(spec)
    approve(spec, files)
    git.initialise(spec.root())
    git.run(spec.root(), ["add", ".env"])
    with pytest.raises(ScaffoldError, match="tracked .env"):
        credentials.execute(spec)
    assert all(not store.writes for store in stores.values())


def test_crlf_clean_tracked_file_is_not_staged_overlap(setup):
    spec, _, _, git, *_ = setup
    spec.root().mkdir()
    git.initialise(spec.root())
    (spec.root() / "README.md").write_bytes(b"Original\r\n")
    git.run(spec.root(), ["add", "README.md"])
    git.run(spec.root(), ["-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "baseline"])
    git.validate_target(spec.root(), "README.md", "Approved\n", None)


def test_existing_human_title_registration_is_reused(setup):
    spec, _, files, _, _, _, complete, _ = setup
    page = spec.engine_root() / "wiki/Projects/Human Project Title.md"
    page.write_bytes(("---\r\ntype: project\r\nrepository_path: " + spec.root().as_posix()
                      + "\r\nagent_guides: [Frontend Development]\r\n---\r\n\r\nExisting source context.\r\n").encode())
    complete.execute(spec)
    assert not (page.parent / "sample.md").exists()
    assert "agent_guides: [Python Development]" in page.read_text()
    assert page.read_bytes().endswith(b"Existing source context.\r\n")
    assert "# Python Development" in (spec.root() / "AGENTS.md").read_text()
    assert "[[Projects/Human Project Title]]" in (spec.engine_root() / "wiki/INDEX.md").read_text()


def test_duplicate_repository_registration_rejected_before_import(setup):
    spec, stores, _, _, _, _, complete, _ = setup
    pages = spec.engine_root() / "wiki/Projects"
    for name in ["First", "Second"]:
        (pages / (name + ".md")).write_text("---\nrepository_path: " + spec.root().as_posix() + "\n---\n\n")
    with pytest.raises(ScaffoldError, match="More than one"):
        complete.execute(spec)
    assert all(not store.writes for store in stores.values())
    assert not spec.root().exists()


def test_generated_lock_from_validation_is_staged(setup):
    spec, _, _, _, _, _, complete, _ = setup
    spec.validation_commands = [[sys.executable, "-c", "from pathlib import Path\nPath('uv.lock').write_text('test lock')"]]
    result = complete.execute(spec)
    assert "uv.lock" in result.staged_files


def test_missing_general_secret_stops_before_clipboard_or_mutation(tmp_path, monkeypatch):
    source = tmp_path / "general.env"
    source.write_text("devos_redis_host=general.test\n")
    store = Store()
    monkeypatch.setattr("devOS.infrastructure.scaffold_adapters.RedisNoSQLAdapter.from_environment", lambda *_: store)
    copy = Mock()
    monkeypatch.setattr("pyperclip.copy", copy)
    with pytest.raises(ScaffoldError, match="Referenced general secret key MISSING is absent"):
        DevOSSecretClient(source).get("MISSING")
    copy.assert_not_called()
    assert not store.writes
