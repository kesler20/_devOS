import pathlib

import pytest
import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg

from devOS.domain import relational
from devOS.use_cases import generate_relational_sql
from devOS.use_cases import generate_relational_dao


FIXTURES = pathlib.Path(__file__).parent / "fixtures/relational"


def assert_matching_postgres_type(actual, expected, dialect):
    if isinstance(expected, pg.ENUM):
        assert actual.name == expected.name
        assert actual.schema == expected.schema
        assert actual.enums == expected.enums
    elif isinstance(expected, pg.ARRAY):
        assert isinstance(actual, pg.ARRAY)
        assert_matching_postgres_type(actual.item_type, expected.item_type, dialect)
    elif isinstance(expected, sa.CHAR) and expected.length is None:
        assert actual.length == 1
    else:
        assert str(actual.compile(dialect=dialect)) == str(expected.compile(dialect=dialect))


@pytest.mark.parametrize("fixture", sorted(FIXTURES.glob("valid*.json")), ids=lambda path: path.stem)
@pytest.mark.parametrize("creation", ["sql", "dao"])
def test_creation_sql_and_generated_dao_match_postgres18(postgres_database, fixture, creation):
    document = relational.SchemaDocument.model_validate_json(fixture.read_text())
    sql = generate_relational_sql.GenerateRelationalSqlUseCase().execute(document)
    scope = {}
    exec(generate_relational_dao.GenerateRelationalDaoUseCase().execute(document), scope)
    metadata = scope["Base"].metadata
    try:
        if creation == "sql":
            with postgres_database.begin() as connection:
                connection.exec_driver_sql(sql)
        else:
            with postgres_database.begin() as connection:
                for namespace in document.namespaces:
                    if namespace.name.name != "public":
                        connection.exec_driver_sql("CREATE SCHEMA " + namespace.name.render_sql())
            metadata.create_all(postgres_database)
        inspector = sa.inspect(postgres_database)
        for namespace in document.namespaces:
            for table in document.tables:
                if table.namespace_id != namespace.id:
                    continue
                generated = metadata.tables[namespace.name.name + "." + table.name.name]
                actual_columns = inspector.get_columns(table.name.name, schema=namespace.name.name)
                assert [column["name"] for column in actual_columns] == [column.name.name for column in table.columns]
                for actual, expected in zip(actual_columns, generated.columns):
                    assert actual["nullable"] == expected.nullable
                    assert_matching_postgres_type(actual["type"], expected.type, postgres_database.dialect)
                    if expected.identity is not None:
                        assert actual["identity"]["always"] == expected.identity.always
                primary_key = inspector.get_pk_constraint(table.name.name, schema=namespace.name.name)
                assert primary_key["constrained_columns"] == [column.name for column in generated.primary_key]
                assert inspector.get_table_comment(table.name.name, schema=namespace.name.name)["text"] == generated.comment
                assert len(inspector.get_check_constraints(table.name.name, schema=namespace.name.name)) == len([item for item in generated.constraints if isinstance(item, sa.CheckConstraint)])
                actual_keys = inspector.get_foreign_keys(table.name.name, schema=namespace.name.name)
                expected_keys = list(generated.foreign_key_constraints)
                assert len(actual_keys) == len(expected_keys)
                for key in actual_keys:
                    expected = next(item for item in expected_keys if [element.parent.name for element in item.elements] == key["constrained_columns"])
                    assert key["referred_columns"] == [element.column.name for element in expected.elements]
                    assert key["referred_table"] == expected.referred_table.name
                    assert key["options"].get("ondelete", "NO ACTION") == expected.ondelete
                    assert key["options"].get("onupdate", "NO ACTION") == expected.onupdate
                    assert key["options"].get("deferrable", False) == expected.deferrable
    finally:
        scope["Base"].registry.dispose()


def test_large_identity_creation_preserves_exact_value(postgres_database):
    document = relational.SchemaDocument.model_validate_json((FIXTURES / "valid-large-identity.json").read_text())
    sql = generate_relational_sql.GenerateRelationalSqlUseCase().execute(document)
    with postgres_database.begin() as connection:
        connection.exec_driver_sql(sql)
        identity = connection.exec_driver_sql('INSERT INTO "public"."generated" DEFAULT VALUES RETURNING "key"').scalar_one()
    assert identity == 9007199254740993
    portable = document.model_dump_json()
    assert '"start":"9007199254740993"' in portable
    assert relational.SchemaDocument.model_validate_json(portable) == document
