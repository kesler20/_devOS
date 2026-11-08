from __future__ import annotations

import dataclasses
import logging
import typing

import pydantic
import sqlalchemy
import sqlalchemy.orm

import adapters_clients.database.sql_database_adapter as database

TOrm = typing.TypeVar("TOrm", bound=sqlalchemy.orm.DeclarativeBase)
TWrite = typing.TypeVar("TWrite", bound=pydantic.BaseModel)
TRead = typing.TypeVar("TRead", bound=pydantic.BaseModel)
TReadRelationship = typing.TypeVar("TReadRelationship", bound=pydantic.BaseModel)
TInput = typing.TypeVar("TInput", bound=pydantic.BaseModel)


class EntityNotFoundError(LookupError):
    pass


class InvalidEntityInputError(ValueError):
    pass


class EntityConstraintError(ValueError):
    pass


class WriteEntityRequest(pydantic.BaseModel, typing.Generic[TWrite]):
    entity: TWrite


class WriteEntityResponse(pydantic.BaseModel, typing.Generic[TRead]):
    entity: TRead


class ReadEntityRequest(pydantic.BaseModel):
    entity_id: database.EntityIdentity


class ReadEntityResponse(pydantic.BaseModel, typing.Generic[TRead]):
    entity: TRead | None


class ReadEntityRelationshipsResponse(
    pydantic.BaseModel, typing.Generic[TReadRelationship]
):
    entity: TReadRelationship | None


class ReadEntityRelationshipRequest(pydantic.BaseModel):
    entity_id: database.EntityIdentity
    relationship: str


class ReadEntityRelationshipResponse(pydantic.BaseModel, typing.Generic[TRead]):
    related_entities: list[pydantic.SerializeAsAny[TRead]]


class ReadAllEntitiesResponse(pydantic.BaseModel, typing.Generic[TRead]):
    entities: list[TRead]


class DeleteEntityRequest(pydantic.BaseModel):
    entity_id: database.EntityIdentity


class DeleteEntityResponse(pydantic.BaseModel):
    message: str


@dataclasses.dataclass(frozen=True)
class CRUDSpec(typing.Generic[TOrm, TWrite, TRead, TReadRelationship]):
    orm_model: type[TOrm]
    write_in: type[TWrite]
    read_out: type[TRead]
    read_relationships_out: type[TReadRelationship] | None = None
    patch_in: type[pydantic.BaseModel] | None = None
    relationship_read_out: dict[str, type[pydantic.BaseModel]] = dataclasses.field(
        default_factory=dict
    )

    def to_orm_write(self, dto: pydantic.BaseModel, creating: bool = True) -> TOrm:
        schema = self.write_in if creating or self.patch_in is None else self.patch_in
        supplied = dto.model_dump(exclude_unset=True)
        if not set(supplied) <= schema.model_fields.keys():
            raise InvalidEntityInputError(
                "Payload contains attributes outside the selected write contract"
            )
        try:
            validated = schema.model_validate(supplied)
        except pydantic.ValidationError as error:
            raise InvalidEntityInputError("Invalid create/PATCH payload") from error
        values = validated.model_dump(exclude_unset=True)
        mapper = typing.cast(
            sqlalchemy.orm.Mapper[TOrm], sqlalchemy.inspect(self.orm_model)
        )
        columns = {
            attribute.key: attribute.columns[0] for attribute in mapper.column_attrs
        }
        if not set(values) <= columns.keys():
            raise InvalidEntityInputError(
                "Writes may contain only mapped scalar attributes"
            )
        for name, column in columns.items():
            if name not in values:
                generated = (
                    column.default is not None
                    or column.server_default is not None
                    or column.identity is not None
                )
                generated = (
                    generated
                    or column
                    is typing.cast(sqlalchemy.Table, column.table).autoincrement_column
                )
                if creating and not column.nullable and not generated:
                    raise InvalidEntityInputError(f"Create requires {name}")
                continue
            value = values[name]
            if value is None:
                if not column.nullable:
                    raise InvalidEntityInputError(f"{name} does not allow null")
                continue
            if creating and column.identity is not None and column.identity.always:
                raise InvalidEntityInputError(
                    f"{name} is generated always and cannot be supplied"
                )
            if not creating and column.primary_key:
                raise InvalidEntityInputError(
                    "PATCH cannot change primary-key attributes"
                )
            try:
                values[name] = database.coerce_database_value(column.type, value)
            except ValueError as error:
                raise InvalidEntityInputError(f"Invalid value for {name}") from error
        return self.orm_model(**values)

    def apply_patch(self, row: TOrm, dto: pydantic.BaseModel) -> TOrm:
        validated = self.to_orm_write(dto, creating=False)
        for name in dto.model_fields_set:
            setattr(row, name, getattr(validated, name))
        return row

    def to_read(self, row: TOrm) -> TRead:
        return self.read_out.model_validate(row, from_attributes=True)

    def to_read_relationships(self, row: TOrm) -> TReadRelationship:
        if self.read_relationships_out is None:
            raise InvalidEntityInputError(
                "Configure read_relationships_out for expanded reads"
            )
        return self.read_relationships_out.model_validate(row, from_attributes=True)


class CRUDUseCase(typing.Generic[TOrm, TWrite, TRead, TReadRelationship]):
    def __init__(
        self,
        db_session: sqlalchemy.orm.Session,
        spec: CRUDSpec[TOrm, TWrite, TRead, TReadRelationship],
    ) -> None:
        self.db_session = database.SQLDatabaseAdapter(db_session)
        self.spec = spec

    def write_entity(
        self,
        request: WriteEntityRequest[TInput],
        entity_id: database.EntityIdentity | None = None,
    ) -> WriteEntityResponse[TRead]:
        if entity_id is None:
            row = self.spec.to_orm_write(request.entity)
        else:
            existing = self.db_session.read_identity(self.spec.orm_model, entity_id)
            if existing is None:
                raise EntityNotFoundError("Entity not found")
            row = self.spec.apply_patch(existing, request.entity)
        try:
            saved = self.db_session.add_value(row)
        except sqlalchemy.exc.IntegrityError as error:
            raise EntityConstraintError(
                "Write violates a database constraint"
            ) from error
        logging.info("Saved %s", self.spec.orm_model.__name__)
        return WriteEntityResponse(entity=self.spec.to_read(saved))

    def read_entity(self, request: ReadEntityRequest) -> ReadEntityResponse[TRead]:
        row = self.db_session.read_identity(self.spec.orm_model, request.entity_id)
        return ReadEntityResponse(
            entity=self.spec.to_read(row) if row is not None else None
        )

    def read_entity_relationships(
        self, request: ReadEntityRequest
    ) -> ReadEntityRelationshipsResponse[TReadRelationship]:
        row = self.db_session.read_identity(self.spec.orm_model, request.entity_id)
        return ReadEntityRelationshipsResponse(
            entity=self.spec.to_read_relationships(row) if row is not None else None
        )

    def read_all_entities(self) -> ReadAllEntitiesResponse[TRead]:
        rows = self.db_session.read_all_values(self.spec.orm_model)
        return ReadAllEntitiesResponse(
            entities=[self.spec.to_read(row) for row in rows]
        )

    def read_entity_relationship(
        self, request: ReadEntityRelationshipRequest
    ) -> ReadEntityRelationshipResponse[pydantic.BaseModel]:
        related_schema = self.spec.relationship_read_out.get(request.relationship)
        mapper = typing.cast(
            sqlalchemy.orm.Mapper[TOrm], sqlalchemy.inspect(self.spec.orm_model)
        )
        if related_schema is None or request.relationship not in mapper.relationships:
            raise InvalidEntityInputError(
                "Configure the related resource's read DTO for this relationship"
            )
        row = self.db_session.read_identity(self.spec.orm_model, request.entity_id)
        if row is None:
            return ReadEntityRelationshipResponse(related_entities=[])
        relationship = mapper.relationships[request.relationship]
        related = getattr(row, request.relationship)
        rows = (
            list(related)
            if relationship.uselist
            else ([related] if related is not None else [])
        )
        return ReadEntityRelationshipResponse(
            related_entities=[
                related_schema.model_validate(item, from_attributes=True)
                for item in rows
            ]
        )

    def delete_entity(self, request: DeleteEntityRequest) -> DeleteEntityResponse:
        try:
            deleted = self.db_session.delete_identity(
                self.spec.orm_model, request.entity_id
            )
        except sqlalchemy.exc.IntegrityError as error:
            raise EntityConstraintError(
                "Delete violates a database constraint"
            ) from error
        if not deleted:
            raise EntityNotFoundError("Entity not found")
        return DeleteEntityResponse(message="Entity deleted successfully")
