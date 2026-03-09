import sqlalchemy.orm
import typing
import pydantic
import dataclasses
from project_name.infrastructure.adapters import SQLAlchemySQLDbAdapter  # type: ignore

# ======================= #
#                         #
#   CRUD GENERIC TYPES    #
#                         #
# ======================= #

TOrm = typing.TypeVar("TOrm")  # SQLAlchemy ORM type
TWrite = typing.TypeVar("TWrite", bound=pydantic.BaseModel)
TRead = typing.TypeVar("TRead", bound=pydantic.BaseModel)
TReadRelationship = typing.TypeVar("TReadRelationship", bound=pydantic.BaseModel)


# ======================== #
#                          #
#   GENERAL CRUD DTOs      #
#                          #
# ======================== #


class WriteEntityRequest(pydantic.BaseModel, typing.Generic[TWrite]):
    """Write request envelope. Keeps a stable key: request.entity"""

    entity: TWrite


class WriteEntityResponse(pydantic.BaseModel, typing.Generic[TRead]):
    """Write response envelope. Keeps a stable key: response.entity"""

    entity: TRead


class ReadEntityRequest(pydantic.BaseModel):
    """Read request envelope. Keeps a stable key: request.entity_id"""

    entity_id: int


class ReadEntityResponse(pydantic.BaseModel, typing.Generic[TRead]):
    entity: TRead | None


class ReadEntityRelationshipsResponse(
    pydantic.BaseModel, typing.Generic[TReadRelationship]
):
    """Response envelope for relationship-expanded entity reads."""

    entity: TReadRelationship | None


class ReadEntityRelationshipRequest(pydantic.BaseModel):
    entity_id: int
    relationship: str


class ReadEntityRelationshipResponse(pydantic.BaseModel, typing.Generic[TRead]):
    related_entities: list[TRead]


class ReadAllEntitiesResponse(pydantic.BaseModel, typing.Generic[TRead]):
    entities: list[TRead]


class DeleteEntityRequest(pydantic.BaseModel):
    entity_id: int


class DeleteEntityResponse(pydantic.BaseModel):
    message: str


# ========================= #
#                           #
#   CRUD SPECIFICATION      #
#                           #
# ========================= #


# NOTE: you could add this to the CRUDUseCase constructor directly,
# but having a separate spec class makes it cleaner as you define the spec once and pass it to
# multiple use case instances within endpoints.
@dataclasses.dataclass(frozen=True)
class CRUDSpec(typing.Generic[TOrm, TWrite, TRead, TReadRelationship]):
    """Constrained spec for a DAO's CRUD schemas.

    The generator should emit one CRUDSpec per ORM model, plus the concrete
    Pydantic schemas (Write/Read/ReadRelationship).

    Attributes
    ----------
    orm_model : type[TOrm]
        The SQLAlchemy ORM model class.
    write_in : type[TWrite]
        Pydantic model for write operations (create/update).
    read_out : type[TRead]
        Pydantic model for shallow read operations (no relationships).
    read_relationships_out : type[TReadRelationship] | None
        Pydantic model for relationship-expanded read operations.
        When set, enables read_entity_relationships() method.
    id_field : str
        Name of the primary key field (default: "id").
    read_relationships_loader_options : list[object]
        SQLAlchemy loader options for eager loading relationships.
        Reserved for future use with joinedload/selectinload.

    Example
    -------
    ```python
    from devOS import CRUDSpec, CRUDUseCase

    class UserWrite(pydantic.BaseModel):
        username: str

    class UserRead(pydantic.BaseModel):
        id: int
        username: str

    class UserReadRelationship(pydantic.BaseModel):
        id: int
        username: str
        posts: list[PostRead]  # References shallow PostRead, not PostReadRelationship

    user_crud_spec = CRUDSpec(
        orm_model=UserORM,
        write_in=UserWrite,
        read_out=UserRead,
        read_relationships_out=UserReadRelationship,
    )

    CRUDUseCase(db_session, user_crud_spec).write_entity(...)
    CRUDUseCase(db_session, user_crud_spec).read_entity_relationships(...)
    ```
    """

    orm_model: type[TOrm]
    write_in: type[TWrite]
    read_out: type[TRead]
    read_relationships_out: type[TReadRelationship] | None = None

    id_field: str = "id"
    read_relationships_loader_options: list[object] = dataclasses.field(
        default_factory=list
    )

    def to_orm_write(self, dto: TWrite) -> TOrm:
        # Default: ORM constructor kwargs from validated DTO data.
        data = dto.model_dump(exclude_unset=True)
        return self.orm_model(**data)  # type: ignore[arg-type]

    def to_read(self, orm_obj: TOrm) -> TRead:
        # Validate/serialize from ORM attributes (shallow, no relationships).
        return self.read_out.model_validate(orm_obj, from_attributes=True)  # type: ignore[return-value]

    def to_read_relationships(self, orm_obj: TOrm) -> TReadRelationship:
        """Serialize ORM object to relationship-expanded DTO.

        Parameters
        ----------
        orm_obj : TOrm
            The ORM object to serialize.

        Returns
        -------
        TReadRelationship
            The relationship-expanded DTO.

        Raises
        ------
        ValueError
            If read_relationships_out is not configured on this spec.
        """
        if self.read_relationships_out is None:
            raise ValueError(
                f"read_relationships_out is not configured for {self.orm_model.__name__}. "
                "Set read_relationships_out in CRUDSpec to use read_entity_relationships()."
            )
        return self.read_relationships_out.model_validate(orm_obj, from_attributes=True)  # type: ignore[return-value]


# =================== #
#                     #
#   CRUD USE CASE     #
#                     #
# =================== #


class CRUDUseCase(typing.Generic[TOrm, TWrite, TRead, TReadRelationship]):
    def __init__(
        self,
        db_session: sqlalchemy.orm.Session,
        spec: CRUDSpec[TOrm, TWrite, TRead, TReadRelationship],
    ):
        self.db_session = SQLAlchemySQLDbAdapter(db_session)
        self.spec = spec

    def write_entity(
        self, request: WriteEntityRequest[TWrite], entity_id: int | None = None
    ) -> WriteEntityResponse[TRead]:
        """Create or update an entity.

        Args:
            request: The write request containing the entity data
            entity_id: Optional ID of existing entity to update. If None, creates new entity.

        Returns:
            WriteEntityResponse with the created or updated entity
        """
        if entity_id is not None:
            # Update existing entity using the adapter's update_values method
            updated = self.db_session.update_values(
                self.spec.orm_model,
                entity_id,
                **request.entity.model_dump(exclude_unset=True),
            )
            if updated is None:
                raise ValueError(f"Entity with id {entity_id} not found")

            result = WriteEntityResponse(entity=self.spec.to_read(updated))
            print(f"Updated entity: {result.entity}")
        else:
            # Create new entity
            orm_obj = self.spec.to_orm_write(request.entity)
            created = self.db_session.add_value(orm_obj)
            result = WriteEntityResponse(entity=self.spec.to_read(created))
            print(f"Created entity: {result.entity}")
        return result

    def read_entity(self, request: ReadEntityRequest) -> ReadEntityResponse[TRead]:
        orm_obj = self.db_session.read_value(
            self.spec.orm_model, **{self.spec.id_field: request.entity_id}
        )
        if orm_obj is None:
            print(f"Entity with id {request.entity_id} not found")
            return ReadEntityResponse(entity=None)
        result = ReadEntityResponse(entity=self.spec.to_read(orm_obj))
        print(f"Read entity: {result.entity}")
        return result

    def read_entity_relationships(
        self, request: ReadEntityRequest
    ) -> ReadEntityRelationshipsResponse[TReadRelationship]:
        """Read an entity with all its relationships expanded.

        Returns the relationship-expanded DTO ({Entity}ReadRelationship) which includes
        scalar fields plus relationship fields. Relationship fields reference other
        entities' shallow Read DTOs (not their ReadRelationship DTOs) to prevent
        recursive serialization.

        Parameters
        ----------
        request : ReadEntityRequest
            Request containing the entity_id to read.

        Returns
        -------
        ReadEntityRelationshipsResponse[TReadRelationship]
            Response with the relationship-expanded entity, or entity=None if not found.

        Raises
        ------
        ValueError
            If read_relationships_out is not configured on the CRUDSpec.
        """
        orm_obj = self.db_session.read_value(
            self.spec.orm_model, **{self.spec.id_field: request.entity_id}
        )
        if orm_obj is None:
            print(f"Entity with id {request.entity_id} not found")
            return ReadEntityRelationshipsResponse(entity=None)
        result = ReadEntityRelationshipsResponse(
            entity=self.spec.to_read_relationships(orm_obj)
        )
        print(f"Read entity with relationships: {result.entity}")
        return result

    def read_all_entities(self) -> ReadAllEntitiesResponse[TRead]:
        entities = self.db_session.read_all_values(self.spec.orm_model)
        result = ReadAllEntitiesResponse(
            entities=[self.spec.to_read(x) for x in entities]
        )
        print("Entities Retrieved:", len(result.entities))
        return result

    def read_entity_relationship(
        self, request: ReadEntityRelationshipRequest
    ) -> ReadEntityRelationshipResponse[TRead]:
        """
        Given an entity ID and a relationship field name, return the related ORM objects
        as a list of read schema objects.
        """
        orm_obj = self.db_session.read_value(
            self.spec.orm_model, **{self.spec.id_field: request.entity_id}
        )
        if orm_obj is None:
            print(f"Entity with id {request.entity_id} not found")
            return ReadEntityRelationshipResponse(related_entities=[])
        related = getattr(orm_obj, request.relationship, None)
        if related is None:
            print(f"Relationship '{request.relationship}' not found on entity")
            return ReadEntityRelationshipResponse(related_entities=[])
        # If the relationship is a list, serialize each; else, wrap in a list
        if isinstance(related, list):
            result = ReadEntityRelationshipResponse(
                related_entities=[self.spec.to_read(x) for x in related]
            )
        else:
            result = ReadEntityRelationshipResponse(
                related_entities=[self.spec.to_read(related)]
            )
        print(
            f"Related entities for {request.relationship}: {len(result.related_entities)}"
        )
        return result

    def delete_entity(self, request: DeleteEntityRequest) -> DeleteEntityResponse:
        self.db_session.delete_value(
            self.spec.orm_model, **{self.spec.id_field: request.entity_id}
        )
        result = DeleteEntityResponse(
            message=f"Entity with id {request.entity_id} deleted successfully"
        )
        print(result.message)
        return result
