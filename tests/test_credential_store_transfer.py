from __future__ import annotations

import fnmatch
import json
import pathlib

import pytest

import devOS.domain.entities as entities
import devOS.use_cases.manage_credentials as manage_credentials


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


SOURCE_STORE: dict[str, entities.JSONValue] = {
    "devos:general": {
        "GENERAL_TOKEN": "general-secret",
        "PRIVATE_KEY": "-----BEGIN KEY-----\nline-one\nline-two\n-----END KEY-----",
        "RETRY_LIMIT": 3,
        "FEATURE_FLAGS": {"beta": True, "regions": ["eu", "uk"]},
    },
    "devos:projects": ["devOS", "sofia_planner"],
    "devos:projects:devOS": {"PROJECT_TOKEN": "devos-secret"},
    "devos:projects:sofia_planner": {"PROJECT_TOKEN": "planner-secret"},
}


def build_use_case(
    database: FakeNoSQLDatabase, project_root: pathlib.Path
) -> manage_credentials.ManageCredentialsUseCase:
    return manage_credentials.ManageCredentialsUseCase(
        database=database,
        project_name="transfer",
        project_root=project_root,
    )


def export_source_store(
    tmp_path: pathlib.Path, home_relative_directory: str
) -> FakeNoSQLDatabase:
    source_database = FakeNoSQLDatabase(SOURCE_STORE)
    build_use_case(source_database, tmp_path).export_store(home_relative_directory)
    return source_database


@pytest.fixture
def export_directory(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> str:
    # The commands resolve their argument against the home directory, so the
    # home directory is redirected rather than the argument made absolute.
    monkeypatch.setattr(pathlib.Path, "home", classmethod(lambda cls: tmp_path))
    return "vault"


def test_export_writes_one_json_document_for_each_key(
    tmp_path: pathlib.Path, export_directory: str
) -> None:
    export_source_store(tmp_path, export_directory)

    export_root = tmp_path / export_directory
    assert sorted(
        path.relative_to(export_root).as_posix() for path in export_root.rglob("*.json")
    ) == [
        "general.json",
        "projects.json",
        "projects/devOS.json",
        "projects/sofia_planner.json",
    ]
    assert json.loads((export_root / "general.json").read_text(encoding="utf-8")) == (
        SOURCE_STORE["devos:general"]
    )


def test_round_trip_into_an_empty_store_reproduces_every_document(
    tmp_path: pathlib.Path, export_directory: str
) -> None:
    export_source_store(tmp_path, export_directory)

    destination_database = FakeNoSQLDatabase()
    build_use_case(destination_database, tmp_path / "project").import_store(
        export_directory
    )

    assert destination_database.values == SOURCE_STORE


def test_import_keeps_existing_values_and_writes_the_rest(
    tmp_path: pathlib.Path, export_directory: str, capsys
) -> None:
    export_source_store(tmp_path, export_directory)

    destination_database = FakeNoSQLDatabase(
        {"devos:general": {"GENERAL_TOKEN": "rotated-secret"}}
    )
    build_use_case(destination_database, tmp_path / "project").import_store(
        export_directory
    )

    general_document = destination_database.values["devos:general"]
    assert general_document["GENERAL_TOKEN"] == "rotated-secret"
    assert general_document["RETRY_LIMIT"] == 3
    assert general_document["FEATURE_FLAGS"] == {"beta": True, "regions": ["eu", "uk"]}
    assert "kept in devos:general: GENERAL_TOKEN" in capsys.readouterr().out


def test_import_unions_the_project_registry(
    tmp_path: pathlib.Path, export_directory: str
) -> None:
    export_source_store(tmp_path, export_directory)

    destination_database = FakeNoSQLDatabase({"devos:projects": ["automation_engine"]})
    build_use_case(destination_database, tmp_path / "project").import_store(
        export_directory
    )

    assert destination_database.values["devos:projects"] == [
        "automation_engine",
        "devOS",
        "sofia_planner",
    ]


def test_import_writes_no_environment_file(
    tmp_path: pathlib.Path, export_directory: str
) -> None:
    export_source_store(tmp_path, export_directory)

    project_root = tmp_path / "project"
    project_root.mkdir()
    build_use_case(FakeNoSQLDatabase(), project_root).import_store(export_directory)

    assert list(project_root.iterdir()) == []


def test_export_refuses_a_key_that_would_escape_the_export_root(
    tmp_path: pathlib.Path, export_directory: str
) -> None:
    database = FakeNoSQLDatabase({"devos:..:escape": {"TOKEN": "value"}})

    with pytest.raises(ValueError, match="relative segment"):
        build_use_case(database, tmp_path).export_store(export_directory)

    assert list((tmp_path / export_directory).rglob("*.json")) == []


def test_a_key_name_holding_a_dot_keeps_its_full_name() -> None:
    relative_path = manage_credentials.document_relative_path("devos:projects:my.app")

    assert relative_path.as_posix() == "projects/my.app.json"
    assert (
        manage_credentials.storage_key_from_document_path(relative_path)
        == "devos:projects:my.app"
    )
