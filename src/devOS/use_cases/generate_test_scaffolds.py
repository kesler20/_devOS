import ast
import logging
import typing

from devOS.domain import resource_api
from devOS.domain import resource_schema
from devOS.domain import test_scaffold


class GenerateTestScaffoldsUseCase:
    def __init__(self) -> None:
        pass

    def execute(
        self,
        source: str,
        module: str,
        kind: typing.Literal["api", "services"],
        app_name: str = "app",
    ) -> str:
        logging.info("Scaffolding %s tests for %s", kind, module)
        if (
            any(not part.isidentifier() for part in module.split("."))
            or not app_name.isidentifier()
        ):
            raise ValueError("Module and application names must be Python identifiers")
        tree = ast.parse(source)
        lines = [
            "# Project-owned test scaffold. Complete inputs, dependency overrides and assertions.",
            "import importlib",
            "import unittest.mock as mock",
            "import pytest",
            "",
        ]
        if kind == "api":
            endpoints = []
            for node in tree.body:
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for decorator in node.decorator_list:
                    if (
                        not isinstance(decorator, ast.Call)
                        or not isinstance(decorator.func, ast.Attribute)
                        or decorator.func.attr
                        not in typing.get_args(test_scaffold.HttpMethod)
                    ):
                        continue
                    path = (
                        decorator.args[0]
                        if decorator.args
                        else next(
                            (
                                value.value
                                for value in decorator.keywords
                                if value.arg == "path"
                            ),
                            None,
                        )
                    )
                    if not isinstance(path, ast.Constant) or not isinstance(
                        path.value, str
                    ):
                        raise ValueError(
                            f"{node.name} needs a static route path before tests can be scaffolded"
                        )
                    endpoints.append(
                        test_scaffold.EndpointScaffold(
                            node.name,
                            typing.cast(test_scaffold.HttpMethod, decorator.func.attr),
                            path.value,
                            [arg.arg for arg in node.args.args],
                        )
                    )
            if not endpoints:
                raise ValueError("No decorated FastAPI endpoints were discovered")
            lines.extend(
                [
                    "import fastapi.testclient",
                    "",
                    "@pytest.fixture",
                    "def client():",
                    f"    application = importlib.import_module({module!r})",
                    "    # Override application dependencies with isolated test services here.",
                    f"    with fastapi.testclient.TestClient(application.{app_name}) as test_client:",
                    "        yield test_client",
                    "",
                ]
            )
            for index, endpoint in enumerate(endpoints):
                lines.extend(
                    [
                        f"@pytest.mark.skip(reason='Unimplemented endpoint requirements for {endpoint.name}')",
                        f"def test_{endpoint.name}_{index}(client):",
                        f"    # Discovered inputs {endpoint.parameters!r}",
                        f"    path = {endpoint.path!r}  # Replace path parameters with fixture values.",
                        f"    response = client.{endpoint.method}(path)",
                        "    # Add request payload, expected status and behaviour assertions.",
                        "    raise NotImplementedError('Define expected endpoint behaviour')",
                        "",
                    ]
                )
        else:
            cases = []
            for node in tree.body:
                if not isinstance(node, ast.ClassDef):
                    continue
                execute = next(
                    (
                        item
                        for item in node.body
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and item.name == "execute"
                    ),
                    None,
                )
                if execute is None:
                    continue
                constructor = next(
                    (
                        item
                        for item in node.body
                        if isinstance(item, ast.FunctionDef) and item.name == "__init__"
                    ),
                    None,
                )
                dependencies = (
                    [
                        item.arg
                        for item in [
                            *constructor.args.args,
                            *constructor.args.kwonlyargs,
                        ]
                        if item.arg != "self"
                    ]
                    if constructor
                    else []
                )
                inputs = [
                    item.arg
                    for item in [*execute.args.args, *execute.args.kwonlyargs]
                    if item.arg != "self"
                ]
                if (
                    execute.args.vararg
                    or execute.args.kwarg
                    or (
                        constructor
                        and (constructor.args.vararg or constructor.args.kwarg)
                    )
                ):
                    raise ValueError(
                        f"{node.name} variadic inputs require a handwritten test"
                    )
                cases.append(
                    test_scaffold.UseCaseScaffold(
                        node.name,
                        dependencies,
                        inputs,
                        isinstance(execute, ast.AsyncFunctionDef),
                    )
                )
            if not cases:
                raise ValueError("No use-case classes with execute were discovered")
            for case in cases:
                lines.extend(
                    [
                        f"@pytest.mark.skip(reason='Unimplemented use-case requirements for {case.name}')"
                    ]
                )
                if case.asynchronous:
                    lines.append("@pytest.mark.asyncio")
                lines.extend(
                    [
                        f"{'async ' if case.asynchronous else ''}def test_{case.name}_execute():",
                        f"    feature = importlib.import_module({module!r})",
                    ]
                )
                for dependency in case.dependencies:
                    lines.append(f"    {dependency} = mock.Mock(name={dependency!r})")
                dependency_arguments = ", ".join(
                    f"{name}={name}" for name in case.dependencies
                )
                lines.append(
                    f"    use_case = feature.{case.name}({dependency_arguments})"
                )
                for parameter in case.inputs:
                    lines.append(
                        f"    {parameter} = None  # Replace with a domain fixture."
                    )
                input_arguments = ", ".join(f"{name}={name}" for name in case.inputs)
                lines.extend(
                    [
                        f"    result = {'await ' if case.asynchronous else ''}use_case.execute({input_arguments})",
                        "    # Arrange dependency responses and assert output and boundary calls.",
                        "    raise NotImplementedError('Define expected use-case behaviour')",
                        "",
                    ]
                )
        result = "\n".join(lines)
        ast.parse(result)
        logging.info("Generated project-owned test scaffolds")
        return result


class GenerateResourceTestsUseCase:
    def __init__(self) -> None:
        pass

    def execute(
        self, resources: list[resource_schema.MappedResource], dto_module: str
    ) -> str:
        logging.info("Generating mounted resource contract tests")
        lines = [
            "# Generated by devOS from SQLAlchemy DAO metadata.",
            "# Consumer conftest supplies client and resource_inputs fixtures with isolated services.",
            "import urllib.parse",
            "import pytest",
            f"import {dto_module} as dto",
            "",
        ]
        for resource in sorted(resources, key=lambda item: item.get_name()):
            name = resource.get_name()
            route = resource_api.get_resource_path(name)
            fields = resource.get_fields()
            keys = [field.name for field in resource.get_identity_fields()]
            if not keys:
                raise ValueError(f"{name} needs a primary key for contract tests")
            nullable = [
                field.name
                for field in fields
                if field.column.nullable and not field.column.primary_key
            ]
            required = [
                field.name
                for field in fields
                if field.accepts_role("write") and not field.is_optional("write")
            ]
            lines.extend(
                [
                    f"def test_{route}_mounted_contract(client, resource_inputs):",
                    f"    payload = resource_inputs[{name!r}]",
                    f"    dto.{name}Write.model_validate(payload)",
                    f"    for required in {required!r}:",
                    "        incomplete = {key: value for key, value in payload.items() if key != required}",
                    f"        assert client.post('/{route}', json={{'entity': incomplete}}).status_code == 422",
                    f"    created = client.post('/{route}', json={{'entity': payload}})",
                    "    assert created.status_code == 201, created.text",
                    "    entity = created.json()['entity']",
                    f"    dto.{name}Read.model_validate(entity)",
                    f"    path = '/{route}/' + '/'.join(urllib.parse.quote(str(entity[key]), safe='') for key in {keys!r})",
                    "    assert client.get(path).json()['entity'] == entity",
                    f"    assert entity in client.get('/{route}').json()['entities']",
                    "    unchanged = client.patch(path, json={'entity': {}})",
                    "    assert unchanged.status_code == 200, unchanged.text",
                    "    assert unchanged.json()['entity'] == entity",
                    "    assert client.patch(path, json={'entity': {'__unknown': True}}).status_code == 422",
                    f"    assert client.patch(path, json={{'entity': {{{keys[0]!r}: entity[{keys[0]!r}]}}}}).status_code == 422",
                    f"    for field in {nullable!r}:",
                    "        response = client.patch(path, json={'entity': {field: None}})",
                    "        assert response.status_code == 200, response.text",
                    "        assert response.json()['entity'][field] is None",
                    "    expanded = client.get(path + '/relationships')",
                    "    assert expanded.status_code == 200, expanded.text",
                    f"    dto.{name}ReadRelationship.model_validate(expanded.json()['entity'])",
                    "    assert client.delete(path).status_code == 200",
                    "    assert client.get(path).status_code == 404",
                    "    assert client.delete(path).status_code == 404",
                    "",
                ]
            )
        result = "\n".join(lines)
        ast.parse(result)
        logging.info("Generated mounted resource contract tests")
        return result
