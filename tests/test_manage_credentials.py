from __future__ import annotations

import json
import pathlib

import dotenv
import pytest

import devOS.domain.entities as entities
import devOS.infrastructure.adapters as adapters
import devOS.use_cases.manage_credentials as manage_credentials


class FakeNoSQLDatabase:
    def __init__(self) -> None:
        self.values: dict[str, adapters.JSONValue] = {}

    def put(self, key: str, value: adapters.JSONValue) -> bool:
        self.values[key] = json.loads(json.dumps(value))
        return True

    def get(self, key: str) -> adapters.JSONValue:
        value = self.values.get(key)
        return json.loads(json.dumps(value)) if value is not None else None

    def delete(self, key: str) -> bool:
        return self.values.pop(key, None) is not None


def build_project_config(project_name: str) -> entities.ProjectConfigSchema:
    return entities.ProjectConfigSchema(
        project_name=project_name,
        home_root=entities.HomeRootConfig(snippets=["snippets"]),
        project_root=entities.ProjectSpecificConfig(
            dao_output_config=[],
            dto_output_config=[],
            api_output_config=[],
            test_api_output_config=[],
            test_services_output_directory=["tests"],
            adapters_output_directory=[
                "src",
                project_name,
                "infrastructure",
                "adapters.py",
            ],
        ),
    )


def test_project_credentials_materialize_without_global_credentials_or_nulls(
    tmp_path: pathlib.Path,
) -> None:
    database = FakeNoSQLDatabase()
    database.values["devos:projects:sample"] = {
        "SHARED": "project",
        "OBJECT": {"enabled": True},
        "MASKED": None,
    }
    (tmp_path / ".env").write_text(
        "devos_redis_url=rediss://bootstrap\nSHARED=stale\n",
        encoding="utf-8",
    )
    use_case = manage_credentials.ManageCredentialsUseCase(
        database=database,
        project_name="sample",
        project_root=tmp_path,
    )

    use_case.get_credentials()

    materialized = dotenv.dotenv_values(tmp_path / ".env")
    assert materialized["devos_redis_url"] == "rediss://bootstrap"
    assert materialized["SHARED"] == "project"
    assert "GENERAL_ONLY" not in materialized
    assert materialized["OBJECT"] == '{"enabled":true}'
    assert "MASKED" not in materialized
    example = (tmp_path / ".env.example").read_text(encoding="utf-8")
    assert "SHARED=\n" in example
    assert "project" not in example


def test_dotenv_import_merges_and_excludes_bootstrap_values(
    tmp_path: pathlib.Path,
) -> None:
    database = FakeNoSQLDatabase()
    database.values["devos:projects:sample"] = {
        "PAST": "keep",
        "UPDATED": "old",
    }
    (tmp_path / ".env").write_text(
        "UPDATED=new\nNEW_KEY=value\ndevos_redis_password=bootstrap\n",
        encoding="utf-8",
    )
    use_case = manage_credentials.ManageCredentialsUseCase(
        database=database,
        project_name="sample",
        project_root=tmp_path,
    )

    use_case.set_credentials("--force")

    assert database.values["devos:projects:sample"] == {
        "PAST": "keep",
        "UPDATED": "new",
        "NEW_KEY": "value",
    }
    assert database.values[manage_credentials.PROJECT_REGISTRY_KEY] == ["sample"]


def test_set_list_get_and_delete_do_not_print_values(
    tmp_path: pathlib.Path, monkeypatch, capsys
) -> None:
    database = FakeNoSQLDatabase()
    copied_values: list[str] = []
    monkeypatch.setattr(
        manage_credentials.pyperclip, "copy", copied_values.append
    )
    use_case = manage_credentials.ManageCredentialsUseCase(
        database=database,
        project_name="sample",
        project_root=tmp_path,
    )

    use_case.set_credential("PROJECT_TOKEN", "project-secret")
    use_case.set_global_secret("GENERAL_TOKEN", "general-secret")
    use_case.store_project_credentials("other-project", {"OTHER_TOKEN": "value"})
    capsys.readouterr()

    use_case.list_credentials()
    overview_output = capsys.readouterr().out
    use_case.list_credentials("other-project")
    listed_output = capsys.readouterr().out
    use_case.get_global_secret("GENERAL_TOKEN")
    use_case.delete_credential("PROJECT_TOKEN")
    use_case.delete_global_secret("GENERAL_TOKEN")

    captured = capsys.readouterr()
    assert "General credentials:" in overview_output
    assert "GENERAL_TOKEN" in overview_output
    assert "Project credentials (sample):" in overview_output
    assert "PROJECT_TOKEN" in overview_output
    assert "Known projects:" in overview_output
    assert "other-project" in overview_output
    assert "PROJECT_TOKEN" not in listed_output
    assert "GENERAL_TOKEN" not in listed_output
    assert "OTHER_TOKEN" in listed_output
    assert "other-project" in listed_output
    assert "project-secret" not in captured.out
    assert "general-secret" not in captured.out
    assert copied_values == ["general-secret"]


def test_export_materializes_every_bundle_as_env_files(
    tmp_path: pathlib.Path, monkeypatch
) -> None:
    database = FakeNoSQLDatabase()
    database.values[manage_credentials.GENERAL_CREDENTIALS_KEY] = {"PAT": "pat-value"}
    database.values["devos:projects:sample"] = {"TOKEN": "token-value", "COUNT": 3}
    database.values[manage_credentials.PROJECT_REGISTRY_KEY] = ["sample"]
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))
    use_case = manage_credentials.ManageCredentialsUseCase(
        database=database,
        project_name="sample",
        project_root=tmp_path,
    )

    use_case.export_credentials("backups/store")

    export_root = tmp_path / "backups" / "store"
    assert dotenv.dotenv_values(export_root / "general.env") == {"PAT": "pat-value"}
    assert dotenv.dotenv_values(export_root / "sample.env") == {
        "TOKEN": "token-value",
        "COUNT": "3",
    }


def test_set_credentials_refuses_to_overwrite_without_force(
    tmp_path: pathlib.Path,
) -> None:
    database = FakeNoSQLDatabase()
    database.values["devos:projects:sample"] = {"TOKEN": "stored-value"}
    (tmp_path / ".env").write_text(
        "TOKEN=local-value\nNEW_KEY=new-value\n", encoding="utf-8"
    )
    use_case = manage_credentials.ManageCredentialsUseCase(
        database=database,
        project_name="sample",
        project_root=tmp_path,
    )

    with pytest.raises(ValueError, match="TOKEN"):
        use_case.set_credentials()

    # Nothing is written when the push aborts.
    assert database.values["devos:projects:sample"] == {"TOKEN": "stored-value"}

    use_case.set_credentials("--force")

    assert database.values["devos:projects:sample"] == {
        "TOKEN": "local-value",
        "NEW_KEY": "new-value",
    }


def test_setup_credentials_copies_project_owned_bundle_and_refuses_overwrite(
    tmp_path: pathlib.Path,
) -> None:
    snippets_root = pathlib.Path(__file__).parents[1] / "snippets"
    setup = manage_credentials.ManageCredentialsUseCase(
        database=None,
        project_name="sample",
        project_root=tmp_path,
    )

    setup.setup_credentials(snippets_root, build_project_config("sample"))

    infrastructure = tmp_path / "src" / "sample" / "infrastructure"
    config_content = (infrastructure / "configs.py").read_text(encoding="utf-8")
    # The project name is resolved at runtime, so nothing is stamped into the copy.
    assert "PROJECT_NAME" not in config_content
    assert (infrastructure / "credentials.py").is_file()

    with pytest.raises(FileExistsError):
        setup.setup_credentials(snippets_root, build_project_config("sample"))

    assert (infrastructure / "configs.py").read_text(
        encoding="utf-8"
    ) == config_content


def test_cli_mapper_exposes_credential_lifecycle() -> None:
    import devOS.user_input_map as user_input_map

    assert "credential" in user_input_map.mapper["set"]
    assert "credentials" in user_input_map.mapper["get"]
    assert "credentials" in user_input_map.mapper["list"]
    assert "credential" in user_input_map.mapper["delete"]
    assert "credentials" in user_input_map.mapper["export"]
    assert "credentials" in user_input_map.mapper["setup"]


def test_materialization_keeps_keys_the_store_does_not_supply(
    tmp_path: pathlib.Path,
) -> None:
    database = FakeNoSQLDatabase()
    database.values["devos:projects:sample"] = {
        "SHARED": "from-redis",
        "LEFT_NULL": None,
    }
    (tmp_path / ".env").write_text(
        "devos_redis_url=rediss://bootstrap\n"
        "SHARED=stale\n"
        "LOCAL_ONLY=keep-me\n"
        "LEFT_NULL=also-keep-me\n"
        'TRICKY_VALUE="a value # with a hash"\n',
        encoding="utf-8",
    )
    use_case = manage_credentials.ManageCredentialsUseCase(
        database=database,
        project_name="sample",
        project_root=tmp_path,
    )

    use_case.get_credentials()

    materialized = dotenv.dotenv_values(tmp_path / ".env")
    assert materialized["SHARED"] == "from-redis"
    assert materialized["LOCAL_ONLY"] == "keep-me"
    assert materialized["LEFT_NULL"] == "also-keep-me"
    assert materialized["devos_redis_url"] == "rediss://bootstrap"
    assert materialized["TRICKY_VALUE"] == "a value # with a hash"

    example = (tmp_path / ".env.example").read_text(encoding="utf-8")
    assert "LOCAL_ONLY=\n" in example
    assert "SHARED=\n" in example
    assert "keep-me" not in example
    assert "from-redis" not in example


def test_bootstrap_reservation_ignores_case(tmp_path: pathlib.Path) -> None:
    database = FakeNoSQLDatabase()
    (tmp_path / ".env").write_text(
        "devos_redis_password=lowercase-bootstrap\n"
        "DEVOS_REDIS_HOST=uppercase-bootstrap\n"
        "REAL_CREDENTIAL=store-me\n",
        encoding="utf-8",
    )
    use_case = manage_credentials.ManageCredentialsUseCase(
        database=database,
        project_name="sample",
        project_root=tmp_path,
    )

    use_case.set_credentials()

    assert database.values["devos:projects:sample"] == {
        "REAL_CREDENTIAL": "store-me"
    }
    with pytest.raises(ValueError):
        entities.CredentialBundle.empty().merge({"DEVOS_REDIS_HOST": "x"})
    with pytest.raises(ValueError):
        entities.CredentialBundle.empty().merge({"devos_redis_host": "x"})
