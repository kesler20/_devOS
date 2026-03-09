import pytest
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from project_name.infrastructure.adapters import SQLAlchemySQLDbAdapter  # type: ignore


class Base(DeclarativeBase):
    pass


class TestUser(Base):
    """Test model for database operations"""

    __tablename__ = "test_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    email = Column(String(100), nullable=False)
    age = Column(Integer, nullable=True)


class TestSQLAlchemySQLDbAdapter:
    """Pytest test class for SQLAlchemySQLDbAdapter"""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup test database and adapter"""
        print("Setting up in-memory database...")
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        Session = sessionmaker(bind=engine)
        self.session = Session()
        self.adapter = SQLAlchemySQLDbAdapter(self.session)

        yield

        print("Cleaning up database...")
        self.session.close()

    def test_add_value(self):
        """Test adding a single value to the database"""
        print("Testing add_value...")
        new_user = TestUser(name="Alice", email="alice@example.com", age=30)
        result = self.adapter.add_value(new_user)

        assert result.id is not None
        assert result.name == "Alice"
        assert result.email == "alice@example.com"
        assert result.age == 30

    def test_add_values(self):
        """Test adding multiple values to the database"""
        print("Testing add_values...")
        users = [
            TestUser(name="Bob", email="bob@example.com", age=25),
            TestUser(name="Charlie", email="charlie@example.com", age=35),
        ]
        result = self.adapter.add_values(TestUser, users)

        assert len(result) == 2
        assert result[0].name == "Bob"
        assert result[1].name == "Charlie"

    def test_read_value(self):
        """Test reading a single value from the database"""
        print("Testing read_value...")
        new_user = TestUser(name="David", email="david@example.com", age=28)
        self.adapter.add_value(new_user)

        result = self.adapter.read_value(TestUser, name="David")

        assert result is not None
        assert result.name == "David"
        assert result.email == "david@example.com"

    def test_read_value_not_found(self):
        """Test reading a non-existent value returns None"""
        print("Testing read_value with non-existent record...")
        result = self.adapter.read_value(TestUser, name="NonExistent")

        assert result is None

    def test_read_values(self):
        """Test reading multiple values from the database"""
        print("Testing read_values...")
        users = [
            TestUser(name="Eve", email="eve1@example.com", age=30),
            TestUser(name="Eve", email="eve2@example.com", age=30),
        ]
        self.adapter.add_values(TestUser, users)

        result = self.adapter.read_values(TestUser, name="Eve")

        assert len(result) == 2
        assert all(user.name == "Eve" for user in result)

    def test_read_all_values(self):
        """Test reading all values from the database"""
        print("Testing read_all_values...")
        users = [
            TestUser(name="Frank", email="frank@example.com", age=40),
            TestUser(name="Grace", email="grace@example.com", age=32),
        ]
        self.adapter.add_values(TestUser, users)

        result = self.adapter.read_all_values(TestUser)

        assert len(result) == 2

    def test_read_all_values_with_pagination(self):
        """Test reading paginated values from the database"""
        print("Testing read_all_values_with_pagination...")
        users = [
            TestUser(name=f"User{i}", email=f"user{i}@example.com", age=20 + i)
            for i in range(5)
        ]
        self.adapter.add_values(TestUser, users)

        page_1 = self.adapter.read_all_values_with_pagination(TestUser, 2, 1)
        page_2 = self.adapter.read_all_values_with_pagination(TestUser, 2, 2)

        assert len(page_1) == 2
        assert len(page_2) == 2
        assert page_1[0].name != page_2[0].name

    def test_update_value(self):
        """Test updating a single field of a record"""
        print("Testing update_value...")
        new_user = TestUser(name="Henry", email="henry@example.com", age=45)
        self.adapter.add_value(new_user)

        result = self.adapter.update_value(
            TestUser, "email", "henry.new@example.com", name="Henry"
        )

        assert result is not None
        assert result.email == "henry.new@example.com"
        assert result.name == "Henry"

    def test_update_value_not_found(self):
        """Test updating a non-existent record returns None"""
        print("Testing update_value with non-existent record...")
        result = self.adapter.update_value(
            TestUser, "email", "new@example.com", name="NonExistent"
        )

        assert result is None

    def test_update_values(self):
        """Test updating multiple fields of a record by ID"""
        print("Testing update_values...")
        new_user = TestUser(name="Ivy", email="ivy@example.com", age=27)
        added = self.adapter.add_value(new_user)

        result = self.adapter.update_values(
            TestUser, added.id, name="Ivy Updated", email="ivy.updated@example.com"
        )

        assert result is not None
        assert result.name == "Ivy Updated"
        assert result.email == "ivy.updated@example.com"

    def test_delete_value(self):
        """Test deleting a specific value from the database"""
        print("Testing delete_value...")
        new_user = TestUser(name="Jack", email="jack@example.com", age=33)
        self.adapter.add_value(new_user)

        result = self.adapter.delete_value(TestUser, name="Jack")

        assert result is True
        assert self.adapter.read_value(TestUser, name="Jack") is None

    def test_delete_value_not_found(self):
        """Test deleting a non-existent value returns False"""
        print("Testing delete_value with non-existent record...")
        is_successful = self.adapter.delete_value(TestUser, name="NonExistent")

        assert is_successful is True

    def test_delete_all_values(self):
        """Test deleting all values from the database"""
        print("Testing delete_all_values...")
        users = [
            TestUser(name="Kate", email="kate@example.com", age=29),
            TestUser(name="Leo", email="leo@example.com", age=31),
        ]
        self.adapter.add_values(TestUser, users)

        self.adapter.delete_all_values(TestUser)
        result = self.adapter.read_all_values(TestUser)

        assert len(result) == 0

    def test_context_manager(self):
        """Test using the adapter as a context manager"""
        print("Testing context manager...")
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        with SQLAlchemySQLDbAdapter(session) as adapter:
            new_user = TestUser(name="Mike", email="mike@example.com", age=38)
            result = adapter.add_value(new_user)
            assert result.id is not None
