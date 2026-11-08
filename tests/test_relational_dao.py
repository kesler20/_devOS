import importlib.util
import pathlib
import subprocess
import sys

import pytest
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg
import sqlalchemy.orm as orm

from devOS.domain import relational
from devOS.use_cases import generate_relational_dao


FIXTURES = pathlib.Path(__file__).parent / "fixtures/relational"


@pytest.fixture
def generated_module(tmp_path):
    document = relational.SchemaDocument.model_validate_json((FIXTURES / "valid.json").read_text())
    code = generate_relational_dao.GenerateRelationalDaoUseCase().execute(document)
    module_path = tmp_path / "generated.py"
    module_path.write_text(code)
    specification = importlib.util.spec_from_file_location("generated", module_path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    yield module
    module.Base.registry.dispose()


def test_generated_dao_preserves_keys_types_constraints_and_navigation(generated_module):
    parent = generated_module.ParentDAO
    child = generated_module.ChildDAO
    assert [column.name for column in parent.__mapper__.primary_key] == ["tenant_id", "id"]
    table = parent.__table__
    assert isinstance(table.c.tenant_id.type, pg.UUID)
    assert table.c.amount.type.precision == 20
    assert table.c.amount.type.scale == 4
    assert table.c.created.type.timezone
    assert table.c.created.type.precision == 3
    assert table.c.labels.type.dimensions == 1
    assert table.c.labels.type.item_type.length == 60
    assert table.c.state.type.enums == ["draft", "active"]
    assert table.c.id.identity.always
    fk = next(iter(child.__table__.foreign_key_constraints))
    assert [element.parent.name for element in fk.elements] == ["tenant_id", "parent_id"]
    assert [element.column.name for element in fk.elements] == ["tenant_id", "id"]
    assert fk.ondelete == "CASCADE" and fk.deferrable and fk.initially == "DEFERRED"
    assert child.__mapper__.relationships["parent"].mapper.class_ is parent
    assert parent.__mapper__.relationships["children"].mapper.class_ is child
    ddl = str(sa.schema.CreateTable(table).compile(dialect=pg.dialect()))
    assert '"App Schema"."Parent"' in ddl
    assert "NUMERIC(20, 4)" in ddl
    assert "GENERATED ALWAYS AS IDENTITY" in ddl


def test_generated_dao_imports_independently_and_handles_graph_fixture(tmp_path):
    document = relational.SchemaDocument.model_validate_json((FIXTURES / "valid-graph.json").read_text())
    generator = generate_relational_dao.GenerateRelationalDaoUseCase()
    source = generator.execute(document)
    assert source == generator.execute(document)
    destination = tmp_path / "generated.py"
    destination.write_text(source)
    harness = """
import generated
import sqlalchemy.orm as orm
orm.configure_mappers()
assert len(generated.Base.metadata.tables) == 3
assert len(generated.ParentDAO.__mapper__.relationships) >= 3
assert len(generated.ParentChildDAO.__mapper__.primary_key) == 3
assert 'position' in generated.ParentChildDAO.__table__.c
"""
    subprocess.run([sys.executable, "-c", harness], cwd=tmp_path, check=True, capture_output=True, text=True)


def test_generated_dao_honours_physical_names_and_orm_aliases(tmp_path):
    document = relational.SchemaDocument.model_validate_json((FIXTURES / "valid.json").read_text())
    document.tables[0].columns[0].name = relational.SqlIdentifier(name="Tenant Key", quoted=True)
    document.orm.columns = [relational.OrmColumn(column_id="tenant", attribute_name="tenant_key")]
    source = generate_relational_dao.GenerateRelationalDaoUseCase().execute(document)
    module_path = tmp_path / "aliased.py"
    module_path.write_text(source)
    specification = importlib.util.spec_from_file_location("aliased", module_path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    try:
        assert module.ParentDAO.__mapper__.attrs["tenant_key"].columns[0].name == "Tenant Key"
        assert "Tenant Key" not in module.ParentDAO.__mapper__.attrs
    finally:
        module.Base.registry.dispose()


def test_dao_generation_requires_primary_key():
    document = relational.SchemaDocument.model_validate_json((FIXTURES / "valid.json").read_text())
    document.tables[1].constraints = [item for item in document.tables[1].constraints if item.kind != "primary_key"]
    with pytest.raises(ValueError, match="needs a primary key"):
        generate_relational_dao.GenerateRelationalDaoUseCase().execute(document)


def test_dao_generation_rejects_reserved_aliases():
    document = relational.SchemaDocument.model_validate_json((FIXTURES / "valid.json").read_text())
    document.orm.tables[0].class_name = "Base"
    with pytest.raises(ValueError, match="class_name alias"):
        generate_relational_dao.GenerateRelationalDaoUseCase().execute(document)


def test_integer_primary_key_without_generation_does_not_become_serial(tmp_path):
    document = relational.SchemaDocument.model_validate({
        "namespaces": [{"id": "public", "name": {"name": "public"}}],
        "tables": [{"id": "thing", "namespace_id": "public", "name": {"name": "thing"},
            "columns": [{"id": "key", "name": {"name": "key"}, "type": {"name": "integer"}, "nullable": False}],
            "constraints": [{"id": "pk", "kind": "primary_key", "column_ids": ["key"]}]}],
    })
    source = generate_relational_dao.GenerateRelationalDaoUseCase().execute(document)
    destination = tmp_path / "plain.py"
    destination.write_text(source)
    specification = importlib.util.spec_from_file_location("plain", destination)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    try:
        sql = str(sa.schema.CreateTable(module.ThingDAO.__table__).compile(dialect=pg.dialect()))
        assert "SERIAL" not in sql
        assert module.ThingDAO.__table__.c.key.autoincrement is False
    finally:
        module.Base.registry.dispose()
