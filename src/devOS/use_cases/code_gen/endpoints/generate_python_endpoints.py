from __future__ import annotations
from devOS.use_cases.utils.file_io import File
import devOS.domain.entities as entities
import devOS.use_cases.utils.codegen_helpers as codegen_utils


def generate_app_definition_code(project_name: str) -> str:
    return f"""
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

DATABASE_URL = "sqlite:///./{project_name}_db.sqlite3"
APP_NAME = "{project_name.replace('_', ' ').title()}"
APP_VERSION = "1.0"

app = FastAPI(title=APP_NAME, version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["root"])
async def read_root():
    return RedirectResponse(url="/docs")


# Database engine and session factory
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    \"\"\"Dependency that yields a database session and ensures it's closed after use.\"\"\"
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
"""

def generate_crud_endpoints_for_dao(
    dao_spec: entities.DAOSchemaSpec, version: str = "v1"
) -> str:
    """Generate CRUD endpoints for a single DAO."""
    name = dao_spec.name
    table_name = dao_spec.table_name
    table_name_lower = table_name.lower()

    # Find primary key property
    pk_prop = next(
        (
            p
            for p in dao_spec.properties
            if p.key_type and p.key_type.type == "primary_key"
        ),
        None,
    )
    identifier_name = pk_prop.name if pk_prop else "id"
    pk_type = entities.convert_type_py(pk_prop.type) if pk_prop else "int"

    code = f"""
{table_name_lower}_spec: use_cases.CRUDSpec[
    dao.{name}, dtos.{name}Write, dtos.{name}Read
] = use_cases.CRUDSpec(
    orm_model=dao.{name},
    write_in=dtos.{name}Write,
    read_out=dtos.{name}Read,
)


@app.post(
    "/{version}/{table_name_lower}",
    response_model=use_cases.WriteEntityResponse[dtos.{name}Read],
    tags=["{table_name_lower}"],
)
async def create_{table_name_lower}(
    request: use_cases.WriteEntityRequest[dtos.{name}Write] = Body(...),
    db_session: sqlalchemy.orm.Session = Depends(get_db),
):
    return use_cases.CRUDUseCase(db_session, {table_name_lower}_spec).write_entity(request)


@app.get(
    "/{version}/{table_name_lower}/{{{table_name_lower}_{identifier_name}}}",
    response_model=use_cases.ReadEntityResponse[dtos.{name}Read],
    tags=["{table_name_lower}"],
)
async def read_{table_name_lower}(
    {table_name_lower}_{identifier_name}: {pk_type} = Path(...),
    db_session: sqlalchemy.orm.Session = Depends(get_db),
):
    return use_cases.CRUDUseCase(db_session, {table_name_lower}_spec).read_entity(
        use_cases.ReadEntityRequest(entity_id={table_name_lower}_{identifier_name})
    )


@app.get(
    "/{version}/{table_name_lower}",
    response_model=use_cases.ReadAllEntitiesResponse[dtos.{name}Read],
    tags=["{table_name_lower}"],
)
async def read_all_{table_name_lower}(
    db_session: sqlalchemy.orm.Session = Depends(get_db),
):
    return use_cases.CRUDUseCase(db_session, {table_name_lower}_spec).read_all_entities()


@app.patch(
    "/{version}/{table_name_lower}/{{{table_name_lower}_{identifier_name}}}",
    response_model=use_cases.WriteEntityResponse[dtos.{name}Read],
    tags=["{table_name_lower}"],
)
async def update_{table_name_lower}(
    {table_name_lower}_{identifier_name}: {pk_type} = Path(...),
    request: use_cases.WriteEntityRequest[dtos.{name}Write] = Body(...),
    db_session: sqlalchemy.orm.Session = Depends(get_db),
):
    return use_cases.CRUDUseCase(db_session, {table_name_lower}_spec).write_entity(request, entity_id={table_name_lower}_{identifier_name})


@app.delete(
    "/{version}/{table_name_lower}/{{{table_name_lower}_{identifier_name}}}",
    response_model=use_cases.DeleteEntityResponse,
    tags=["{table_name_lower}"],
)
async def delete_{table_name_lower}(
    {table_name_lower}_{identifier_name}: {pk_type} = Path(...),
    db_session: sqlalchemy.orm.Session = Depends(get_db),
):
    return use_cases.CRUDUseCase(db_session, {table_name_lower}_spec).delete_entity(
        use_cases.DeleteEntityRequest(entity_id={table_name_lower}_{identifier_name})
    )
"""

    return code


def generate_relationship_endpoints_for_dao(
    dao_spec: entities.DAOSchemaSpec, version: str = "v1"
) -> str:
    """Generate endpoints for all relationships of a DAO."""
    name = dao_spec.name
    table_name = dao_spec.table_name
    table_name_lower = table_name.lower()

    # Find primary key property
    pk_prop = next(
        (
            p
            for p in dao_spec.properties
            if p.key_type and p.key_type.type == "primary_key"
        ),
        None,
    )
    identifier_name = pk_prop.name if pk_prop else "id"
    pk_type = entities.convert_type_py(pk_prop.type) if pk_prop else "int"

    code = ""
    for prop in dao_spec.properties:
        if prop.type not in {"array", "object"}:
            continue
        rel_name = prop.name
        rel_path = f"/{version}/{table_name_lower}/{{{table_name_lower}_{identifier_name}}}/{rel_name}"
        code += f"""
@app.get(
    "{rel_path}",
    response_model=use_cases.ReadEntityRelationshipResponse,
    tags=["{table_name_lower}"],
)
async def read_{table_name_lower}_{rel_name}_relationship(
    {table_name_lower}_{identifier_name}: {pk_type} = Path(...),
    db_session: sqlalchemy.orm.Session = Depends(get_db),
):
    return use_cases.CRUDUseCase(db_session, {table_name_lower}_spec).read_entity_relationship(
        use_cases.ReadEntityRelationshipRequest(
            entity_id={table_name_lower}_{identifier_name},
            relationship="{rel_name}"
        )
    )
"""
    return code


def generate_crud_endpoints_file(dao_specs: list[entities.DAOSchemaSpec]) -> str:
    """Generate CRUD endpoints file from DAO specs."""
    code = """from __future__ import annotations
import sqlalchemy.orm
from fastapi import Body, Path, Depends
import project_name.use_cases.use_cases as use_cases
import project_name.use_cases.crud_dto as dtos
import project_name.domain.dao as dao  
from project_name.infrastructure.app import app, get_db
"""

    # Generate CRUD endpoints - group by tag
    dao_by_tag: dict[str, list[entities.DAOSchemaSpec]] = {}
    for dao_spec in dao_specs:
        tag = dao_spec.table_name.lower()
        if tag not in dao_by_tag:
            dao_by_tag[tag] = []
        dao_by_tag[tag].append(dao_spec)

    for tag, daos in dao_by_tag.items():
        code += codegen_utils.generate_tag_block_comment(tag.upper())
        for dao_spec in daos:
            code += generate_crud_endpoints_for_dao(dao_spec, version="v1")
            code += generate_relationship_endpoints_for_dao(dao_spec, version="v1")

    return code


def generate_endpoints_code(
    endpoints_spec: entities.EndpointsSpec, dao_specs: list[entities.DAOSchemaSpec]
) -> str:
    """Generate custom endpoints file from endpoint specs."""
    code = """from __future__ import annotations
import typing
import sqlalchemy.orm
import fastapi
from fastapi import Body, HTTPException, Depends, UploadFile, Path
import project_name.use_cases.use_cases as use_cases
import project_name.use_cases.dto as dtos
import project_name.domain.dao as dao  
from project_name.infrastructure.crud_routes import app, get_db
from fastapi.responses import FileResponse
"""

    # Track which tags have block comments already
    tags_with_comments: set[str] = set()

    # Get all tags from DAO specs
    for dao_spec in dao_specs:
        tags_with_comments.add(dao_spec.table_name.lower())

    # Generate custom endpoints - one block comment per tag (only if not already added)
    for tag, endpoints in endpoints_spec.endpoints.items():
        if endpoints:
            # Filter endpoints by language before adding block comment
            valid_endpoints = [
                ep for ep in endpoints if ep.language is None or "python" in ep.language
            ]

            if valid_endpoints and tag not in tags_with_comments:
                code += codegen_utils.generate_tag_block_comment(tag.upper())
                tags_with_comments.add(tag)

            for ep in valid_endpoints:
                pascal = entities.convert_to_pascal(ep.name)

                method = ep.method.lower()
                v = ep.version
                path = ep.path.lstrip("/")
                full_path = f"/{v}/{path}"

                path_fields, body_fields = codegen_utils.generate_schema_for_request(
                    ep, language="python"
                )
                path_fields = codegen_utils.merge_implied_path_params_into_path_fields(
                    ep.path, path_fields
                )

                code += (
                    f'@app.{method}("{full_path}", response_model=dtos.{pascal}Response, tags={[tag]!r})\n'
                    f"async def {ep.name}(\n"
                )

                for f in sorted(path_fields, key=lambda x: x["name"]):
                    desc = f.get("description")
                    typ = f["type"]
                    if desc:
                        code += f'    {f["name"]}: {typ} = Path(..., description="{desc}"),\n'
                    else:
                        code += f'    {f["name"]}: {typ} = Path(...),\n'

                if path_fields and body_fields:
                    code += f"    body: dtos.{pascal}Body = Body(...),\n"
                elif (not path_fields) and body_fields:
                    code += f"    request: dtos.{pascal}Request = Body(...),\n"

                code += "):\n"

                has_request = False
                if path_fields and body_fields:
                    args = ", ".join(
                        f'{f["name"]}={f["name"]}'
                        for f in sorted(path_fields, key=lambda x: x["name"])
                    )
                    code += f"    request = dtos.{pascal}Request(**body.model_dump(), {args})\n"
                    has_request = True
                elif path_fields and not body_fields and ep.request_schema:
                    args = ", ".join(
                        f'{f["name"]}={f["name"]}'
                        for f in sorted(path_fields, key=lambda x: x["name"])
                    )
                    code += f"    request = dtos.{pascal}Request({args})\n"
                    has_request = True
                elif (not path_fields) and body_fields:
                    has_request = True  # request param already exists

                if has_request:
                    code += f"    return use_cases.{ep.use_case.name}().{ep.use_case.method}(request)\n\n"
                else:
                    code += f"    return use_cases.{ep.use_case.name}().{ep.use_case.method}()\n\n"

    return code


def main():
    endpoints_raw = File("tests", "specs", "endpoints_spec.json").get_json()
    endpoints_spec = entities.EndpointsSpec.model_validate(endpoints_raw)

    dao_raw = File("tests", "specs", "dao_spec.json").get_json()
    dao_specs = [entities.DAOSchemaSpec.model_validate(d) for d in dao_raw]

    # Generate CRUD endpoints from DAO specs
    crud_endpoints_code = generate_crud_endpoints_file(dao_specs)
    print("Generated CRUD Endpoints Code:\n", crud_endpoints_code)
    File("tests", "devOS", "crud_endpoints.py").write(crud_endpoints_code)

    # Generate custom endpoints from endpoint specs
    endpoints_code = generate_endpoints_code(endpoints_spec, dao_specs)
    print("Generated Custom Endpoints Code:\n", endpoints_code)
    File("tests", "devOS", "generated_endpoints.py").write(endpoints_code)


if __name__ == "__main__":
    main()
