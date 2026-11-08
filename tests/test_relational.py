import copy
import json
import pathlib

import jsonschema
import pydantic
import pytest

from devOS.domain import relational
from devOS.use_cases import generate_relational_contracts
from devOS import relational_cli


FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "relational"


def test_relational_fixture_preserves_order_and_stable_references():
    document = relational.SchemaDocument.model_validate_json((FIXTURES / "valid.json").read_text())
    child = document.tables[1]
    foreign_key = next(item for item in child.constraints if isinstance(item, relational.ForeignKey))
    assert foreign_key.column_ids == ["child_tenant", "child_parent"]
    assert foreign_key.target_column_ids == ["tenant", "parent_id"]
    parent = document.tables[0]
    parent.name.name = "renamed_parent"
    parent.columns[0].name.name = "renamed_tenant"
    reopened = relational.SchemaDocument.model_validate_json(document.model_dump_json())
    assert reopened.tables[1].constraints[-1].target_table_id == parent.id
    assert reopened.diagram.tables[0].table_id == parent.id
    assert reopened.orm.tables[0].table_id == parent.id


def test_generated_contracts_are_deterministic():
    generator = generate_relational_contracts.GenerateRelationalContractsUseCase()
    artifacts = generator.execute()
    assert artifacts == generator.execute()


def test_schema_commands_work_outside_git_without_credentials(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert relational_cli.main(["validate", str(FIXTURES / "valid.json")]) == 0
    assert "Valid relational" in capsys.readouterr().out
    assert relational_cli.main(["contracts", "--json-schema", "contract.json", "--typescript", "contract.ts"]) == 0
    jsonschema.Draft202012Validator.check_schema(json.loads((tmp_path / "contract.json").read_text()))
    assert relational_cli.main(["contracts", "--json-schema", "same", "--typescript", "same"]) == 1
    assert not (tmp_path / "same").exists()


@pytest.mark.parametrize("fixture", sorted(FIXTURES.glob("invalid-*.json")), ids=lambda path: path.stem)
def test_invalid_shared_fixture_has_actionable_diagnostic(fixture):
    case = json.loads(fixture.read_text())
    with pytest.raises(pydantic.ValidationError, match=case["diagnostic"]):
        relational.SchemaDocument.model_validate(case["document"])


@pytest.mark.parametrize("name", ["uuid", "boolean", "text", "jsonb", "bytea", "date"])
def test_serial_rejects_non_integer_types(name):
    with pytest.raises(pydantic.ValidationError, match="scalar integer"):
        relational.Column(id="column", name={"name": "id"}, type={"name": name}, serial=True, nullable=False)


@pytest.mark.parametrize("parameters", [
    {"name": "text", "length": 4},
    {"name": "integer", "precision": 4},
    {"name": "numeric", "scale": 2},
    {"name": "timestamp", "time_precision": 7},
    {"name": "enum"},
    {"name": "text", "enum_id": "status"},
    {"name": "varchar", "length": 0},
    {"name": "point"},
])
def test_unsupported_type_parameters_fail(parameters):
    with pytest.raises(pydantic.ValidationError):
        relational.SqlType.model_validate(parameters)


def test_revalidation_rejects_deleted_referenced_column():
    document = json.loads((FIXTURES / "valid.json").read_text())
    document["tables"][0]["columns"].pop(0)
    with pytest.raises(pydantic.ValidationError, match="outside"):
        relational.SchemaDocument.model_validate(document)


def test_graph_fixture_preserves_self_cycles_multiple_paths_and_junction_payload():
    document = relational.SchemaDocument.model_validate_json((FIXTURES / "valid-graph.json").read_text())
    parent, child, junction = document.tables
    assert any(isinstance(item, relational.ForeignKey) and item.target_table_id == parent.id for item in parent.constraints)
    assert any(isinstance(item, relational.ForeignKey) and item.target_table_id == child.id for item in parent.constraints)
    assert len([item for item in child.constraints if isinstance(item, relational.ForeignKey) and item.target_table_id == parent.id]) == 2
    assert junction.columns[-1].name.name == "position"
    assert len(junction.constraints[0].column_ids) == 3


def test_diagram_does_not_change_schema_semantics():
    payload = json.loads((FIXTURES / "valid.json").read_text())
    without_diagram = copy.deepcopy(payload)
    without_diagram.pop("diagram")
    assert relational.SchemaDocument.model_validate(payload).tables == relational.SchemaDocument.model_validate(without_diagram).tables
