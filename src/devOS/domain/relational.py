from __future__ import annotations

import keyword
import dataclasses
import re
import typing

import pydantic
import sqlglot
import sqlglot.expressions

StableId = typing.Annotated[str, pydantic.Field(min_length=1)]
TypeName = typing.Literal[
    "smallint",
    "integer",
    "bigint",
    "numeric",
    "real",
    "double precision",
    "boolean",
    "text",
    "varchar",
    "char",
    "uuid",
    "date",
    "time",
    "timetz",
    "timestamp",
    "timestamptz",
    "interval",
    "bytea",
    "json",
    "jsonb",
    "enum",
]
ForeignKeyAction = typing.Literal[
    "NO ACTION",
    "RESTRICT",
    "CASCADE",
    "SET NULL",
    "SET DEFAULT",
]


@dataclasses.dataclass(frozen=True)
class DocumentContracts:
    json_schema: str
    typescript: str


class SqlIdentifier(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    name: str = pydantic.Field(min_length=1, max_length=63)
    quoted: bool = False

    @pydantic.model_validator(mode="after")
    def validate_name(self) -> SqlIdentifier:
        if "\x00" in self.name or len(self.name.encode("utf-8")) > 63:
            raise ValueError(
                "SQL identifiers must fit 63 UTF-8 bytes and contain no NUL"
            )
        if not self.quoted and not re.fullmatch(r"[a-z_][a-z0-9_$]*", self.name):
            raise ValueError("Unquoted identifiers must be lowercase SQL names")
        return self

    def render_sql(self) -> str:
        return '"' + self.name.replace('"', '""') + '"'

    @classmethod
    def from_postgres_ast(
        cls, identifier: sqlglot.expressions.Expression
    ) -> SqlIdentifier:
        if not isinstance(identifier, sqlglot.expressions.Identifier):
            raise ValueError(
                f"Expected a SQL identifier, got {identifier.sql(dialect='postgres')}"
            )
        quoted = bool(identifier.args.get("quoted"))
        return cls(
            name=identifier.name if quoted else identifier.name.lower(), quoted=quoted
        )


class SqlType(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    name: TypeName
    length: int | None = pydantic.Field(default=None, ge=1)
    precision: int | None = pydantic.Field(default=None, ge=1, le=1000)
    scale: int | None = pydantic.Field(default=None, ge=-1000, le=1000)
    time_precision: int | None = pydantic.Field(default=None, ge=0, le=6)
    enum_id: StableId | None = None
    array_dimensions: int = pydantic.Field(default=0, ge=0, le=6)

    @pydantic.model_validator(mode="after")
    def validate_parameters(self) -> SqlType:
        if self.length is not None and self.name not in {"varchar", "char"}:
            raise ValueError("length applies only to varchar/char")
        if (
            self.precision is not None or self.scale is not None
        ) and self.name != "numeric":
            raise ValueError("precision/scale apply only to numeric")
        if self.scale is not None and self.precision is None:
            raise ValueError("numeric scale requires precision")
        if self.time_precision is not None and self.name not in {
            "time",
            "timetz",
            "timestamp",
            "timestamptz",
            "interval",
        }:
            raise ValueError("time_precision applies only to temporal types")
        if (self.name == "enum") != (self.enum_id is not None):
            raise ValueError("enum types require enum_id, other types must omit it")
        return self

    def render_sql(self, document: SchemaDocument) -> str:
        if self.name == "enum":
            enum_type = next(item for item in document.enums if item.id == self.enum_id)
            namespace = next(
                item
                for item in document.namespaces
                if item.id == enum_type.namespace_id
            )
            scalar_type = (
                namespace.name.render_sql() + "." + enum_type.name.render_sql()
            )
        else:
            scalar_type = self.name.upper()
        if self.length is not None:
            scalar_type += f"({self.length})"
        if self.precision is not None:
            scalar_type += (
                f"({self.precision}"
                + (f", {self.scale}" if self.scale is not None else "")
                + ")"
            )
        if self.time_precision is not None:
            scalar_type += f"({self.time_precision})"
        return scalar_type + "[]" * self.array_dimensions

    def render_sqlalchemy(self, document: SchemaDocument) -> str:
        scalar_types = {
            "smallint": "sa.SmallInteger()",
            "integer": "sa.Integer()",
            "bigint": "sa.BigInteger()",
            "real": "pg.REAL()",
            "double precision": "pg.DOUBLE_PRECISION()",
            "boolean": "sa.Boolean()",
            "text": "sa.Text()",
            "uuid": "pg.UUID(as_uuid=True)",
            "date": "sa.Date()",
            "bytea": "sa.LargeBinary()",
            "json": "pg.JSON(none_as_null=True)",
            "jsonb": "pg.JSONB(none_as_null=True)",
        }
        if self.name == "enum":
            assert self.enum_id is not None
            scalar = "enum_" + str(
                next(
                    index
                    for index, item in enumerate(document.enums)
                    if item.id == self.enum_id
                )
            )
        elif self.name in {"varchar", "char"}:
            scalar = (
                "sa.String" if self.name == "varchar" else "sa.CHAR"
            ) + f"(length={self.length!r})"
        elif self.name == "numeric":
            scalar = f"sa.Numeric(precision={self.precision!r}, scale={self.scale!r})"
        elif self.name in {"timestamp", "timestamptz", "time", "timetz"}:
            constructor = (
                "pg.TIMESTAMP"
                if self.name in {"timestamp", "timestamptz"}
                else "pg.TIME"
            )
            timezone = self.name in {"timestamptz", "timetz"}
            scalar = f"{constructor}(timezone={timezone!r}, precision={self.time_precision!r})"
        elif self.name == "interval":
            scalar = f"pg.INTERVAL(precision={self.time_precision!r})"
        else:
            scalar = scalar_types[self.name]
        if self.array_dimensions:
            return f"pg.ARRAY({scalar}, dimensions={self.array_dimensions})"
        return scalar

    @classmethod
    def from_postgres_ast(
        cls, expression: sqlglot.expressions.DataType, document: SchemaDocument
    ) -> SqlType:
        dimensions = 0
        while expression.this == sqlglot.expressions.DataType.Type.ARRAY:
            if expression.args.get("values"):
                raise ValueError("Explicit PostgreSQL array bounds are unsupported")
            dimensions += 1
            if len(expression.expressions) != 1 or not isinstance(
                expression.expressions[0], sqlglot.expressions.DataType
            ):
                raise ValueError("Unsupported PostgreSQL array type")
            expression = expression.expressions[0]
        for name, value in expression.args.items():
            if value and name not in {"this", "kind", "expressions", "nested"}:
                raise ValueError(f"Unsupported SQL type option {name}")
        type_names: dict[str, TypeName] = {
            "SMALLINT": "smallint",
            "INT": "integer",
            "BIGINT": "bigint",
            "DECIMAL": "numeric",
            "FLOAT": "real",
            "DOUBLE": "double precision",
            "BOOLEAN": "boolean",
            "TEXT": "text",
            "VARCHAR": "varchar",
            "CHAR": "char",
            "UUID": "uuid",
            "DATE": "date",
            "TIME": "time",
            "TIMETZ": "timetz",
            "TIMESTAMP": "timestamp",
            "TIMESTAMPTZ": "timestamptz",
            "INTERVAL": "interval",
            "VARBINARY": "bytea",
            "JSON": "json",
            "JSONB": "jsonb",
            "SMALLSERIAL": "smallint",
            "SERIAL": "integer",
            "BIGSERIAL": "bigint",
        }
        type_name = expression.this.value
        if type_name == "USER-DEFINED":
            enum_name = expression.args.get("kind")
            if isinstance(enum_name, sqlglot.expressions.Dot):
                namespace_name = SqlIdentifier.from_postgres_ast(enum_name.this).name
                name = SqlIdentifier.from_postgres_ast(enum_name.expression).name
            elif isinstance(enum_name, sqlglot.expressions.Identifier):
                namespace_name = "public"
                name = SqlIdentifier.from_postgres_ast(enum_name).name
            else:
                raise ValueError(
                    f"Unsupported user-defined type {expression.sql(dialect='postgres')}"
                )
            namespaces = {
                namespace.id: namespace.name.name for namespace in document.namespaces
            }
            enum_type = next(
                (
                    item
                    for item in document.enums
                    if namespaces[item.namespace_id] == namespace_name
                    and item.name.name == name
                ),
                None,
            )
            if enum_type is None:
                raise ValueError(f"Unknown enum type {namespace_name}.{name}")
            return cls(name="enum", enum_id=enum_type.id, array_dimensions=dimensions)
        if type_name not in type_names:
            raise ValueError(
                f"Unsupported PostgreSQL type {expression.sql(dialect='postgres')}"
            )
        parameters = []
        for parameter in expression.expressions:
            parameter_text = parameter.sql(dialect="postgres")
            if not re.fullmatch(r"-?\d+", parameter_text):
                raise ValueError(f"Unsupported type parameter {parameter_text}")
            parameters.append(int(parameter_text))
        sql_type = cls(name=type_names[type_name], array_dimensions=dimensions)
        if parameters:
            if sql_type.name in {"varchar", "char"} and len(parameters) == 1:
                sql_type.length = parameters[0]
            elif sql_type.name == "numeric" and len(parameters) <= 2:
                sql_type.precision = parameters[0]
                sql_type.scale = parameters[1] if len(parameters) == 2 else None
            elif (
                sql_type.name
                in {"time", "timetz", "timestamp", "timestamptz", "interval"}
                and len(parameters) == 1
            ):
                sql_type.time_precision = parameters[0]
            else:
                raise ValueError(f"Unsupported parameters for {sql_type.name}")
        return cls.model_validate_json(sql_type.model_dump_json())


def validate_sequence_integer(value: object) -> int:
    if type(value) is int:
        if abs(typing.cast(int, value)) > 9007199254740991:
            raise ValueError(
                "Identity integers outside the JavaScript safe range must be decimal strings"
            )
        return typing.cast(int, value)
    if isinstance(value, str) and re.fullmatch(
        r"(?:0|[1-9][0-9]*|-[1-9][0-9]*)", value
    ):
        return int(value)
    raise ValueError("Identity options require an integer or canonical decimal string")


SequenceInteger = typing.Annotated[
    int,
    pydantic.BeforeValidator(
        validate_sequence_integer, json_schema_input_type=int | str
    ),
    pydantic.Field(ge=-9223372036854775808, le=9223372036854775807),
    pydantic.PlainSerializer(str, return_type=str, when_used="json"),
]


class Identity(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    generation: typing.Literal["always", "by_default"] = "by_default"
    start: SequenceInteger | None = None
    increment: SequenceInteger | None = None
    min_value: SequenceInteger | None = None
    max_value: SequenceInteger | None = None
    cache: SequenceInteger | None = pydantic.Field(default=None, ge=1)
    cycle: bool = False

    @pydantic.model_validator(mode="after")
    def validate_sequence(self) -> Identity:
        if self.increment == 0:
            raise ValueError("Identity increment must not be zero")
        if self.min_value is not None and self.max_value is not None:
            if self.min_value >= self.max_value:
                raise ValueError("Identity minimum must be below maximum")
        if self.start is not None:
            if self.min_value is not None and self.start < self.min_value:
                raise ValueError("Identity start must be at least minimum")
            if self.max_value is not None and self.start > self.max_value:
                raise ValueError("Identity start must be at most maximum")
        return self

    def render_sql(self) -> str:
        generation = "ALWAYS" if self.generation == "always" else "BY DEFAULT"
        settings = {
            "START WITH": self.start,
            "INCREMENT BY": self.increment,
            "MINVALUE": self.min_value,
            "MAXVALUE": self.max_value,
            "CACHE": self.cache,
        }
        options = [
            f"{name} {value}" for name, value in settings.items() if value is not None
        ]
        if self.cycle:
            options.append("CYCLE")
        result = f"GENERATED {generation} AS IDENTITY"
        return result + (" (" + " ".join(options) + ")" if options else "")


class Column(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    id: StableId
    name: SqlIdentifier
    type: SqlType
    nullable: bool = True
    description: str | None = None
    default: str | None = pydantic.Field(default=None, min_length=1)
    serial: bool = False
    identity: Identity | None = None

    @pydantic.model_validator(mode="after")
    def validate_generation(self) -> Column:
        if self.serial or self.identity is not None:
            if (
                self.type.name not in {"smallint", "integer", "bigint"}
                or self.type.array_dimensions
            ):
                raise ValueError("Serial/identity requires a scalar integer type")
            if self.serial and self.identity is not None or self.default is not None:
                raise ValueError(
                    "Serial, identity and explicit defaults are mutually exclusive"
                )
            if self.nullable:
                raise ValueError("Serial/identity columns must be non-nullable")
        return self

    def render_sql(self, document: SchemaDocument) -> str:
        sql_type = self.type.render_sql(document)
        if self.serial:
            sql_type = {
                "smallint": "SMALLSERIAL",
                "integer": "SERIAL",
                "bigint": "BIGSERIAL",
            }[self.type.name]
        result = self.name.render_sql() + " " + sql_type
        if self.identity is not None:
            result += " " + self.identity.render_sql()
        if self.default is not None:
            result += " DEFAULT (" + self.default + ")"
        if not self.nullable:
            result += " NOT NULL"
        return result

    def render_sqlalchemy(self, document: SchemaDocument, table: Table) -> str:
        namespace = next(
            item.name.name
            for item in document.namespaces
            if item.id == table.namespace_id
        )
        arguments = [repr(self.name.name), self.type.render_sqlalchemy(document)]
        if self.identity:
            identity = self.identity
            arguments.append(
                f"sa.Identity(always={identity.generation == 'always'!r}, start={identity.start!r}, increment={identity.increment!r}, minvalue={identity.min_value!r}, maxvalue={identity.max_value!r}, cache={identity.cache!r}, cycle={identity.cycle!r})"
            )
        if self.serial:
            sequence_name = table.name.name + "_" + self.name.name + "_seq"
            if len(sequence_name.encode("utf-8")) > 63:
                raise ValueError(
                    f"{self.id} serial sequence name exceeds the supported 63-byte limit"
                )
            sequence = f"sa.Sequence({sequence_name!r}, schema=sa.sql.quoted_name({namespace!r}, True), quote=True)"
            arguments.extend([sequence, "server_default=" + sequence + ".next_value()"])
        elif self.default is not None:
            arguments.append(f"server_default=sa.text({self.default!r})")
        if self.identity is None:
            arguments.append("autoincrement=False")
        arguments.extend(
            [
                f"nullable={self.nullable!r}",
                "quote=True",
                f"comment={self.description!r}",
                f"info={{'devos_id': {self.id!r}}}",
            ]
        )
        return "sa.Column(" + ", ".join(arguments) + ")"


def parse_sql_expression(expression: str) -> sqlglot.expressions.Expression:
    try:
        statements = sqlglot.parse("SELECT " + expression, read="postgres")
    except sqlglot.errors.ParseError as error:
        raise ValueError(f"Invalid SQL expression: {expression}") from error
    if len(statements) != 1 or not isinstance(
        statements[0], sqlglot.expressions.Select
    ):
        raise ValueError(
            "SQL expressions must contain a single expression, not statements"
        )
    statement = statements[0]
    if len(statement.expressions) != 1 or any(
        value for name, value in statement.args.items() if name != "expressions"
    ):
        raise ValueError(
            "SQL expressions must contain a single expression without query clauses"
        )
    result = statement.expressions[0]
    if any(
        result.find_all(
            sqlglot.expressions.Select,
            sqlglot.expressions.Subquery,
            sqlglot.expressions.Alias,
        )
    ):
        raise ValueError(
            "Queries and aliases are unsupported in default/check expressions"
        )
    return result


class Namespace(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    id: StableId
    name: SqlIdentifier
    description: str | None = None


class EnumType(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    id: StableId
    namespace_id: StableId
    name: SqlIdentifier
    values: list[str] = pydantic.Field(min_length=1)
    description: str | None = None

    @pydantic.field_validator("values")
    @classmethod
    def validate_values(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("Enum labels must be unique")
        if any("\x00" in value or len(value.encode("utf-8")) > 63 for value in values):
            raise ValueError("Enum labels must fit 63 UTF-8 bytes and contain no NUL")
        return values


class KeyConstraint(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    id: StableId
    kind: typing.Literal["primary_key", "unique"]
    name: SqlIdentifier | None = None
    column_ids: list[StableId] = pydantic.Field(min_length=1)
    deferrable: bool = False
    initially_deferred: bool = False

    def render_sql(self, table: Table) -> str:
        prefix = "CONSTRAINT " + self.name.render_sql() + " " if self.name else ""
        kind = "PRIMARY KEY" if self.kind == "primary_key" else "UNIQUE"
        result = prefix + kind + " (" + table.render_column_names(self.column_ids) + ")"
        if self.deferrable:
            result += " DEFERRABLE INITIALLY " + (
                "DEFERRED" if self.initially_deferred else "IMMEDIATE"
            )
        return result


class ForeignKey(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    id: StableId
    kind: typing.Literal["foreign_key"]
    name: SqlIdentifier | None = None
    column_ids: list[StableId] = pydantic.Field(min_length=1)
    target_table_id: StableId
    target_column_ids: list[StableId] = pydantic.Field(min_length=1)
    on_delete: ForeignKeyAction = "NO ACTION"
    on_update: ForeignKeyAction = "NO ACTION"
    match: typing.Literal["SIMPLE", "FULL"] = "SIMPLE"
    deferrable: bool = False
    initially_deferred: bool = False

    def render_sql(self, table: Table, document: SchemaDocument) -> str:
        target = next(
            item for item in document.tables if item.id == self.target_table_id
        )
        prefix = "CONSTRAINT " + self.name.render_sql() + " " if self.name else ""
        result = (
            prefix + "FOREIGN KEY (" + table.render_column_names(self.column_ids) + ")"
        )
        result += (
            " REFERENCES "
            + target.render_qualified_name(document)
            + " ("
            + target.render_column_names(self.target_column_ids)
            + ")"
        )
        result += (
            " MATCH "
            + self.match
            + " ON DELETE "
            + self.on_delete
            + " ON UPDATE "
            + self.on_update
        )
        if self.deferrable:
            result += " DEFERRABLE INITIALLY " + (
                "DEFERRED" if self.initially_deferred else "IMMEDIATE"
            )
        return result


class CheckConstraint(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    id: StableId
    kind: typing.Literal["check"]
    name: SqlIdentifier | None = None
    expression: str = pydantic.Field(min_length=1)

    def render_sql(self) -> str:
        prefix = "CONSTRAINT " + self.name.render_sql() + " " if self.name else ""
        return prefix + "CHECK (" + self.expression + ")"


Constraint = typing.Annotated[
    KeyConstraint | ForeignKey | CheckConstraint,
    pydantic.Field(discriminator="kind"),
]


class Index(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    id: StableId
    name: SqlIdentifier
    column_ids: list[StableId] = pydantic.Field(min_length=1)
    unique: bool = False
    method: typing.Literal["btree"] = "btree"


class Table(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    id: StableId
    namespace_id: StableId
    name: SqlIdentifier
    description: str | None = None
    columns: list[Column] = pydantic.Field(min_length=1)
    constraints: list[Constraint] = pydantic.Field(default_factory=list)
    indexes: list[Index] = pydantic.Field(default_factory=list)

    def render_qualified_name(self, document: SchemaDocument) -> str:
        namespace = next(
            item for item in document.namespaces if item.id == self.namespace_id
        )
        return namespace.name.render_sql() + "." + self.name.render_sql()

    def render_column_names(self, column_ids: list[str]) -> str:
        columns = {column.id: column for column in self.columns}
        return ", ".join(columns[value].name.render_sql() for value in column_ids)

    def validate_expressions(self) -> None:
        column_names = {column.name.name for column in self.columns}
        for column in self.columns:
            if column.default is not None:
                expression = parse_sql_expression(column.default)
                if any(expression.find_all(sqlglot.expressions.Column)):
                    raise ValueError(f"{column.id} default must not reference columns")
        for constraint in self.constraints:
            if isinstance(constraint, CheckConstraint):
                expression = parse_sql_expression(constraint.expression)
                for referenced_column in expression.find_all(
                    sqlglot.expressions.Column
                ):
                    if (
                        referenced_column.name not in column_names
                        or referenced_column.table
                    ):
                        raise ValueError(
                            f"{constraint.id} check references unknown or qualified column {referenced_column.sql()}"
                        )


class TablePosition(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    table_id: StableId
    x: float
    y: float
    color: str | None = pydantic.Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")


class Viewport(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)
    x: float = 0.0
    y: float = 0.0
    zoom: float = pydantic.Field(default=1.0, gt=0)


class DiagramLayout(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    tables: list[TablePosition] = pydantic.Field(default_factory=list)
    viewport: Viewport | None = None


class OrmTable(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    table_id: StableId
    class_name: str

    @pydantic.field_validator("class_name")
    @classmethod
    def validate_class_name(cls, value: str) -> str:
        cls.require_class_name(value)
        return value

    @staticmethod
    def require_class_name(value: str) -> None:
        if (
            not value.isidentifier()
            or keyword.iskeyword(value)
            or value in {"Base", "sa", "orm", "pg"}
            or value.startswith(("enum_", "table_"))
        ):
            raise ValueError(
                "ORM class_name alias must be a valid, non-reserved Python identifier"
            )


class OrmColumn(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    column_id: StableId
    attribute_name: str

    @pydantic.field_validator("attribute_name")
    @classmethod
    def validate_attribute_name(cls, value: str) -> str:
        cls.require_attribute_name(value)
        return value

    @staticmethod
    def require_attribute_name(value: str) -> None:
        if (
            not value.isidentifier()
            or keyword.iskeyword(value)
            or value in {"metadata", "registry"}
            or value.startswith("__")
        ):
            raise ValueError(
                "ORM attribute_name must be a valid, non-reserved Python identifier"
            )


class OrmNavigationBinding(typing.NamedTuple):
    table_id: str
    attribute_name: str


class OrmRelationship(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    foreign_key_id: StableId
    attribute_name: str
    reverse_attribute_name: str | None = None
    cascade: typing.Literal["save-update, merge", "all", "all, delete-orphan"] = (
        "save-update, merge"
    )

    @pydantic.field_validator("attribute_name", "reverse_attribute_name")
    @classmethod
    def validate_attribute_name(cls, value: str | None) -> str | None:
        if value is not None:
            OrmColumn.require_attribute_name(value)
        return value


class OrmConfiguration(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    tables: list[OrmTable] = pydantic.Field(default_factory=list)
    columns: list[OrmColumn] = pydantic.Field(default_factory=list)
    relationships: list[OrmRelationship] = pydantic.Field(default_factory=list)


class SchemaDocument(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)
    version: typing.Literal[1] = 1
    namespaces: list[Namespace] = pydantic.Field(default_factory=list)
    enums: list[EnumType] = pydantic.Field(default_factory=list)
    tables: list[Table] = pydantic.Field(default_factory=list)
    diagram: DiagramLayout | None = None
    orm: OrmConfiguration | None = None

    @pydantic.field_validator("version", mode="before")
    @classmethod
    def validate_version(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("Document version must be an integer")
        return value

    @pydantic.model_validator(mode="after")
    def validate_references(self) -> SchemaDocument:
        # IDs are document-wide identities, names are scoped SQL identities.
        objects: list[
            Namespace
            | EnumType
            | Table
            | Column
            | KeyConstraint
            | ForeignKey
            | CheckConstraint
            | Index
        ] = [
            *self.namespaces,
            *self.enums,
            *self.tables,
        ]
        for table in self.tables:
            objects.extend([*table.columns, *table.constraints, *table.indexes])
        identifiers = [item.id for item in objects]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Duplicate stable ID in document")
        namespace_ids = {item.id for item in self.namespaces}
        if len({item.name.name for item in self.namespaces}) != len(self.namespaces):
            raise ValueError("Duplicate namespace name")
        named_objects: list[EnumType | Table] = [*self.enums, *self.tables]
        qualified_names: dict[str, set[str]] = {}
        for item in named_objects:
            namespace_objects = qualified_names.setdefault(item.namespace_id, set())
            if item.name.name in namespace_objects:
                raise ValueError("Duplicate table/enum SQL name in namespace")
            namespace_objects.add(item.name.name)
        for item in named_objects:
            if item.namespace_id not in namespace_ids:
                raise ValueError(
                    f"{item.id} references missing namespace {item.namespace_id}"
                )
        enum_ids = {item.id for item in self.enums}
        tables = {item.id: item for item in self.tables}
        columns = {
            column.id: column for table in self.tables for column in table.columns
        }
        foreign_keys = {
            constraint.id: constraint
            for table in self.tables
            for constraint in table.constraints
            if isinstance(constraint, ForeignKey)
        }
        index_names: dict[str, set[str]] = {}
        for table in self.tables:
            table.validate_expressions()
            owned_columns = {column.id for column in table.columns}
            if len({column.name.name for column in table.columns}) != len(
                table.columns
            ):
                raise ValueError(f"Duplicate column name in {table.id}")
            constraint_names = [
                item.name.name for item in table.constraints if item.name is not None
            ]
            if len(set(constraint_names)) != len(constraint_names):
                raise ValueError(f"Duplicate constraint name in {table.id}")
            primary_keys = [
                item for item in table.constraints if item.kind == "primary_key"
            ]
            if len(primary_keys) > 1:
                raise ValueError(f"Multiple primary keys in {table.id}")
            for column in table.columns:
                if (
                    column.type.enum_id is not None
                    and column.type.enum_id not in enum_ids
                ):
                    raise ValueError(f"{column.id} references missing enum")
            for constraint in [*table.constraints, *table.indexes]:
                if isinstance(constraint, CheckConstraint):
                    continue
                if len(set(constraint.column_ids)) != len(constraint.column_ids):
                    raise ValueError(f"{constraint.id} repeats a key column")
                if not set(constraint.column_ids) <= owned_columns:
                    raise ValueError(
                        f"{constraint.id} references columns outside {table.id}"
                    )
                if isinstance(constraint, Index):
                    namespace_indexes = index_names.setdefault(
                        table.namespace_id, set()
                    )
                    if (
                        constraint.name.name in namespace_indexes
                        or constraint.name.name
                        in qualified_names.get(table.namespace_id, set())
                    ):
                        raise ValueError(
                            f"Duplicate index/relation name for {constraint.id}"
                        )
                    namespace_indexes.add(constraint.name.name)
                    continue
                if constraint.initially_deferred and not constraint.deferrable:
                    raise ValueError(
                        f"{constraint.id} initially_deferred requires deferrable"
                    )
                if isinstance(constraint, KeyConstraint):
                    if constraint.kind == "primary_key" and any(
                        columns[value].nullable for value in constraint.column_ids
                    ):
                        raise ValueError(
                            f"{constraint.id} primary key columns must be non-nullable"
                        )
                    continue
                target = tables.get(constraint.target_table_id)
                if target is None:
                    raise ValueError(f"{constraint.id} references missing target table")
                target_columns = {column.id for column in target.columns}
                if not set(constraint.target_column_ids) <= target_columns:
                    raise ValueError(
                        f"{constraint.id} references columns outside target table"
                    )
                if len(constraint.column_ids) != len(constraint.target_column_ids):
                    raise ValueError(
                        f"{constraint.id} foreign key pairs must have equal lengths"
                    )
                if len(set(constraint.target_column_ids)) != len(
                    constraint.target_column_ids
                ):
                    raise ValueError(f"{constraint.id} repeats a target column")
                target_keys = [
                    item
                    for item in target.constraints
                    if isinstance(item, KeyConstraint) and not item.deferrable
                ]
                target_indexes = [item for item in target.indexes if item.unique]
                unique_targets: list[KeyConstraint | Index] = [
                    *target_keys,
                    *target_indexes,
                ]
                if not any(
                    set(item.column_ids) == set(constraint.target_column_ids)
                    for item in unique_targets
                ):
                    raise ValueError(
                        f"{constraint.id} target is not a non-deferrable unique key"
                    )
        if self.diagram is not None:
            layout_ids = [item.table_id for item in self.diagram.tables]
            if (
                len(set(layout_ids)) != len(layout_ids)
                or not set(layout_ids) <= tables.keys()
            ):
                raise ValueError(
                    "Diagram contains duplicate or missing table references"
                )
        if self.orm is not None:
            alias_groups = {
                "table_id": [item.table_id for item in self.orm.tables],
                "column_id": [item.column_id for item in self.orm.columns],
                "foreign_key_id": [
                    item.foreign_key_id for item in self.orm.relationships
                ],
            }
            available_ids = {
                "table_id": set(tables),
                "column_id": set(columns),
                "foreign_key_id": set(foreign_keys),
            }
            for field, alias_ids in alias_groups.items():
                if (
                    len(set(alias_ids)) != len(alias_ids)
                    or not set(alias_ids) <= available_ids[field]
                ):
                    raise ValueError(f"ORM configuration has duplicate/missing {field}")
            names = [item.class_name for item in self.orm.tables]
            names.extend(item.attribute_name for item in self.orm.columns)
            names.extend(item.attribute_name for item in self.orm.relationships)
            names.extend(
                item.reverse_attribute_name
                for item in self.orm.relationships
                if item.reverse_attribute_name
            )
            if any(
                not value.isidentifier() or keyword.iskeyword(value) for value in names
            ):
                raise ValueError("ORM aliases must be Python identifiers")
            if len({item.class_name for item in self.orm.tables}) != len(
                self.orm.tables
            ):
                raise ValueError("ORM class names must be unique")
        return self
