import pytest
import os
import uuid
import sqlalchemy as sa
from devOS.infrastructure import credential_vault


@pytest.fixture(autouse=True)
def isolated_vault(tmp_path, monkeypatch):
    config = tmp_path / "machine-config.json"
    credential_vault.write_document(
        config, {"vault_directory": str(tmp_path / "vault")}
    )
    monkeypatch.setattr(credential_vault, "CONFIG_PATH", config)


@pytest.fixture
def postgres_database():
    admin_url = os.environ.get("DEVOS_TEST_POSTGRES_URL")
    if admin_url is None:
        pytest.skip("Set DEVOS_TEST_POSTGRES_URL for isolated PostgreSQL 18 checks")
    url = sa.engine.make_url(admin_url)
    assert (
        url.host in {"127.0.0.1", "localhost"} and url.username == "devos_test"
    ), "PostgreSQL acceptance tests require the explicit local test instance"
    admin = sa.create_engine(url, isolation_level="AUTOCOMMIT")
    database_name = "devos_test_" + uuid.uuid4().hex
    try:
        with admin.connect() as connection:
            version = int(
                connection.exec_driver_sql("SHOW server_version_num").scalar_one()
            )
            assert 180000 <= version < 190000, "Acceptance requires PostgreSQL 18"
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        database = sa.create_engine(url.set(database=database_name))
        try:
            yield database
        finally:
            database.dispose()
            with admin.connect() as connection:
                connection.exec_driver_sql(
                    f'DROP DATABASE "{database_name}" WITH (FORCE)'
                )
    finally:
        admin.dispose()


import json
import fnmatch
from devOS.domain import entities


class FakeNoSQLDatabase:
    def __init__(self, values: dict[str, entities.JSONValue] | None = None) -> None:
        self.values: dict[str, entities.JSONValue] = (
            {} if values is None else json.loads(json.dumps(values))
        )

    def put(self, key, value):
        self.values[key] = json.loads(json.dumps(value))
        return True

    def get(self, key):
        return self.values.get(key)

    def delete(self, key):
        return self.values.pop(key, None) is not None

    def keys(self, pattern):
        return sorted(key for key in self.values if fnmatch.fnmatch(key, pattern))


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
from devOS.infrastructure.scaffold_adapters import (
    BootstrapSourceAdapter,
    DevOSSecretAdapter,
    GitProjectAdapter,
    ProjectFilesAdapter,
)
from devOS.use_cases.scaffold_project import (
    ConfigureGitHubSecretsUseCase,
    ConfigureProjectCredentialsUseCase,
    InspectProjectScaffoldUseCase,
    ScaffoldProjectUseCase,
    render_project_files,
)


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
    local.write_text(
        "devos_redis_host=local.test\ndevos_redis_password=bootstrap-local\n"
    )
    ci.write_text("devos_redis_url=rediss://ci.test\n")
    engine = protocol / "automation_engine"
    (engine / "wiki/SOPs").mkdir(parents=True)
    (engine / "wiki/Projects").mkdir()
    (engine / "wiki/INDEX.md").write_text("# Index\n")
    (engine / "scripts").mkdir()
    import config
    import shutil

    shutil.copytree(
        pathlib.Path(config.__file__).parent,
        engine / "wiki/Snippets/python/config",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
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
        (engine / "wiki/SOPs" / (guide + ".md")).write_text(
            "# " + guide + "\n\nProject contract.\n"
        )
    spec = ScaffoldSpec(
        protocol_root=protocol,
        project_name="sample",
        description="Inform a useful decision.",
        stack="python",
        credential_resolutions={},
        ci_store={"bootstrap": {"env_file": ci}},
        github={"owner": "kesler", "repository": "sample"},
        data_project=True,
        prd="# Product\n",
        decision_log="# Requirements\n\n# Specifications\n",
        readme_body="## Install\n\nRun `uv sync`.\n",
        validation_commands=[[sys.executable, "-m", "compileall", "-q", "src"]],
    )
    files, git = ProjectFilesAdapter(), GitProjectAdapter()
    bootstrap = BootstrapSourceAdapter(Mock())
    stores = {"local.test": Store(), "rediss://ci.test": Store()}
    credentials = ConfigureProjectCredentialsUseCase(
        bootstrap,
        files,
        git,
        lambda values: stores[
            values.get("devos_redis_host") or values["devos_redis_url"]
        ],
    )
    github = GitHub()
    secrets = ConfigureGitHubSecretsUseCase(bootstrap, github)
    complete = ScaffoldProjectUseCase(
        credentials, secrets, bootstrap, github, files, git
    )
    return spec, stores, files, git, credentials, secrets, complete, github
