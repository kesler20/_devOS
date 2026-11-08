import dotenv
import pytest

from devOS.domain import scaffold
from devOS.infrastructure import credential_vault
from devOS.infrastructure import os_adapter
from devOS.infrastructure import github_repository_client
from devOS.use_cases import manage_credentials
from conftest import FakeNoSQLDatabase
import unittest.mock as mock
import pydantic


def prepare_environment(spec, files):
    root = spec.root()
    root.mkdir()
    (root / ".env").write_text(
        'TOKEN="literal ${UNDEFINED} # value"\n', encoding="utf-8"
    )
    spec.expected_files = files.inventory(root)
    return root


def test_scaffold_populates_and_verifies_selected_ci_store(setup):
    spec, stores, files, _, credentials, *_ = setup
    root = prepare_environment(spec, files)
    result = credentials.execute(spec)
    assert stores["rediss://ci.test"].values["devos:projects:sample"] == {
        "TOKEN": "literal ${UNDEFINED} # value"
    }
    assert "CI credential bundle verified" in result.stores_verified
    assert (
        dotenv.dotenv_values(root / ".env", interpolate=False)["TOKEN"]
        == "literal ${UNDEFINED} # value"
    )


def test_ci_readback_failure_retains_original_environment(setup):
    spec, stores, files, _, credentials, *_ = setup
    root = prepare_environment(spec, files)
    original = (root / ".env").read_bytes()
    stores["rediss://ci.test"].fail = True
    with pytest.raises(scaffold.ScaffoldError, match="readback"):
        credentials.execute(spec)
    assert (root / ".env").read_bytes() == original


def test_complete_scaffold_preserves_materialized_credential_example(setup):
    spec, _, files, _, _, _, complete, _ = setup
    root = prepare_environment(spec, files)
    complete.execute(spec)
    assert "TOKEN=" in (root / ".env.example").read_text()
    assert "literal" not in (root / ".env.example").read_text()


def test_credential_import_preserves_literal_dollar_values(tmp_path):
    (tmp_path / ".env").write_text('TOKEN="literal ${UNDEFINED} # value"\n')
    database = FakeNoSQLDatabase()
    manager = manage_credentials.ManageCredentialsUseCase(database, "sample", tmp_path)
    manager.set_credentials()
    assert database.values["devos:projects:sample"] == {
        "TOKEN": "literal ${UNDEFINED} # value"
    }


def test_system_command_failure_is_reported(monkeypatch):
    monkeypatch.setattr(os_adapter.os, "system", lambda _: 1)
    with pytest.raises(RuntimeError, match="exit status 1"):
        os_adapter.OperatingSystemAdapter(".").execute_command("test command")


def test_legacy_command_failure_returns_nonzero():
    import devOS

    def fail():
        raise ValueError("invalid operation")

    with pytest.raises(SystemExit) as outcome:
        devOS.traverse_command_mapper(["test"], {"test": {"leaf node": fail}})
    assert outcome.value.code == 1


def test_github_client_uses_explicit_service_coordinates():
    session = mock.Mock()
    session.request.return_value = mock.Mock(
        status_code=200, json=lambda: {"description": "sample"}
    )
    client = github_repository_client.GitHubRepositoryClient(
        pydantic.SecretStr("test token"), session, base_url="https://fake.test/"
    )
    assert client.ensure_repository("test", "repo", "sample") == "test/repo"
    assert session.request.call_args.args[1] == "https://fake.test/repos/test/repo"


@pytest.mark.parametrize(
    "load", ["dotenv.load_dotenv()", "dotenv.load_dotenv(interpolate=True)"]
)
def test_scaffold_rejects_interpolating_existing_settings(setup, load):
    spec, _, files, _, credentials, *_ = setup
    root = prepare_environment(spec, files)
    path = root / spec.config_directory() / "configs.py"
    path.parent.mkdir(parents=True)
    path.write_text("import dotenv\n" + load + "\n", encoding="utf-8")
    spec.expected_files = files.inventory(root)
    original = (root / ".env").read_bytes()
    with pytest.raises(scaffold.ScaffoldError, match="interpolate=False"):
        credentials.execute(spec)
    assert (root / ".env").read_bytes() == original


def test_scaffold_installs_complete_offline_configuration_bundle(setup):
    import os
    import subprocess
    import sys

    spec, _, files, _, credentials, *_ = setup
    root = prepare_environment(spec, files)
    (root / ".env").write_text(
        'PAT="literal ${UNDEFINED} # value"\nTOKEN=other\n', encoding="utf-8"
    )
    spec.expected_files = files.inventory(root)
    source = spec.engine_root() / "wiki/Snippets/python/config/configs.py"
    source.write_bytes(
        source.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    )
    credentials.execute(spec)
    for name in manage_credentials.CONFIG_SNIPPET_FILE_NAMES:
        assert (root / spec.config_directory() / name).is_file()
    assert (root / "docs/snippets/config/requirements-test.txt").is_file()
    environment = dict(os.environ, PYTHONPATH=str(root / "src"))
    environment.pop("PAT", None)
    loaded = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sample.infrastructure.configs as config; assert config.dotenv_var.PAT.get_secret_value() == 'literal ${UNDEFINED} # value'",
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert loaded.returncode == 0, loaded.stderr
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/snippets/config", "-q"],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    "settings_config",
    [
        "    class Config:\n        env_file = '.env'\n",
        "    class Config:\n        env_file: str = '.env'\n",
        "    model_config = {'env_file': '.env'}\n",
        "    model_config = pydantic_settings.SettingsConfigDict(env_file='.env')\n",
    ],
)
def test_scaffold_rejects_pydantic_dotenv_reread(setup, settings_config):
    spec, _, files, _, credentials, *_ = setup
    root = prepare_environment(spec, files)
    spec.config_content = (
        "import dotenv\nimport pydantic_settings\ndotenv.load_dotenv(interpolate=False)\nclass Settings(pydantic_settings.BaseSettings):\n"
        + settings_config
        + "settings = Settings()\n"
    )
    with pytest.raises(scaffold.ScaffoldError, match="without rereading"):
        credentials.execute(spec)
    assert not (root / spec.config_directory()).exists()
