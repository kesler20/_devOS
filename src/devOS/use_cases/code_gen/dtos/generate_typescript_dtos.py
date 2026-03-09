from devOS.use_cases.utils.file_io import File
import devOS.domain.entities as entities
import devOS.use_cases.utils.codegen_helpers as codegen_utils


def to_pascal_case(s: str) -> str:
    return "".join(word.capitalize() for word in s.replace("-", "_").split("_"))


def to_camel_case(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


def ts_type_from_py_type(
    py_type: str, prop: entities.DAOSchemaProperty | None = None
) -> str:
    # Map Python types to TypeScript types for Zod
    if py_type in {"int", "integer"}:
        return "z.number()"
    if py_type in {"str", "string", "text"}:
        return "z.string()"
    if py_type in {"float", "number"}:
        return "z.number()"
    if py_type in {"bool", "boolean"}:
        return "z.boolean()"
    if py_type == "array" and prop and prop.linked_property:
        linked = to_pascal_case(prop.linked_property.table) + "ReadSchema"
        return f"z.array({linked})"
    if py_type == "object" and prop and prop.linked_property:
        linked = to_pascal_case(prop.linked_property.table) + "ReadSchema"
        return f"{linked}.nullable().optional()"
    return "z.any()"


def generate_block_comment(title: str) -> str:
    pad = 3
    label = title.strip().upper()
    inner_width = max(len(label) + (pad * 2), 18)
    top = f"// {'=' * inner_width} //"
    empty = f"// {' ' * inner_width} //"
    mid = f"// {label.center(inner_width)} //"
    return f"\n{top}\n{empty}\n{mid}\n{empty}\n{top}\n"


def generate_dtos_for_dao(dao_spec: entities.DAOSchemaSpec) -> str:
    name = to_pascal_case(dao_spec.name)
    table_name_lower = dao_spec.table_name.lower()
    code = generate_block_comment(f"{name} DTOs")

    # WriteSchema: only required, non-id, non-relationship fields
    write_props = [
        p
        for p in dao_spec.properties
        if not (p.key_type and p.key_type.type == "primary_key")
        and p.required
        and p.type not in {"array", "object"}
    ]

    code += f"\n// {table_name_lower} - Write schema (only required fields)\n"
    code += f"export const {name}WriteSchema = z.object({{\n"
    for prop in write_props:
        ts_type = ts_type_from_py_type(prop.type, prop)
        code += f"  {to_camel_case(prop.name)}: {ts_type},\n"
    code += "});\n"
    code += f"export type {name}Write = z.infer<typeof {name}WriteSchema>;\n\n"

    code += f"\n// POST /v1/{table_name_lower} - Request\n"
    code += f"export const {name}CreateRequestSchema = z.object({{\n"
    code += f"  entity: {name}WriteSchema,\n"
    code += "});\n"
    code += f"export type {name}CreateRequest = z.infer<typeof {name}CreateRequestSchema>;\n\n"

    code += f"// PATCH /v1/{table_name_lower}/{{{table_name_lower}_id}} - Request\n"
    code += f"export const {name}UpdateRequestSchema = z.object({{\n"
    code += f"  entity: {name}WriteSchema,\n"
    code += "});\n"
    code += f"export type {name}UpdateRequest = z.infer<typeof {name}UpdateRequestSchema>;\n\n"

    code += (
        f"\n// {table_name_lower} - Read schema (all fields including relationships)\n"
    )
    code += f"export const {name}ReadSchema = z.object({{\n"
    for prop in dao_spec.properties:
        ts_type = ts_type_from_py_type(prop.type, prop)
        optional = ""
        if not prop.required:
            if "nullable()" in ts_type or "optional()" in ts_type:
                optional = ".optional()"
            else:
                ts_type += ".nullable().optional()"
        code += f"  {to_camel_case(prop.name)}: {ts_type}{optional},\n"
    code += "});\n\n"
    code += f"export type {name}Read = z.infer<typeof {name}ReadSchema>;\n\n"

    # Single entity response
    code += f"// GET /v1/{table_name_lower}/{{{table_name_lower}_id}}\n"
    code += f"export const {name}ResponseSchema = z.object({{\n"
    code += f"  entity: {name}ReadSchema,\n"
    code += "});\n"
    code += f"export type {name}Response = z.infer<typeof {name}ResponseSchema>;\n\n"

    # List response
    code += f"// GET /v1/{table_name_lower} (list)\n"
    code += f"export const {name}ListResponseSchema = z.object({{\n"
    code += f"  entities: z.array({name}ReadSchema),\n"
    code += "});\n"
    code += f"export type {name}ListResponse = z.infer<typeof {name}ListResponseSchema>;\n\n"

    return code


def generate_custom_endpoint_schemas(endpoints_spec: entities.EndpointsSpec) -> str:
    code = ""
    for tag, endpoints in endpoints_spec.endpoints.items():
        if not endpoints:
            continue

        # Filter endpoints by language before adding block comment
        valid_endpoints = [
            ep for ep in endpoints if ep.language is None or "typescript" in ep.language
        ]

        if not valid_endpoints:
            continue

        code += generate_block_comment(f"{to_pascal_case(tag)} Custom Endpoint DTOs")
        for ep in valid_endpoints:
            pascal = entities.convert_to_pascal(ep.name)
            # Request schema
            path_fields, body_fields = codegen_utils.generate_schema_for_request(ep)
            path_fields = codegen_utils.merge_implied_path_params_into_path_fields(
                ep.path, path_fields
            )
            request_fields = path_fields + body_fields
            if request_fields:
                code += f"// {ep.method.upper()} /{ep.version}/{ep.path.lstrip('/')} - Request\n"
                code += f"export const {pascal}RequestSchema = z.object({{\n"
                for f in request_fields:
                    ts_type = ts_type_from_py_type(f["type"])
                    code += f"  {to_camel_case(f['name'])}: {ts_type},\n"
                code += "});\n"
                code += f"export type {pascal}Request = z.infer<typeof {pascal}RequestSchema>;\n\n"
            # Response schema
            code += f"// {ep.method.upper()} /{ep.version}/{ep.path.lstrip('/')} - Response\n"
            if ep.response_schema:
                code += f"export const {pascal}ResponseSchema = z.object({{\n"
                for fname, fs in ep.response_schema.items():
                    if fs.name is None:
                        continue

                    ts_type = (
                        f"z.array({to_pascal_case(fs.name)}ReadSchema)"
                        if fs.type == "dao" and fs.is_list
                        else ts_type_from_py_type(fs.type)
                    )
                    code += f"  {to_camel_case(fname)}: {ts_type},\n"
                code += "});\n"
                code += f"export type {pascal}Response = z.infer<typeof {pascal}ResponseSchema>;\n\n"
            else:
                code += f"export const {pascal}ResponseSchema = z.object({{}});\n"
                code += f"export type {pascal}Response = z.infer<typeof {pascal}ResponseSchema>;\n\n"
    return code


def main():
    endpoints_raw = File("tests", "specs", "endpoints_spec.json").get_json()
    endpoints_spec = entities.EndpointsSpec.model_validate(endpoints_raw)
    dao_raw = File("tests", "specs", "dao_spec.json").get_json()
    dao_specs = [entities.DAOSchemaSpec.model_validate(d) for d in dao_raw]

    code = "import { z } from 'zod';\n\n"

    for dao_spec in dao_specs:
        code += generate_dtos_for_dao(dao_spec)

    code += generate_custom_endpoint_schemas(endpoints_spec)

    print("TypeScript DTO code generated:\n")
    print(code)
    File("tests", "devOS", "generated_schema.ts").write(code)


if __name__ == "__main__":
    main()
