# 😼 devOS

<div style="display:flex;">
  <h1>Development Operating System</h1>
  <img src="frontend\src\assets\logo.svg" style="width:15%" />
</div>

**devOS** is a development acceleration toolkit that combines visual design tools,
code generation, local automation and credential setup to eliminate
the gap between prototype and production code.

## Scaffold Protocol projects

Use `my-scaffold-project` to research and agree product documentation and technical
setup, then apply the approved specification with devOS.

```text
dev scaffold inspect <project-path>
dev scaffold apply <spec-path>
dev scaffold credentials apply <spec-path>
dev scaffold secrets apply <spec-path>
```

These commands work without the legacy project wizard or an existing Git repository.
They support Python, data projects and React setup. Complete apply imports and
verifies credentials, configures repository metadata and Actions secrets, validates
local setup and stages only affected files. New repositories are private with no
initial commit. Existing visibility is preserved. No command commits or pushes.

Read [the specification and recovery contract](docs/scaffolding.md) before applying.
Install the local CLI with `uv sync --locked`, then run it through `uv run dev` or
the environment's `dev` executable. Live Actions verification follows a user push.

---

## Relational authoring and generation

Studio is a standalone ReactFlow editor for relational schemas. Open or export a
portable JSON document and export PostgreSQL creation SQL. Optional table positions,
colours and viewport travel with the document. Schema and resource commands work
outside Git without credentials.

```text
dev ui
dev schema import-sql creation.sql --output schema.json
dev schema validate schema.json
dev schema sql schema.json --output schema.sql
dev build dao schema.json --output src/consumer/dao.py
dev build dto consumer.dao --python-output src/consumer/dto.py --typescript-output frontend/src/dto.ts
dev build api consumer.dao --dto-module consumer.dto --crud-module consumer.crud --session-module consumer.database --output src/consumer/routes.py
dev build tests contracts consumer.dao --dto-module consumer.dto --output tests/test_resource_contracts.py
dev build tests api src/consumer/custom_routes.py --module consumer.app --output tests/test_custom_routes.py
dev build tests services src/consumer/use_cases.py --module consumer.use_cases --output tests/test_custom_use_cases.py
```

Import SQL to initialize a new document. Author later changes in Studio. The
relational document derives SQL and SQLAlchemy DAOs. Mapped DAO metadata derives
Python/Pydantic and TypeScript/Zod resource contracts, default FastAPI routers and
CRUD contract tests. Generated files have designated ownership. Regeneration
preserves installed support, application startup, configuration and custom tests.

Agents install and adapt the canonical CRUD bundle and SQL database companion from
automation_engine's wiki/Snippets/python with their config, dependencies and offline
tests. Generated routers consume the installed module and an application-provided
get_session function. Mount router with app.include_router. Business operations
and authorization remain in separate modules.

Read [the relational contract and command guide](docs/relational-schema.md) for
supported PostgreSQL features, paths, wire types, ownership and test fixtures.
Creation SQL is intended for a new schema. Live database introspection, migrations,
views, triggers, functions and partitioning are outside this release.

Custom endpoint and use-case test scaffolds are project-owned and explicitly
skipped until their input fixtures and assertions are implemented. Generated CRUD
contract tests use isolated consumer client and resource_inputs fixtures and
exercise mounted behavior. Their pass counts are reported separately.

## Development checks

```text
uv sync --locked
pnpm --dir frontend install --frozen-lockfile
uv run pytest
uv run mypy src
pnpm --dir frontend typecheck
pnpm --dir frontend build
```

Set DEVOS_TEST_POSTGRES_URL to the explicit local PostgreSQL 18 test instance with
user devos_test to run database acceptance. Each test creates and drops a unique
isolated database. CI provisions this service. Consumer fixtures install their own
support and do not import devOS or the wiki at runtime.

Studio starts with frontend dependencies only. Use dev ui /path/to/devOS/frontend
--port 3000 to choose another source directory or port. Its production build is a
static frontend and needs no Python backend or hosted storage.

### Managing credentials

The local creds.json vault is authoritative. Root keys occupy the top level and project objects use an internal project_ prefix. --project selects the current origin repository name independently of storage naming. Named Redis and Prefect stores live in the separate vault config.json. Run dev config creds to select its directory, saved in gitignored .devos/config.json inside devOS.

```bash
dev set creds TOKEN value
dev set creds TOKEN replacement --force
dev set creds TOKEN project-value --project
dev get creds TOKEN
dev get creds TOKEN --root
dev get creds TOKEN --project
dev list creds
dev delete TOKEN
dev delete TOKEN --root
dev delete TOKEN --project
dev materialise creds
```

Set rejects existing keys, including identical values, unless forced. Get and delete search root and the current project and require explicit scope when both match. Outside repositories they check root only. Get copies to the clipboard. List displays root and all project key names without values.

Only materialise writes .env. Set, delete and import modify only the vault. Materialization preserves comments, unrelated assignments and existing values for null entries, and creates a value-free .env.example.

### Credential design decisions

One credential vocabulary replaces separate secrets and credentials workflows. Projects never inherit root values. Explicit project assignment limits exposure and prevents cross-project conflicts. Local JSON removes mandatory Redis or Prefect setup. Remote transfers and materialization are separate operations so importing cannot unexpectedly rewrite a project's environment.

A managed vault location with version history or version control is highly recommended. Suitable choices include Google Drive, OneDrive, an Obsidian Vault with a configured history mechanism, or a private GitHub repository. The user's selected system owns history, retention and recovery. devOS does not initialize Git, commit changes or guarantee recovery. An Obsidian Vault directory alone does not provide version control. History can retain previous confidential values.

### Remote store to vault to environment

Configure targets in the vault config.json using your own connection values.

```json
{
  "stores": {
    "deployment-redis": {
      "type": "redis",
      "connection": {"host": "localhost", "port": 6379, "password": "", "db": 0, "ssl": false}
    },
    "deployment-prefect": {
      "type": "prefect",
      "api_url": "http://localhost:4200/api",
      "api_key": ""
    }
  }
}
```

Redis supports url, host, port, username, password, db and ssl. URL takes precedence. Prefect requires its optional package. Connection values stay in vault config, never tracked project setup files.

```bash
dev import creds deployment-redis
dev materialise creds
dev export creds deployment-prefect
dev export creds deployment-prefect --force
```

Import adds missing keys, accepts identical values and rejects differences unless forced. Local-only keys survive. Export creates missing bundles and requires force to replace existing bundles with exact project contents. Root credentials never enter transfers. Redis uses devos:projects:<name>. Prefect uses JSON Secret blocks with normalized devos-projects-<name> names and rejects ambiguous project mappings.

[Standalone loading examples](examples/credentials/README.md) provide independent Redis and Prefect LoadingCredsUseCase configuration. Local scaffolding uses .env by default.

Migrate existing Redis and dotenv sources with python scripts/migrate_credentials_vault.py --protocol-root PATH. Migration verifies readback, leaves Redis intact and stops on differing values. Repeat --keep-local PROJECT KEY for explicit local-source choices. Materialize separately.

---

### Reusable bundles

Agents use automation_engine's `wiki/Snippets/` and `wiki/SOPs/Snippets.md` to
maintain and install complete bundles with implementation, offline tests,
dependencies and scoped credential setup. devOS retains credential storage.
Python scaffolding consumes the selected automation_engine checkout's config
bundle and installs its adapted tests and setup files. Generated project guides
come from wiki engineering SOPs through `scripts/sync_project_agents.py`.

### Keeping devOS Up to Date

Add [devOS_profile.ps1](devOS_profile.ps1) to your PowerShell profile. It exposes a
`dev-update` alias that pulls the latest changes, reinstalls the package into the
currently activated environment, and returns you to your project directory:

```powershell
# From your project directory (devOS lives one level up by default)
dev-update

# Specify a different devOS location or return directory
dev-update -DevOSPath "C:/path/to/devOS" -TargetDir "my-project"
```

> **Activate your environment before running `dev-update`** — the script installs
> directly into whatever `pip` is on your `PATH`.

## Installation

### Prerequisites

- **Node.js** v18 or above
- **Python** 3.12 or above
- A Git repository for commands that operate on remotes or releases
- (Optional) Tooling required by your local `ralph.sh` workflow

### Install globally on macOS

Install devOS as an isolated command-line tool with `pipx`. The editable
installation exposes `dev` everywhere while continuing to execute the source in
the cloned repository. Python 3.14 can be shared with cliOS and satisfies devOS's
Python requirement.

Confirm that Homebrew and `pipx` are available.

```bash
brew --version
pipx --version
```

Install Python 3.14 through Homebrew.

```bash
brew install python@3.14
"$(brew --prefix python@3.14)/bin/python3.14" --version
```

Clone devOS into `~/protocol` if it is not already present.

```bash
mkdir -p "$HOME/protocol"
git clone https://github.com/kesler20/devOS.git "$HOME/protocol/devOS"
```

Install the repository with `pipx`.

```bash
pipx install \
  --python "$(brew --prefix python@3.14)/bin/python3.14" \
  --editable "$HOME/protocol/devOS"
```

If `pipx` reports that `devos` is already installed, replace that installation.

```bash
pipx uninstall devos
pipx install \
  --python "$(brew --prefix python@3.14)/bin/python3.14" \
  --editable "$HOME/protocol/devOS"
```

Make sure the directory where `pipx` exposes commands is on `PATH`, then restart
the login shell.

```bash
pipx ensurepath
exec zsh -l
```

Verify that the executable is available.

```bash
command -v dev
pipx list
```

`command -v dev` should resolve to `~/.local/bin/dev`. Schema and targeted build
commands work outside Git. Repository operations use the current checkout.

### Install globally on Windows

Install devOS as an editable global tool with `uv`. Python 3.14 can be shared with
cliOS and satisfies devOS's Python requirement.

```powershell
uv python install 3.14
uv python find 3.14
```

Clone devOS into the `protocol` folder if it is not already present.

```powershell
New-Item -ItemType Directory -Force -Path "$HOME\protocol" | Out-Null
git clone https://github.com/kesler20/devOS.git "$HOME\protocol\devOS"
Set-Location "$HOME\protocol\devOS"
```

Install the repository. The editable installation keeps `dev` connected to the
source checkout.

```powershell
uv tool install --python 3.14 --editable .
uv tool update-shell
```

Open a new PowerShell window after `uv tool update-shell`, then verify the command
from an active Git repository.

```powershell
Set-Location "$HOME\protocol\devOS"
Get-Command dev
dev version
```

If devOS is already installed through `uv`, replace or refresh the installation.

```powershell
uv tool install --force --python 3.14 --editable "$HOME\protocol\devOS"
```

### Configure devOS

Install frontend dependencies with pnpm --dir frontend install --frozen-lockfile.
Launch Studio with dev ui. Use dev scaffold inspect and the approved scaffold
specification for project setup.

Run `dev config creds`, set project values with `dev set creds KEY VALUE --project`, then run `dev materialise creds` inside the repository.

Verify the standalone CLI.

```bash
dev schema --help
```

### Update or remove devOS

Because the installation is editable, source changes take effect immediately.
Pull repository updates normally. Reinstall only when dependencies, entry points,
or package metadata change.

```bash
git -C "$HOME/protocol/devOS" pull
pipx reinstall devos
```

Remove the global command without deleting the repository.

```bash
pipx uninstall devos
```

On Windows, pull changes and refresh the `uv` installation with the following
commands.

```powershell
git -C "$HOME\protocol\devOS" pull
uv tool install --force --python 3.14 --editable "$HOME\protocol\devOS"
```

Remove the Windows installation without deleting the repository.

```powershell
uv tool uninstall devos
```

---
## Contributing

devOS is designed to be **forked and customized**. To contribute:

1. Fork the repository
2. Update templates or generators and follow the wiki SOP for reusable bundles
3. Submit a PR with your improvements
4. Or keep your fork private and sync upstream changes periodically

---

## License

MIT License — See [LICENSE](LICENSE) for details.

---