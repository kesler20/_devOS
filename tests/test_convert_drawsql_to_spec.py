from devOS.use_cases.convert_drawsql_to_spec import convert_drawsql_to_spec


SAMPLE_SQL = """
CREATE TABLE "authors" (
    "id" INT PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "bio" TEXT
);

CREATE TABLE "books" (
    "id" INT PRIMARY KEY,
    "title" VARCHAR(255) NOT NULL,
    "price" DECIMAL(10,2),
    "published_at" DATETIME,
    "author_id" INT NOT NULL,
    FOREIGN KEY ("author_id") REFERENCES "authors"("id")
);
"""


def test_convert_drawsql_to_spec_builds_one_spec_per_table():
    specs = convert_drawsql_to_spec(SAMPLE_SQL)

    assert [spec.name for spec in specs] == ["Authors", "Books"]
    assert [spec.table_name for spec in specs] == ["authors", "books"]


def test_convert_drawsql_to_spec_maps_sql_types_and_primary_key():
    authors = convert_drawsql_to_spec(SAMPLE_SQL)[0]
    properties_by_name = {p.name: p for p in authors.properties}

    assert properties_by_name["id"].type == "int"
    assert properties_by_name["id"].key_type is not None
    assert properties_by_name["id"].key_type.type == "primary_key"
    assert properties_by_name["id"].key_type.behaviors == ["auto_increment"]

    assert properties_by_name["name"].type == "str"
    assert properties_by_name["name"].required is True

    assert properties_by_name["bio"].type == "text"
    assert properties_by_name["bio"].required is None


def test_convert_drawsql_to_spec_resolves_table_level_foreign_key():
    books = convert_drawsql_to_spec(SAMPLE_SQL)[1]
    author_id = next(p for p in books.properties if p.name == "author_id")

    assert author_id.type == "int"
    assert author_id.key_type is not None
    assert author_id.key_type.type == "foreign_key"
    assert author_id.key_type.table == "authors"
    assert author_id.key_type.column == "id"
    assert author_id.key_type.behaviors == ["ondelete_cascade"]

    price = next(p for p in books.properties if p.name == "price")
    assert price.type == "float"

    published_at = next(p for p in books.properties if p.name == "published_at")
    assert published_at.type == "datetime"


def test_convert_drawsql_to_spec_resolves_inline_foreign_key():
    sql = """
    CREATE TABLE "teams" (
        "id" INT PRIMARY KEY,
        "name" VARCHAR(255) NOT NULL
    );

    CREATE TABLE "players" (
        "id" INT PRIMARY KEY,
        "team_id" INT REFERENCES "teams"("id")
    );
    """
    players = convert_drawsql_to_spec(sql)[1]
    team_id = next(p for p in players.properties if p.name == "team_id")

    assert team_id.key_type is not None
    assert team_id.key_type.type == "foreign_key"
    assert team_id.key_type.table == "teams"
    assert team_id.key_type.column == "id"
