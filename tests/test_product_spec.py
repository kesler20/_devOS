import json
import pathlib
import re
import typing

import devOS.credential_cli as credential_cli


ROOT = pathlib.Path(__file__).resolve().parents[1]
ROUTED_COMMANDS = {
    "add",
    "build",
    "commit",
    "config",
    "release",
    "scaffold",
    "schema",
    "setup",
    "sync",
    "ui",
    "version",
}
CREDENTIAL_COMMANDS = {
    "delete",
    "export",
    "get",
    "import",
    "list",
    "materialise",
    "set",
}


def read_contract() -> dict[str, object]:
    text = (ROOT / "docs" / "product" / "spec.md").read_text(encoding="utf-8")
    match = re.search(
        r"<!-- spec-contract -->\s*```json\s*(\{.*?\})\s*```",
        text,
        re.S,
    )
    assert match is not None, "Missing executable contract in spec.md"
    return typing.cast(dict[str, object], json.loads(match.group(1)))


def test_documented_command_roots_match_the_cli_surface() -> None:
    contract = read_contract()
    documented = set(typing.cast(list[str], contract["command_roots"]))

    for command in CREDENTIAL_COMMANDS:
        assert credential_cli.handles([command])

    init_source = (ROOT / "src" / "devOS" / "__init__.py").read_text(
        encoding="utf-8"
    )
    mapper_source = (ROOT / "src" / "devOS" / "user_input_map.py").read_text(
        encoding="utf-8"
    )
    independently_routed = {"scaffold", "schema", "ui"}
    for command in independently_routed:
        assert f'["{command}"]' in init_source
    assert 'sys.argv[1:2] == ["build"]' in init_source
    assert 'sys.argv[2:3] != ["context"]' in init_source
    for command in ROUTED_COMMANDS - independently_routed:
        assert f'"{command}"' in mapper_source

    assert documented == ROUTED_COMMANDS | CREDENTIAL_COMMANDS


def test_spec_declares_generated_and_protected_ownership() -> None:
    contract = read_contract()
    generated = set(typing.cast(list[str], contract["generated_owners"]))
    protected = set(typing.cast(list[str], contract["protected_owners"]))

    assert generated == {
        "relational-schema",
        "creation-sql",
        "sqlalchemy-dao",
        "resource-dto",
        "resource-api",
        "resource-contract-test",
    }
    assert protected == {
        "application-feature",
        "custom-test",
        "database-migration",
        "product-design",
    }
    assert generated.isdisjoint(protected)
