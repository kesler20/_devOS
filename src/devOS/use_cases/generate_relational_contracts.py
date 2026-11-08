import json
import logging
import typing

import pydantic.json_schema

from devOS.domain import relational


class GenerateRelationalContractsUseCase:
    def __init__(self) -> None:
        pass

    def execute(self) -> relational.DocumentContracts:
        logging.info("Generating relational document contracts")
        schema = relational.SchemaDocument.model_json_schema()

        def render_type(node: pydantic.json_schema.JsonSchemaValue) -> str:
            if "$ref" in node:
                return typing.cast(str, node["$ref"]).split("/")[-1]
            if "const" in node:
                return json.dumps(node["const"])
            if "enum" in node:
                return " | ".join(json.dumps(value) for value in node["enum"])
            for alternatives in ("anyOf", "oneOf"):
                if alternatives in node:
                    return (
                        "("
                        + " | ".join(render_type(value) for value in node[alternatives])
                        + ")"
                    )
            if node.get("type") == "object":
                required = node.get("required", [])
                fields = [
                    "  "
                    + json.dumps(name)
                    + ("" if name in required else "?")
                    + ": "
                    + render_type(value)
                    + ";"
                    for name, value in node.get("properties", {}).items()
                ]
                return "{\n" + "\n".join(fields) + "\n}"
            if node.get("type") == "array":
                return "Array<" + render_type(node["items"]) + ">"
            scalar_types = {
                "string": "string",
                "integer": "number",
                "number": "number",
                "boolean": "boolean",
                "null": "null",
            }
            return scalar_types[node["type"]]

        declarations = ["// Generated from devOS.domain.relational.SchemaDocument.\n"]
        declarations.extend(
            "export type " + name + " = " + render_type(node) + ";\n"
            for name, node in schema["$defs"].items()
        )
        declarations.append(
            "export type SchemaDocument = " + render_type(schema) + ";\n"
        )
        declarations.append(
            'export const sqlTypeNames: Array<SqlType["name"]> = '
            + json.dumps(schema["$defs"]["SqlType"]["properties"]["name"]["enum"])
            + ";\n"
        )
        result = relational.DocumentContracts(
            json_schema=json.dumps(schema, indent=2) + "\n",
            typescript="\n".join(declarations),
        )
        logging.info("Generated relational document contracts")
        return result
