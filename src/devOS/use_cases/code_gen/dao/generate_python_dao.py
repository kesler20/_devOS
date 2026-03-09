from devOS.use_cases.utils.file_io import File
import typing
import devOS.domain.entities as entities

# ===================== #
#                       #
#   Codegen helpers     #
#                       #
# ===================== #


def _is_primary_key(prop: entities.DAOSchemaProperty) -> bool:
    return bool(prop.key_type and prop.key_type.type in {"primary_key", "primary"})


def _is_foreign_key(prop: entities.DAOSchemaProperty) -> bool:
    return bool(prop.key_type and prop.key_type.type in {"foreign_key", "foreign"})


def _has_behavior(prop: entities.DAOSchemaProperty, behavior: str) -> bool:
    return bool(
        prop.key_type
        and prop.key_type.behaviors
        and behavior in prop.key_type.behaviors
    )


def _get_ondelete(prop: entities.DAOSchemaProperty) -> typing.Optional[str]:
    if not (prop.key_type and prop.key_type.behaviors):
        return None
    behaviors = set(prop.key_type.behaviors)
    if "ondelete_cascade" in behaviors or "delete_cascade" in behaviors:
        return "CASCADE"
    if "ondelete_set_null" in behaviors or "set_null" in behaviors:
        return "SET NULL"
    if "ondelete_restrict" in behaviors or "restrict" in behaviors:
        return "RESTRICT"
    return None


def get_property_type(prop: entities.DAOSchemaProperty) -> str:
    # NOTE: relationship "array" types are always a list at runtime (empty list vs None),
    # so we model them as List[T] even if `required` is false.
    if prop.type == "int":
        return "int" if prop.required else "typing.Optional[int]"
    if prop.type == "str":
        return "str" if prop.required else "typing.Optional[str]"
    if prop.type == "float":
        return "float" if prop.required else "typing.Optional[float]"
    if prop.type == "text":
        return "str" if prop.required else "typing.Optional[str]"
    if prop.type == "bool":
        return "bool" if prop.required else "typing.Optional[bool]"
    if prop.type == "datetime":
        return "datetime" if prop.required else "typing.Optional[datetime]"
    if prop.type == "enum" and prop.enum_name:
        return prop.enum_name if prop.required else f"typing.Optional[{prop.enum_name}]"
    if prop.type == "array" and prop.linked_property:
        return f"typing.List[{prop.linked_property.table}]"
    if prop.type == "object" and prop.linked_property:
        return (
            f"{prop.linked_property.table}"
            if prop.required
            else f"typing.Optional[{prop.linked_property.table}]"
        )
    if prop.type == "many_to_many" and prop.many_to_many:
        return (
            f"typing.List[{prop.linked_property.table}]"
            if prop.linked_property
            else "typing.List[typing.Any]"
        )
    return "typing.Any"


def _get_scalar_sa_type(prop: entities.DAOSchemaProperty) -> str:
    if prop.type == "int":
        return "sqlalchemy.Integer"
    if prop.type == "str":
        return "sqlalchemy.String"
    if prop.type == "float":
        return "sqlalchemy.Float"
    if prop.type == "bool":
        return "sqlalchemy.Boolean"
    if prop.type == "text":
        return "sqlalchemy.Text"
    if prop.type == "datetime":
        return "sqlalchemy.DateTime"
    if prop.type == "enum" and prop.enum_name:
        return f'sqlalchemy.Enum({prop.enum_name}, name="{prop.enum_name.lower()}")'
    return "sqlalchemy.String"


def _nullable_kw(prop: entities.DAOSchemaProperty) -> str:
    if _is_primary_key(prop):
        return ""
    # relationships don't use nullable
    if prop.type in {"array", "object", "many_to_many"}:
        return ""
    return "nullable=False" if prop.required else "nullable=True"


def _get_default_value(prop: entities.DAOSchemaProperty) -> typing.Optional[str]:
    """Get the default value expression for a property."""
    if prop.default_value is None:
        return None
    return prop.default_value


def generate_enum_code(enum_def: entities.DAOSchemaEnum) -> str:
    """Generate code for an enum definition."""
    code = f"class {enum_def.name}(enum.Enum):"
    if enum_def.description:
        code += f'\n    """{enum_def.description}"""'

    for member in enum_def.members:
        code += f'\n    {member.key} = "{member.value}"'

    code += "\n"
    return code


def generate_all_enums_code(specs: list[entities.DAOSchemaSpec]) -> str:
    """Generate code for all enums from all specs, avoiding duplicates."""
    seen_enums: dict[str, entities.DAOSchemaEnum] = {}

    for spec in specs:
        if spec.enums:
            for enum_def in spec.enums:
                if enum_def.name not in seen_enums:
                    seen_enums[enum_def.name] = enum_def

    if not seen_enums:
        return ""

    code = ""
    for enum_def in seen_enums.values():
        code += generate_enum_code(enum_def) + "\n"

    return code


def _mapped_column_lines(prop: entities.DAOSchemaProperty) -> list[str]:
    if prop.type in {"array", "object", "many_to_many"}:
        return []

    nullable_kw = _nullable_kw(prop)
    default_val = _get_default_value(prop)

    if _is_primary_key(prop):
        auto_inc = _has_behavior(prop, "auto_increment")
        sa_type = _get_scalar_sa_type(prop)
        extra = ", autoincrement=True" if auto_inc else ""
        return [
            f"    {prop.name}: sqlalchemy.orm.Mapped[{get_property_type(prop)}] = sqlalchemy.orm.mapped_column(",
            f"        {sa_type}, primary_key=True{extra}",
            f"    )",
        ]

    if _is_foreign_key(prop):
        ondelete = _get_ondelete(prop)
        fk_target = f"{prop.key_type.table}.{prop.key_type.column}"  # type: ignore
        if ondelete:
            fk_expr = f'sqlalchemy.ForeignKey("{fk_target}", ondelete="{ondelete}")'
        else:
            fk_expr = f'sqlalchemy.ForeignKey("{fk_target}")'

        extras = []
        if nullable_kw:
            extras.append(nullable_kw)
        if default_val:
            extras.append(f"default={default_val}")
        extras_str = ", " + ", ".join(extras) if extras else ""

        return [
            f"    {prop.name}: sqlalchemy.orm.Mapped[{get_property_type(prop)}] = sqlalchemy.orm.mapped_column(",
            f"        {fk_expr}{extras_str}",
            f"    )",
        ]

    sa_type = _get_scalar_sa_type(prop)
    extras = []
    if nullable_kw:
        extras.append(nullable_kw)
    if default_val:
        extras.append(f"default={default_val}")
    extras_str = ", " + ", ".join(extras) if extras else ""

    return [
        f"    {prop.name}: sqlalchemy.orm.Mapped[{get_property_type(prop)}] = sqlalchemy.orm.mapped_column({sa_type}{extras_str})"
    ]


def _find_fk_name_for_object_relationship(
    spec: entities.DAOSchemaSpec, rel_prop: entities.DAOSchemaProperty
) -> typing.Optional[str]:
    # Heuristic: "<relationship_name>_id" preferred, else first FK column.
    preferred = f"{rel_prop.name}_id"
    for p in spec.properties:
        if p.name == preferred and _is_foreign_key(p):
            return p.name
    for p in spec.properties:
        if _is_foreign_key(p):
            return p.name
    return None


def _relationship_lines(
    spec: entities.DAOSchemaSpec, prop: entities.DAOSchemaProperty
) -> list[str]:
    if prop.type == "many_to_many" and prop.many_to_many:
        return _many_to_many_relationship_lines(spec, prop)
    if not prop.linked_property:
        return []
    if prop.type == "array":
        lines = [
            f"    {prop.name}: sqlalchemy.orm.Mapped[{get_property_type(prop)}] = sqlalchemy.orm.relationship(",
        ]
        if prop.linked_property.property:
            lines.append(f'        back_populates="{prop.linked_property.property}",')
        if prop.linked_property.cascade:
            lines.append(f'        cascade="{prop.linked_property.cascade}",')
        if prop.linked_property.order_by:
            lines.append(f'        order_by="{prop.linked_property.order_by}",')
        if prop.linked_property.foreign_key:
            lines.append(f"        foreign_keys=[{prop.linked_property.foreign_key}],")
        lines.append(f"    )")
        return lines
    if prop.type == "object":
        lines = [
            f"    {prop.name}: sqlalchemy.orm.Mapped[{get_property_type(prop)}] = sqlalchemy.orm.relationship(",
        ]
        if prop.linked_property.property:
            lines.append(f'        back_populates="{prop.linked_property.property}",')
        if prop.linked_property.cascade:
            lines.append(f'        cascade="{prop.linked_property.cascade}",')
        if prop.linked_property.order_by:
            lines.append(f'        order_by="{prop.linked_property.order_by}",')
        if prop.linked_property.foreign_key:
            lines.append(f"        foreign_keys=[{prop.linked_property.foreign_key}],")
        else:
            fk_name = _find_fk_name_for_object_relationship(spec, prop)
            if fk_name:
                lines.append(f"        foreign_keys=[{fk_name}],")
        lines.append(f"    )")
        return lines
    return []


def _many_to_many_relationship_lines(
    spec: entities.DAOSchemaSpec, prop: entities.DAOSchemaProperty
) -> list[str]:
    """Generate relationship lines for many-to-many relationships."""
    m2m = prop.many_to_many
    if not m2m:
        return []

    target_type = prop.linked_property.table if prop.linked_property else "typing.Any"
    lines = [
        f"    {prop.name}: sqlalchemy.orm.Mapped[typing.List[{target_type}]] = sqlalchemy.orm.relationship(",
    ]

    # Convert the association table name to PascalCase to match the generated variable name
    assoc_table_var = entities.convert_to_pascal(m2m.association_table)

    if m2m.self_referential:
        # Self-referential many-to-many requires primaryjoin and secondaryjoin
        assoc_table_ref = f"association_dao.{assoc_table_var}"
        left_col = m2m.left_column or f"{prop.name}_id"
        right_col = m2m.right_column or f"related_{prop.name}_id"

        if m2m.primaryjoin:
            lines.append(f"        primaryjoin=lambda: {m2m.primaryjoin},")
        else:
            lines.append(
                f"        primaryjoin=lambda: {spec.name}.id == {assoc_table_var}.c.{left_col},"
            )

        if m2m.secondaryjoin:
            lines.append(f"        secondaryjoin=lambda: {m2m.secondaryjoin},")
        else:
            lines.append(
                f"        secondaryjoin=lambda: {spec.name}.id == {assoc_table_var}.c.{right_col},"
            )

        lines.append(f"        secondary={assoc_table_ref},")
    else:
        # Simple many-to-many with secondary table
        assoc_table_ref = f"association_dao.{assoc_table_var}"
        lines.append(f"        secondary={assoc_table_ref},")

        if prop.linked_property and prop.linked_property.property:
            lines.append(f'        back_populates="{prop.linked_property.property}",')

    lines.append(f"    )")
    return lines


# ================ #
#                  #
#   Codegen main   #
#                  #
# ================ #


def generate_association_table_code(
    assoc: entities.DAOSchemaAssociationTable,
) -> str:
    """Generate code for a simple association table (sqlalchemy.Table)."""
    variable_name = entities.convert_to_pascal(assoc.table_name)
    lines = [
        f"{variable_name} = sqlalchemy.Table(",
        f'    "{assoc.table_name}",',
        "    Base.metadata,",
    ]

    for col in assoc.columns:
        ondelete = f', ondelete="{col.ondelete}"' if col.ondelete else ""
        fk = f'sqlalchemy.ForeignKey("{col.foreign_key_table}.{col.foreign_key_column}"{ondelete})'
        pk = ", primary_key=True" if col.primary_key else ""
        lines.append(f"    sqlalchemy.Column(")
        lines.append(f'        "{col.name}",')
        lines.append(f"        {fk}{pk},")
        lines.append(f"    ),")

    lines.append(")")
    return "\n".join(lines) + "\n"


def generate_association_class_code(
    assoc: entities.DAOSchemaAssociationTable,
) -> str:
    """Generate code for an association class (explicit model with extra columns)."""
    class_name = assoc.class_name or entities.convert_to_pascal(assoc.table_name)
    code = f"""class {class_name}(Base):
    __tablename__ = "{assoc.table_name}"
"""

    # Generate foreign key columns
    for col in assoc.columns:
        ondelete = f', ondelete="{col.ondelete}"' if col.ondelete else ""
        fk = f'sqlalchemy.ForeignKey("{col.foreign_key_table}.{col.foreign_key_column}"{ondelete})'
        pk_str = ",\n        primary_key=True," if col.primary_key else ""
        col_type = "int" if col.type == "int" else "typing.Any"
        code += f"""
    {col.name}: sqlalchemy.orm.Mapped[{col_type}] = sqlalchemy.orm.mapped_column(
        {fk}{pk_str}
    )"""

    # Generate extra properties if any
    if assoc.extra_properties:
        for prop in assoc.extra_properties:
            lines = _mapped_column_lines(prop)
            if lines:
                code += "\n" + "\n".join(lines)

    # Generate unique constraints if any
    if assoc.unique_constraints:
        constraints = []
        for cols in assoc.unique_constraints:
            col_list = ", ".join(f'"{c}"' for c in cols)
            constraint_name = f"uq_{'_'.join(cols)}"
            constraints.append(
                f'        sqlalchemy.UniqueConstraint({col_list}, name="{constraint_name}"),'
            )
        code += f"""

    __table_args__ = (
{chr(10).join(constraints)}
    )"""

    code += "\n"
    return code


def generate_dao_code(spec: entities.DAOSchemaSpec) -> str:
    code = f"""class {spec.name}(Base):"""
    if spec.description:
        code += f"""
    \"\"\"{spec.description}\"\"\""""
    code += f"""
    __tablename__ = "{spec.table_name}"
"""

    for prop in spec.properties:
        lines = _mapped_column_lines(prop)
        if lines:
            code += "\n" + "\n".join(lines)

    for prop in spec.properties:
        lines = _relationship_lines(spec, prop)
        if lines:
            code += "\n" + "\n".join(lines)

    if spec.unique_constraints:
        constraints = []
        for cols in spec.unique_constraints:
            col_list = ", ".join(f'"{c}"' for c in cols)
            constraint_name = f"uq_{spec.table_name}_{'_'.join(cols)}"
            constraints.append(
                f'        sqlalchemy.UniqueConstraint({col_list}, name="{constraint_name}"),'
            )
        code += f"""\n\n    __table_args__ = (
{chr(10).join(constraints)}
    )"""

    # Generate __repr__ with class name and non-relationship fields
    non_rel_props = [
        p for p in spec.properties if p.type not in {"array", "object", "many_to_many"}
    ]

    if non_rel_props:
        repr_fields = ", ".join(f"{p.name}={{self.{p.name}!r}}" for p in non_rel_props)
        code += f"""

    def __repr__(self) -> str:
        return f"{spec.name}({repr_fields})"
"""

    code += "\n"
    return code


def generate_all_association_tables(specs: list[entities.DAOSchemaSpec]) -> str:
    """Generate all association tables from all specs."""
    code = ""
    for spec in specs:
        if not spec.association_tables:
            continue
        for assoc in spec.association_tables:
            has_extra_properties = (
                assoc.extra_properties and len(assoc.extra_properties) > 0
            )
            if has_extra_properties:
                code += generate_association_class_code(assoc) + "\n"
            else:
                code += generate_association_table_code(assoc) + "\n"
    return code


def generate_code_header() -> str:
    return """from __future__ import annotations
import typing
import enum
import sqlalchemy
import sqlalchemy.orm
from datetime import datetime, UTC
import project_name.domain.association_dao as association_dao
from project_name.domain.association_dao import Base

"""


def generate_association_dao_header() -> str:
    return """from __future__ import annotations
import typing
import sqlalchemy
import sqlalchemy.orm

class Base(sqlalchemy.orm.DeclarativeBase):
    pass

"""


def main():
    raw_specs = File("src", "devOS", "dao_spec.json").get_json()
    specs = [entities.DAOSchemaSpec.model_validate(raw_spec) for raw_spec in raw_specs]

    final_code = generate_code_header()

    # Generate all enums
    enums_code = generate_all_enums_code(specs)
    if enums_code:
        final_code += enums_code + "\n"

    # Generate DAO classes
    for spec in specs:
        final_code += generate_dao_code(spec) + "\n"

    File("src", "devOS", "generated_dao.py").write(final_code)

    # generate association_dao.py
    assoc_code = generate_association_dao_header()
    assoc_code += generate_all_association_tables(specs)
    File("src", "devOS", "association_dao.py").write(assoc_code)


if __name__ == "__main__":
    main()
