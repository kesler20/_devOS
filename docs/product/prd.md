# devOS product requirements

## Problem and users

Kesler and coding agents need consistent project setup without reconstructing
credential, documentation and repository operations for every project. Existing
projects also need targeted adoption that preserves code layout, user design and
unrelated working changes. devOS provides local developer tooling for scaffolding,
credentials and code generation.

## Project scaffolding workflow

Kesler invokes `my-scaffold-project` for a new or existing Protocol project.
The main agent inspects project files and the task, reads the Obsidian scratchpad,
and launches a separate read-only vault researcher. It uses `my-grill-me` in native
Plan mode to agree the product, requirements, source tables and technical setup.
It presents complete documents and file changes for approval.

After approval and leaving Plan mode, the agent creates a value-free execution
specification. devOS imports and verifies existing credentials in the local JSON
vault, writes setup and product files, validates locally, configures repository
metadata and Actions secrets, registers engineering guides and stages exact paths.
Kesler reviews, commits and pushes. Live Actions can then be verified.

Standalone credential and Actions-secret commands support scoped setup and
recovery. Diagnosed tooling failures may use equivalent tools for remaining
authorised operations after partial-state inspection.

## Scope

Support Python, data projects and React setup, including targeted fullstack
integration. Generate product documentation, README, config loading, dependencies,
agreed Docker setup and CI. CD requires an agreed target and trigger. Do not
generate feature implementations, application entry points or UI shells.

Keep required quick-code and notebook folders in Git. Scripts are untested quick
coding. Do not impose an experiment-report format. Preserve Obsidian sources as
supporting evidence. TickTick owns task progress and validation, rather than a
Markdown status tracker.

## Nomenclature

| Term | Definition |
| --- | --- |
| Scaffold | Agreed product documents and technical setup applied to a Protocol project |
| ScaffoldSpec | Transient typed execution input containing approved content, references and conflict choices, without secret values |
| ScaffoldInspection | Read-only report of file fingerprints, setup requirements and credential key comparisons |
| ScaffoldResult | Safe record of applied and staged paths, completed operations and pending user actions |
| Bootstrap | Connection settings for explicitly selected remote project loading |
| Project bundle | Credentials deliberately assigned to an internal project object in the JSON vault |
| Root credentials | Top-level JSON values retrieved explicitly and never inherited by projects |
| Store selection | Optional named Redis or Prefect target separate from the local vault |
| Relational DSL | Versioned JSON representation of the Studio-authored PostgreSQL schema with optional diagram layout |
| DAO | SQLAlchemy mapped class derived from the relational DSL |
| Generated artifact | Designated file derived by devOS and replaced by regeneration |
| Installed bundle | Reusable implementation, config and tests adapted by an agent and owned by the target project |
| CRUD contract test | Regenerable test of standard generated CRUD behaviour |
| Test scaffold | Initial custom endpoint or use-case test code subsequently owned by the project |
| Source table | Semantically described pipeline input with schema, grain, derivation and provenance |

## Acceptance

Verified vault imports must precede local credential removal. Existing design,
visibility, remotes and unrelated Git changes must survive setup. Failures must
return a nonzero code with safe partial-operation context. React browser code must
not contain a Redis credential loader. Test external boundaries offline and run
applicable maintained devOS checks.

## Reusable bundle workflow

Agents maintain and install complete reusable bundles from automation_engine's
`wiki/Snippets/` under its Snippets SOP. Bundles carry implementation, relevant
offline tests, dependencies, config, credential requirements and scoped setup.
Installed tests import target code and run without the library checkout or secrets.
devOS scaffolding uses typed dotenv settings locally. Remote loaders are selected explicitly.
devOS remains the credential store with explicit project assignments.

## Credential workflow

Unified creds commands use the local JSON vault. Project objects have an internal prefix hidden behind --project. Set requires force for existing keys. Ambiguous get and delete require explicit scope. Materialize is separate from imports and uses Git remote identity. Managed history is strongly recommended and user-owned. Standalone remote-loading examples live in devOS.

## Relational authoring and targeted generation

The primary application focus is web development. devOS scaffolds repetitive
parts and provides targeted synchronization rather than prescribing an entire
application architecture. Credential and GitHub workflows remain independent.

Studio is a standalone drawSQL-like relational editor. Its portable JSON DSL
contains the PostgreSQL schema and optional positions, colours and viewport.
SQL import may initialize a new document. Subsequent schema edits happen in Studio.
The DSL derives PostgreSQL creation SQL and SQLAlchemy DAOs. Generated DAOs are
not independently edited. Resource DTOs, CRUD endpoints and generated contract
tests derive from the generated ORM metadata using the reusable CRUD conventions.
No bidirectional schema synchronization is provided.

Default CRUD generation needs no additional per-resource specification. Application
customization can select a narrower contract, but a mandatory API profile is not a
prerequisite for default CRUD. Separate ORM configuration may express application
names and navigation behaviour without changing physical schema semantics.

The bounded PostgreSQL release preserves namespaces, quoted names, enums, arrays,
precise type parameters, ordered columns, defaults and identity, composite keys,
checks, ordinary indexes, referential actions and deferrability. Unsupported
constructs fail explicitly. Views, functions, triggers, partitioning, live database
introspection and migration generation/application are outside this release.

Agents install and adapt generic CRUDUseCase, DTO envelopes, database adapters,
clients, configuration, File IO and build examples from automation_engine's wiki.
Installed support is project-owned and never overwritten by recurring builds.
Targeted commands generate only selected schema-derived artifacts into designated
files. Custom application behaviour remains in separate project-owned modules.

Standard CRUD contract tests can regenerate. Integration tests scaffolded from
custom endpoints and unit tests scaffolded from use cases become project-owned.
Their assertions are maintained by agents from requirements. Unimplemented test
scaffolds do not establish correctness.

Acceptance includes matching SQL/ORM relational semantics, matching Python and
TypeScript wire contracts, usable CRUD through an application-supplied database
session, deterministic regeneration and preservation of installed support and
custom tests. CRUD identities use the mapped key attributes and support typed
single keys and complete composite keys. PATCH distinguishes omission from null
and does not permit primary-key mutation. Bigint and numeric wire values are
strings. Relationship projections remain finite and use the related resource's
read contract.
