import logging
import typing
import uuid

import sqlglot
import sqlglot.expressions as expressions
import sqlglot.tokens as tokens

from devOS.domain import relational
from devOS.domain import relational_sql_schema


class ImportRelationalSqlUseCase:
    def __init__(self) -> None:
        pass

    def execute(self, source: str) -> relational.SchemaDocument:
        logging.info("Initializing a relational document from PostgreSQL creation SQL")
        normalized = relational_sql_schema.NormalizedCreationSql.from_source(source)
        try:
            statements = sqlglot.parse(normalized.source, read="postgres")
        except sqlglot.errors.ParseError as error:
            raise ValueError(
                f"Invalid or unsupported PostgreSQL creation syntax: {error}"
            ) from error
        document = relational.SchemaDocument()
        pending_constraints: list[relational_sql_schema.SqlConstraintInput] = []
        identity_position = 0

        def reject_options(
            expression: expressions.Expression, allowed: set[str]
        ) -> None:
            unexpected = [
                name
                for name, value in expression.args.items()
                if value and name not in allowed
            ]
            if unexpected:
                raise ValueError(
                    f"Unsupported {type(expression).__name__} options {', '.join(unexpected)}: {expression.sql(dialect='postgres')}"
                )

        # Register explicit namespaces and enum types before resolving column types.
        for statement in statements:
            if statement is None:
                continue
            if (
                isinstance(statement, expressions.Create)
                and statement.args.get("kind") == "SCHEMA"
            ):
                reject_options(statement, {"this", "kind"})
                identifier = relational.SqlIdentifier.from_postgres_ast(
                    statement.this.args["db"]
                )
                namespace_id = str(
                    uuid.uuid5(uuid.NAMESPACE_URL, "devos/namespace/" + identifier.name)
                )
                document.namespaces.append(
                    relational.Namespace(id=namespace_id, name=identifier)
                )
            elif isinstance(statement, expressions.Command):
                enum_tokens = sqlglot.Dialect.get_or_raise("postgres").tokenize(
                    statement.sql()
                )
                text = [token.text.upper() for token in enum_tokens]
                if len(text) < 8 or text[:2] != ["CREATE", "TYPE"]:
                    raise ValueError(f"Unsupported SQL statement {statement.sql()}")
                position = 2
                enum_identifier = relational.SqlIdentifier(
                    name=(
                        enum_tokens[position].text
                        if enum_tokens[position].token_type
                        == tokens.TokenType.IDENTIFIER
                        else enum_tokens[position].text.lower()
                    ),
                    quoted=enum_tokens[position].token_type
                    == tokens.TokenType.IDENTIFIER,
                )
                namespace_identifier = relational.SqlIdentifier(name="public")
                if enum_tokens[position + 1].token_type == tokens.TokenType.DOT:
                    namespace_identifier = enum_identifier
                    position += 2
                    enum_identifier = relational.SqlIdentifier(
                        name=(
                            enum_tokens[position].text
                            if enum_tokens[position].token_type
                            == tokens.TokenType.IDENTIFIER
                            else enum_tokens[position].text.lower()
                        ),
                        quoted=enum_tokens[position].token_type
                        == tokens.TokenType.IDENTIFIER,
                    )
                position += 1
                if (
                    text[position : position + 3] != ["AS", "ENUM", "("]
                    or enum_tokens[-1].token_type != tokens.TokenType.R_PAREN
                ):
                    raise ValueError(
                        "Only CREATE TYPE name AS ENUM (string labels) is supported"
                    )
                values = []
                expect_label = True
                for label_position in range(position + 3, len(enum_tokens) - 1):
                    expected_type = (
                        tokens.TokenType.STRING
                        if expect_label
                        else tokens.TokenType.COMMA
                    )
                    if enum_tokens[label_position].token_type != expected_type:
                        raise ValueError(
                            "Enum labels must be a comma-separated list of SQL strings"
                        )
                    if expected_type == tokens.TokenType.STRING:
                        values.append(enum_tokens[label_position].text)
                    expect_label = not expect_label
                if not values or enum_tokens[-2].token_type != tokens.TokenType.STRING:
                    raise ValueError(
                        "Enum labels must be nonempty and cannot have a trailing comma"
                    )
                namespace = next(
                    (
                        item
                        for item in document.namespaces
                        if item.name.name == namespace_identifier.name
                    ),
                    None,
                )
                if namespace is None:
                    namespace = relational.Namespace(
                        id=str(
                            uuid.uuid5(
                                uuid.NAMESPACE_URL,
                                "devos/namespace/" + namespace_identifier.name,
                            )
                        ),
                        name=namespace_identifier,
                    )
                    document.namespaces.append(namespace)
                enum_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"devos/enum/{namespace.id}/{enum_identifier.name}",
                    )
                )
                document.enums.append(
                    relational.EnumType(
                        id=enum_id,
                        namespace_id=namespace.id,
                        name=enum_identifier,
                        values=values,
                    )
                )

        for statement in statements:
            if (
                statement is None
                or not isinstance(statement, expressions.Create)
                or statement.args.get("kind") != "TABLE"
            ):
                continue
            reject_options(statement, {"this", "kind"})
            schema = statement.this
            if not isinstance(schema, expressions.Schema) or not isinstance(
                schema.this, expressions.Table
            ):
                raise ValueError(
                    "Only ordinary CREATE TABLE with explicit columns is supported"
                )
            table_name = relational_sql_schema.SqlTableName.from_postgres_ast(
                schema.this
            )
            namespace = next(
                (
                    item
                    for item in document.namespaces
                    if item.name.name == table_name.namespace.name
                ),
                None,
            )
            if namespace is None:
                namespace = relational.Namespace(
                    id=str(
                        uuid.uuid5(
                            uuid.NAMESPACE_URL,
                            "devos/namespace/" + table_name.namespace.name,
                        )
                    ),
                    name=table_name.namespace,
                )
                document.namespaces.append(namespace)
            table_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"devos/table/{namespace.id}/{table_name.name.name}",
                )
            )
            columns = []
            for member in schema.expressions:
                if not isinstance(member, expressions.ColumnDef):
                    pending_constraints.append(
                        relational_sql_schema.SqlConstraintInput(table_id, member)
                    )
                    continue
                reject_options(member, {"this", "kind", "constraints"})
                column_name = relational.SqlIdentifier.from_postgres_ast(member.this)
                column_id = str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"devos/column/{table_id}/{column_name.name}",
                    )
                )
                if not isinstance(member.kind, expressions.DataType):
                    raise ValueError(
                        f"Column {column_name.name} requires a supported SQL type"
                    )
                sql_type = relational.SqlType.from_postgres_ast(member.kind, document)
                serial = member.kind.this.value in {
                    "SERIAL",
                    "SMALLSERIAL",
                    "BIGSERIAL",
                }
                nullable = not serial
                default = None
                identity = None
                for constraint in member.args.get("constraints") or []:
                    kind = constraint.kind
                    if isinstance(kind, expressions.NotNullColumnConstraint):
                        reject_options(kind, {"allow_null"})
                        if constraint.this is not None:
                            raise ValueError(
                                "Named NOT NULL constraints are unsupported"
                            )
                        nullable = bool(kind.args.get("allow_null"))
                    elif isinstance(kind, expressions.DefaultColumnConstraint):
                        if default is not None or constraint.this is not None:
                            raise ValueError(
                                "Repeated or named defaults are unsupported"
                            )
                        default = kind.this.unnest().sql(dialect="postgres")
                    elif isinstance(
                        kind, expressions.GeneratedAsIdentityColumnConstraint
                    ):
                        if identity is not None or identity_position >= len(
                            normalized.identities
                        ):
                            raise ValueError(
                                "Unexpected or repeated identity generation"
                            )
                        identity = normalized.identities[identity_position]
                        identity_position += 1
                        nullable = False
                    else:
                        constraint_name = (
                            relational.SqlIdentifier.from_postgres_ast(constraint.this)
                            if constraint.this is not None
                            else None
                        )
                        pending_constraints.append(
                            relational_sql_schema.SqlConstraintInput(
                                table_id, kind, column_id, constraint_name
                            )
                        )
                columns.append(
                    relational.Column(
                        id=column_id,
                        name=column_name,
                        type=sql_type,
                        nullable=nullable,
                        default=default,
                        serial=serial,
                        identity=identity,
                    )
                )
            document.tables.append(
                relational.Table(
                    id=table_id,
                    namespace_id=namespace.id,
                    name=table_name.name,
                    columns=columns,
                )
            )

        # ALTER ADD constraints uses the same ordered key contract as inline syntax.
        for statement in statements:
            if not isinstance(statement, expressions.Alter):
                continue
            reject_options(statement, {"this", "kind", "actions"})
            if statement.args.get("kind") != "TABLE" or not isinstance(
                statement.this, expressions.Table
            ):
                raise ValueError("Only ALTER TABLE ADD constraints is supported")
            table_name = relational_sql_schema.SqlTableName.from_postgres_ast(
                statement.this
            )
            namespace = next(
                (
                    item
                    for item in document.namespaces
                    if item.name.name == table_name.namespace.name
                ),
                None,
            )
            table = next(
                (
                    item
                    for item in document.tables
                    if namespace
                    and item.namespace_id == namespace.id
                    and item.name.name == table_name.name.name
                ),
                None,
            )
            if table is None:
                raise ValueError(f"Unknown ALTER TABLE target {table_name.name.name}")
            for action in statement.args.get("actions") or []:
                if not isinstance(action, expressions.AddConstraint):
                    raise ValueError(
                        f"Unsupported ALTER action {action.sql(dialect='postgres')}"
                    )
                reject_options(action, {"expressions"})
                pending_constraints.extend(
                    relational_sql_schema.SqlConstraintInput(table.id, constraint)
                    for constraint in action.expressions
                )
        for pending in pending_constraints:
            table = next(
                item for item in document.tables if item.id == pending.table_id
            )
            table.constraints.append(pending.to_relational(document))

        for statement in statements:
            if statement is None:
                continue
            if (
                isinstance(statement, expressions.Create)
                and statement.args.get("kind") == "INDEX"
            ):
                reject_options(statement, {"this", "kind", "unique"})
                index = statement.this
                reject_options(index, {"this", "table", "params"})
                table_name = relational_sql_schema.SqlTableName.from_postgres_ast(
                    index.args["table"]
                )
                namespace = next(
                    (
                        item
                        for item in document.namespaces
                        if item.name.name == table_name.namespace.name
                    ),
                    None,
                )
                table = next(
                    (
                        item
                        for item in document.tables
                        if namespace
                        and item.namespace_id == namespace.id
                        and item.name.name == table_name.name.name
                    ),
                    None,
                )
                if table is None:
                    raise ValueError(f"Unknown index table {table_name.name.name}")
                parameters = index.args["params"]
                reject_options(parameters, {"using", "columns"})
                method = parameters.args.get("using")
                if method is not None and method.name.lower() != "btree":
                    raise ValueError("Only ordinary btree indexes are supported")
                column_ids = []
                for ordered_column in parameters.args.get("columns") or []:
                    if ordered_column.args.get("desc") or ordered_column.args.get(
                        "nulls_first"
                    ):
                        raise ValueError(
                            "Explicit descending/nulls-first index ordering is unsupported"
                        )
                    column = ordered_column.this
                    if not isinstance(column, expressions.Column) or column.table:
                        raise ValueError(
                            "Index expressions and qualified columns are unsupported"
                        )
                    name = relational.SqlIdentifier.from_postgres_ast(column.this).name
                    source_column = next(
                        (item for item in table.columns if item.name.name == name), None
                    )
                    if source_column is None:
                        raise ValueError(f"Unknown indexed column {name}")
                    column_ids.append(source_column.id)
                index_name = relational.SqlIdentifier.from_postgres_ast(index.this)
                table.indexes.append(
                    relational.Index(
                        id=str(
                            uuid.uuid5(
                                uuid.NAMESPACE_URL,
                                f"devos/index/{table.id}/{index_name.name}",
                            )
                        ),
                        name=index_name,
                        column_ids=column_ids,
                        unique=bool(statement.args.get("unique")),
                    )
                )
            elif isinstance(statement, expressions.Comment):
                reject_options(statement, {"this", "kind", "expression"})
                comment = statement.expression
                if (
                    not isinstance(comment, expressions.Literal)
                    or not comment.is_string
                ):
                    raise ValueError("Comments require a SQL string")
                kind = statement.args.get("kind")
                if kind == "SCHEMA":
                    name = relational.SqlIdentifier.from_postgres_ast(
                        statement.this
                    ).name
                    namespace = next(
                        (
                            item
                            for item in document.namespaces
                            if item.name.name == name
                        ),
                        None,
                    )
                    if namespace is None:
                        raise ValueError(f"Unknown commented namespace {name}")
                    namespace.description = comment.this
                elif kind in {"TABLE", "TYPE"}:
                    table_name = relational_sql_schema.SqlTableName.from_postgres_ast(
                        statement.this
                    )
                    namespace = next(
                        (
                            item
                            for item in document.namespaces
                            if item.name.name == table_name.namespace.name
                        ),
                        None,
                    )
                    candidates: list[relational.Table | relational.EnumType] = (
                        list(document.tables)
                        if kind == "TABLE"
                        else list(document.enums)
                    )
                    target = next(
                        (
                            item
                            for item in candidates
                            if namespace
                            and item.namespace_id == namespace.id
                            and item.name.name == table_name.name.name
                        ),
                        None,
                    )
                    if target is None:
                        raise ValueError(
                            f"Unknown commented {kind.lower()} {table_name.name.name}"
                        )
                    target.description = comment.this
                elif kind == "COLUMN" and isinstance(
                    statement.this, expressions.Column
                ):
                    commented_column = statement.this
                    namespace_name = (
                        relational.SqlIdentifier.from_postgres_ast(
                            commented_column.args["db"]
                        ).name
                        if commented_column.db
                        else "public"
                    )
                    table_name_text = relational.SqlIdentifier.from_postgres_ast(
                        commented_column.args["table"]
                    ).name
                    namespace = next(
                        (
                            item
                            for item in document.namespaces
                            if item.name.name == namespace_name
                        ),
                        None,
                    )
                    table = next(
                        (
                            item
                            for item in document.tables
                            if namespace
                            and item.namespace_id == namespace.id
                            and item.name.name == table_name_text
                        ),
                        None,
                    )
                    column_name_text = relational.SqlIdentifier.from_postgres_ast(
                        commented_column.this
                    ).name
                    column_target = (
                        next(
                            (
                                item
                                for item in table.columns
                                if item.name.name == column_name_text
                            ),
                            None,
                        )
                        if table
                        else None
                    )
                    if column_target is None:
                        raise ValueError(f"Unknown commented column {column_name_text}")
                    column_target.description = comment.this
                else:
                    raise ValueError(f"Unsupported COMMENT target {kind}")
            elif isinstance(statement, expressions.Create) and statement.args.get(
                "kind"
            ) in {"TABLE", "SCHEMA"}:
                continue
            elif not isinstance(statement, (expressions.Command, expressions.Alter)):
                raise ValueError(
                    f"Unsupported SQL statement {statement.sql(dialect='postgres')}"
                )
        if identity_position != len(normalized.identities):
            raise ValueError(
                "Identity input did not match the parsed column definitions"
            )
        result = relational.SchemaDocument.model_validate_json(
            document.model_dump_json()
        )
        logging.info("Imported relational document with %s tables", len(result.tables))
        return result
