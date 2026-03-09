from devOS.use_cases.utils.file_io import File
import devOS.domain.entities as entities
import devOS.use_cases.utils.codegen_helpers as codegen_utils


# ===================== #
#                       #
#   GENERATE SCHEMA     #
#                       #
# ===================== #


def is_relationship_property(prop: entities.DAOSchemaProperty) -> bool:
    """Check if a property represents a relationship (one-to-many, many-to-one, many-to-many).

    A property is a relationship if:
    - type is "array" or "object" AND linked_property is set (one-to-many / one-to-one)
    - type is "many_to_many" OR many_to_many config is set
    """
    if prop.type in {"array", "object"} and prop.linked_property is not None:
        return True
    if prop.type == "many_to_many" or prop.many_to_many is not None:
        return True
    return False


def get_relationship_type_for_read(
    prop: entities.DAOSchemaProperty, dao_spec: entities.DAOSchemaSpec
) -> str:
    """Get the Python type annotation for a relationship field in ReadRelationship DTO.

    Relationship fields reference other entities' SHALLOW Read DTOs only.

    Parameters
    ----------
    prop : entities.DAOSchemaProperty
        The property to generate a type for.
    dao_spec : entities.DAOSchemaSpec
        The DAO spec containing association table definitions.

    Returns
    -------
    str
        The Python type annotation for the relationship field.
    """
    if prop.linked_property is not None:
        related_entity_name = entities.convert_to_pascal(prop.linked_property.table)
        if prop.type == "array":
            return f"list[{related_entity_name}Read]"
        elif prop.type == "object":
            return f"{related_entity_name}Read | None"
    if prop.many_to_many is not None:
        # For many-to-many, derive the related entity from the association table
        # Look up the association table and find the "other" foreign key column
        assoc_table_name = prop.many_to_many.association_table
        if dao_spec.association_tables:
            for assoc_table in dao_spec.association_tables:
                if assoc_table.table_name == assoc_table_name:
                    # Find the column that points to the "other" entity (not this entity)
                    for col in assoc_table.columns:
                        # Skip the column that points back to this entity
                        if col.foreign_key_table.lower() != dao_spec.table_name.lower():
                            related_entity_name = entities.convert_to_pascal(
                                col.foreign_key_table
                            )
                            return f"list[{related_entity_name}Read]"
        # Fallback: use property name heuristic if association table not found
        related_entity_name = entities.convert_to_pascal(prop.name.rstrip("s"))
        return f"list[{related_entity_name}Read]"
    return "typing.Any"


def generate_write_and_read_dtos_for_dao(dao_spec: entities.DAOSchemaSpec) -> str:
    """Generate Write, Read (shallow), and ReadRelationship DTOs for a single DAO.

    - {Entity}Write: input model with required, non-PK, non-relationship fields
    - {Entity}Read: SHALLOW output model with scalar columns + FK id fields ONLY
    - {Entity}ReadRelationship: expanded output model with relationships pointing to
      other entities' shallow Read DTOs
    """
    # Write DTO: only required, non-id, non-relationship fields
    write_props = [
        p
        for p in dao_spec.properties
        if not (p.key_type and p.key_type.type == "primary_key")
        and p.required
        and not is_relationship_property(p)
    ]

    code = f"""
class {dao_spec.name}Write(pydantic.BaseModel):
    \"\"\"Write DTO for {dao_spec.name}. Contains required scalar fields only.\"\"\"
"""
    if not write_props:
        code += "    pass\n"
    else:
        for prop in write_props:
            py_type = entities.convert_type_py(prop.type)
            code += f"    {prop.name}: {py_type}\n"

    # Read DTO (SHALLOW): scalar fields + FK id fields only, NO relationships
    scalar_props = [p for p in dao_spec.properties if not is_relationship_property(p)]

    code += f"""

class {dao_spec.name}Read(pydantic.BaseModel):
    \"\"\"Shallow Read DTO for {dao_spec.name}. Contains scalar columns and FK ids only.

    This DTO does NOT include relationship fields to prevent recursive serialization.
    Use {dao_spec.name}ReadRelationship for expanded views with relationships.
    \"\"\"
"""
    if not scalar_props:
        code += "    pass\n"
    else:
        for prop in scalar_props:
            py_type = entities.convert_type_py(prop.type)
            if prop.required:
                code += f"    {prop.name}: {py_type}\n"
            else:
                code += f"    {prop.name}: {py_type} | None = None\n"

    # ReadRelationship DTO: scalar fields + relationship fields (referencing shallow Read DTOs)
    relationship_props = [p for p in dao_spec.properties if is_relationship_property(p)]

    code += f"""

class {dao_spec.name}ReadRelationship(pydantic.BaseModel):
    \"\"\"Relationship-expanded Read DTO for {dao_spec.name}.

    Includes all scalar fields plus relationship fields. Relationship fields
    reference other entities' shallow Read DTOs (not their ReadRelationship DTOs)
    to prevent recursive/cyclic serialization.
    \"\"\"
"""
    # First, include all scalar fields (same as Read DTO)
    for prop in scalar_props:
        py_type = entities.convert_type_py(prop.type)
        if prop.required:
            code += f"    {prop.name}: {py_type}\n"
        else:
            code += f"    {prop.name}: {py_type} | None = None\n"

    # Then, include relationship fields
    for prop in relationship_props:
        rel_type = get_relationship_type_for_read(prop, dao_spec)
        # Relationships are typically optional (lazy-loaded may be None/empty)
        if prop.type == "array" or prop.many_to_many is not None:
            # Lists default to empty list
            code += f"    {prop.name}: {rel_type} = []\n"
        else:
            # Object relationships are optional
            code += f"    {prop.name}: {rel_type} = None\n"

    # Handle case where there are no fields at all
    if not scalar_props and not relationship_props:
        code += "    pass\n"

    return code


def generate_dao_dtos_file(dao_specs: list[entities.DAOSchemaSpec]) -> str:
    """Generate Write/Read/ReadRelationship DTOs file from DAO specs.

    Generated DTOs follow the shallow read + explicit relationship view pattern:
    - {Entity}Write: input model (shallow, required fields)
    - {Entity}Read: output model (SHALLOW - scalars + FK ids only)
    - {Entity}ReadRelationship: output model (expanded - includes relationships
      pointing to other entities' shallow Read DTOs)
    """
    code = """from __future__ import annotations
import typing
import pydantic

"""

    # Generate Write/Read/ReadRelationship DTOs - group by tag
    dao_by_tag: dict[str, list[entities.DAOSchemaSpec]] = {}
    for dao_spec in dao_specs:
        tag = dao_spec.name.lower()
        if tag not in dao_by_tag:
            dao_by_tag[tag] = []
        dao_by_tag[tag].append(dao_spec)

    for tag, daos in dao_by_tag.items():
        code += codegen_utils.generate_schema_block_comment(f"{tag.upper()} DTOs")
        for dao_spec in daos:
            code += generate_write_and_read_dtos_for_dao(dao_spec)

    return code


def generate_dto_code(
    endpoints_spec: entities.EndpointsSpec, dao_specs: list[entities.DAOSchemaSpec]
) -> str:
    """Generate custom endpoint DTOs file from endpoint specs."""
    code = """from __future__ import annotations
import typing
import pydantic
import project_name.use_cases.crud_dto as dto

"""

    # Track which tags have block comments already
    tags_with_comments: set[str] = set()

    # Get all tags from DAO specs
    for dao_spec in dao_specs:
        tags_with_comments.add(dao_spec.name.lower())

    # Generate custom endpoint DTOs - one block comment per tag (only if not already added)
    for tag, endpoints in endpoints_spec.endpoints.items():
        if endpoints:
            # Filter endpoints by language before adding block comment
            valid_endpoints = [
                ep for ep in endpoints if ep.language is None or "python" in ep.language
            ]

            if valid_endpoints and tag not in tags_with_comments:
                code += codegen_utils.generate_schema_tag_block_comment(tag)
                tags_with_comments.add(tag)

            for ep in valid_endpoints:
                pascal = entities.convert_to_pascal(ep.name)

                path_fields, body_fields = codegen_utils.generate_schema_for_request(
                    ep, language="python"
                )
                path_fields = codegen_utils.merge_implied_path_params_into_path_fields(
                    ep.path, path_fields
                )

                request_fields = path_fields + body_fields
                if request_fields:
                    if path_fields and body_fields:
                        code += f"""
class {pascal}Body(pydantic.BaseModel):
    \"\"\"Body payload for {ep.name}.\"\"\"
"""
                        for f in body_fields:
                            code += "\n" + codegen_utils.render_pydantic_field_line(
                                f["name"],
                                f["type"],
                                bool(f["required"]),
                                f.get("description"),
                            )
                        code += "\n"

                    code += f"""
class {pascal}Request(pydantic.BaseModel):
    \"\"\"Request for {ep.name}.\"\"\"
"""
                    for f in request_fields:
                        code += "\n" + codegen_utils.render_pydantic_field_line(
                            f["name"],
                            f["type"],
                            bool(f["required"]),
                            f.get("description"),
                        )
                    code += "\n"

                code += f"""
class {pascal}Response(pydantic.BaseModel):
    \"\"\"Response for {ep.name}.\"\"\"
"""
                if not ep.response_schema:
                    code += "    pass\n"
                else:
                    filtered_response_fields = {
                        fname: fs
                        for fname, fs in ep.response_schema.items()
                        if fs.language is None or "python" in fs.language
                    }
                    if not filtered_response_fields:
                        code += "    pass\n"
                    else:
                        for fname, fs in filtered_response_fields.items():
                            code += "\n" + codegen_utils.render_pydantic_field_line(
                                fname,
                                codegen_utils.get_field_type_from_spec(fs),
                                True,
                                fs.description,
                            )
                        code += "\n"

    return code


def main():
    endpoints_raw = File("tests", "specs", "endpoints_spec.json").get_json()
    endpoints_spec = entities.EndpointsSpec.model_validate(endpoints_raw)

    dao_raw = File("tests", "specs", "dao_spec.json").get_json()
    dao_specs = [entities.DAOSchemaSpec.model_validate(d) for d in dao_raw]

    # Generate Write/Read DTOs from DAO specs
    dao_dtos_code = generate_dao_dtos_file(dao_specs)
    print("DAO DTOs code generated:\n")
    print(dao_dtos_code)
    File("tests", "devOS", "dao_dto.py").write(dao_dtos_code)

    # Generate custom endpoint DTOs from endpoint specs
    schema_code = generate_dto_code(endpoints_spec, dao_specs)
    print("Custom endpoint DTOs code generated:\n")
    print(schema_code)
    File("tests", "devOS", "generated_schema.py").write(schema_code)


if __name__ == "__main__":
    main()
