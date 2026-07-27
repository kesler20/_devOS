from __future__ import annotations

from typing import Any


class SQLDatabaseAdapter:
    """Wrap a SQLAlchemy session with small CRUD operations.

    Parameters
    ----------
    session
        SQLAlchemy-compatible session. Tests can pass an in-memory SQLite
        session.
    """

    def __init__(self, session: Any) -> None:
        self.__session = session

    def __enter__(self) -> "SQLDatabaseAdapter":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying session.

        Side Effects
        ------------
        Releases the database connection held by the session.
        """

        self.__session.close()

    def add_value(self, row: Any) -> Any:
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

        self.__session.add(row)
        self.__session.commit()
        self.__session.refresh(row)
        return row

    def add_values(self, rows: list[Any]) -> list[Any]:
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

        self.__session.add_all(rows)
        self.__session.commit()
        return rows

    def read_value(self, table: type[Any], **filters: Any) -> Any | None:
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

        row = self.__session.query(table).filter_by(**filters).first()
        if row is not None:
            self.__session.refresh(row)
        return row

    def read_values(self, table: type[Any], **filters: Any) -> list[Any]:
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

        return list(self.__session.query(table).filter_by(**filters).all())

    def read_all_values(self, table: type[Any]) -> list[Any]:
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

        return list(self.__session.query(table).all())

    def read_all_values_with_pagination(
        self,
        table: type[Any],
        number_of_objects_per_page: int,
        current_page_number: int,
    ) -> list[Any]:
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

    def update_values(self, table: type[Any], row_id: Any, **values: Any) -> Any | None:
        """Update one row by ``id``.

        Parameters
        ----------
        table
            ORM table class.
        row_id
            Value of the row ``id`` column.
        **values
            Column values to update.

        Returns
        -------
        Any | None
            Updated row, or ``None`` when no row exists.
        """

        row = self.__session.query(table).filter_by(id=row_id).first()
        if row is None:
            return None

        for key, value in values.items():
            setattr(row, key, value)

        self.__session.commit()
        self.__session.refresh(row)
        return row

    def update_value(
        self, table: type[Any], key: str, value: Any, **filters: Any
    ) -> list[Any]:
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
        self.__session.commit()
        return self.read_values(table, **filters)

    def delete_value(self, table: type[Any], **filters: Any) -> bool:
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
        self.__session.commit()
        return self.read_values(table, **filters) == []

    def delete_all_values(self, table: type[Any]) -> None:
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
        self.__session.commit()
