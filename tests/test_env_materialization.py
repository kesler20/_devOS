from __future__ import annotations

import json
import pathlib

import dotenv

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


def build_use_case(
    tmp_path: pathlib.Path,
) -> tuple[manage_credentials.ManageCredentialsUseCase, FakeNoSQLDatabase]:
    database = FakeNoSQLDatabase()
    use_case = manage_credentials.ManageCredentialsUseCase(
        database=database,
        project_name="sample",
        project_root=tmp_path,
    )
    return use_case, database


def test_materialization_edits_in_place_and_preserves_comments(
    tmp_path: pathlib.Path,
) -> None:
    use_case, database = build_use_case(tmp_path)
    database.values["devos:projects:sample"] = {
        "PAT": "new-pat",
        "TOKEN": "new-token",
        "BRAND_NEW": "appended",
    }
    original = (
        "# Github Configs\n"
        "PAT=old-pat\n"
        "\n"
        "# Service Configs\n"
        "TOKEN=old-token\n"
        "LOCAL_ONLY=untouched\n"
    )
    (tmp_path / ".env").write_text(original, encoding="utf-8")

    use_case.get_credentials()

    updated = (tmp_path / ".env").read_text(encoding="utf-8")
    # Comments, blank lines and ordering all survive.
    assert "# Github Configs" in updated
    assert "# Service Configs" in updated
    assert updated.index("# Github Configs") < updated.index("PAT=")
    assert updated.index("# Service Configs") < updated.index("TOKEN=")

    values = dotenv.dotenv_values(tmp_path / ".env")
    assert values["PAT"] == "new-pat"
    assert values["TOKEN"] == "new-token"
    assert values["LOCAL_ONLY"] == "untouched"
    assert values["BRAND_NEW"] == "appended"

    # The appended block is separated by exactly two blank lines.
    assert updated.endswith('LOCAL_ONLY=untouched\n\n\nBRAND_NEW="appended"\n')


def test_materialization_backs_up_the_previous_file(
    tmp_path: pathlib.Path,
) -> None:
    use_case, database = build_use_case(tmp_path)
    database.values["devos:projects:sample"] = {"TOKEN": "new-token"}
    original = "# keep me\nTOKEN=old-token\n"
    (tmp_path / ".env").write_text(original, encoding="utf-8")

    use_case.get_credentials()

    assert (tmp_path / ".devos_backup" / ".env").read_text(encoding="utf-8") == original
    assert dotenv.dotenv_values(tmp_path / ".env")["TOKEN"] == "new-token"


def test_materialization_rewrites_an_exported_assignment_in_place(
    tmp_path: pathlib.Path,
) -> None:
    use_case, database = build_use_case(tmp_path)
    database.values["devos:projects:sample"] = {"TOKEN": "new-token"}
    (tmp_path / ".env").write_text("export TOKEN=old-token\n", encoding="utf-8")

    use_case.get_credentials()

    updated = (tmp_path / ".env").read_text(encoding="utf-8")
    assert updated == 'export TOKEN="new-token"\n'


def test_materialization_writes_a_fresh_file_without_a_leading_gap(
    tmp_path: pathlib.Path,
) -> None:
    use_case, database = build_use_case(tmp_path)
    database.values["devos:projects:sample"] = {"TOKEN": "new-token"}

    use_case.get_credentials()

    assert (tmp_path / ".env").read_text(encoding="utf-8") == 'TOKEN="new-token"\n'
    assert not (tmp_path / ".devos_backup").exists()


def test_set_credential_writes_the_store_and_the_env_file(
    tmp_path: pathlib.Path,
) -> None:
    use_case, database = build_use_case(tmp_path)
    (tmp_path / ".env").write_text(
        "# Service Configs\nTOKEN=old-token\n", encoding="utf-8"
    )

    use_case.set_credential("TOKEN", "new-token")
    use_case.set_credential("BRAND_NEW", "fresh")

    assert database.values["devos:projects:sample"] == {
        "TOKEN": "new-token",
        "BRAND_NEW": "fresh",
    }
    updated = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "# Service Configs" in updated
    values = dotenv.dotenv_values(tmp_path / ".env")
    assert values["TOKEN"] == "new-token"
    assert values["BRAND_NEW"] == "fresh"
    assert (tmp_path / ".devos_backup" / ".env").is_file()
