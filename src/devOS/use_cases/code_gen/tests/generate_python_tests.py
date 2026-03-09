from __future__ import annotations
from devOS.use_cases.utils.file_io import File
import typing
import ast
from pydantic import BaseModel


class EndpointInfo(BaseModel):
    """Information about a FastAPI endpoint.

    Attributes
    ----------
    name : str
        Endpoint name.
    method : str
        HTTP method for the endpoint.
    path : str
        Route path for the endpoint.
    """

    name: str
    method: str
    path: str


def extract_class_methods(source_code: str, class_name: str) -> list[str]:
    """Extract public method names from a class in source code."""
    try:
        tree = ast.parse(source_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                return [
                    item.name
                    for item in node.body
                    if isinstance(item, ast.FunctionDef)
                    and not item.name.startswith("_")
                ]
    except:
        pass
    return []


def has_db_session_param(source_code: str, class_name: str) -> bool:
    """Check if class __init__ has db_session parameter."""
    try:
        tree = ast.parse(source_code)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                        return any(arg.arg == "db_session" for arg in item.args.args)
    except:
        pass
    return False


def generate_test_class(
    class_name: str,
    methods: list[str],
    is_adapter: bool = False,
    needs_db: bool = False,
) -> str:
    """Generate a pytest test class."""
    test_class_name = f"Test{class_name}"
    setup_comment = "Setup {} instance {}".format(
        class_name, "with mocked dependencies" if is_adapter else "before each test"
    )

    lines = [
        "",
        f"class {test_class_name}:",
        f'    """Pytest test class for {class_name}"""',
        "",
    ]

    instance_init = f"self.instance = {class_name}()"
    if is_adapter:
        instance_init = f"self.instance = None  # {class_name}(...)"
    elif needs_db:
        instance_init = f"self.instance = {class_name}(db_session)"

    lines.extend(
        [
            "    @pytest.fixture(autouse=True)",
            f"    def setup_method(self{', db_session' if needs_db else ''}):",
            f'        """{setup_comment}"""',
        ]
    )

    if is_adapter:
        lines.append("        # TODO: Initialize with appropriate mocks")

    lines.extend(
        [
            f"        {instance_init}",
            "        yield",
            "        self.instance = None",
            "",
        ]
    )

    for method in methods:
        lines.extend(
            [
                f'    @pytest.mark.skip(reason="Test case not implemented yet")',
                f"    def test_{method}(self):",
                f'        """Test {method} method"""',
                "        pass",
                "",
            ]
        )

    return "\n".join(lines)


def extract_endpoint_info(source_code: str) -> list[EndpointInfo]:
    """Extract endpoint information from a FastAPI routes file (AST-based)."""
    endpoints: list[EndpointInfo] = []

    HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}

    def _expr_to_route_path(expr: ast.AST) -> str | None:
        # Handles: "/path", f"/path/{id}", f"/path/{{id}}" (escaped braces), etc.
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return expr.value

        if isinstance(expr, ast.JoinedStr):
            parts: list[str] = []
            for v in expr.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    parts.append(v.value)
                elif isinstance(v, ast.FormattedValue):
                    # Best-effort placeholder rendering
                    try:
                        inner = ast.unparse(v.value)  # py3.9+
                    except Exception:
                        inner = "expr"
                    parts.append("{" + inner + "}")
            return "".join(parts) or None

        return None

    try:
        tree = ast.parse(source_code)
    except Exception:
        return endpoints

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            if not isinstance(dec.func, ast.Attribute):
                continue

            method = dec.func.attr.lower()
            if method not in HTTP_METHODS:
                continue

            # Ensure it's called on something like `app.<method>` (common FastAPI pattern)
            base = dec.func.value
            if isinstance(base, ast.Name) and base.id not in {"app", "router"}:
                continue

            path_expr: ast.AST | None = dec.args[0] if dec.args else None
            if path_expr is None:
                for kw in dec.keywords:
                    if kw.arg in {"path", "url_path"}:
                        path_expr = kw.value
                        break

            path = _expr_to_route_path(path_expr) if path_expr is not None else None
            if not path:
                continue

            # Skip test generation for the root directory endpoint
            if path.strip() == "/":
                continue

            endpoints.append(
                EndpointInfo(
                    name=node.name,
                    method=method.upper(),
                    path=path,
                )
            )

    return endpoints


def generate_endpoint_tests(endpoints: list[EndpointInfo]) -> str:
    """Generate pytest tests for FastAPI endpoints."""
    lines = [
        "",
        "class TestEndpoints:",
        '    """Pytest test class for FastAPI endpoints"""',
        "",
        "    @pytest.fixture(autouse=True)",
        "    def setup_method(self):",
        '        """Setup test client"""',
        "        from project_name.infrastructure.routes import app",
        "        with TestClient(app) as client:",
        "            self.client = client",
        "            yield",
        "",
    ]

    for endpoint in endpoints:
        # Defensive: also skip here in case endpoints are provided externally
        if endpoint.path.strip() == "/":
            continue

        method = endpoint.method.lower()
        func_name = endpoint.name
        path = endpoint.path
        lines.extend(
            [
                f"    def test_{func_name}(self):",
                f'        """Test {method.upper()} {path}"""',
                f"        response = self.client.{method}('{path}')",
                "        assert response.status_code == 200",
                "",
            ]
        )

    return "\n".join(lines)


def generate_db_fixture() -> str:
    """Generate module-level database session fixture."""
    lines = [
        "",
        "@pytest.fixture(scope='module')",
        "def db_session():",
        '    """Create database session for tests"""',
        "    from sqlalchemy import create_engine",
        "    from sqlalchemy.orm import sessionmaker",
        "    ",
        "    # TODO: Configure test database URL",
        "    engine = create_engine('sqlite:///:memory:')",
        "    SessionLocal = sessionmaker(bind=engine)",
        "    session = SessionLocal()",
        "    ",
        "    yield session",
        "    ",
        "    session.close()",
        "    engine.dispose()",
        "",
    ]
    return "\n".join(lines)


class GenerateTestsUseCase:
    """Use case for generating test files from existing code."""

    def generate_tests_for_file(
        self,
        code: str,
        file_type: typing.Literal["usecase", "adapter", "endpoint"],
    ) -> str | None:
        if file_type == "endpoint":
            endpoints = extract_endpoint_info(code)
            print(f"Found {len(endpoints)} endpoints")  # Debug output
            if not endpoints:
                return None
            imports = [
                "import pytest",
                "from fastapi.testclient import TestClient",
                "",
            ]
            return "\n".join(imports) + generate_endpoint_tests(endpoints)

        try:
            tree = ast.parse(code)
            classes_to_test = [
                node.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef) and not node.name.startswith("_")
            ]

            if not classes_to_test:
                return None

            class_names = []
            test_contents = []
            is_adapter = file_type == "adapter"
            has_any_db = False

            for class_name in classes_to_test:
                if f"Test{class_name}" in code:
                    continue

                methods = extract_class_methods(code, class_name)
                if not methods:
                    continue

                needs_db = has_db_session_param(code, class_name)
                if needs_db:
                    has_any_db = True

                class_names.append(class_name)
                test_contents.append(
                    generate_test_class(class_name, methods, is_adapter, needs_db)
                )

            if not test_contents:
                return None

            imports = ["import pytest"]
            if is_adapter:
                imports.append("from unittest.mock import Mock, patch")
            imports.append(f"from project_name import {', '.join(class_names)}")
            imports.append("")

            result = "\n".join(imports)

            # Add module-level db fixture if any class needs it
            if has_any_db:
                result += generate_db_fixture()

            result += "\n".join(test_contents)

            return result

        except Exception as e:
            print(f"Error generating tests: {e}")
            return None


def main():
    generator = GenerateTestsUseCase()
    code = File("tests", "devOS", "generated_endpoints.py").read()
    print("Generating tests for generated_endpoints.py...")
    print(code)
    result = generator.generate_tests_for_file(code, file_type="endpoint")
    print("Generated test code:")
    print(result)
    File("tests", "generated_tests", "test_generated_endpoints.py").write(result or "")


if __name__ == "__main__":
    main()
