import pathlib

import pytest
import sqlglot

from devOS.domain import relational
from devOS.use_cases import generate_relational_sql
from devOS import relational_cli


FIXTURE = pathlib.Path(__file__).parent / "fixtures/relational/valid.json"


def test_creation_sql_preserves_supported_schema_semantics():
    document = relational.SchemaDocument.model_validate_json(FIXTURE.read_text())
    generator = generate_relational_sql.GenerateRelationalSqlUseCase()
    sql = generator.execute(document)
    assert sql == generator.execute(document)
    assert 'CREATE SCHEMA "App Schema"' in sql
    assert "AS ENUM ('draft', 'active')" in sql
    assert 'NUMERIC(20, 4)' in sql
    assert 'VARCHAR(60)[]' in sql
    assert 'TIMESTAMPTZ(3)' in sql
    assert 'GENERATED ALWAYS AS IDENTITY' in sql
    assert 'PRIMARY KEY ("tenant_id", "id")' in sql
    assert 'FOREIGN KEY ("tenant_id", "parent_id") REFERENCES "App Schema"."Parent" ("tenant_id", "id")' in sql
    assert 'ON DELETE CASCADE ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED' in sql
    assert sql.index('CREATE TABLE "App Schema"."child"') < sql.index('ALTER TABLE')
    assert 'CREATE INDEX "parent_state_idx"' in sql
    assert 'CHECK (amount >= 0)' in sql
    assert len(sqlglot.parse(sql, read="postgres")) == 7


def test_sql_escapes_comments_and_enum_labels():
    document = relational.SchemaDocument.model_validate_json(FIXTURE.read_text())
    document.tables[0].description = "Owner's table"
    document.enums[0].values.append("owner's")
    sql = generate_relational_sql.GenerateRelationalSqlUseCase().execute(document)
    assert "'Owner''s table'" in sql
    assert "'owner''s'" in sql


@pytest.mark.parametrize("expression", ["1; DROP TABLE users", "1, 2", "1 FROM users", "(SELECT 1)", "1 AS alias"])
def test_sql_rejects_statements_and_queries_in_expressions(expression):
    document = relational.SchemaDocument.model_validate_json(FIXTURE.read_text())
    document.tables[0].columns[-1].default = expression
    with pytest.raises(ValueError, match="expressions"):
        generate_relational_sql.GenerateRelationalSqlUseCase().execute(document)


def test_sql_rejects_unknown_check_columns_before_writing(tmp_path):
    document = relational.SchemaDocument.model_validate_json(FIXTURE.read_text())
    document.tables[0].constraints[-1].expression = "missing_column > 0"
    source = tmp_path / "schema.json"
    source.write_text(document.model_dump_json())
    destination = tmp_path / "schema.sql"
    destination.write_text("preserve")
    assert relational_cli.main(["sql", str(source), "--output", str(destination)]) == 1
    assert destination.read_text() == "preserve"


def test_sql_command_outside_git_preserves_source(tmp_path, monkeypatch):
    source = tmp_path / "schema.json"
    source.write_text(FIXTURE.read_text())
    monkeypatch.chdir(tmp_path)
    assert relational_cli.main(["sql", "schema.json", "--output", "schema.sql"]) == 0
    assert (tmp_path / "schema.sql").read_text().startswith("-- Generated")
    original = source.read_text()
    assert relational_cli.main(["sql", "schema.json", "--output", "schema.json"]) == 1
    assert source.read_text() == original
