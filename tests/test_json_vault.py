import json
import pathlib
import types

import dotenv
import pytest

from devOS import credential_cli as cli
from devOS.infrastructure import credential_vault as storage


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "get_project_name", lambda root: "sample")
    return storage.JSONCredentialVaultAdapter(tmp_path / "vault")


def run(vault, *arguments):
    return cli.main(list(arguments), vault=vault, root=vault.directory.parent)


def test_duplicate_set_and_scoped_overwrite(vault):
    assert run(vault, "set", "creds", "TOKEN", "root") == 0
    assert run(vault, "set", "creds", "TOKEN", "root") == 1
    assert run(vault, "set", "creds", "TOKEN", "project", "--project") == 0
    assert run(vault, "set", "creds", "TOKEN", "new", "--project") == 1
    assert run(vault, "set", "creds", "TOKEN", "new", "--project", "--force") == 0
    assert vault.read() == {"TOKEN": "root", "project_sample": {"TOKEN": "new"}}
    assert not (vault.directory.parent / ".env").exists()


def test_get_and_delete_require_scope_on_collision(vault, monkeypatch, capsys):
    vault.write({"TOKEN": "root-sensitive", "project_sample": {"TOKEN": "project-sensitive"}})
    clipboard = []
    monkeypatch.setattr(cli.pyperclip, "copy", clipboard.append)
    assert run(vault, "get", "creds", "TOKEN") == 1
    assert run(vault, "delete", "TOKEN") == 1
    assert clipboard == []
    assert run(vault, "get", "creds", "TOKEN", "--project") == 0
    assert clipboard == ["project-sensitive"]
    assert run(vault, "delete", "TOKEN", "--root") == 0
    assert run(vault, "delete", "TOKEN") == 0
    output = capsys.readouterr()
    assert "root-sensitive" not in output.out + output.err
    assert "project-sensitive" not in output.out + output.err


def test_listing_all_projects_hides_values(vault, capsys):
    vault.write({"ROOT_KEY": "sensitive", "project_sample": {"ONE": "sensitive"}, "project_other": {"TWO": "sensitive"}})
    assert run(vault, "list", "creds") == 0
    output = capsys.readouterr().out
    assert all(name in output for name in ["ROOT_KEY", "sample", "ONE", "other", "TWO"])
    assert "sensitive" not in output


def test_invalid_json_never_overwritten(vault):
    vault.directory.mkdir()
    vault.path.write_text('{"broken":')
    assert run(vault, "set", "creds", "TOKEN", "value") == 1
    assert vault.path.read_text() == '{"broken":'


def test_reserved_key_and_conflicting_flags(vault):
    assert run(vault, "set", "creds", "project_bad", "value") == 1
    assert run(vault, "set", "creds", "TOKEN", "value", "--root", "--project") == 1


def test_materialisation_preserves_local_content(vault):
    root = vault.directory.parent
    (root / ".env").write_text('# comment\nLOCAL=keep\nEMPTY=keep\nTOKEN=old\n')
    vault.write({"ROOT_SECRET": "excluded", "project_sample": {"TOKEN": "a$literal\nline", "EMPTY": None}})
    assert run(vault, "materialise", "creds") == 0
    values = dotenv.dotenv_values(root / ".env", interpolate=False)
    assert values == {"LOCAL": "keep", "EMPTY": "keep", "TOKEN": "a$literal\nline"}
    assert (root / ".env").read_text().startswith("# comment")
    assert "a$literal" not in (root / ".env.example").read_text()


def test_remote_import_export_protection(vault, monkeypatch):
    class Remote:
        value = {"TOKEN": "remote", "OTHER": "added"}
        def get(self, key):
            assert key == "devos:projects:sample"
            return self.value
        def put(self, key, value):
            self.value = value.copy()
            return True
    remote = Remote()
    monkeypatch.setattr(cli.credential_vault, "get_remote_store", lambda vault, name: remote)
    vault.write({"ROOT": "private", "project_sample": {"TOKEN": "local", "LOCAL": "kept"}})
    assert run(vault, "import", "creds", "store") == 1
    assert "OTHER" not in vault.read()["project_sample"]
    assert run(vault, "import", "creds", "store", "--force") == 0
    assert vault.read()["project_sample"]["LOCAL"] == "kept"
    assert not (vault.directory.parent / ".env").exists()
    assert run(vault, "export", "creds", "store") == 1
    assert run(vault, "export", "creds", "store", "--force") == 0
    assert remote.value == vault.read()["project_sample"]
    assert "ROOT" not in remote.value


def test_configuration_prompt_and_noninteractive_error(tmp_path, monkeypatch):
    config = tmp_path / "machine.json"
    with pytest.raises(storage.VaultError, match="not configured"):
        storage.get_configured_vault(config)
    monkeypatch.setattr("builtins.input", lambda prompt: str(tmp_path / "managed"))
    assert storage.get_configured_vault(config, interactive=True) == tmp_path / "managed"
    assert storage.get_configured_vault(config) == tmp_path / "managed"


def test_atomic_replace_failure_keeps_original(vault, monkeypatch):
    vault.write({"TOKEN": "old"})
    def fail(*args):
        raise OSError("replace failed")
    monkeypatch.setattr(storage.os, "replace", fail)
    with pytest.raises(OSError):
        vault.write({"TOKEN": "new"})
    assert vault.read() == {"TOKEN": "old"}
    assert not list(vault.directory.glob(".devos-*.tmp"))


def test_no_repository_root_operations(vault, monkeypatch):
    monkeypatch.setattr(cli, "get_project_name", lambda root: None)
    assert run(vault, "set", "creds", "TOKEN", "value") == 0
    assert run(vault, "set", "creds", "OTHER", "value", "--project") == 1
    assert run(vault, "delete", "TOKEN") == 0


def test_prefect_adapter_explicit_target_and_sync_async_calls(monkeypatch):
    import contextlib
    import sys
    import types
    blocks = {}
    settings_seen = []
    class Secret:
        def __init__(self, value):
            self.value = value.get_secret_value()
        @classmethod
        async def load(cls, name):
            if name not in blocks:
                raise ValueError("not found")
            return blocks[name]
        async def save(self, name, overwrite=False):
            assert overwrite
            blocks[name] = self
        def get(self):
            return self.value
    def temporary_settings(settings):
        settings_seen.append(settings)
        return contextlib.nullcontext()
    monkeypatch.setitem(sys.modules, "prefect.blocks.system", types.SimpleNamespace(Secret=Secret))
    monkeypatch.setitem(sys.modules, "prefect.settings", types.SimpleNamespace(PREFECT_API_URL="url", PREFECT_API_KEY="key", temporary_settings=temporary_settings))
    store = storage.PrefectCredentialStoreAdapter({"api_url": "https://fake.test/api", "api_key": "sensitive"})
    assert store.get("devos:projects:sample") is None
    assert store.put("devos:projects:sample", {"TOKEN": "value"})
    assert store.get("devos:projects:sample") == {"TOKEN": "value"}
    assert all(item == {"url": "https://fake.test/api", "key": "sensitive"} for item in settings_seen)


def test_named_redis_target_uses_explicit_configuration(vault, monkeypatch):
    from devOS.infrastructure import adapters
    received = []
    remote = object()
    monkeypatch.setattr(adapters.RedisNoSQLAdapter, "from_environment", lambda values: received.append(values) or remote)
    storage.write_document(vault.directory / "config.json", {"stores": {"sample": {"type": "redis", "connection": {"host": "fake.test", "ssl": True}}}})
    assert storage.get_remote_store(vault, "sample") is remote
    assert received == [{"devos_redis_host": "fake.test", "devos_redis_ssl": "true"}]


def test_prefect_colliding_project_names_rejected(vault, monkeypatch):
    vault.write({"project_sample": {"TOKEN": "value"}, "project_Sample": {"TOKEN": "other"}})
    store = storage.PrefectCredentialStoreAdapter({"api_url": "https://fake.test/api"})
    monkeypatch.setattr(cli.credential_vault, "get_remote_store", lambda vault, name: store)
    assert run(vault, "export", "creds", "prefect") == 1
