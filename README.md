# 😼 devOS

<div style="display:flex;">
  <h1>Development Operating System</h1>
  <img src="frontend\src\assets\logo.svg" style="width:15%" />
</div>

**devOS** is a development acceleration toolkit that combines visual design tools,
code generation, local automation and credential setup to eliminate
the gap between prototype and production code.

![drawUML](assets/drawUML.png)

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

## TL;DR — devOS in 5 Minutes

### Assumptions

- You are inside an active **git repository**
- You have **Node.js** installed
- The `dev` command is installed with `pipx`

### Configure a Project

Point devOS at your project's directories and language once, then everything else
(code gen, credential setup and automation utilities) reads from that config.

```bash
dev config
```

This writes `specs/project_config.json` with paths for DAOs, DTOs, routes, tests, and
contract synchronization outputs.

---

### Build Project Artefacts

Generate DAOs, DTOs, CRUD routes, and tests from your JSON specification:

```bash
dev build project_name               # full build — all artefacts for the named project
dev build dao project_name           # DAOs only
dev build dto project_name           # DTOs only
dev build api project_name           # API routes only
dev build tests api project_name     # API test scaffolding only
dev build tests services project_name # service test scaffolding only
dev build context .py,.md .          # aggregate project context file
dev sync                              # sync classes marked with @contract across Python/TypeScript
```

---

### Launch the ORM Builder UI

Open the visual entity designer (drawORM) in your browser:

```bash
dev ui path,to,devOS
```

> If this doesn't work, make sure you have Node.js installed and run `npm install` in
> the `devOS/frontend` directory.

Design entities, set field types and relationships, then export directly to
`specs/dao_spec.json`.

---

### Managing Credentials

Store credentials as JSON documents in Redis. Project runtimes load only the
credential bundle for the current Git project. General credentials remain available
only through the explicit secrets commands.

Configure Redis with either a single URL:

```dotenv
devos_redis_url=rediss://username:password@host:6379/0
```

Or separate `devos_redis_host`, `devos_redis_port`, `devos_redis_username`,
`devos_redis_password`, `devos_redis_db`, and `devos_redis_ssl` variables. The URL
takes precedence when both forms are present.

Install a project-owned loader and configuration template:

```bash
dev setup credentials
```

Push the current `.env`, set one value, or materialize the project credentials:

```bash
dev set credentials             # refuses to overwrite existing keys
dev set credentials true        # force an overwrite
dev set credential API_TOKEN token-value
dev get credentials
```

General values use the existing secrets command:

```bash
dev set secrets secret_key secret_value
dev get secrets secret_key
```

The get command copies the value to the clipboard without printing it. Without a
project name, listing shows global key names, the current project's key names, and
the registered projects. With a project name, it shows only that project's key names:

```bash
dev list credentials
dev list credentials project-name
```

Export the complete credential estate as one `.env` file per bundle. The destination
is relative to your home directory and should remain outside OneDrive and Git:

```bash
dev export credentials vault-export
```

Copy the whole store into a second Redis database with a lossless JSON mirror.
Export writes one file per stored key, dropping the `devos:` prefix and turning
the remaining colons into folders, so `devos:projects:devOS` becomes
`projects/devOS.json`:

```bash
dev export store "Protocol/00 PKM/3 Resources/vault"
```

Both commands talk to whichever database the current `.env` describes, so the
`devos_redis_*` variables are what select the destination. Point them at the
second database, then import. Import writes only to Redis, never to `.env`, and
never replaces a value that is already there: an existing credential is kept and
reported, everything else lands, and the project registry is unioned.

```bash
dev import store "Protocol/00 PKM/3 Resources/vault"
```

The exported tree holds every credential in plaintext, so delete it once the
import is done.

The one-time legacy migration is intentionally a script rather than a permanent
command:

```bash
python scripts/migrate_credentials_vault.py
```

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

## Table of Contents

- [TL;DR — devOS in 5 Minutes](#tldr--devos-in-5-minutes)
- [Philosophy](#philosophy)
- [Core Components](#core-components)
- [Installation](#installation)
- [Key Concepts](#key-concepts)
- [Architecture](#architecture)
- [Code Generation](#code-generation)
- [Software Design](#software-design)
- [Usage](#usage)

---

## Philosophy

The advent of LLMs means there's **no excuse** for not having tests, documentation,
and high-quality clean code. devOS is built on these principles:

1. **Prototype first, refactor with design** — Write messy code to understand the
   problem, then use devOS to rewrite it properly
2. **First version is always throwaway** — Accept that prototypes are learning tools,
   not production artifacts
3. **Specifications over implementations** — JSON specifications export to any
   language and avoid AST parsing errors
4. **Version-controlled development assets** use the canonical wiki library for
   complete reusable code bundles
5. **Local agent workflows** use registered engineering guides and complete
   reusable bundles

devOS is **not distributed via PyPI**. It is cloned locally and installed as an
editable `pipx` tool so the `dev` command is available across projects. The cloned
repository lets you:

- Customize default configs and settings for your team
- Install reusable wiki bundles through the agent workflow
- Use it as a Redis-backed credential database client
- Run local Ralph workflows without cloud dependencies

---

## Core Components

### drawORM — Visual ORM Designer

A UI ORM builder powered by
[React Flow](https://reactflow.dev/docs/guides/custom-nodes/), inspired by
[drawSQL](https://drawsql.app/).

**Purpose:** Refactoring tool for data models

- Design your domain entities visually
- Generate DAOs, DTOs, CRUD routes, and tests automatically
- Syncs specifications bidirectionally (like xstate, but for Clean Architecture)

### drawUML — Specification Builder

A domain-specific visual language on top of JSON for defining:

- Endpoints and schemas
- Advanced behaviors (on-delete rules, data transformations, pre/post-instantiation
  hooks)
- Business logic constraints

**Why JSON specifications?**

- Easier to export to different programming languages
- Less error-prone than building abstract syntax trees
- Machine-readable for LLM code generation
- Type-safe and version-controllable

### Agent workflow

Agents use the canonical wiki Snippets SOP for reusable code bundles. Refresh
registered project instructions through automation_engine's
`scripts/sync_project_agents.py`. devOS supplies scaffolding, code generation and
scoped credential setup for those workflows.

---

## Installation

### Prerequisites

- **Node.js** v18 or above
- **Python** 3.12 or above
- An active **git repository** (devOS extracts repo name, tags, etc.)
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

`command -v dev` should resolve to `~/.local/bin/dev`. Run devOS commands inside
an active Git repository because devOS uses the current repository for project
configuration.

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

1. **Run the setup command:**

```bash
dev setup
```

This will:

- Install the ORM builder UI (React frontend)
- Configure environment variables
- Locate the canonical wiki library for credential setup

2. **Configure credential storage:**

Set the Redis bootstrap variables, then run `dev setup credentials`. Redis becomes
the credential authority. A local `.env` remains an explicit materialization and
offline fallback.

3. **Verify installation:**

```bash
dev version
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

## Key Concepts

### Specification-Driven Development

devOS assumes you update **DAOs and endpoints via specifications**, freeing you to
focus on:

- Writing use cases
- Implementing adapters (services)
- Creating comprehensive tests

### The Credential Database

Redis stores one JSON document for general credentials and one per Git project.
Applications load only their own project document at import time through their copied
`configs.py` bundle. General credentials are available only through the explicit
secrets commands.
Redis is authoritative when available. If it cannot be reached, values already loaded
from a local `.env` remain in place.

Explicit exports preserve arbitrary JSON values under:

```text
vault-export/
  general/credentials.json
  projects/<project-name>/credentials.json
```

### Reusable bundles

The canonical library is automation_engine's `wiki/Snippets/`, governed by its
Snippets SOP. Agents adapt complete bundles and run their offline tests in the
target. Provider configuration and credential assignment remain explicit.

### Configuration Paths

Paths are entered as **comma-separated lists** to remain platform-agnostic.

**home_root configs:**

- Global configs using the user home directory as root
- Paths start from `~` or `$HOME`

**project_root configs:**

- Project-specific paths starting from the repository root
- Define directories, filenames, and programming languages for generated code

### ORM Builder UI Guidelines

- Use **array types** to indicate one-to-many relationships
- AI autocomplete is available in the editor for endpoint definitions
- Visual design syncs bidirectionally with JSON specifications

---

## Architecture

### System Overview

```mermaid
graph TB
    subgraph "Visual Design Layer"
        A[drawORM UI]
        B[drawUML UI]
    end

    subgraph "Specification Layer"
        C[JSON Specifications]
        D[Domain-Specific Rules]
    end

    subgraph "Code Generation Layer"
        E[DAO Generator]
        F[DTO Generator]
        G[Route Generator]
        H[Test Generator]
        I[LLM Codegen]
    end

    subgraph "Local Workflow"
      J[Ralph Scripts]
      K[Project Instructions]
      L[Local Task Execution]
    end

    subgraph "Developer Assets"
        M[Wiki Snippet Bundles]
        N[Redis Credential Database]
        O[Templates]
    end

    A --> C
    B --> C
    C --> D
    D --> E
    D --> F
    D --> G
    D --> H
    D --> I
    E --> J
    F --> J
    G --> J
    H --> J
    I --> J
    J --> K
    K --> L
    M --> J
    N --> J
    O --> E
    O --> F
    O --> G
    O --> H
```

### Data Flow

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant UI as drawORM/drawUML
    participant Spec as JSON Specification
    participant Gen as Code Generator
    participant Ralph as Ralph Workflow
    participant Local as Local Task Runtime

    Dev->>UI: Design entities & endpoints
    UI->>Spec: Generate JSON specification
    Spec->>Gen: Parse and validate
    Gen->>Ralph: Create local generation task
    Ralph->>Local: Execute code generation
    Local->>Ralph: Apply templates & snippets
    Gen->>Dev: Produce DAOs, DTOs, routes, tests
    Dev->>Local: Review generated changes
```

### Clean Architecture Layers

devOS enforces Clean Architecture principles through code generation:

```
┌─────────────────────────────────────────┐
│          Domain Layer                    │
│  • entities.py (DAOs)                   │
│  • Business rules & constraints         │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│        Use Cases Layer                   │
│  • crud_dto.py, custom_dto.py           │
│  • use_cases.py                         │
│  • ports.py (interfaces)                │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│      Infrastructure Layer                │
│  • crud_routes.py, custom_routes.py     │
│  • adapters.py                          │
│  • schema.py (external contracts)       │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│          Tests Layer                     │
│  • unit_tests.py                        │
│  • integration_tests.py                 │
└─────────────────────────────────────────┘
```

**Dependency Rule:** Inner layers never depend on outer layers.

---

## Code Generation

### Supported Languages

- **Python** (FastAPI, SQLAlchemy, Pydantic)
- **TypeScript** (React, Express, type definitions)
- **More languages** via LLM codegen when not explicitly supported

### Generation Workflow

1. **Design in drawORM/drawUML** — Visually define entities, relationships, and
   endpoints
2. **Export JSON specification** — Domain-specific rules encoded as JSON
3. **Run code generator:**

```bash
dev build project_name               # Generate all artifacts
dev build dao project_name           # Generate DAOs only
dev build dto project_name           # Generate DTOs only
dev build api project_name           # Generate API routes only
dev build tests api project_name     # Generate API test scaffolding only
dev build tests services project_name # Generate service test scaffolding only
dev sync                              # Translate all classes in @contract files
```

4. **LLM Integration** — When programming language is not specified, devOS invokes an
   LLM codegen workflow using `AGENTS.md` for architectural guidance

### Test Generation

- **Service tests:** Code generator searches for files with `@service` marker
- **API tests:** Generates tests only for endpoints created by devOS code generator

### Extending Generated Code

Generated code is **importable** and **extensible**:

```python
# Import generated routes
from generated_endpoints import app

# Extend with custom routes
@app.route("/custom_endpoint", methods=["POST"])
def custom_endpoint():
    return {"message": "Custom logic here"}
```

### Suggested Project Structure

```
project/
├── domain/
│   └── dao.py                    # Generated entities
├── use_cases/
│   ├── crud_dto.py               # Generated CRUD DTOs
│   ├── custom_dto.py             # Your custom DTOs
│   ├── use_cases.py              # Your business logic
│   ├── ports.py                  # Interfaces for adapters
│   └── utils/                    # Shared utilities
├── infrastructure/
│   ├── crud_routes.py            # Generated CRUD routes
│   ├── custom_routes.py          # Your custom routes
│   ├── adapters.py               # External service adapters
│   └── schema.py                 # Third-party contracts
└── tests/
    ├── unit_tests.py             # Generated unit tests
    └── integration_tests.py      # Generated integration tests
```

---

---

## Software Design

### React Component Architecture

The frontend is built with React + TypeScript following event-driven patterns
outlined in `AGENTS.md`.

```mermaid
classDiagram
   App <|-- Console
   Console <|-- UmlDiagram
   Console <|-- NavbarComponent
   Console : - edges
   Console : - nodes
   Console : + handleCopy()
   Console : + createTable()
   Console : + onEventNodesChange()
   Console : + onEventEdgesChange()

   UmlDiagram : - gridTable
   UmlDiagram : + viewComment
   UmlDiagram : + objectComment
   UmlDiagram : + insertMode
   UmlDiagram : + findIndex()
   UmlDiagram : + addRow()
   UmlDiagram : + deleteRow()
   UmlDiagram : + handleNavigation()
   UmlDiagram : + handleObjectClick()

   NavbarComponent : - sideBarView
   NavbarComponent : + onEventExportJSON()
   NavbarComponent : + onEventImportJSON()
   NavbarComponent : + onEventCreateTable()
```

### Console Design (Container Component)

**View:** The Console component is divided into two sections:

1. **NavbarComponent** — Uses `createTable` and `handleCopy` to modify parent state
2. **React Flow Grid** — Uses `UmlDiagram` as custom nodes:

```jsx
const nodeTypes = { umlDiagram: UmlDiagram };
```

**State:** The node data structure:

```jsx
{
  id: `node-${nodes.length + 1}`,
  type: "umlDiagram",
  position: { x: 10, y: 10 },
  data: {
    objectName: "Object Name",
    comment: "Object Description",
    color: getRandomColor(),
    gridTable: [
      {
        visibility: "+",
        signature: "",
        type: "",
        comment: "signature description",
      },
    ],
  },
}
```

This data is passed to `UmlDiagram` via the `data` prop and modified through:

- `addRow()` / `deleteRow()` — Manage entity fields
- `handleObjectClick()` — Select/focus entities
- `handleNavigation()` — Keyboard navigation within the grid

### Backend Architecture

Follows Clean Architecture principles (see `AGENTS.md`):

```
domain/ → use_cases/ → infrastructure/
```

- **domain/entities.py** — Business entities and DAOs
- **use_cases/** — Business logic, DTOs, and ports
- **infrastructure/** — Adapters, routes, clients, and external contracts

---

## Usage

### Quick Start

1. **Launch the ORM builder:**

```bash
dev ui path,to,devOS
```

2. **Design your entities:**
   - Drag nodes onto the canvas
   - Define fields with types and relationships
   - Add constraints and validation rules

3. **Export specification:**

Use the drawORM save/export action in the UI. It writes to `specs/dao_spec.json`.

4. **Generate code:**

```bash
dev build project_name
```

5. **Implement use cases:**

Write your business logic in `use_cases/use_cases.py` using the generated DTOs and
DAOs.

6. **Run tests:**

```bash
pytest tests/
```

### Configuration

Edit `specs/project_config.json` to customize:

```json
{
  "project_name": "my-project",
  "home_root": {
    "snippets": ["protocol", "automation_engine", "wiki", "Snippets"]
  },
  "project_root": {
    "dao_output_config": [
      { "directory": ["src", "my_app", "domain", "dao.py"], "language": "python" }
    ],
    "dto_output_config": [
      { "directory": ["src", "my_app", "use_cases", "dto.py"], "language": "python" }
    ],
    "api_output_config": [
      {
        "directory": ["src", "my_app", "infrastructure", "routes.py"],
        "language": "python"
      }
    ],
    "test_api_output_config": [
      { "directory": ["tests", "test_routes.py"], "language": "python" }
    ],
    "test_services_output_directory": ["tests"],
    "contract_sync_output_config": [
      {
        "source_language": "python",
        "output_directory": ["src", "typescript_code", "schema"]
      },
      {
        "source_language": "typescript",
        "output_directory": ["src", "python_code", "schema"]
      }
    ]
  }
}
```

Any class inside files containing `@contract` is translated to the opposite language
using the same filename stem. Example: `types.ts` -> `types.py` in the configured
destination.

---

## Why devOS?

### The Problem

With LLMs, we can generate high-quality code faster than ever. But we still:

- Write throwaway prototypes that never get refactored
- Lack tests and documentation
- Rebuild the same patterns across projects
- Struggle to maintain consistency in large teams

### The Solution

devOS bridges the gap between **prototype** and **production**:

1. **Visual design tools** eliminate manual boilerplate
2. **JSON specifications** ensure portability and type safety
3. **Ralph-first local workflows** keep automation under your control
4. **Complete wiki bundles** carry tested patterns and setup into projects
5. **LLM integration** handles unsupported languages and edge cases

### When to Use devOS

✅ **Use devOS when:**

- Starting a new project that needs Clean Architecture
- Refactoring a prototype into production code
- Standardizing patterns across multiple projects
- Working on proprietary code that can't use cloud AI services
- You want generated tests, docs, and scaffolding automatically

❌ **Don't use devOS when:**

- Building a quick throwaway script
- Project structure is too unique for code generation
- Team prefers full manual control over every file

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

## Roadmap

- [ ] Support for more programming languages (Go, Rust, Java)
- [ ] GraphQL schema generation
- [ ] Integration with more task management tools (Jira, Linear, etc.)
- [ ] Real-time collaboration on drawORM canvas
- [ ] Export to OpenAPI/Swagger specifications
- [ ] Plugin system for custom code generators

---

**Built with ❤️ by developers who are tired of rewriting the same code.**
