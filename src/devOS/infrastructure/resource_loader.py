import ast
import importlib
import logging
import pathlib
import sys

import sqlalchemy as sa
import sqlalchemy.orm as orm

from devOS.domain import resource_schema
from devOS.domain import generated_artifact


def get_module_path(root: pathlib.Path, name: str) -> pathlib.Path:
    return root.joinpath(*name.split(".")).with_suffix(".py")


def validate_support(root: pathlib.Path, name: str) -> None:
    path = get_module_path(root, name)
    guidance = "Install and adapt the canonical CRUD and SQL database snippets in the consumer project before API generation"
    if not path.is_file():
        raise ValueError(f"Missing CRUD support {path}. {guidance}")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    exports = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }
    exports.update(
        alias.asname or alias.name
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    )
    required = {
        "CRUDUseCase",
        "CRUDSpec",
        "WriteEntityRequest",
        "WriteEntityResponse",
        "ReadEntityRequest",
        "ReadEntityResponse",
        "ReadEntityRelationshipsResponse",
        "ReadAllEntitiesResponse",
        "DeleteEntityRequest",
        "DeleteEntityResponse",
        "EntityNotFoundError",
        "InvalidEntityInputError",
        "EntityConstraintError",
    }
    missing = required - exports
    if missing:
        raise ValueError(f"CRUD support lacks {', '.join(sorted(missing))}. {guidance}")


def load_resources(
    root: pathlib.Path, name: str
) -> list[resource_schema.MappedResource]:
    logging.info("Loading DAO metadata from %s", name)
    path = get_module_path(root, name)
    if not path.is_file():
        raise ValueError(f"DAO module does not exist at {path}")
    sys.path.insert(0, str(root.resolve()))
    try:
        module = importlib.import_module(name)
    finally:
        sys.path.pop(0)
    if (
        module.__file__ is None
        or pathlib.Path(module.__file__).resolve() != path.resolve()
    ):
        raise ValueError("DAO module resolved outside the selected Python root")
    resources = []
    for value in vars(module).values():
        if not isinstance(value, type):
            continue
        mapper: orm.Mapper | None = sa.inspect(value, raiseerr=False)
        if isinstance(mapper, orm.Mapper) and mapper.class_.__module__ == name:
            mapper.registry.configure()
            resources.append(resource_schema.MappedResource(mapper))
    if not resources:
        raise ValueError("Selected DAO module contains no mapped resource classes")
    logging.info("Loaded %s mapped resources", len(resources))
    return resources


def write_artifacts(
    artifacts: list[generated_artifact.GeneratedArtifact], sources: list[pathlib.Path]
) -> None:
    paths = [artifact.path.resolve() for artifact in artifacts]
    if len(paths) != len(set(paths)):
        raise ValueError("Generated output files must have distinct paths")
    for artifact in artifacts:
        artifact.validate_destination(sources)
    for artifact in artifacts:
        artifact.path.parent.mkdir(parents=True, exist_ok=True)
        artifact.path.write_text(artifact.content, encoding="utf-8")
