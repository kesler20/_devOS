from __future__ import annotations
import re

from devOS.domain import entities
import devOS.use_cases.utils.file_io as file_io

# Maps common SQL DDL types to devOS's DAOSchemaProperty.type vocabulary
# (int, str, text, bool, float, datetime, enum, array, object, many_to_many).
# drawSQL's SQL export always emits one of these base type names, optionally
# with a size/precision argument (e.g. VARCHAR(255), DECIMAL(10,2)) which this
# converter ignores rather than modelling column width.
SQL_TYPE_TO_SPEC_TYPE = {
    "int": "int",
    "integer": "int",
    "bigint": "int",
    "smallint": "int",
    "serial": "int",
    "bigserial": "int",
    "varchar": "str",
    "char": "str",
    "string": "str",
    "text": "text",
    "longtext": "text",
    "mediumtext": "text",
    "bool": "bool",
    "boolean": "bool",
    "float": "float",
    "double": "float",
    "decimal": "float",
    "numeric": "float",
    "real": "float",
    "date": "datetime",
    "datetime": "datetime",
    "timestamp": "datetime",
    "timestamptz": "datetime",
}

CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`]?(\w+)[\"`]?\s*\((.*?)\)\s*;",
    re.IGNORECASE | re.DOTALL,
)
INLINE_FK_RE = re.compile(
    r"REFERENCES\s+[\"`]?(\w+)[\"`]?\s*\(\s*[\"`]?(\w+)[\"`]?\s*\)", re.IGNORECASE
)
TABLE_FK_RE = re.compile(
    r"FOREIGN\s+KEY\s*\(\s*[\"`]?(\w+)[\"`]?\s*\)\s*"
    r"REFERENCES\s+[\"`]?(\w+)[\"`]?\s*\(\s*[\"`]?(\w+)[\"`]?\s*\)",
    re.IGNORECASE,
)
TABLE_PK_RE = re.compile(r"PRIMARY\s+KEY\s*\(([^)]+)\)", re.IGNORECASE)
TYPE_RE = re.compile(r"^[\"`]?(\w+)[\"`]?\s+([a-zA-Z][\w]*)\s*(?:\([^)]*\))?")


def convert_drawsql_to_spec(sql: str) -> list[entities.DAOSchemaSpec]:
    """Convert a drawSQL SQL DDL export into devOS `DAOSchemaSpec` entries.

    Handles the common drawSQL SQL-export shape: one `CREATE TABLE` per
    entity, inline column-level `PRIMARY KEY`/`REFERENCES`, and table-level
    `PRIMARY KEY (...)`/`FOREIGN KEY (...) REFERENCES ...` clauses. Does not
    infer many-to-many associations or synthesize the reverse
    (one-to-many/object) side of a relationship the way the ReactFlow
    drawORM builder (`set_dao_spec.build_dao_spec`) does - each foreign key
    is emitted as a single `key_type` on the owning column, since SQL DDL
    already states the relationship explicitly rather than needing it
    derived from a diagram.
    """

    def split_top_level(body: str) -> list[str]:
        """Split a CREATE TABLE body on commas, ignoring commas inside parens
        (needed for types like DECIMAL(10,2))."""
        parts: list[str] = []
        depth = 0
        current: list[str] = []
        for char in body:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            if char == "," and depth == 0:
                parts.append("".join(current))
                current = []
            else:
                current.append(char)
        if current:
            parts.append("".join(current))
        return [p.strip() for p in parts if p.strip()]

    def to_pascal_case(name: str) -> str:
        parts = [p for p in re.split(r"[_\-\s]+", name) if p]
        return "".join(p[:1].upper() + p[1:].lower() for p in parts) or name

    specs: list[entities.DAOSchemaSpec] = []

    for match in CREATE_TABLE_RE.finditer(sql):
        table_name = match.group(1)
        body = match.group(2)
        lines = split_top_level(body)

        properties: list[entities.DAOSchemaProperty] = []
        table_level_pk_columns: list[str] = []
        table_level_fks: dict[str, tuple[str, str]] = {}

        for line in lines:
            pk_match = TABLE_PK_RE.match(line)
            if pk_match:
                table_level_pk_columns = [
                    c.strip().strip('"`') for c in pk_match.group(1).split(",")
                ]
                continue

            fk_match = TABLE_FK_RE.match(line)
            if fk_match:
                column, ref_table, ref_column = fk_match.groups()
                table_level_fks[column] = (ref_table, ref_column)
                continue

            if re.match(r"^(UNIQUE|CONSTRAINT|CHECK|INDEX|KEY)\b", line, re.IGNORECASE):
                continue

            type_match = TYPE_RE.match(line)
            if not type_match:
                continue
            column_name, sql_type = type_match.groups()
            spec_type = SQL_TYPE_TO_SPEC_TYPE.get(sql_type.lower(), "str")

            required = bool(re.search(r"\bNOT\s+NULL\b", line, re.IGNORECASE))
            is_inline_pk = bool(re.search(r"\bPRIMARY\s+KEY\b", line, re.IGNORECASE))

            key_type = None
            if is_inline_pk:
                key_type = entities.DAOSchemaKeyType(
                    type="primary_key", behaviors=["auto_increment"]
                )
                required = True

            inline_fk = INLINE_FK_RE.search(line)
            if inline_fk:
                ref_table, ref_column = inline_fk.groups()
                key_type = entities.DAOSchemaKeyType(
                    type="foreign_key",
                    table=ref_table,
                    column=ref_column,
                    behaviors=["ondelete_cascade"],
                )

            properties.append(
                entities.DAOSchemaProperty(
                    name=column_name.lower(),
                    type=spec_type,
                    required=required or None,
                    key_type=key_type,
                )
            )

        for prop in properties:
            if prop.key_type is not None:
                continue
            if prop.name in table_level_pk_columns:
                prop.key_type = entities.DAOSchemaKeyType(
                    type="primary_key", behaviors=["auto_increment"]
                )
                prop.required = True
            elif prop.name in table_level_fks:
                ref_table, ref_column = table_level_fks[prop.name]
                prop.key_type = entities.DAOSchemaKeyType(
                    type="foreign_key",
                    table=ref_table,
                    column=ref_column,
                    behaviors=["ondelete_cascade"],
                )

        specs.append(
            entities.DAOSchemaSpec(
                name=to_pascal_case(table_name),
                table_name=table_name.lower(),
                properties=properties,
            )
        )

    return specs


class ConvertDrawsqlToSpecUseCase:
    def execute(self, sql_path: str) -> None:
        """
        Convert a drawSQL SQL export at `sql_path` into a DAO spec.

        Side Effects
        ------------
        Overwrites `specs/dao_spec.json` with the converted spec.
        """
        sql = file_io.File(sql_path).read_as_utf8()
        specs = convert_drawsql_to_spec(sql)
        file_io.File("specs", "dao_spec.json").write_json(
            [spec.model_dump() for spec in specs]
        )
        print(
            f"Converted {len(specs)} table(s) from {sql_path} to specs/dao_spec.json."
        )
