# Requirements

## Product and workflow

Research and the main interview precede mutations. `my-grill-me` owns planning
and approval, with one separate read-only vault researcher permitted by the calling
skill. Resolve every applicable material choice before applying. This provides
source-grounded setup without delegating stakeholder decisions.

Setup supports Python, data projects and React, with no generated entry points or
UI shell. Existing layout and useful content are preserved through targeted changes.
One agreed description is used in repository metadata, README and manifests.

## Credential integrity

The local JSON vault is authoritative. Root and explicitly assigned project credentials share one vocabulary. Set requires force for existing keys. Ambiguous reads and deletions require scope. Project prefixes remain internal. Root inheritance was rejected because it exposes unrelated credentials.

Import into the vault before materializing .env. Optional Redis and Prefect transfers contain only project bundles. Managed history through Google Drive, OneDrive, an Obsidian Vault with configured history or private GitHub is highly recommended. The user owns retention and recovery. Built-in Git and automatic commits were rejected in favour of external history.

The rationale is to keep routine local credential management independent of a
running remote service and configure one vault path once. Scope expresses which
project may receive a credential. A separate secrets category does not solve that
access boundary. Publishing a shared Redis bootstrap credential to a project's CI
can grant access to unrelated personal credentials, so remote publication is
explicit and limited to the selected project bundle. Separating vault writes from
materialization also makes local environment changes deliberate.

Decision sources are the [July 30 daily note](../../../00%20PKM/2%20Activities/Daily%20Notes/2026-07-30.md)
and its [vault task](https://ticktick.com/webapp/#p/inbox122673285/tasks/6a6af534d77e77f54239b079),
which establish interchangeable remote adapters and local materialization, the
[October 7 daily note](../../../00%20PKM/2%20Activities/Daily%20Notes/2026-10-07.md)
at 13:35 and 15:05 through 15:07, which identify the access risk and propose local
JSON with unified terminology, and the
[October 8 daily note](../../../00%20PKM/2%20Activities/Daily%20Notes/2026-10-08.md)
under devOS changes, which selects the local vault as the default. The approved
credential plan specifies explicit root and project scope, overwrite protection
and user-managed history. The Obsidian Resources Vault is the selected local
location. An Obsidian directory alone does not provide version control.

## Review boundary

Configure repository metadata and Actions secrets while staging local changes
without committing or pushing. Create new repositories private without an initial
commit. Preserve existing owner, remote and visibility. Broad Git helpers are
rejected because they stage, commit and push unrelated work.

# Specifications

## Software architecture

Typed scaffold inputs and results live in the domain. Separate inspection,
credential and secret use cases compose the full operation. Dispatch scaffold
commands before legacy eager Git and credential initialisation so inspection and
new-project setup work outside Git.

Reuse credential validation and materialization with the local JSON adapter. Extend management
with comparison and verified import rather than maintaining another store. Use dotenv before typed settings locally. Independent remote examples live in devOS. Preserve existing settings through reviewed content changes.

The [October 8 daily note](../../../00%20PKM/2%20Activities/Daily%20Notes/2026-10-08.md)
at 10:36 motivates a loading use case that accepts the selected store adapter.
The modelOS Prefect example supplies the project JSON Secret-block pattern.
Keeping Redis and Prefect examples independent lets deployed projects select
dynamic loading without making either service a prerequisite for local settings.

## Repository and CI/CD

Use a dedicated GitHub REST client and PyNaCl sealed encryption for Actions secrets.
CI Redis bootstrap is optional, otherwise assigned project values are supplied directly. Map uppercase repository
secret names to lowercase runtime settings only where appropriate. Preserve
existing workflows unless replacement is approved. CI reflects available code.
CD requires a target and release trigger agreed in the interview.

## Documentation ownership

Repository `docs/product/` owns requirements, vocabulary and decisions. Kesler owns
design content, with agent writes limited to the dedicated source-table inventory.
Register repository paths and canonical engineering guides in the wiki, then use
the existing synchronisation tool to generate project instructions. TickTick owns
execution status. Scratchpad sources remain intact.

## Failure recovery

Report the failed operation and completed work without confidential values.
Unavailable, unsupported or demonstrably faulty tooling permits agent fallback
after rereading partial state. Conflicts, failed verification, permissions and
outages need resolution first. Preserve import verification and staging boundaries
through recovery. Test fake Redis stores, mocked GitHub and temporary repositories
instead of mutating live services during acceptance checks.

## Reusable bundle ownership

The canonical library lives in automation_engine's `wiki/Snippets/`. Agent
maintenance and installation replace snippet CLI management and prompt sync.
This keeps reusable code with its governing SOP and carries offline verification,
dependencies and scoped setup into each target. Retaining CLI management would
split ownership and allow single-file copies to omit required support.

Scaffolding resolves the config bundle from its selected automation_engine checkout.
Credential setup uses the configured wiki library path. Both install adapted tests
and support files. Existing credential storage, explicit project assignments and
per-key conflict verification remain unchanged. Incomplete examples are retained
in automation_engine's archive outside the active library.

The [October 7 daily note](../../../00%20PKM/2%20Activities/Daily%20Notes/2026-10-07.md)
and [snippet bundle task](https://ticktick.com/webapp/#p/6834be6e75dd780000000141/tasks/6ac6180f8f089f3769bb8a1a)
motivate moving complete snippets and their tests together into automation_engine.
The same day's credential discussion identifies the maintenance cost of keeping
another tool responsible for workflows already owned by the agent or editor.

## Data models: JSON and SQL

devOS does not support JSON data modelling. JSON suits unstructured data because it
lets the data model be designed from the consumer backwards: design the frontend and
UI first, then fill in the data models they require. SQL is the opposite, a bottom-up
approach that starts from the data model and optimises for querying and normalisation.
That bottom-up design belongs in devOS Studio, so devOS supports SQL and leaves JSON
shapes to the consuming application.

The source is the [October 9 daily note](../../../00%20PKM/2%20Activities/Daily%20Notes/2026-10-09.md)
at 08:44. This decision concerns application data-model generation. JSON remains
the serialization format for the credential vault and the relational DSL. The
restriction concerns modelling unstructured application data, not representing
a relational schema in JSON.

## Relational generation and bundle ownership

Studio owns edits to the relational JSON DSL. SQL import initializes a document,
then generation flows from DSL to SQL/SQLAlchemy DAOs and from ORM metadata to
resource DTOs, CRUD endpoints and contract tests. Bidirectional editing was rejected
because it introduces competing schema authority and conflict resolution.

Generic CRUD conventions supply enough information for default endpoint and DTO
generation. A mandatory resource profile would add specification work to repetitive
CRUD, so customization is optional. SQL and ORM preserve database semantics, while
application behaviour, authorization and transaction composition remain explicit.

Reusable CRUD machinery, DTO envelopes, database adapters, File IO and build
examples belong to automation_engine's complete snippet library. Agents install
and adapt them with config, dependencies and tests. Recurring builds own only
schema-derived outputs. Recopying generic templates on every DAO build was rejected
because it overwrites agent customization and duplicates the maintained library.
Generated default CRUD tests have designated ownership. Custom endpoint and use-case
test starters transfer to the project so later generation preserves their assertions.

Typed/composite identities use mapped primary-key attributes because conventional
integer id fields do not represent all relational schemas. Separate Write, Patch
and Read contracts preserve database defaults and distinguish omission from null.
Bigint and numeric strings avoid precision loss across JavaScript and Python.
Finite relationship projections use the related resource's DTO without recursive
serialization. Creation SQL is not a live database migration workflow.

The generic CRUD bundle retains its established public operation methods and
Session constructor. The Python guide's existing-convention precedence applies
to that extracted bundle. A new generic dispatch method or replacement adapter
architecture would add unrelated migration work to the typed identity change.

## Studio interface

Studio retains its existing design. The centered navigation, gradient title and
create-table button, section controls, dotted canvas, coloured table strips,
teal table names, inline required/name/type rows, green/yellow handles, row-plus
controls and floating information panels keep their current treatment. Content
and control meanings reflect relational schema authoring and separate ORM
configuration. Navigation properties never appear as physical columns. Preserving
the interface keeps the existing editing workflow while changing schema authority.
