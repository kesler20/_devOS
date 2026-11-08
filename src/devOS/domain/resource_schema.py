from __future__ import annotations

import dataclasses
import json
import keyword
import typing

import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as pg
import sqlalchemy.orm as orm

ResourceRole = typing.Literal["write", "patch", "read", "identity"]
ReadValueKind = typing.Literal[
    "numeric", "uuid", "enum", "bytes", "duration", "temporal"
]


@dataclasses.dataclass(frozen=True)
class ResourceContracts:
    python: str
    typescript: str


class ResourceField(typing.NamedTuple):
    name: str
    column: sa.Column[object]

    def accepts_role(self, role: ResourceRole) -> bool:
        if role == "identity":
            return self.column.primary_key
        if role == "patch":
            return not self.column.primary_key
        if role == "write":
            return self.column.identity is None or not self.column.identity.always
        return True

    def render_python_type(self) -> str:
        def render_scalar(sql_type: sa.types.TypeEngine) -> str:
            if isinstance(sql_type, pg.ARRAY):
                scalar = render_scalar(sql_type.item_type)
                result = "list[" + scalar + " | None]"
                for dimension in range(1, sql_type.dimensions or 1):
                    result = "list[" + result + "]"
                return (
                    "typing.Annotated["
                    + result
                    + ", pydantic.AfterValidator(validate_rectangular_array)]"
                )
            if isinstance(sql_type, sa.Enum):
                return (
                    "typing.Literal["
                    + ", ".join(repr(value) for value in sql_type.enums)
                    + "]"
                )
            if isinstance(sql_type, sa.BigInteger):
                return "BigIntegerString"
            if isinstance(sql_type, sa.Integer):
                minimum = (
                    -32768 if isinstance(sql_type, sa.SmallInteger) else -2147483648
                )
                maximum = 32767 if isinstance(sql_type, sa.SmallInteger) else 2147483647
                return f"typing.Annotated[int, pydantic.BeforeValidator(validate_integer), pydantic.Field(ge={minimum}, le={maximum})]"
            if isinstance(sql_type, sa.Float):
                return "pydantic.StrictFloat"
            if isinstance(sql_type, sa.Numeric):
                return "NumericString"
            if isinstance(sql_type, sa.Boolean):
                return "pydantic.StrictBool"
            if isinstance(sql_type, sa.Uuid):
                return "UUIDString"
            if isinstance(sql_type, sa.DateTime):
                return "DatetimeString"
            if isinstance(sql_type, sa.Date):
                return "DateString"
            if isinstance(sql_type, sa.Time):
                return "TimeString"
            if isinstance(sql_type, (sa.Interval, pg.INTERVAL)):
                return "DurationString"
            if isinstance(sql_type, sa.LargeBinary):
                return "BytesString"
            if isinstance(sql_type, sa.JSON):
                return "pydantic.JsonValue"
            if isinstance(sql_type, sa.String):
                if sql_type.length is not None:
                    return f"typing.Annotated[str, pydantic.StringConstraints(strict=True, max_length={sql_type.length})]"
                return "pydantic.StrictStr"
            raise ValueError(f"Unsupported DTO type for {self.name}: {sql_type}")

        return render_scalar(self.column.type)

    def render_zod_type(self) -> str:
        def render_scalar(sql_type: sa.types.TypeEngine) -> str:
            if isinstance(sql_type, pg.ARRAY):
                result = "z.array(" + render_scalar(sql_type.item_type) + ".nullable())"
                for dimension in range(1, sql_type.dimensions or 1):
                    result = "z.array(" + result + ")"
                return (
                    result
                    + ".refine(isRectangularArray, 'Array dimensions must be rectangular')"
                )
            if isinstance(sql_type, sa.Enum):
                return "z.enum(" + json.dumps(sql_type.enums) + ")"
            if isinstance(sql_type, sa.BigInteger):
                return "BigIntegerStringSchema"
            if isinstance(sql_type, sa.Integer):
                minimum = (
                    -32768 if isinstance(sql_type, sa.SmallInteger) else -2147483648
                )
                maximum = 32767 if isinstance(sql_type, sa.SmallInteger) else 2147483647
                return f"z.number().int().min({minimum}).max({maximum})"
            if isinstance(sql_type, sa.Float):
                return "z.number().finite()"
            if isinstance(sql_type, sa.Numeric):
                return "NumericStringSchema"
            if isinstance(sql_type, sa.Boolean):
                return "z.boolean()"
            if isinstance(sql_type, sa.Uuid):
                return "z.guid()"
            if isinstance(sql_type, sa.DateTime):
                return "DatetimeStringSchema"
            if isinstance(sql_type, sa.Date):
                return "DateStringSchema"
            if isinstance(sql_type, sa.Time):
                return "TimeStringSchema"
            if isinstance(sql_type, (sa.Interval, pg.INTERVAL)):
                return "DurationStringSchema"
            if isinstance(sql_type, sa.LargeBinary):
                return "BytesStringSchema"
            if isinstance(sql_type, sa.JSON):
                return "z.json()"
            if isinstance(sql_type, sa.String):
                if sql_type.length is not None:
                    return f"z.string().refine(value => Array.from(value).length <= {sql_type.length}, 'String exceeds column length')"
                return "z.string()"
            raise ValueError(f"Unsupported DTO type for {self.name}: {sql_type}")

        return render_scalar(self.column.type)

    def render_python_field(self, role: ResourceRole) -> str:
        annotation = self.render_python_type()
        if self.column.nullable:
            annotation += " | None"
        default = " = pydantic.Field(default=None)" if self.is_optional(role) else ""
        return f"    {self.name}: {annotation}{default}"

    def render_zod_field(self, role: ResourceRole) -> str:
        annotation = self.render_zod_type()
        if self.column.nullable:
            annotation += ".nullable()"
        if self.is_optional(role):
            annotation += ".optional()"
        return "  " + json.dumps(self.name) + ": " + annotation + ","

    def is_optional(self, role: ResourceRole) -> bool:
        if role == "patch":
            return True
        if role == "write":
            return (
                self.column.nullable
                or self.column.default is not None
                or self.column.server_default is not None
                or self.column.identity is not None
                or self.column
                is typing.cast(sa.Table, self.column.table).autoincrement_column
            )
        return False

    def render_read_conversion(self) -> str | None:
        kind: ReadValueKind
        sql_type = self.column.type
        dimensions = 0
        if isinstance(sql_type, pg.ARRAY):
            dimensions = sql_type.dimensions or 1
            sql_type = sql_type.item_type
        if isinstance(sql_type, (sa.BigInteger, sa.Numeric)) and not isinstance(
            sql_type, sa.Float
        ):
            kind = "numeric"
        elif isinstance(sql_type, sa.Uuid):
            kind = "uuid"
        elif isinstance(sql_type, sa.Enum):
            kind = "enum"
        elif isinstance(sql_type, sa.LargeBinary):
            kind = "bytes"
        elif isinstance(sql_type, (sa.Interval, pg.INTERVAL)):
            kind = "duration"
        elif isinstance(sql_type, (sa.DateTime, sa.Date, sa.Time)):
            kind = "temporal"
        else:
            return None
        return f"        values[{self.name!r}] = convert_read_value(values[{self.name!r}], {kind!r}, {dimensions})"


@dataclasses.dataclass(frozen=True)
class MappedResource:
    mapper: orm.Mapper

    def get_name(self) -> str:
        name = self.mapper.class_.__name__.removesuffix("DAO")
        if not name or not name.isidentifier():
            raise ValueError("Resource names must be Python identifiers")
        return name

    def get_fields(self) -> list[ResourceField]:
        fields = [
            ResourceField(
                attribute.key, typing.cast(sa.Column[object], attribute.columns[0])
            )
            for attribute in self.mapper.column_attrs
        ]
        for field in fields:
            if (
                not field.name.isidentifier()
                or keyword.iskeyword(field.name)
                or field.name.startswith("_")
                or field.name.startswith("model_")
            ):
                raise ValueError(
                    f"{field.name!r} requires an ORM alias usable as a DTO field"
                )
        return fields

    def get_identity_fields(self) -> list[ResourceField]:
        fields = {field.column: field for field in self.get_fields()}
        return [
            fields[typing.cast(sa.Column[object], column)]
            for column in self.mapper.primary_key
        ]
