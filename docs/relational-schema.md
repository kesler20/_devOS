# Relational schema contract

SchemaDocument version 1 stores namespaces, enums, tables, ordered columns,
constraints and ordinary btree indexes. IDs are nonempty, document-wide identities.
SQL names are scoped to their namespace or owning table. Unquoted names are
lowercase. Quoted names retain case and punctuation. Names fit 63 UTF-8 bytes.

Foreign keys store ordered source and target column IDs. Their target is a
non-deferrable primary/unique key or unique ordinary index. Reordering a key pair
changes its meaning. Primary-key columns are non-nullable. A table can have one
primary key. Tables without primary keys can generate SQL, but cannot generate
mapped DAOs without an explicit primary key.

The supported scalar types are smallint, integer, bigint, numeric, real, double
precision, boolean, text, varchar, char, uuid, date, time, timetz, timestamp,
timestamptz, interval, bytea, json, jsonb and document-defined enums. Arrays retain
their declared dimensionality. Length applies to varchar/char. Numeric precision
and scale and temporal precision remain explicit. Serial and identity generation
apply to non-nullable scalar integer columns and exclude explicit defaults.
Identity sequence options serialize as canonical decimal strings to preserve the
full signed 64-bit range. Safe JSON integers are accepted as inputs. Numbers outside
JavaScript's safe integer range require strings and fail validation otherwise.

Check/default SQL expressions remain SQL text. Creation-SQL generation validates
them before rendering. Defaults cannot reference columns. Checks can reference
only columns of their owning table. Expressions cannot contain statements,
queries or aliases. Renaming a referenced column requires updating its check
expressions in the same edit. ID-based key and layout references retain identity
through renames. Deleting referenced objects requires resolving their references.

Optional diagram data contains table positions, colours and viewport only.
Optional ORM configuration contains table/column aliases and FK navigation names.
It never introduces physical columns. Database referential actions are separate
from ORM lifecycle settings. Resource DTO/API profiles are not required by the
document contract.

Studio authors the document. SQL import initializes a new document. SQL and DAOs
are derived outputs. Generated ORM metadata drives resource generation. There is
no reverse synchronization or live migration workflow. Unknown fields and
unsupported constructs fail explicitly.

The Python model owns the structural JSON Schema and TypeScript declarations.
Generate them with `dev schema contracts --json-schema
frontend/src/relational.schema.json --typescript frontend/src/relational.types.ts`.
Browser semantic validation and Python reference validation share fixtures under
`tests/fixtures/relational/`. Use `dev schema validate schema.json` outside Git
without credentials. Export creation SQL with `dev schema sql schema.json
--output schema.sql`. SQL output cannot replace its input document.

## Targeted resource commands

Run each command independently in the consumer directory. Explicit file paths
select derived outputs. Python module names resolve beneath --python-root, which
defaults to src. DAO imports execute the selected local module to inspect mapped
metadata. Keep module imports free of application startup and live services.

```text
dev schema import-sql creation.sql --output schema.json
dev build dao schema.json --output src/consumer/dao.py
dev build dto consumer.dao --python-output src/consumer/dto.py --typescript-output frontend/src/dto.ts
dev build api consumer.dao --dto-module consumer.dto --crud-module consumer.crud --session-module consumer.database --session-provider get_session --output src/consumer/routes.py
dev build tests contracts consumer.dao --dto-module consumer.dto --output tests/test_resource_contracts.py
dev build tests api src/consumer/custom_routes.py --module consumer.app --output tests/test_custom_routes.py
dev build tests services src/consumer/use_cases.py --module consumer.use_cases --output tests/test_custom_use_cases.py
dev ui
dev ui C:/Users/Kesler/protocol/devOS/frontend --port 3000
```

Before API generation, an agent installs and adapts the wiki CRUD bundle and SQL
database companion under the consumer's chosen modules. Install their dependencies,
config and offline tests together. The session provider yields an application-owned
SQLAlchemy Session. The generated module exports router, which the application
mounts with app.include_router. Business routes and authorization remain separate.

Default routes use the resource class name without a DAO suffix, converted to
snake_case. A ParentDAO class yields /parent. Keys appear in the mapped primary-key
order. ParentDAO with tenant and id keys yields /parent/{key_tenant}/{key_id}.
POST and PATCH accept an entity envelope. Responses use the installed bundle's
entity/entities envelopes. Missing entities return 404, invalid payloads return 422
and relational constraint conflicts return 409. Expanded reads use /relationships.
Array, JSON and binary keys require custom routes because they lack this scalar
path contract. Ordinary junction resources use their own complete composite keys.

Write contracts permit omission when nullable or supplied by a database default
or generation rule. Always-generated columns cannot be supplied. Patch contracts
contain scalar non-key columns and retain only supplied fields. Explicit null
requires a nullable column. Bigint and numeric values travel as strings, bytea as
base64, UUIDs and temporal values as strings, and arrays retain dimensionality.
Read models are shallow. ReadRelationship models add one finite layer of related
resource Read models. The TypeScript output supplies Zod validators and inferred
types and requires Zod 4 in its consuming package.

Generated files carry an ownership header. Rebuilds replace only recognized derived
files and reject source-path collisions or project-owned destinations before writing.
SQL import exclusively creates a new document. Custom test scaffolds become
project-owned immediately and cannot be regenerated over existing assertions.
Scaffolds remain explicitly skipped until their requirements and fixtures are filled
in. Generated CRUD contract tests require consumer conftest fixtures named client
and resource_inputs. The client mounts routers with isolated services. resource_inputs
maps resource names to valid create payloads and seeds related rows where needed.

## Local release checks

Install Python development dependencies with uv sync --locked and frontend
dependencies with pnpm --dir frontend install --frozen-lockfile. Run pytest,
mypy src, pnpm --dir frontend typecheck and pnpm --dir frontend build.

PostgreSQL acceptance requires DEVOS_TEST_POSTGRES_URL pointing to a local
PostgreSQL 18 instance with test user devos_test. The tests create and drop unique
databases. They reject remote hosts or another user. CI provisions this isolated
service and runs SQL/ORM equivalence, shared Python/TypeScript payload validation,
independent mounted CRUD and generated behavioral contract tests. Independent
consumer support lives in tests/fixtures/consumer_support and requires no adjacent
wiki checkout. Tests without that explicit database URL report PostgreSQL cases
as skipped rather than claiming database acceptance.
