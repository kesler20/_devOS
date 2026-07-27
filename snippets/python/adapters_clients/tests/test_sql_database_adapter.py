from adapters_clients.database.sql_database_adapter import SQLDatabaseAdapter


class Query:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def filter_by(self, **filters):
        filtered_rows = [
            row
            for row in self.rows
            if all(getattr(row, key, None) == value for key, value in filters.items())
        ]
        return Query(filtered_rows)

    def first(self):
        return self.rows[0] if self.rows else None

    def all(self):
        return list(self.rows)

    def offset(self, offset_number: int):
        return Query(self.rows[offset_number:])

    def limit(self, limit_number: int):
        return Query(self.rows[:limit_number])

    def update(self, values):
        for row in self.rows:
            for key, value in values.items():
                setattr(row, key, value)


class FakeSession:
    def __init__(self) -> None:
        self.rows: list[Row] = []
        self.closed = False

    def add(self, row):
        row.id = len(self.rows) + 1
        self.rows.append(row)

    def add_all(self, rows):
        for row in rows:
            self.add(row)

    def commit(self):
        return None

    def refresh(self, row):
        return row

    def query(self, table):
        return Query([row for row in self.rows if isinstance(row, table)])

    def delete(self, row):
        self.rows.remove(row)

    def close(self):
        self.closed = True


class Row:
    def __init__(self, name: str) -> None:
        self.id: int | None = None
        self.name = name


def test_crud_operations() -> None:
    session = FakeSession()
    adapter = SQLDatabaseAdapter(session)

    created = adapter.add_value(Row("alpha"))
    assert created.id == 1
    assert adapter.read_value(Row, name="alpha") is created

    adapter.update_values(Row, created.id, name="beta")
    assert adapter.read_value(Row, id=created.id).name == "beta"

    adapter.add_values([Row("gamma"), Row("delta")])
    assert len(adapter.read_all_values(Row)) == 3
    assert [row.name for row in adapter.read_all_values_with_pagination(Row, 2, 2)] == [
        "delta"
    ]

    assert adapter.delete_value(Row, name="beta") is True
    assert adapter.read_value(Row, name="beta") is None


def test_context_manager_closes_session() -> None:
    session = FakeSession()

    with SQLDatabaseAdapter(session):
        pass

    assert session.closed is True
