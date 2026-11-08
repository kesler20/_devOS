from __future__ import annotations

import typing
import uuid

import sqlglot.expressions
import sqlglot.tokens

from devOS.domain import relational


class NormalizedCreationSql(typing.NamedTuple):
    source: str
    identities: list[relational.Identity]

    @classmethod
    def from_source(cls, source: str) -> NormalizedCreationSql:
        # SQLGlot's PostgreSQL parser lacks CACHE and arbitrary identity-option order.
        # Retain those options as typed input while giving it the basic identity AST.
        tokens = sqlglot.Dialect.get_or_raise("postgres").tokenize(source)
        for position, token in enumerate(tokens[:-1]):
            if (
                token.token_type
                not in {
                    sqlglot.tokens.TokenType.STRING,
                    sqlglot.tokens.TokenType.IDENTIFIER,
                }
                and token.text.upper() == "NOT"
                and tokens[position + 1].text.upper() == "ENFORCED"
            ):
                raise ValueError("NOT ENFORCED constraints are unsupported")
        identities = []
        replacements: dict[int, int] = {}
        for position, token in enumerate(tokens[:-1]):
            if (
                token.token_type
                not in {
                    sqlglot.tokens.TokenType.STRING,
                    sqlglot.tokens.TokenType.IDENTIFIER,
                }
                and token.text.upper() == "NOT"
                and tokens[position + 1].text.upper() == "DEFERRABLE"
            ):
                replacements[token.start] = tokens[position + 1].end + 1
        position = 0
        while position < len(tokens):
            token = tokens[position]
            if (
                token.token_type
                in {
                    sqlglot.tokens.TokenType.STRING,
                    sqlglot.tokens.TokenType.IDENTIFIER,
                }
                or token.text.upper() != "GENERATED"
            ):
                position += 1
                continue
            generation_position = position + 1
            if generation_position >= len(tokens):
                break
            generation = tokens[generation_position].text.upper()
            if generation == "ALWAYS":
                identity_position = generation_position + 2
                mode: typing.Literal["always", "by_default"] = "always"
            elif (
                generation == "BY"
                and generation_position + 1 < len(tokens)
                and tokens[generation_position + 1].text.upper() == "DEFAULT"
            ):
                identity_position = generation_position + 3
                mode = "by_default"
            else:
                position += 1
                continue
            if (
                identity_position >= len(tokens)
                or tokens[identity_position].text.upper() != "IDENTITY"
            ):
                position += 1
                continue
            identity = relational.Identity(generation=mode)
            option_position = identity_position + 1
            if (
                option_position < len(tokens)
                and tokens[option_position].token_type
                == sqlglot.tokens.TokenType.L_PAREN
            ):
                start_position = option_position
                option_position += 1
                seen = set()
                while (
                    option_position < len(tokens)
                    and tokens[option_position].token_type
                    != sqlglot.tokens.TokenType.R_PAREN
                ):
                    option = tokens[option_position].text.upper()
                    option_position += 1
                    negative_option = option == "NO"
                    if negative_option:
                        if option_position >= len(tokens):
                            raise ValueError("Incomplete identity sequence option")
                        option = tokens[option_position].text.upper()
                        option_position += 1
                    if option in {"START", "START WITH"}:
                        field = "start"
                        if (
                            option == "START"
                            and option_position < len(tokens)
                            and tokens[option_position].text.upper() == "WITH"
                        ):
                            option_position += 1
                    elif option in {"INCREMENT", "INCREMENT BY"}:
                        field = "increment"
                        if (
                            option == "INCREMENT"
                            and option_position < len(tokens)
                            and tokens[option_position].text.upper() == "BY"
                        ):
                            option_position += 1
                    elif option in {"MINVALUE", "MAXVALUE", "CACHE", "CYCLE"}:
                        field = {
                            "MINVALUE": "min_value",
                            "MAXVALUE": "max_value",
                            "CACHE": "cache",
                            "CYCLE": "cycle",
                        }[option]
                    else:
                        raise ValueError(f"Unsupported identity option {option}")
                    if (
                        field in seen
                        or negative_option
                        and option not in {"MINVALUE", "MAXVALUE", "CYCLE"}
                    ):
                        raise ValueError(
                            f"Repeated or invalid identity option {option}"
                        )
                    seen.add(field)
                    if option == "CYCLE":
                        identity.cycle = not negative_option
                        continue
                    if negative_option:
                        continue
                    sign = 1
                    if (
                        option_position < len(tokens)
                        and tokens[option_position].token_type
                        == sqlglot.tokens.TokenType.DASH
                    ):
                        sign = -1
                        option_position += 1
                    if (
                        option_position >= len(tokens)
                        or tokens[option_position].token_type
                        != sqlglot.tokens.TokenType.NUMBER
                        or not tokens[option_position].text.isdigit()
                    ):
                        raise ValueError(
                            f"Identity option {option} requires an integer"
                        )
                    setattr(
                        identity, field, str(sign * int(tokens[option_position].text))
                    )
                    option_position += 1
                if option_position >= len(tokens):
                    raise ValueError("Unterminated identity sequence options")
                replacements[tokens[start_position].start] = (
                    tokens[option_position].end + 1
                )
            identities.append(
                relational.Identity.model_validate_json(identity.model_dump_json())
            )
            position = option_position + 1
        normalized = source
        for start, end in sorted(replacements.items(), reverse=True):
            normalized = normalized[:start] + normalized[end:]
        return cls(normalized, identities)


class SqlTableName(typing.NamedTuple):
    namespace: relational.SqlIdentifier
    name: relational.SqlIdentifier

    @classmethod
    def from_postgres_ast(cls, table: sqlglot.expressions.Table) -> SqlTableName:
        if (
            table.catalog
            or table.args.get("alias")
            or any(
                value
                for name, value in table.args.items()
                if name not in {"this", "db"}
            )
        ):
            raise ValueError("Only namespace-qualified SQL table names are supported")
        namespace = (
            relational.SqlIdentifier.from_postgres_ast(table.args["db"])
            if table.db
            else relational.SqlIdentifier(name="public")
        )
        return cls(namespace, relational.SqlIdentifier.from_postgres_ast(table.this))


class SqlConstraintInput(typing.NamedTuple):
    table_id: str
    expression: sqlglot.expressions.Expression
    column_id: str | None = None
    name: relational.SqlIdentifier | None = None

    def to_relational(
        self, document: relational.SchemaDocument
    ) -> relational.Constraint:
        table = next(item for item in document.tables if item.id == self.table_id)
        expression = self.expression
        supported_arguments = {
            "this",
            "expressions",
            "options",
            "include",
            "nulls",
            "index_type",
            "enforced",
            "reference",
        }
        unknown_arguments = [
            field
            for field, value in expression.args.items()
            if value and field not in supported_arguments
        ]
        if unknown_arguments:
            raise ValueError(
                f"Unsupported constraint options {', '.join(unknown_arguments)}"
            )
        allowed_options = {
            "DEFERRABLE",
            "NOT DEFERRABLE",
            "INITIALLY DEFERRED",
            "INITIALLY IMMEDIATE",
        }
        options = expression.args.get("options") or []
        if not isinstance(
            expression, (sqlglot.expressions.Reference, sqlglot.expressions.ForeignKey)
        ) and any(value not in allowed_options for value in options):
            raise ValueError(
                f"Unsupported constraint options in {expression.sql(dialect='postgres')}"
            )
        deferrable = "DEFERRABLE" in options
        initially_deferred = "INITIALLY DEFERRED" in options
        name = self.name
        if isinstance(expression, sqlglot.expressions.Constraint):
            if len(expression.expressions) != 1:
                raise ValueError(
                    "A named constraint must contain one supported constraint"
                )
            name = relational.SqlIdentifier.from_postgres_ast(expression.this)
            return SqlConstraintInput(
                self.table_id, expression.expressions[0], self.column_id, name
            ).to_relational(document)
        identifier = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"devos/constraint/{table.id}/{len(table.constraints)}/{name.name if name else ''}",
            )
        )
        if isinstance(expression, sqlglot.expressions.CheckColumnConstraint):
            if expression.args.get("enforced"):
                raise ValueError("Explicit check enforcement options are unsupported")
            return relational.CheckConstraint(
                id=identifier,
                kind="check",
                name=name,
                expression=expression.this.sql(dialect="postgres"),
            )
        if isinstance(
            expression,
            (
                sqlglot.expressions.PrimaryKey,
                sqlglot.expressions.PrimaryKeyColumnConstraint,
                sqlglot.expressions.UniqueColumnConstraint,
            ),
        ):
            if (
                expression.args.get("nulls")
                or expression.args.get("index_type")
                or expression.args.get("on_conflict")
            ):
                raise ValueError(
                    "NULLS NOT DISTINCT and custom key indexes are unsupported"
                )
            index_parameters = expression.args.get("include")
            if index_parameters is not None and any(
                value for value in index_parameters.args.values()
            ):
                raise ValueError("Key index parameters are unsupported")
            if self.column_id is not None:
                column_ids = [self.column_id]
            else:
                column_expressions = (
                    expression.this.expressions
                    if isinstance(
                        expression, sqlglot.expressions.UniqueColumnConstraint
                    )
                    else expression.expressions
                )
                column_names = [
                    relational.SqlIdentifier.from_postgres_ast(item).name
                    for item in column_expressions
                ]
                column_ids = []
                for column_name in column_names:
                    column = next(
                        (
                            item
                            for item in table.columns
                            if item.name.name == column_name
                        ),
                        None,
                    )
                    if column is None:
                        raise ValueError(
                            f"Unknown key column {column_name} in {table.name.name}"
                        )
                    column_ids.append(column.id)
            kind: typing.Literal["unique", "primary_key"] = (
                "unique"
                if isinstance(expression, sqlglot.expressions.UniqueColumnConstraint)
                else "primary_key"
            )
            if kind == "primary_key":
                for column in table.columns:
                    if column.id in column_ids:
                        column.nullable = False
            return relational.KeyConstraint(
                id=identifier,
                kind=kind,
                name=name,
                column_ids=column_ids,
                deferrable=deferrable,
                initially_deferred=initially_deferred,
            )
        if isinstance(
            expression, (sqlglot.expressions.ForeignKey, sqlglot.expressions.Reference)
        ):
            reference = (
                expression.args["reference"]
                if isinstance(expression, sqlglot.expressions.ForeignKey)
                else expression
            )
            referenced_schema = reference.this
            if not isinstance(
                referenced_schema, sqlglot.expressions.Schema
            ) or not isinstance(referenced_schema.this, sqlglot.expressions.Table):
                raise ValueError(
                    "Foreign keys require an explicit referenced column list"
                )
            target_name = SqlTableName.from_postgres_ast(referenced_schema.this)
            namespace = next(
                (
                    item
                    for item in document.namespaces
                    if item.name.name == target_name.namespace.name
                ),
                None,
            )
            target = next(
                (
                    item
                    for item in document.tables
                    if namespace
                    and item.namespace_id == namespace.id
                    and item.name.name == target_name.name.name
                ),
                None,
            )
            if target is None:
                raise ValueError(
                    f"Unknown FK target {target_name.namespace.name}.{target_name.name.name}"
                )
            source_names = (
                [
                    relational.SqlIdentifier.from_postgres_ast(item).name
                    for item in expression.expressions
                ]
                if self.column_id is None
                else []
            )
            column_ids = [self.column_id] if self.column_id else []
            for source_name in source_names:
                column = next(
                    (item for item in table.columns if item.name.name == source_name),
                    None,
                )
                if column is None:
                    raise ValueError(f"Unknown foreign key column {source_name}")
                column_ids.append(column.id)
            target_names = [
                relational.SqlIdentifier.from_postgres_ast(item).name
                for item in referenced_schema.expressions
            ]
            target_ids = []
            for target_column_name in target_names:
                column = next(
                    (
                        item
                        for item in target.columns
                        if item.name.name == target_column_name
                    ),
                    None,
                )
                if column is None:
                    raise ValueError(f"Unknown target column {target_column_name}")
                target_ids.append(column.id)
            actions = {
                "on_delete": "NO ACTION",
                "on_update": "NO ACTION",
                "match": "SIMPLE",
            }
            reference_options = reference.args.get("options") or []
            for option in reference_options:
                if option.startswith("ON DELETE "):
                    actions["on_delete"] = option.removeprefix("ON DELETE ")
                elif option.startswith("ON UPDATE "):
                    actions["on_update"] = option.removeprefix("ON UPDATE ")
                elif option.startswith("MATCH "):
                    actions["match"] = option.removeprefix("MATCH ")
                elif option not in allowed_options:
                    raise ValueError(f"Unsupported foreign key option {option}")
            return relational.ForeignKey.model_validate(
                {
                    "id": identifier,
                    "kind": "foreign_key",
                    "name": name,
                    "column_ids": column_ids,
                    "target_table_id": target.id,
                    "target_column_ids": target_ids,
                    "on_delete": actions["on_delete"],
                    "on_update": actions["on_update"],
                    "match": actions["match"],
                    "deferrable": "DEFERRABLE" in reference_options,
                    "initially_deferred": "INITIALLY DEFERRED" in reference_options,
                }
            )
        raise ValueError(f"Unsupported constraint {expression.sql(dialect='postgres')}")
