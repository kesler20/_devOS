from __future__ import annotations

import json
import pathlib

import dotenv
import pytest

import devOS.domain.entities as entities
import devOS.infrastructure.credential_database as credential_database
import devOS.use_cases.manage_credentials as manage_credentials


class FakeNoSQLDatabase:
    def __init__(self) -> None:
        self.values: dict[str, credential_database.JSONValue] = {}

    def put(self, key: str, value: credential_database.JSONValue) -> bool:
        self.values[key] = json.loads(json.dumps(value))
        return True

    def get(self, key: str) -> credential_database.JSONValue:
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


def test_project_credentials_override_general_and_materialize_without_nulls(
    tmp_path: pathlib.Path,
) -> None:
    database = FakeNoSQLDatabase()
    database.values[manage_credentials.GENERAL_CREDENTIALS_KEY] = {
        "SHARED": "general",
        "GENERAL_ONLY": True,
        "MASKED": "general",
    }
    database.values["devos:credentials:project:sample"] = {
        "SHARED": "project",
        "OBJECT": {"enabled": True},
        "MASKED": None,
    }
    (tmp_path / ".env").write_text(
        "DEVOS_CREDENTIALS_REDIS_URL=rediss://bootstrap\nSHARED=stale\n",
        encoding="utf-8",
    )
    use_case = manage_credentials.ManageCredentialsUseCase(
        database=database,
        project_name="sample",
        project_root=tmp_path,
    )

    use_case.get_credentials()

    materialized = dotenv.dotenv_values(tmp_path / ".env")
    assert materialized["DEVOS_CREDENTIALS_REDIS_URL"] == "rediss://bootstrap"
    assert materialized["SHARED"] == "project"
    assert materialized["GENERAL_ONLY"] == "true"
    assert materialized["OBJECT"] == '{"enabled":true}'
    assert "MASKED" not in materialized
    example = (tmp_path / ".env.example").read_text(encoding="utf-8")
    assert "SHARED=\n" in example
    assert "project" not in example


def test_dotenv_import_merges_and_excludes_bootstrap_values(
    tmp_path: pathlib.Path,
) -> None:
    database = FakeNoSQLDatabase()
    database.values["devos:credentials:project:sample"] = {
        "PAST": "keep",
        "UPDATED": "old",
    }
    (tmp_path / ".env").write_text(
        "UPDATED=new\nNEW_KEY=value\nDEVOS_CREDENTIALS_REDIS_PASSWORD=bootstrap\n",
        encoding="utf-8",
    )
    use_case = manage_credentials.ManageCredentialsUseCase(
        database=database,
        project_name="sample",
        project_root=tmp_path,
    )

    use_case.set_credentials()

    assert database.values["devos:credentials:project:sample"] == {
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
    use_case.list_credentials()
    use_case.get_global_secret("GENERAL_TOKEN")
    use_case.delete_credential("PROJECT_TOKEN")
    use_case.delete_global_secret("GENERAL_TOKEN")

    captured = capsys.readouterr()
    assert "project-secret" not in captured.out
    assert "general-secret" not in captured.out
    assert "PROJECT_TOKEN" in captured.out
    assert "GENERAL_TOKEN" in captured.out
    assert copied_values == ["general-secret"]


def test_export_and_import_round_trip_json_types(tmp_path: pathlib.Path) -> None:
    source_database = FakeNoSQLDatabase()
    source_database.values[manage_credentials.GENERAL_CREDENTIALS_KEY] = {
        "FLAGS": [True, False],
        "COUNT": 3,
    }
    source_database.values["devos:credentials:project:sample"] = {
        "OBJECT": {"ratio": 1.5},
    }
    source_database.values[manage_credentials.PROJECT_REGISTRY_KEY] = ["sample"]
    source_use_case = manage_credentials.ManageCredentialsUseCase(
        database=source_database,
        project_name="sample",
        project_root=tmp_path,
    )
    export_path = tmp_path / "vault-export"

    source_use_case.export_credentials(str(export_path))

    target_database = FakeNoSQLDatabase()
    target_database.values[manage_credentials.GENERAL_CREDENTIALS_KEY] = {
        "PAST": "keep"
    }
    target_use_case = manage_credentials.ManageCredentialsUseCase(
        database=target_database,
        project_name="sample",
        project_root=tmp_path,
    )
    target_use_case.import_credentials(str(export_path))

    assert target_database.values[manage_credentials.GENERAL_CREDENTIALS_KEY] == {
        "PAST": "keep",
        "FLAGS": [True, False],
        "COUNT": 3,
    }
    assert target_database.values["devos:credentials:project:sample"] == {
        "OBJECT": {"ratio": 1.5}
    }


def test_setup_credentials_copies_project_owned_bundle_and_refuses_overwrite(
    tmp_path: pathlib.Path,
) -> None:
    snippets_root = pathlib.Path(__file__).parents[1] / "snippets"
    setup = manage_credentials.SetupCredentialsUseCase(
        snippets_root=snippets_root,
        project_config=build_project_config("sample"),
        project_root=tmp_path,
    )

    setup.execute()

    infrastructure = tmp_path / "src" / "sample" / "infrastructure"
    config_content = (infrastructure / "configs.py").read_text(encoding="utf-8")
    assert 'PROJECT_NAME = "sample"' in config_content
    assert (infrastructure / "credentials" / "runtime_loader.py").is_file()

    with pytest.raises(FileExistsError):
        setup.execute()

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
    assert "credentials" in user_input_map.mapper["import"]
    assert "credentials" in user_input_map.mapper["setup"]
