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
specification. devOS imports and verifies existing credentials in both selected
stores, writes setup and product files, validates locally, configures repository
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
| Bootstrap | Redis connection settings and explicit devOS project identity needed to load a project's bundle |
| Project bundle | Credentials deliberately assigned to `devos:projects:<project-name>` |
| General secrets | Values in `devos:general`, accessed explicitly through the secrets workflow rather than injected into a project |
| Store selection | Independently chosen local or CI Redis connection plus per-key conflict decisions |
| Source table | Semantically described pipeline input with schema, grain, derivation and provenance |

## Acceptance

Verified two-store imports must precede local credential removal. Existing design,
visibility, remotes and unrelated Git changes must survive setup. Failures must
return a nonzero code with safe partial-operation context. React browser code must
not contain a Redis credential loader. Test external boundaries offline and run
applicable maintained devOS checks.

## Reusable bundle workflow

Agents maintain and install complete reusable bundles from automation_engine's
`wiki/Snippets/` under its Snippets SOP. Bundles carry implementation, relevant
offline tests, dependencies, config, credential requirements and scoped setup.
Installed tests import target code and run without the library checkout or secrets.
devOS scaffolding and credential setup consume the canonical config bundle.
devOS remains the credential store with explicit project assignments.
