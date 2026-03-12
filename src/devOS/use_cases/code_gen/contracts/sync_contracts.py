from __future__ import annotations
import ast
import os
import re
import typing

from devOS.domain import entities
from devOS.use_cases.utils.file_io import File


class SyncContractsUseCase:
    """Synchronize `@contract` files between Python and TypeScript.

    Files are discovered by scanning for the ``@contract`` marker in ``.py``,
    ``.ts`` and ``.tsx`` files. Output locations are controlled by
    ``project_root.contract_sync_output_config``.
    """

    _IGNORED_DIRECTORIES = {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        "dist",
        "build",
        "htmlcov",
    }

    def __init__(self, project_structure: entities.ProjectConfigSchema):
        self.project_structure = project_structure

    def execute(self, project_name: str | None = None) -> None:
        """Scan and sync all `@contract` files."""
        contract_files = self._search_for_contract_files()
        contract_configs = (
            self.project_structure.project_root.contract_sync_output_config
        )

        if not contract_configs:
            print(
                "No contract_sync_output_config found in project config. "
                "Skipping contract sync."
            )
            return

        for contract_file in contract_files:
            source_language = self._infer_language(contract_file)
            if source_language is None:
                continue

            for output_config in contract_configs:
                if output_config.source_language != source_language:
                    continue

                source_code = File(contract_file).read_as_utf8()
                translated_code = self._translate_code(source_code, source_language)
                if translated_code is None:
                    continue
                if not self._has_translated_contracts(translated_code, source_language):
                    print(
                        "Skipping empty contract translation for:",
                        contract_file,
                    )
                    continue

                destination_filename = self._build_destination_filename(
                    contract_file, source_language
                )
                destination_parts = output_config.output_directory + [
                    destination_filename
                ]

                print(
                    "Syncing contract:",
                    contract_file,
                    "->",
                    os.path.join(*destination_parts),
                )
                File(*destination_parts).write_as_utf8(translated_code)

    def _search_for_contract_files(self) -> list[str]:
        contract_files: list[str] = []
        for dirpath, dirnames, filenames in os.walk("."):
            dirnames[:] = [
                dirname
                for dirname in dirnames
                if dirname not in self._IGNORED_DIRECTORIES
            ]

            for filename in filenames:
                if not filename.endswith((".py", ".ts", ".tsx")):
                    continue

                file_path = os.path.join(dirpath, filename)
                try:
                    content = File(file_path).read_as_utf8()
                except Exception:
                    continue

                if "@contract" in content:
                    contract_files.append(file_path)

        return sorted(contract_files)

    def _infer_language(
        self, file_path: str
    ) -> typing.Optional[entities.SupportedLanguagesValues]:
        if file_path.endswith(".py"):
            return "python"
        if file_path.endswith(".ts") or file_path.endswith(".tsx"):
            return "typescript"
        return None

    def _build_destination_filename(
        self, source_path: str, source_language: str
    ) -> str:
        source_name = os.path.basename(source_path)
        stem, _ = os.path.splitext(source_name)
        if source_language == "python":
            return f"{stem}.ts"
        return f"{stem}.py"

    def _translate_code(
        self,
        source_code: str,
        source_language: entities.SupportedLanguagesValues,
    ) -> str | None:
        if source_language == "python":
            return self._translate_python_to_typescript(source_code)
        if source_language == "typescript":
            return self._translate_typescript_to_python(source_code)
        return None

    def _has_translated_contracts(
        self,
        translated_code: str,
        source_language: entities.SupportedLanguagesValues,
    ) -> bool:
        if source_language == "python":
            return "Schema = z.object({" in translated_code
        if source_language == "typescript":
            return (
                "class " in translated_code
                and "(pydantic.BaseModel):" in translated_code
            )
        return False

    def _translate_python_to_typescript(self, source_code: str) -> str:
        class_specs = self._parse_python_contract_classes(source_code)
        if not class_specs:
            return "import { z } from 'zod';\n"

        lines: list[str] = [
            "import { z } from 'zod';",
            "",
        ]

        for class_name, fields in class_specs:
            lines.append(f"export const {class_name}Schema = z.object({{")
            for field_name, field_zod_type in fields:
                lines.append(f"  {field_name}: {field_zod_type},")
            lines.append("});")
            lines.append(
                f"export type {class_name} = z.infer<typeof {class_name}Schema>;"
            )
            lines.append("")

        return "\n".join(lines).strip() + "\n"

    def _parse_python_contract_classes(
        self, source_code: str
    ) -> list[tuple[str, list[tuple[str, str]]]]:
        try:
            module = ast.parse(source_code)
        except SyntaxError:
            return []

        class_specs: list[tuple[str, list[tuple[str, str]]]] = []
        for node in module.body:
            if not isinstance(node, ast.ClassDef):
                continue

            fields: list[tuple[str, str]] = []
            for item in node.body:
                if not isinstance(item, ast.AnnAssign):
                    continue
                if not isinstance(item.target, ast.Name):
                    continue

                field_name = item.target.id
                base_type_node, is_optional = self._strip_optional_annotation(
                    item.annotation
                )
                zod_type = self._python_type_node_to_zod(base_type_node)

                if is_optional or item.value is not None:
                    if ".optional()" not in zod_type:
                        zod_type += ".optional()"

                fields.append((field_name, zod_type))

            if fields:
                class_specs.append((node.name, fields))

        return class_specs

    def _strip_optional_annotation(self, node: ast.AST) -> tuple[ast.AST, bool]:
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            left, right = node.left, node.right
            if self._is_none_node(left):
                return right, True
            if self._is_none_node(right):
                return left, True

        if isinstance(node, ast.Subscript):
            root_name = self._full_name(node.value)
            if root_name in {"typing.Optional", "Optional"}:
                if isinstance(node.slice, ast.Tuple) and len(node.slice.elts) > 0:
                    return node.slice.elts[0], True
                return node.slice, True

            if root_name in {"typing.Union", "Union"}:
                union_nodes = self._extract_subscript_items(node.slice)
                filtered_nodes = [n for n in union_nodes if not self._is_none_node(n)]
                is_optional = len(filtered_nodes) != len(union_nodes)
                if len(filtered_nodes) == 1:
                    return filtered_nodes[0], is_optional

        return node, False

    def _python_type_node_to_zod(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            if node.id == "str":
                return "z.string()"
            if node.id in {"int", "float"}:
                return "z.number()"
            if node.id == "bool":
                return "z.boolean()"
            if node.id in {"dict", "Dict"}:
                return "z.record(z.string(), z.any())"
            if node.id in {"list", "List"}:
                return "z.array(z.any())"
            return "z.any()"

        if isinstance(node, ast.Subscript):
            root_name = self._full_name(node.value)

            if root_name in {"list", "typing.List", "List"}:
                inner = self._extract_subscript_items(node.slice)
                inner_type = (
                    self._python_type_node_to_zod(inner[0]) if inner else "z.any()"
                )
                return f"z.array({inner_type})"

            if root_name in {"dict", "typing.Dict", "Dict"}:
                return "z.record(z.string(), z.any())"

        return "z.any()"

    def _translate_typescript_to_python(self, source_code: str) -> str:
        schema_specs = self._parse_typescript_contract_schemas(source_code)
        if not schema_specs:
            return "from __future__ import annotations\nimport pydantic\n"

        lines: list[str] = [
            "from __future__ import annotations",
            "import typing",
            "import pydantic",
            "",
        ]

        for class_name, fields in schema_specs:
            lines.append(f"class {class_name}(pydantic.BaseModel):")
            for field_name, python_type, optional in fields:
                if optional:
                    lines.append(f"    {field_name}: {python_type} | None = None")
                else:
                    lines.append(f"    {field_name}: {python_type}")
            lines.append("")

        return "\n".join(lines).strip() + "\n"

    def _parse_typescript_contract_schemas(
        self, source_code: str
    ) -> list[tuple[str, list[tuple[str, str, bool]]]]:
        pattern = re.compile(
            r"(?:export\s+)?const\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)Schema\s*=\s*z\.object\(\s*\{(?P<body>.*?)\}\s*\)\s*;",
            re.DOTALL,
        )
        field_pattern = re.compile(
            r"^\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)\??\s*:\s*(?P<expr>.+?)\s*,?\s*$"
        )

        class_specs: list[tuple[str, list[tuple[str, str, bool]]]] = []

        for match in pattern.finditer(source_code):
            class_name = match.group("name")
            body = match.group("body")
            fields: list[tuple[str, str, bool]] = []

            for raw_line in body.splitlines():
                stripped = raw_line.strip()
                if not stripped or stripped.startswith("//"):
                    continue

                field_match = field_pattern.match(raw_line)
                if not field_match:
                    continue

                field_name = field_match.group("name")
                zod_expr = field_match.group("expr").strip().rstrip(",")
                python_type, optional = self._zod_expression_to_python_type(zod_expr)
                fields.append((field_name, python_type, optional))

            if fields:
                class_specs.append((class_name, fields))

        return class_specs

    def _zod_expression_to_python_type(self, expression: str) -> tuple[str, bool]:
        optional = ".optional()" in expression or ".nullable()" in expression
        clean_expression = expression.replace(".optional()", "").replace(
            ".nullable()", ""
        )

        if clean_expression.startswith("z.string"):
            return "str", optional
        if clean_expression.startswith("z.number"):
            return "float", optional
        if clean_expression.startswith("z.boolean"):
            return "bool", optional
        if clean_expression.startswith("z.any"):
            return "typing.Any", optional
        if clean_expression.startswith("z.enum"):
            return "str", optional
        if clean_expression.startswith("z.object"):
            return "dict[str, typing.Any]", optional
        if clean_expression.startswith("z.record"):
            return "dict[str, typing.Any]", optional
        if clean_expression.startswith("z.array"):
            inner = self._extract_call_inner_expression(clean_expression)
            if inner is None:
                return "list[typing.Any]", optional
            inner_type, _ = self._zod_expression_to_python_type(inner)
            return f"list[{inner_type}]", optional

        return "typing.Any", optional

    def _extract_call_inner_expression(self, expression: str) -> str | None:
        left_paren = expression.find("(")
        right_paren = expression.rfind(")")
        if left_paren == -1 or right_paren == -1 or right_paren <= left_paren:
            return None
        return expression[left_paren + 1 : right_paren].strip()

    def _extract_subscript_items(self, node: ast.AST) -> list[ast.AST]:
        if isinstance(node, ast.Tuple):
            return list(node.elts)
        return [node]

    def _is_none_node(self, node: ast.AST) -> bool:
        return isinstance(node, ast.Constant) and node.value is None

    def _full_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._full_name(node.value)
            if parent:
                return f"{parent}.{node.attr}"
            return node.attr
        return ""
