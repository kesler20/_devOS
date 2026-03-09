import pytest
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, DeclarativeBase, relationship
import pydantic
import project_name.use_cases.use_cases as use_cases  # type: ignore


class Base(DeclarativeBase):
    pass


class TestCollectionORM(Base):
    """Test ORM model for collections"""

    __tablename__ = "test_collections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    description = Column(String(200), nullable=True)

    items = relationship("TestItemORM", back_populates="collection")


class TestItemORM(Base):
    """Test ORM model for items with relationship to collections"""

    __tablename__ = "test_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    collection_id = Column(Integer, ForeignKey("test_collections.id"))

    collection = relationship("TestCollectionORM", back_populates="items")


class CollectionWrite(pydantic.BaseModel):
    """Write schema for collections"""

    name: str
    description: str | None = None


class CollectionRead(pydantic.BaseModel):
    """Read schema for collections"""

    id: int
    name: str
    description: str | None = None

    model_config = pydantic.ConfigDict(from_attributes=True)


class ItemWrite(pydantic.BaseModel):
    """Write schema for items"""

    name: str
    collection_id: int


class ItemRead(pydantic.BaseModel):
    """Read schema for items"""

    id: int
    name: str
    collection_id: int

    model_config = pydantic.ConfigDict(from_attributes=True)


class TestCRUDUseCase:
    """Pytest test class for use_cases.CRUDUseCase"""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup test database and use case"""
        print("Setting up in-memory database...")
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine)
        self.session = Session()

        # Create CRUD specs
        self.collection_spec = use_cases.CRUDSpec(
            orm_model=TestCollectionORM,
            write_in=CollectionWrite,
            read_out=CollectionRead,
        )

        self.item_spec = use_cases.CRUDSpec(
            orm_model=TestItemORM,
            write_in=ItemWrite,
            read_out=ItemRead,
        )

        self.collection_crud = use_cases.CRUDUseCase(self.session, self.collection_spec)
        self.item_crud = use_cases.CRUDUseCase(self.session, self.item_spec)

        yield

        print("Cleaning up database...")
        self.session.close()

    def test_write_entity_create(self):
        """Test creating a new entity"""
        print("Testing write_entity (create)...")
        request = use_cases.WriteEntityRequest(
            entity=CollectionWrite(
                name="Test Collection", description="A test collection"
            )
        )

        response = self.collection_crud.write_entity(request)

        assert response.entity.id is not None
        assert response.entity.name == "Test Collection"
        assert response.entity.description == "A test collection"

    def test_write_entity_update(self):
        """Test updating an existing entity"""
        print("Testing write_entity (update)...")
        # Create entity first
        create_request = use_cases.WriteEntityRequest(
            entity=CollectionWrite(
                name="Original Name", description="Original description"
            )
        )
        created = self.collection_crud.write_entity(create_request)

        # Update the entity
        update_request = use_cases.WriteEntityRequest(
            entity=CollectionWrite(
                name="Updated Name", description="Updated description"
            )
        )
        response = self.collection_crud.write_entity(
            update_request, entity_id=created.entity.id
        )

        assert response.entity.id == created.entity.id
        assert response.entity.name == "Updated Name"
        assert response.entity.description == "Updated description"

    def test_read_entity(self):
        """Test reading a single entity"""
        print("Testing read_entity...")
        # Create entity first
        create_request = use_cases.WriteEntityRequest(
            entity=CollectionWrite(name="Read Test", description="Test reading")
        )
        created = self.collection_crud.write_entity(create_request)

        # Read the entity
        read_request = use_cases.ReadEntityRequest(entity_id=created.entity.id)
        response = self.collection_crud.read_entity(read_request)

        assert response.entity is not None
        assert response.entity.id == created.entity.id
        assert response.entity.name == "Read Test"

    def test_read_entity_not_found(self):
        """Test reading a non-existent entity returns None"""
        print("Testing read_entity (not found)...")
        request = use_cases.ReadEntityRequest(entity_id=999)
        response = self.collection_crud.read_entity(request)

        assert response.entity is None

    def test_read_all_entities(self):
        """Test reading all entities"""
        print("Testing read_all_entities...")
        # Create multiple entities
        collections = [
            CollectionWrite(name=f"Collection {i}", description=f"Description {i}")
            for i in range(3)
        ]
        for collection in collections:
            self.collection_crud.write_entity(
                use_cases.WriteEntityRequest(entity=collection)
            )

        response = self.collection_crud.read_all_entities()

        assert len(response.entities) == 3
        assert all(entity.name.startswith("Collection") for entity in response.entities)

    def test_read_all_entities_empty(self):
        """Test reading all entities when table is empty"""
        print("Testing read_all_entities (empty)...")
        response = self.collection_crud.read_all_entities()

        assert len(response.entities) == 0

    def test_read_entity_relationship_one_to_many(self):
        """Test reading one-to-many relationship"""
        print("Testing read_entity_relationship (one-to-many)...")
        # Create a collection
        collection_request = use_cases.WriteEntityRequest(
            entity=CollectionWrite(
                name="Main Collection", description="Parent collection"
            )
        )
        collection = self.collection_crud.write_entity(collection_request)

        # Create items related to the collection
        items = [
            ItemWrite(name=f"Item {i}", collection_id=collection.entity.id)
            for i in range(3)
        ]
        for item in items:
            self.item_crud.write_entity(use_cases.WriteEntityRequest(entity=item))

        # Read the relationship
        request = use_cases.ReadEntityRelationshipRequest(
            entity_id=collection.entity.id, relationship="items"
        )
        response = self.collection_crud.read_entity_relationship(request)

        assert len(response.related_entities) == 3
        assert all(
            entity.name.startswith("Item") for entity in response.related_entities
        )

    def test_read_entity_relationship_entity_not_found(self):
        """Test reading relationship when entity doesn't exist"""
        print("Testing read_entity_relationship (entity not found)...")
        request = use_cases.ReadEntityRelationshipRequest(
            entity_id=999, relationship="items"
        )
        response = self.collection_crud.read_entity_relationship(request)

        assert len(response.related_entities) == 0

    def test_read_entity_relationship_not_found(self):
        """Test reading non-existent relationship"""
        print("Testing read_entity_relationship (relationship not found)...")
        # Create a collection
        collection_request = use_cases.WriteEntityRequest(
            entity=CollectionWrite(name="Test Collection", description="Test")
        )
        collection = self.collection_crud.write_entity(collection_request)

        # Try to read a non-existent relationship
        request = use_cases.ReadEntityRelationshipRequest(
            entity_id=collection.entity.id, relationship="nonexistent_relationship"
        )
        response = self.collection_crud.read_entity_relationship(request)

        assert len(response.related_entities) == 0

    def test_delete_entity(self):
        """Test deleting an entity"""
        print("Testing delete_entity...")
        # Create entity first
        create_request = use_cases.WriteEntityRequest(
            entity=CollectionWrite(name="To Delete", description="Will be deleted")
        )
        created = self.collection_crud.write_entity(create_request)

        # Delete the entity
        delete_request = use_cases.DeleteEntityRequest(entity_id=created.entity.id)
        response = self.collection_crud.delete_entity(delete_request)

        assert "deleted successfully" in response.message

        # Verify it's deleted
        read_request = use_cases.ReadEntityRequest(entity_id=created.entity.id)
        read_response = self.collection_crud.read_entity(read_request)
        assert read_response.entity is None

    def test_delete_entity_cascade(self):
        """Test deleting entity with cascade to related entities"""
        print("Testing delete_entity (with cascade)...")
        # Create a collection with items
        collection_request = use_cases.WriteEntityRequest(
            entity=CollectionWrite(name="To Delete", description="Parent")
        )
        collection = self.collection_crud.write_entity(collection_request)

        # Create related items
        for i in range(2):
            item_request = use_cases.WriteEntityRequest(
                entity=ItemWrite(name=f"Item {i}", collection_id=collection.entity.id)
            )
            self.item_crud.write_entity(item_request)

        # Delete the collection (should cascade to items)
        delete_request = use_cases.DeleteEntityRequest(entity_id=collection.entity.id)
        self.collection_crud.delete_entity(delete_request)

        # Verify collection is deleted
        read_request = use_cases.ReadEntityRequest(entity_id=collection.entity.id)
        response = self.collection_crud.read_entity(read_request)
        assert response.entity is None

    def test_custom_id_field(self):
        """Test CRUD operations with custom ID field name"""
        print("Testing custom id_field...")
        # Create a spec with custom id field
        custom_spec = use_cases.CRUDSpec(
            orm_model=TestCollectionORM,
            write_in=CollectionWrite,
            read_out=CollectionRead,
            id_field="id",  # Explicit even though it's default
        )
        custom_crud = use_cases.CRUDUseCase(self.session, custom_spec)

        # Create and read
        create_request = use_cases.WriteEntityRequest(
            entity=CollectionWrite(name="Custom ID Test", description="Test")
        )
        created = custom_crud.write_entity(create_request)

        read_request = use_cases.ReadEntityRequest(entity_id=created.entity.id)
        response = custom_crud.read_entity(read_request)

        assert response.entity is not None
        assert response.entity.id == created.entity.id

    def test_write_entity_partial_update(self):
        """Test partial update using exclude_unset"""
        print("Testing write_entity (partial update)...")
        # Create entity
        create_request = use_cases.WriteEntityRequest(
            entity=CollectionWrite(name="Original", description="Original description")
        )
        created = self.collection_crud.write_entity(create_request)

        # Update only name (description should remain)
        update_request = use_cases.WriteEntityRequest(
            entity=CollectionWrite(
                name="Updated Only Name", description="Original description"
            )
        )
        response = self.collection_crud.write_entity(
            update_request, entity_id=created.entity.id
        )

        assert response.entity.name == "Updated Only Name"
        assert response.entity.description == "Original description"
