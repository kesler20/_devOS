# Project scaffolding

`my-scaffold-project` handles source research, the main planning interview and
approval. devOS executes the agreed setup through value-free JSON specifications.
Only setup and documentation are generated automatically. Application entry points,
UI shells and feature code are outside this workflow.

## Commands

| Command | Result |
| --- | --- |
| `dev scaffold inspect <project-path>` | Read-only file fingerprints, missing setup, staged paths, environment key names and configured local bundle comparison |
| `dev scaffold apply <spec-path>` | Complete approved scaffold, GitHub metadata and secrets, registration, validation and exact-path staging |
| `dev scaffold credentials apply <spec-path>` | Import and verify the local JSON vault, then prepare local dotenv config, materialized `.env`, example and ignores |
| `dev scaffold secrets apply <spec-path>` | Upload assigned project values or explicitly selected CI bootstrap to an existing repository and verify secret names |
| `dev scaffold schema` | Current typed JSON input schema |

Install this local checkout with `uv sync --locked`. Use `uv run dev scaffold ...`
from devOS or its installed `dev` executable from another directory. Inspection
does not initialise Git, import credentials or invoke the legacy configuration wizard.
The standalone credential and secret operations do not stage, commit or push.

## Approved specification

Keep the transient specification outside the target repository. The specification
contains approved content and references, never confidential values. Use a fresh
inspection to confirm the approved state and populate `expected_files` with its
fingerprints, including `.env` when present. Changed files require renewed inspection
and agreement. Unknown fields are rejected without echoing their input values.

```json
{
  "protocol_root": "C:/Users/Kesler/protocol",
  "project_name": "example-project",
  "description": "Inform an agreed product decision.",
  "stack": "python",
  "data_project": true,
  "credential_resolutions": {},
  "ci_store": {
    "bootstrap": {"secret_keys": {"devos_redis_url": "CI_REDIS_URL"}},
    "resolutions": {}
  },
  "github": {
    "owner": "agreed-owner",
    "repository": "example-project",
    "token_secret_key": "github_token"
  },
  "readme_body": "## Local setup\n\nRun `uv sync` to install the setup package.\n",
  "prd": "# Product\n\nApproved product requirements.\n",
  "decision_log": "# Requirements\n\nApproved requirements and rationale.\n\n# Specifications\n\nApproved specifications.\n",
  "source_tables": "Approved semantic schemas and provenance.",
  "expected_files": {},
  "validation_commands": [["uv", "sync"], ["uv", "run", "python", "-m", "compileall", "-q", "src"]]
}
```

The example shows input structure. Replace its agreed content with the full
reviewed documents and actual setup guide. A scaffold without application code
has no startup command.

| Field | Meaning |
| --- | --- |
| `project_path` | Optional existing path within `protocol_root`, otherwise root plus project name |
| `stack` | `python`, `react` or `fullstack` |
| `python_package`, `python_version`, `config_path` | Actual package identifier, supported Python version and relative settings directory |
| `config_content` | Reviewed existing config integration, with module-scope `dotenv.load_dotenv(interpolate=False)` before typed settings construction |
| `package_manager`, `frontend_path` | `uv`, `pip`, `npm` or `pnpm`, plus the fullstack frontend path |
| `ci_runner` | Default `ubuntu-latest`, or an agreed `self-hosted` runner for local service access |
| `agent_guides`, `automation_engine_root` | Selected canonical guide names and optional registry/tool checkout |
| `files` | Reviewed relative-path/content changes for imports, Docker, integration and custom CI/CD workflows |
| `expected_files` | Inspection fingerprints of existing affected files, including `.env` |
| `validation_commands` | Agreed argument arrays executed locally without shell expansion, with output captured rather than printed |

Project-relative paths use forward slashes. Protected `.env`, design and generated
metadata use dedicated fields. Symlink targets and escaping paths are rejected.
Python setup reads `wiki/Snippets/python/config/` from `automation_engine_root`
(or `protocol_root/automation_engine`), copies `credentials.py` byte for byte,
and uses its settings pattern. It installs adapted offline tests under
`tests/snippets/config/`, bundle setup files under `docs/snippets/config/`, runtime
dependencies and pytest in the PEP 621 manifest. Run copied tests in the target.
The selected automation_engine checkout must contain the complete config bundle.
Existing settings require reviewed integration. React setup never generates a
credential loader in browser code. One description is used in GitHub, README and
all applicable package manifests.

`design.md` is empty initially, unless an agreed inventory is supplied. Inventory
updates replace only its dedicated `## Source Tables` section. Other design content
is preserved. Required folders have tracked placeholders. Existing CI is preserved
unless explicitly replaced through `files`. Default CI installs available setup,
compiles Python config, runs existing tests and uses available React check scripts.
It maps CI bootstrap secret names to lowercase devOS settings only for Python jobs.
Add CD and job-specific dependency installation through approved workflow changes.

## Credential setup

The configured JSON vault is the local authority. credential_resolutions selects local or stored values when .env assignments differ. Verify import before materializing .env. ci_store is optional and explicitly enables Redis bootstrap publication. Without it, CI receives the assigned project bundle. Remote loaders are optional. Local execution reads the materialized environment.

## Repository and failure contract

The complete use case preflights files and staged overlaps, verifies imports,
writes approved files, runs agreed validation, configures GitHub metadata and
secrets, registers the project and generates `AGENTS.md` with the existing
`sync_project_agents.py`, then stages exact scaffold paths. New GitHub repositories
are private and created without an initial commit. Existing owner, origin and
visibility remain. Unrelated files and staged changes are retained. No operation
commits or pushes. Live Actions execution remains pending until Kesler pushes.

Failures return nonzero exit codes and a safe operation, category, reason and
completed-operation report. Invalid input returns code 2. Runtime operation failure
returns code 1. Inspect files, bundles, registry, GitHub metadata and secret names
before recovery. Validation output is captured to avoid leaking credentials. To
diagnose a failing check, run it locally with the same care for secret output.

Agent fallback applies only to unavailable or unsupported tooling or diagnosed
implementation failures. Finish remaining authorised operations with equivalent
tools or direct edits after identifying partial completion. Record the reason in
TickTick and verify the same results. Credential conflicts, failed import readback,
permissions and service outages require resolution first. Never replay successful
mutations blindly, rewrite `.env` before verified imports or stage unrelated files.

## Maintained interfaces and verification

`ScaffoldSpec`, `ScaffoldInspection` and `ScaffoldResult` live in the domain.
`InspectProjectScaffoldUseCase`, `ConfigureProjectCredentialsUseCase`,
`ConfigureGitHubSecretsUseCase` and `ScaffoldProjectUseCase` compose existing
credential management with project-file, Git and dedicated GitHub REST adapters.
CLI dispatch precedes eager legacy Git and credential initialisation.

Run `uv run python -m pytest` for the devOS suite. Tests use the isolated canonical consumer bundle under
`tests/fixtures/consumer_support/python`.
Scaffold acceptance tests use fake Redis
stores, mocked GitHub responses and temporary Git repositories, including failure
recovery, dotenv loading, literal imports and unrelated staged changes.
