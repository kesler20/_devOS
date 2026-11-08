from __future__ import annotations

import datetime
import logging
import base64
import binascii
import decimal
import types
import typing
import uuid

import pydantic
import sqlalchemy
import sqlalchemy.orm

TRow = typing.TypeVar("TRow")
ScalarIdentity = (
    str
    | int
    | float
    | bool
    | bytes
    | uuid.UUID
    | decimal.Decimal
    | datetime.datetime
    | datetime.date
    | datetime.time
)


class CompositeIdentity(pydantic.RootModel[dict[str, ScalarIdentity]]):
    pass


EntityIdentity = ScalarIdentity | CompositeIdentity


def coerce_database_value(
    sql_type: sqlalchemy.types.TypeEngine[object], value: object
) -> object:
    if value is None:
        return None
    if isinstance(sql_type, sqlalchemy.JSON):
        return pydantic.TypeAdapter(pydantic.JsonValue).validate_python(value)
    if isinstance(sql_type, sqlalchemy.ARRAY):
        if not isinstance(value, list):
            raise ValueError("SQL array values must be lists")
        dimensions = sql_type.dimensions or 1
        item_type = (
            sql_type.item_type
            if dimensions == 1
            else sqlalchemy.ARRAY(sql_type.item_type, dimensions=dimensions - 1)
        )
        return [
            coerce_database_value(
                typing.cast(sqlalchemy.types.TypeEngine[object], item_type), item
            )
            for item in value
        ]
    if isinstance(sql_type, sqlalchemy.LargeBinary) and isinstance(value, str):
        try:
            return base64.b64decode(value, validate=True)
        except binascii.Error as error:
            raise ValueError("Binary values must contain valid base64") from error
    if (
        isinstance(sql_type, sqlalchemy.Enum)
        and sql_type.enum_class is not None
        and isinstance(value, str)
    ):
        members = list(sql_type.enum_class)
        if len(members) != len(sql_type.enums):
            members = list(sql_type.enum_class.__members__.values())
        for label, member in zip(sql_type.enums, members):
            if value == label:
                return member
        raise ValueError("Unknown SQL enum label")
    if isinstance(sql_type, sqlalchemy.Enum) and value not in sql_type.enums:
        raise ValueError("Unknown SQL enum label")
    return pydantic.TypeAdapter(sql_type.python_type).validate_python(value)


class SQLDatabaseAdapter:
    """Wrap a SQLAlchemy session with small CRUD operations.

    Parameters
    ----------
    session
        SQLAlchemy-compatible session. Tests can pass an in-memory SQLite
        session.
    """

    def __init__(self, session: sqlalchemy.orm.Session) -> None:
        self.__session = session

    def __enter__(self) -> "SQLDatabaseAdapter":
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: types.TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying session.

        Side Effects
        ------------
        Releases the database connection held by the session.
        """

        logging.info("Closing SQL database session")
        self.__session.close()
        logging.info("Closed SQL database session")

    def add_value(self, row: TRow) -> TRow:
        """Insert one ORM row and refresh it.

        Parameters
        ----------
        row
            ORM instance to insert.

        Returns
        -------
        Any
            Inserted and refreshed ORM instance.
        """

        logging.info("Saving %s row", type(row).__name__)
        self.__session.add(row)
        try:
            self.__session.commit()
        except sqlalchemy.exc.IntegrityError:
            self.__session.rollback()
            raise
        self.__session.refresh(row)
        logging.info("Saved %s row", type(row).__name__)
        return row

    def add_values(self, rows: list[TRow]) -> list[TRow]:
        """Insert many ORM rows.

        Parameters
        ----------
        rows
            ORM instances to insert.

        Returns
        -------
        list[Any]
            The same rows after commit.
        """

        logging.info("Saving %s SQL rows", len(rows))
        self.__session.add_all(rows)
        try:
            self.__session.commit()
        except sqlalchemy.exc.IntegrityError:
            self.__session.rollback()
            raise
        logging.info("Saved %s SQL rows", len(rows))
        return rows

    def read_value(self, table: type[TRow], **filters: object) -> TRow | None:
        """Read the first row matching filters.

        Parameters
        ----------
        table
            ORM table class.
        **filters
            Column filters passed to ``filter_by``.

        Returns
        -------
        Any | None
            First matching row, or ``None``.
        """

        logging.info("Reading %s by filters", table.__name__)
        row = self.__session.query(table).filter_by(**filters).first()
        if row is not None:
            self.__session.refresh(row)
        logging.info("Read %s by filters, found=%s", table.__name__, row is not None)
        return row

    def read_identity(self, table: type[TRow], identity: EntityIdentity) -> TRow | None:
        logging.info("Reading %s by mapped identity", table.__name__)
        mapper = typing.cast(sqlalchemy.orm.Mapper[TRow], sqlalchemy.inspect(table))
        key_columns = {
            mapper.get_property_by_column(column).key: column
            for column in mapper.primary_key
        }
        if isinstance(identity, CompositeIdentity):
            supplied = identity.root
        else:
            if len(key_columns) != 1:
                raise ValueError(
                    "Composite identity requires all primary-key attributes"
                )
            supplied = {next(iter(key_columns)): identity}
        if set(supplied) != set(key_columns):
            raise ValueError(
                "Identity must contain exactly all mapped primary-key attributes"
            )
        values = {}
        for name, column in key_columns.items():
            value = supplied[name]
            if isinstance(value, bool) and column.type.python_type is not bool:
                raise ValueError(f"Invalid primary-key type for {name}")
            values[name] = coerce_database_value(column.type, value)
        row = self.__session.get(table, values)
        if row is not None:
            self.__session.refresh(row)
        logging.info(
            "Read %s by mapped identity, found=%s", table.__name__, row is not None
        )
        return row

    def delete_identity(self, table: type[TRow], identity: EntityIdentity) -> bool:
        logging.info("Deleting %s by mapped identity", table.__name__)
        row = self.read_identity(table, identity)
        if row is None:
            logging.info("Delete %s found no row", table.__name__)
            return False
        self.__session.delete(row)
        try:
            self.__session.commit()
        except sqlalchemy.exc.IntegrityError:
            self.__session.rollback()
            raise
        logging.info("Deleted %s by mapped identity", table.__name__)
        return True

    def read_values(self, table: type[TRow], **filters: object) -> list[TRow]:
        """Read all rows matching filters.

        Parameters
        ----------
        table
            ORM table class.
        **filters
            Column filters passed to ``filter_by``.

        Returns
        -------
        list[Any]
            Matching rows.
        """

        logging.info("Reading %s rows by filters", table.__name__)
        rows = list(self.__session.query(table).filter_by(**filters).all())
        logging.info("Read %s %s rows", len(rows), table.__name__)
        return rows

    def read_all_values(self, table: type[TRow]) -> list[TRow]:
        """Read all rows from a table.

        Parameters
        ----------
        table
            ORM table class.

        Returns
        -------
        list[Any]
            All rows in the table.
        """

        logging.info("Reading all %s rows", table.__name__)
        rows = list(self.__session.query(table).all())
        logging.info("Read %s %s rows", len(rows), table.__name__)
        return rows

    def read_all_values_with_pagination(
        self,
        table: type[TRow],
        number_of_objects_per_page: int,
        current_page_number: int,
    ) -> list[TRow]:
        """Read a page of rows from a table.

        Parameters
        ----------
        table
            ORM table class.
        number_of_objects_per_page
            Number of rows per page.
        current_page_number
            One-indexed page number.

        Returns
        -------
        list[Any]
            Rows for the selected page.
        """

        if number_of_objects_per_page <= 0:
            raise ValueError("number_of_objects_per_page must be positive.")
        if current_page_number <= 0:
            raise ValueError("current_page_number must be positive.")

        offset_number = (current_page_number - 1) * number_of_objects_per_page
        return list(
            self.__session.query(table)
            .offset(offset_number)
            .limit(number_of_objects_per_page)
            .all()
        )

    def update_values(
        self, table: type[TRow], row_id: EntityIdentity, **values: object
    ) -> TRow | None:
        """Update one row using its complete primary-key identity.

        Parameters
        ----------
        table
            ORM table class.
        row_id
            Scalar key or CompositeIdentity with every mapped primary-key attribute.
        **values
            Column values to update.

        Returns
        -------
        Any | None
            Updated row, or ``None`` when no row exists.
        """

        row = self.read_identity(table, row_id)
        if row is None:
            return None

        for key, value in values.items():
            setattr(row, key, value)

        try:
            self.__session.commit()
        except sqlalchemy.exc.IntegrityError:
            self.__session.rollback()
            raise
        self.__session.refresh(row)
        return row

    def update_value(
        self, table: type[TRow], key: str, value: object, **filters: object
    ) -> list[TRow]:
        """Update one column on rows matching filters.

        Parameters
        ----------
        table
            ORM table class.
        key
            Column name to update.
        value
            New column value.
        **filters
            Column filters passed to ``filter_by``.

        Returns
        -------
        list[Any]
            Rows still matching the original filters after commit.
        """

        self.__session.query(table).filter_by(**filters).update({key: value})
        try:
            self.__session.commit()
        except sqlalchemy.exc.IntegrityError:
            self.__session.rollback()
            raise
        return self.read_values(table, **filters)

    def delete_value(self, table: type[TRow], **filters: object) -> bool:
        """Delete rows matching filters.

        Parameters
        ----------
        table
            ORM table class.
        **filters
            Column filters passed to ``filter_by``.

        Returns
        -------
        bool
            ``True`` when no matching rows remain.
        """

        rows_to_delete = self.read_values(table, **filters)
        for row in rows_to_delete:
            self.__session.delete(row)
        try:
            self.__session.commit()
        except sqlalchemy.exc.IntegrityError:
            self.__session.rollback()
            raise
        return self.read_values(table, **filters) == []

    def delete_all_values(self, table: type[TRow]) -> None:
        """Delete all rows from a table.

        Parameters
        ----------
        table
            ORM table class.

        Side Effects
        ------------
        Commits deleted rows.
        """

        for row in self.read_all_values(table):
            self.__session.delete(row)
        try:
            self.__session.commit()
        except sqlalchemy.exc.IntegrityError:
            self.__session.rollback()
            raise
