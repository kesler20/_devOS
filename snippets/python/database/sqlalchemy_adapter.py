from sqlalchemy.orm import Session
from typing import TypeVar, List, Any, Optional

T = TypeVar("T")


class SQLAlchemySQLDbAdapter:
    """The SQLAlchemySQLDbAdapter allows to implement CRUD operations on the tables of an SQL database.
    This is dove via SQLAlchemy tables which are the ORMs in python.

    initialise the SQLAlchemySQLDbAdapter in two main ways:

    Example
    -------
    ```python
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from ai_agent.domain.entities import Questionnaire
    from ai_agent.infrastructure.adapters import SQLAlchemySQLDbAdapter
    engine = create_engine('sqlite:///example.db')


    Session = sessionmaker(bind=engine)

    with Session() as session:
        db_adapter = SQLAlchemySQLDbAdapter(session)

        # Use db_adapter for CRUD operations
        db_adapter.add_value(Questionnaire(title="Sample Questionnaire", status="draft"))
        db_adapter.add_values(Questionnaire, [new_row])
        db_adapter.update_values(Questionnaire, 1, title="Updated Title")
        db_adapter.read_value(Questionnaire, id=1)
        db_adapter.read_values(Questionnaire, status="draft")
        db_adapter.read_all_values(Questionnaire)
        db_adapter.delete_value(Questionnaire, id=1)

    ```
    """

    def __init__(self, db: Session) -> None:
        self.session = db

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        """close the session to allow other processes to access the database"""
        self.session.close()

    def add_value(self, new_row: T) -> T:
        """add_value this method will add a row to the given table. i.e.

        ## Example
        ```python
        new_row = User(name='Alice', age=30)
        session = SQLAlchemySQLDbAdapter()
        session.add_value(new_row)
        ```

        Parameters
        ---

        new_row T
            this is the instance of the table class that we want to insert
            i.e. new_user = User(name='Alice')

        Returns
        ---
        result: T
        """
        # Insert a new row into the table
        self.session.add(new_row)
        self.session.commit()
        self.session.refresh(new_row)
        return new_row

    def add_values(self, class_table: type[T], new_row: List[T]) -> List[T]:
        """add_values this method will add a row to the given table. i.e.

        ## Example
        ```python
        new_row = User(name='Alice', age=30)
        session = SQLAlchemySQLDbAdapter()
        session.add_values(new_row)
        ```

        Parameters
        ---

        new_row List[T]
            this is the instance of the table class that we want to insert
            i.e. new_user = User(name='Alice')

        Returns
        ---
        result: List[T]
        """
        # Insert a new row into the table
        self.session.add_all(new_row)
        self.session.commit()
        return self.read_all_values(class_table)

    def update_values(
        self, class_table: type[T], row_id: Any, **kwargs: Any
    ) -> T | None:
        """This method updates all the values of a record in the database

        # Example
        ```python
        updated_row = Username="Daniel",email="email@gmail.com")
        session = SQLAlchemySQLDbAdapter()
        session.update_values(User, updated_row.dict(),name="Kesler")
        ```

        Parameters
        ----------

        class_table : Any
            the class that the table we want to update is represented in
        values: Dict[str, Any]
            a dictionary with all the key value pairs of the new object
        **kwargs : Any
            the key value pairs used to identify the record to modify

        Returns
        -------
        Any
            the updated record
        """
        row = self.session.query(class_table).filter_by(id=row_id).first()

        # update the properties dynamically based on a dictionary of key-value pairs
        for key, value in kwargs.items():
            print(key, value)
            setattr(row, key, value)

        self.session.flush()
        self.session.refresh(row)
        # commit the changes
        self.session.commit()
        return row

    def update_value(
        self, class_table: type[T], key: str, value: Any, **kwargs: Any
    ) -> Optional[T]:
        """update_value will update a record in the table

        ## Example
        ```python
        # this line will update the record email from Kesler to John
        session.update_value(database.User, "email", "John", email="Kesler")
        ```

        Parameters
        ----------
        class_table : Any
          this is the table of the database that the record we want
          to update is in

        key : str
          the column of the record we want to update
        value : Any
          the updated value of the record

        kwargs : Any
          key value pairs used to locate the record in the database

        Returns
        -------
        Optional[T]
          return the updated record, or None if not found
        """
        row = self.session.query(class_table).filter_by(**kwargs).first()
        if row is None:
            return None

        setattr(row, key, value)
        self.session.commit()
        self.session.refresh(row)
        return row

    def read_value(self, class_table: type[T], **kwargs: Any) -> Optional[T]:
        """read_value this will read a specific value (row) from the given table.

        # Example
        ```python
        session = SQLAlchemySQLDbAdapter()
        session.read_value(User,name="Mark")
        ```

        Parameters
        ---

        class_table type
            this is the name of the class of the table i.e. User
        **kwargs tuple
            this is the key value pair that we want to use for our query i.e.
            name='Paul'

        Returns
        ---
        result: tuple
            this will return all the records which meet the given conditions, i.e.
            if we are looking for name='Paul' it will return all the rows with the name 'Paul'
        """
        row = self.session.query(class_table).filter_by(**kwargs).first()
        if row is None:
            return None
        self.session.refresh(row)
        return row

    def read_values(self, class_table: type[T], **kwargs: Any) -> List[T]:
        """read_values gets all the values which have the specific combinations of
        keys and values passed

        # Example
        ```python
        sesion = SQLAlchemySQLDbAdapter()
        all_users_named_kesler = session.read_all_values(User,name="kesler")
        ```

        Parameters
        ---

        class_table type
            this is the name of the class of the table i.e. User
        kwargs : Any
            combination of key value pairs to identify the user

        Returns
        ---
        result: Any
        """
        return self.session.query(class_table).filter_by(**kwargs).all()

    def read_all_values(self, class_table: type[T]) -> List[T]:
        """read_all_values this method will read all the values from the SQL table

        # Example
        ```python
        sesion = SQLAlchemySQLDbAdapter()
        session.read_all_values(User)
        ```

        Parameters
        ---

        class_table type
            this is the name of the class of the table i.e. User

        Returns
        ---
        result: Any
        """
        # Query for all rows in the table
        return self.session.query(class_table).all()

    def read_all_values_with_pagination(
        self,
        class_table: type[T],
        number_of_objects_per_page: int,
        current_page_number: int,
    ) -> List[T]:
        """`read_all_values_with_pagination` this method will read all the values from the SQL table

        # Example
        ```python
        sesion = SQLAlchemySQLDbAdapter()
        session.read_all_values_with_pagination(User)
        ```

        Parameters
        ---

        class_table type
            this is the name of the class of the table i.e. User

        Returns
        ---
        result: Any
        """
        offset_number = (current_page_number - 1) * number_of_objects_per_page
        return (
            self.session.query(class_table)
            .offset(offset_number)
            .limit(number_of_objects_per_page)
            .all()
        )

    def delete_all_values(self, class_table: type[T]) -> None:
        """delete_value this method can be used to delete a specific value on the table or all the values which meet a specific condition.
        the row can be identified with a key value pair.

        ## Example
        ```python
        session = SQLAlchemySQLDbAdapter()
        session.delete_value(User,name="Paula")
        ```

        Parameters
        ---

        class_table type
            this is the name of the class of the table i.e. User
        **kargs tuple
            this is the key value pair that we want to use for our query i.e.
            name='Paul', this will mean that we wabnt to delete all the users
            named Paul

        Returns
        ---
        result: None
        """
        # Delete a row from the table
        rows_to_delete = self.session.query(class_table).all()
        for row_to_delete in rows_to_delete:
            self.session.delete(row_to_delete)
        self.session.commit()

    def delete_value(self, class_table: type[T], **kwargs: Any) -> bool:
        """delete_value this method can be used to delete a specific value on the table or all the values which meet a specific condition.
        the row can be identified with a key value pair.

        ## Example
        ```python
        session = SQLAlchemySQLDbAdapter()
        session.delete_value(User,name="Paula")
        ```

        Parameters
        ---

        class_table type
            this is the name of the class of the table i.e. User
        **kargs tuple
            this is the key value pair that we want to use for our query i.e.
            name='Paul', this will mean that we wabnt to delete all the users
            named Paul

        Returns
        ---
        result: None
        """
        # Delete a row from the table
        rows_to_delete = self.session.query(class_table).filter_by(**kwargs).all()
        for row_to_delete in rows_to_delete:
            self.session.delete(row_to_delete)
        self.session.commit()
        return (
            True
            if self.session.query(class_table).filter_by(**kwargs).all() == []
            else False
        )

