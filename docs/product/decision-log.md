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

Import every non-bootstrap assignment from an existing `.env` into both selected
stores under one identity. Skip identical values, import missing keys, and require
an explicit source choice for each differing key independently in each store.
Verify bundles and project registration before rewriting `.env`. Silent overwrites
would discard stakeholder choices and are rejected.

Use references and the general-secret clipboard workflow for confidential values.
Specifications and results contain no raw secrets. Final `.env` is bootstrap-only,
with a value-free example and ignore rules. Browser code cannot load Redis secrets.

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

Reuse existing credential bundles, registry and Redis adapters. Extend management
with comparison and verified import rather than maintaining another store. Copy
canonical runtime `credentials.py` unchanged and use its settings pattern for
actual integrations. Preserve existing settings through reviewed content changes.

## Repository and CI/CD

Use a dedicated GitHub REST client and PyNaCl sealed encryption for Actions secrets.
Local and CI Redis connections are selected separately. Map uppercase repository
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
