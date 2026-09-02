## 0. Soul

This section defines the agent's working style and behaviour.

### Ask, Don't Assume

- If Kesler references something unfamiliar check the World-Model Wiki (`WIKI/INDEX.md`) and past Claude Code conversations (`CLAUDE_CODE_CONVOS`) for relevant context before asking.
- Ask when, after checking those, missing information could still materially change
  the result. Otherwise use the most reasonable interpretation.
- Once you get an answer, save it to the relevant context or file (the wiki, if it's
  a durable fact about Kesler's reality; the project itself, if it's project-specific)
  so the same question never has to be asked twice.

### Confidential Information

- Retrieve confidential values from devOS general secrets with `dev get secrets <KEY>`.
  This copies the value to the clipboard without printing it.
- Never write confidential values to the wiki, logs, plans, prompts, or tool output.
- If a required value is absent from devOS, search personal sources, store a discovered
  value with `dev set secrets <KEY> <VALUE>`, and remove it from the wiki when present.
  Preserve historical records such as emails, receipts, and captured conversations.

### Pinging Kesler

- When something needs Kesler's direct attention (such as a genuine question left after
  checking Ask, Don't Assume's sources, something missed or blocked, a decision
  only he can make) state the flag or question plainly and surface it through
  whatever push/alert mechanism the current harness provides so it reaches him over mobile.

### Minimal Footprint

- Don't add anything that wasn't asked for. Make the smallest edit that accomplishes
  the task.
	- As such, read the artefact before editing and review it afterward to avoid inconsistencies or repetitions.
- When a change makes prior behavior, a proposed item, or a deferred idea
  obsolete, write the artefact as if that thing never existed. Remove rejected
  items entirely instead of replacing them with negative rules, out-of-scope
  statements, or explanations, unless the artefact is explicitly a changelog or
  decision log. Example - if a checklist item is rejected, delete the checklist
  item rather than writing "do not do this item".
- When asked to fix a bug or solve a problem, carry the work through to the real
  failing workflow and solve the underlying issue. Use browser control, live
  service checks, logs, reruns, or other available tools when they are needed to
  verify the actual problem and its resolution. Do not substitute defensive
  wrappers, broad `try`/`catch` blocks, silent skips, or ignored errors for a
  real fix. Patch code only when the investigation shows a code change is the
  correct fix, or when Kesler explicitly asks for that kind of patch.
- Never make edits, run writes, or take other side-effecting actions off the back of a
  question alone, only an explicit request for a change authorizes one.

### Precision Over Padding

- When replying to me, avoid echoing the prompt, no repetition.
- Write edited artefacts as current-state truth. Do not include prompt wording,
  change-request language, migration history, or explanations of what used to be
  true unless the artefact is explicitly a changelog or decision log. Without the
  conversation or change request that produced it, leftover change-request
  language will not make sense to a future reader of the artefact.
- No unnecessary bolding.
- NO em-dashes!
- NO semicolons!
- Use colons only when strictly necessary inside YAML frontmatter, a bare colon followed by a space breaks parsing
  entirely. Check with a YAML parser after editing one.

---

## 1. Knowledge Base

### Folder Structure

```
ROOT
├── HOME                    = ~
├── LOCAL_DOWNLOADS         = ~/Downloads
├── PROTOCOL                = ~/Protocol
├── WIKI                    = PROTOCOL/automation_engine/wiki

PERSONAL KNOWLEDGE MANAGEMENT (OneDrive)
├── ONEDRIVE                = ~/OneDrive/00 PKM
├── PHD_ONEDRIVE            = ~/OneDrive - University College London/00 PKM

GOUSTO GOOGLE DRIVE
├── GOUSTO_DRIVE            = ~/Library/CloudStorage/GoogleDrive-kesler.isoko@gousto.co.uk/My Drive/00 PKM
├── GOUSTO_PROJECTS         = GOUSTO_DRIVE/1 Projects
├── GOUSTO_ACTIVITIES       = GOUSTO_DRIVE/2 Activities
│   └── GOUSTO_SOPS         = GOUSTO_ACTIVITIES/SOPs
├── GOUSTO_RESOURCES        = GOUSTO_DRIVE/3 Resources
│   ├── GOUSTO_EMAILS       = GOUSTO_RESOURCES/Emails
│   ├── GOUSTO_MESSAGES     = GOUSTO_RESOURCES/Messages
│   ├── GOUSTO_MEETINGS     = GOUSTO_RESOURCES/Meetings
│   └── GOUSTO_TEMPLATES    = GOUSTO_RESOURCES/Templates
└── GOUSTO_ARCHIVE          = GOUSTO_DRIVE/4 Archive

PROJECTS
├── PROJECTS                = ONEDRIVE/1 Projects
├── PHD_PROJECTS            = PHD_ONEDRIVE/1 Projects
├── OBSIDIAN_PROJECTS       = PROTOCOL/00 PKM/1 Projects

ACTIVITIES
├── ACTIVITIES              = ONEDRIVE/2 Activities
├── PHD_ACTIVITIES          = PHD_ONEDRIVE/2 Activities
├── OBSIDIAN_ACTIVITIES     = PROTOCOL/00 PKM/2 Activities
│   ├── OBSIDIAN_SOPS        = OBSIDIAN_ACTIVITIES/SOPs
│   ├── OBSIDIAN_MEETINGS    = OBSIDIAN_ACTIVITIES/Meetings
│   │   └── AI_MEETING_NOTES = OBSIDIAN_MEETINGS/AI Meeting Notes
│   ├── DAILY_NOTES         = OBSIDIAN_ACTIVITIES/Daily Notes
│   └── CAREER              = OBSIDIAN_ACTIVITIES/Career
│       ├── CAREER_DB        = CAREER/Database
│       └── CAREER_NOTES     = CAREER/Notes

RESOURCES (General)
├── RESOURCES               = ONEDRIVE/3 Resources
│   ├── TEXTBOOKS           = RESOURCES/Textbooks
│   ├── PAPERS              = RESOURCES/Papers
│   ├── DATA_LAKE           = RESOURCES/Data Lake
│   └── DOWNLOADS           = RESOURCES/Downloads

RESOURCES (PhD-Specific)
├── PHD_RESOURCES           = PHD_ONEDRIVE/3 Resources
│   ├── PHD_PAPERS          = PHD_RESOURCES/Papers
│   ├── PHD_TEXTBOOKS       = PHD_RESOURCES/Textbooks
│   ├── PHD_TEMPLATES       = PHD_RESOURCES/Templates
│   ├── PHD_MEETINGS        = PHD_RESOURCES/Meetings
│   ├── PHD_DATA_LAKE       = PHD_RESOURCES/Data Lake
│   │   └── sofia_planner_data.json  = PHD_DATA_LAKE/sofia_planner_data.json
│   ├── PHD_DOWNLOADS       = PHD_RESOURCES/Downloads
│   ├── PHD_EMAILS          = PHD_RESOURCES/Emails
│   ├── PHD_MESSAGES        = PHD_RESOURCES/Messages
│   ├── PHD_CAPTURED_NOTES  = PHD_RESOURCES/Captured Notes
│   │   ├── CLAUDE_CODE_CONVOS = PHD_CAPTURED_NOTES/Claude Code
│   │   └── CODEX_CONVOS       = PHD_CAPTURED_NOTES/Codex
│   └── PHD_RECEIPTS        = PHD_RESOURCES/Receipts

OBSIDIAN VAULT
├── OBSIDIAN                = PROTOCOL/00 PKM
├── OBSIDIAN_RESOURCES      = OBSIDIAN/3 Resources
│   ├── TEMPLATES           = OBSIDIAN_RESOURCES/Templates
│   ├── ZETTELKASTEN        = OBSIDIAN_RESOURCES/Zettelkasten
│   │   ├── TUTORIALS        = ZETTELKASTEN/Tutorials
│   │   ├── LEAF_NOTES       = ZETTELKASTEN/Leaf Notes
│   │   ├── EVERGREEN_NOTES  = ZETTELKASTEN/Evergreen Notes
│   │   └── CAPTURED_NOTES   = ZETTELKASTEN/Captured Notes
│   │       ├── READWISE            = CAPTURED_NOTES/Readwise
│   │       │   └── READWISE_ARTICLES = READWISE/Articles
│   │       ├── CAPTURED_PAPERS     = CAPTURED_NOTES/Papers
│   │       ├── CAPTURED_TEXTBOOKS  = CAPTURED_NOTES/Textbooks
│   ├── CONFIGS             = OBSIDIAN_RESOURCES/Configs
│   │   ├── POWERSHELL_PROFILE = CONFIGS/Microsoft.PowerShell_profile.ps1
│   │   └── TERMINAL_SETTINGS  = CONFIGS/windows_terminal_settings.json
│   └── DATABASES           = OBSIDIAN_RESOURCES/Databases
│       └── PEOPLE          = DATABASES/People
```
### Where to Look

**System configs** (`CONFIGS`): captured snapshots of machine configuration files:
PowerShell profile (`Microsoft.PowerShell_profile.ps1`), Windows Terminal settings
(`windows_terminal_settings.json`), and the VS Code user profile under
`CONFIGS/VS Code/` (settings, keybindings, tasks, snippets, the installed extension
list, and the workbench UI layout extracted from `state.vscdb`, with a `RESTORE.md`
describing how to rebuild the profile on a new machine). These are auto-refreshed by the
`capture_system_configs` pipeline in `automation_engine` on every ingestion run. Do
not edit these files directly; edit the originals and let the pipeline sync them.

**Agent prompts** (`ACTIVE_AGENT_PROMPTS_FOLDER`): captured snapshots of the
current (not laid off) agent role files (`agents/career-coach.md`,
`agents/dietitian.md`, `agents/forward-deployed-engineer.md`,
`agents/teacher.md`, `agents/shared.md`) and the root `AGENTS.md`. The active
capture profile writes them to `EVERGREEN_NOTES` on PhD computers and
`GOUSTO_RESOURCES/Agent Prompts` on Gousto computers. These are auto-refreshed
by the `capture_agent_prompts` pipeline in `automation_engine` on every
ingestion run. Do not edit these files directly. Edit the originals and let the
pipeline sync them.

**Downloads** (`PHD_DOWNLOADS`, `LOCAL_DOWNLOADS`): the general dump. Files land here
when nothing else is specified. If the task prompt suggests starting directories,
start there. If not, or if you have exhausted other locations, check downloads (PhD
or Local downloads, the personal onedrive one will not contain anything). For
attachments and files associated with emails, check here.

**Emails** (`PHD_EMAILS`): captured Gmail and Outlook inbox messages, written as
Markdown files by the `capture_all_emails_to_markdown` ingestion pipeline. Each file
is named `YYYY-MM-DD - [subject-slug].md` and contains frontmatter with `source`,
`from`, and `date`. Check this folder first for any task that involves an email
thread, follow-up, or message that was received rather than downloaded as a file.

**Messages** (`PHD_MESSAGES`): captured WhatsApp messages, forwarded via a Zapier
automation into TickTick's Inbox as `[MESSAGE] ...` tasks and written to Markdown by
the `capture_whatsapp_messages_to_markdown` ingestion pipeline. One file per
contact per day, named `YYYY-MM-DD - [contact-slug].md`, with frontmatter `source:
whatsapp`, `from`, and `date`; same-day messages from the same contact append to the
existing file rather than creating a new one. Check this folder for anything
received as a WhatsApp message rather than email.

**Active captured communications** (`ACTIVE_EMAILS_FOLDER`,
`ACTIVE_MESSAGES_FOLDER`, `ACTIVE_MEETINGS_FOLDER`): `configs.CAPTURE_PROFILE`
selects Gousto when the mounted Gousto Drive exists and PhD otherwise. On Gousto,
these contain Gousto Gmail, Slack DMs and mentions, and raw Fathom transcripts.
Agents use these active paths for communication intake. Daily Notes, TickTick,
the Wiki, project context, and role databases do not switch with this profile.

**Meeting transcripts** (`PHD_MEETINGS`): raw meeting transcripts and recordings are
stored in the meetings folders. These contain the full record of what was discussed.

**Meeting notes** (`AI_MEETING_NOTES`, `OBSIDIAN_MEETINGS`): the Obsidian meetings
folder contains structured meeting notes, agenda items, action items, and things to
discuss. These are the curated counterpart to the raw transcripts. You can use the
obsidian meetings file to see meeting notes taken by me and meeting agenda items that
I will want to ask in the next meeting(s).

**Overall Plans** (`sofia_planner_data.json`): this file in the `PHD_DATA_LAKE`
contains financial plan, diet plan, and budget data captured from the Sofia planner
backend.

**Plan notes** (`LEAF_NOTES`): `[PLAN]` notes are context and handoff state.
Read relevant plans before acting when the user invokes a plan, when a task links
to one, or when the plan is clearly about the project or system you are changing.
Do not treat plan notes as task intake unless a role file explicitly says so.

**Project bundles** (`OBSIDIAN_PROJECTS`): project folders under
`PROTOCOL/00 PKM/1 Projects` are the durable project bundle. For project,
technical, prompt, system, research, or code work, read the relevant project
bundle before acting. Start with the design document, README, roadmap, R&S
history, and any files named by the source item or plan.

**Daily notes** (`DAILY_NOTES`): the Obsidian daily notes capture day-to-day context,
thoughts, and quick references. Useful for reconstructing timelines and finding what
was happening around a specific date and gather additional context.

**Past Claude Code conversations** (`CLAUDE_CODE_CONVOS`): prior Claude Code sessions
captured by the `capture_claude_code_conversations` ingestion pipeline, one markdown
file per session in the PhD OneDrive captured-notes archive, under a subfolder named
for the originating project. Frontmatter has
`source: claude-code`, `project`, `session_id`, `cwd`, and `date`. Check this folder
when you need context from a past Claude Code conversation, such as a prior decision,
an approach already tried, or a technical discussion, rather than assuming it's not
recoverable.

Each project's subfolder also has a `Memory/` sibling, captured by the
`capture_agent_memories` ingestion pipeline: a straight copy of that project's
auto-memory files (`MEMORY.md` index plus individual `feedback_*`/`project_*`/
`user_*`/`reference_*` notes). It is fully wiped and rewritten every run, so it
always reflects current memory state, not a history — edits and deletions at the
source (`~/.claude/projects/{project}/memory/`) show up immediately and forgotten
memories don't linger. On the Gousto profile, conversations and memory folders
use `GOUSTO_RESOURCES/Captured Notes/Claude Code` instead of the PhD destination.

**Past Codex conversations** (`CODEX_CONVOS`): prior Codex CLI sessions captured by
the same `capture_agent_memories` ingestion pipeline, one markdown file per session
in the PhD OneDrive captured-notes archive, under a subfolder named for the originating
project. Frontmatter has `source: codex`,
`project`, `session_id`, `cwd`, and `date`. Check this folder alongside
`CLAUDE_CODE_CONVOS` for prior decisions, approaches already tried, or technical
discussion that happened through Codex rather than Claude Code.

The same pipeline also mirrors Codex's own memory files (distinct from session
transcripts): each Codex Desktop automation's `~/.codex/automations/{automation}/memory.md`
lands in `CODEX_CONVOS/{automation}/Memory/memory.md`, and the general Codex CLI
memory (`~/.codex/memories/*.md`, used outside any automation) lands in
`CODEX_CONVOS/codex-global/Memory/`. Same wipe-and-rewrite semantics as the Claude
Code `Memory/` siblings above. On the Gousto profile, conversations and memory
folders use `GOUSTO_RESOURCES/Captured Notes/Codex` instead of the PhD destination.

**Zettelkasten** (`TUTORIALS`): a collection of software tutorials showing best
practices for different technologies such as Prefect, TypeScript, and React. When
writing a new tutorial, add `?` markers on key concepts and commands worth
memorising; these mark items for spaced repetition review.

**Code and engineering** (`PROTOCOL`): for coding tasks, always read
`devOS/AGENTS.md` (the canonical, always up-to-date coding style guide). You
can also use tutorials as mentioned above, and `OBSIDIAN_PROJECTS` contains design
documents, architecture decisions, and task context for each project. If more context
is needed for a coding task, look up the relevant project folder in
`OBSIDIAN_PROJECTS` (`PROTOCOL/00 PKM/1 Projects`) or the relevant software activity
folder in `OBSIDIAN_ACTIVITIES` (`PROTOCOL/00 PKM/2 Activities`).

**People CRM** (`PEOPLE`): the canonical records for people. Use `list_people` for
person lookup when available, then update the matching CRM note.

**Institutions database** (`3 Resources/Databases/Institutions`): the canonical
records for organizations and institutions. Do not create or update wiki pages for
people, organizations, or institutions.

**World-Model Wiki** (`WIKI`): a flat, undated vault modeling Kesler's cross-project
reality, decisions, resources, budgets, events, and systems. People live in the
Obsidian People CRM, while organizations and institutions live in the Institutions
database. It complements, not replaces,
auto-memory: auto-memory captures *how* to collaborate with Kesler; the wiki captures
*what is currently true* about his life, across harnesses and projects.

- **When to use it**: for any task touching Kesler's real-world context, check
  `WIKI/INDEX.md` first, then read only the relevant page(s), and check
  `CLAUDE_CODE_CONVOS` too whenever the topic could have come up in a prior
  session (a recurring goal, plan, decision, or something Kesler references as
  unfamiliar — see Ask, Don't Assume above); resolve from there before asking
  for clarification. This precedes any Folder Structure/Where to Look
  pointer to a specific data file — read the wiki
  page first even when a more specific-looking file is named elsewhere in this
  document, since the wiki holds the current, reconciled fact and the raw file may
  be stale or partial.
- **How to navigate it**: use frontmatter `tags` for topic search, `[[wikilinks]]` in
  `## Relationships` for multi-hop traversal across entities, and
  `git log --follow -p -- "wiki/<page>.md"` to recover history or check for
  superseded facts.
- **Writing to it**: treat this as a running log, not a wrap-up step — update the
  relevant page and `WIKI/INDEX.md` as soon as a new durable fact surfaces, not only
  when a task finishes. Route people facts to the People CRM and organization or
  institution facts to the Institutions database instead. This applies just as much
  while reading sources as part of normal work, including transcripts, messages,
  emails, and notes, as it does when actively stuck: don't wait until you're blocked on an ambiguity to
  persist a durable fact, record it the moment you learn it. Don't silently overwrite conflicting
  information; check `git log` first, and if a genuine conflict remains, record it
  under `## Open Questions / Contradictions`.
- **Logging decisions**: any durable decision — a tradeoff, an architecture
  change, e.g. changing a skill because of a tradeoff or removing an MCP server —
  gets a dated entry (date, decision, rationale, alternatives considered) in the
  relevant wiki page, appended to an existing page on that topic or, if none
  fits, a new page tagged `decision`. If it's unclear which page applies or
  whether a new one is warranted, ping Kesler rather than guessing. Requirement
  and design decisions internal to a single project are the exception: those are
  dated reasoning lines in that project's R&S file, nested under the requirement
  or design item they decided (see [[Project R&S Format]]). The wiki keeps
  cross-project, real-world, and agent-architecture decisions.
- **Update cadence**: at the end of any non-trivial task — a plan completed, a
  decision made, a piece of research concluded — do a quick pass over what was
  learned and check whether any of it belongs in the wiki before moving on, rather
  than waiting to be asked.

### Obsidian CLI

The `Obsidian.com` CLI talks to Kesler's live, on-screen Obsidian instance over
IPC — any command that creates, opens, moves, or switches vaults visibly disrupts
whatever he's looking at (steals focus, opens tabs, can switch the active vault,
launches the app if it wasn't running). Restrict it to read-only queries where it
beats grepping markdown:

- `search` / `search:context`: uses Obsidian's own search index.
- `backlinks` / `links` / `orphans` / `unresolved`: real link-graph queries
  (resolves aliases and wikilinks), not achievable by grepping markdown.
- `tags` / `aliases` / `properties`: vault-wide indexes with counts, not
  per-file greps.
- `tasks` (list only, not `task`/toggle): vault-wide checkbox task queries.
- `read` / `file` / `folder` / `vault info=...`: metadata lookups.

### Navigation Tip

Obsidian notes use `[[links]]` to reference other files. When you read a note, follow
its links to discover related material.

### TickTick Task Template

Work and Side Projects tasks follow a standard content template — `Links` / `Status`
sections. The canonical copy is `3 Resources/Templates/Task Template.md`.

**Dependency structure**: when a task can't start until another finishes, its
`# Status` section opens with a `Depends on <task title or reference>` optionally followed by more
lines of context. Real example, the `[Connectivity Paper]` chain in `Work`:
`Results and Discussion Section` depends on `methodology section`, which depends on
`complete flow-lab` (`cannot write methodology before implementing full software
with examples`).

`agents/forward-deployed-engineer.md` writes this template when it creates a
TickTick task. Add distinct actionable steps as TickTick subtasks rather than
itemised description bullets when possible. Tasks created for Kesler belong in
Inbox with today's deadline and medium priority, or high when the source is
urgent, and never carry the `agents` tag.

---

## 2. Skills, Agents & MCP Tools

Prioritise these over improvising a procedure from scratch: check whether a skill,
agent, or MCP tool already covers the task before building an ad hoc process by hand.

**MCP Tools**

* Use the official `mcp__ticktick__*` MCP tools for TickTick reads/writes —
  ahead of automation_engine's own client (real `update_task`, not
  delete-and-recreate).
* Call automation_engine's own use cases directly for people notes,
  MyFitnessPal, email drafting/archiving, and calendar events — e.g.
  `python -c "from automation_engine.use_cases.tools.<module> import <Class>; ..."`
  (pip-installed system-wide, works from any directory, no venv activation
  needed). Prefer these over the official Gmail/Outlook/Microsoft 365/Google
  Calendar connectors for anything email- or calendar-related: those don't
  carry the permissions needed for drafting, archiving, or event creation.
* Use the matching skill instead of a raw one-off call where one exists —
  `my-add-to-mendeley` for Mendeley, `/my-word-doc` for `.docx` output.
* Use `list_people` instead of searching the `PEOPLE` folder.

**Browser control**

Use harness-native browser controls for any task that needs browser UI work. Do the
work there instead of waiting for Kesler to drive the browser.

* In Claude Code, use `mcp__claude-in-chrome__*`.
* In Codex, use the `browser:control-in-app-browser` skill. Read that skill before
  browser work and use it as the Codex equivalent of Claude's Chrome control tools.

**Skills** (`.agents/skills/` for Codex and `.claude/skills/` for Claude Code
discovery - see Skill Naming & Sync below)

* `my-general-writing`: base protocol for any written output — document structure,
  output paths, filename rules, References vs Sources. Other writing skills build on
  this one; use it directly when no more specific skill applies.
* `my-contact-research-crm`: create or update a person note in the Professionals CRM
  for a contact not yet in the database.
* `my-add-to-mendeley`: add a reference to Mendeley with full metadata — always use
  this rather than a manual API call when a citation needs to exist in Mendeley.
* The remaining `my-*` skills cover specific recurring outputs (budget updates, paper
  drafts and reviews, handovers). Check the skill list
  before improvising a similar procedure by hand.
* `frontend-design`: imported third-party skill for distinctive UI/visual design work.
* When a task turns out to be hard — web research, chrome use, several failed steps, a pivot
  away from the initial approach (e.g. a delay-repay claim pipeline) — capture the
  approach that actually worked as a new `my-*` skill (see Skill Naming & Sync)
  once the task succeeds, so the next run starts from that process instead of
  repeating the same trial and error. Keep the skill itself minimal: the working
  steps only, not the failed attempts or speculative extensions.

**Agents** (`agents/`): a team of role-based agents, each triggered by the Codex
Desktop app's automations and also invocable interactively via the Agent tool.
Every agent reads `agents/shared.md` first — the run log, author line, and
constraints common to the whole team — then its own `agents/<role>.md`.

---

## 3. Development Rules

### Universal Coding Workflow

These rules apply to every agent that reads or changes code, scripts, notebooks,
CI/CD, prompts, rules files, or skill files:

1. Read the target project's `AGENTS.md` first. If the project has no local
   `AGENTS.md`, read `~/Protocol/devOS/AGENTS.md` in full before touching code.
2. Read the relevant `[PLAN]` note, project bundle folder, and project design
   document when the work is project, technical, prompt, system, research, or
   code related.
3. Read the relevant source files before editing and target only the files
   needed for the task.
4. Implement using existing project conventions and the smallest coherent edit.
5. Update the corresponding design document when the change affects
   requirements, architecture, API behavior, deployment behavior, data model, or
   durable project context.
6. Validate with the project's tests, type checks, lint checks, service checks,
   browser checks, render review, or the domain-appropriate equivalent.
7. Record validation evidence in the run log, plan note, or final response when
   it is not obvious from generated artifacts.

### Resolving PowerShell Aliases in Bash

Many project commands are PowerShell aliases or functions. When a command is unavailable in bash, 
**do not skip it or ask the user to run it**; instead:

1. Read the PowerShell profile at `CONFIGS/Microsoft.PowerShell_profile.ps1`
   (`~/Protocol/00 PKM/3 Resources/Configs/Microsoft.PowerShell_profile.ps1`), the
   source of truth for all aliases.
2. Find the alias or function definition to understand what it does.
3. Run the equivalent commands directly in bash.

---

### devOS Utility Updates

Tracked utils: `file_io`, `dynamic_array`, `codegen_helpers` (and any future utils
added to `devOS/src/devOS/use_cases/utils/`).

**Rule**: whenever you modify a utility file in devOS, you must also update the devOS
snippet store so the snippet reflects the latest version. Use the `dev set snippet`
command (or `dev-sync write_agents` via the PowerShell alias) as
appropriate. If a new util is added, note it in this list.

### AGENTS.md Updates

**Rule**: whenever you update `devOS/AGENTS.md`, you must:

1. Run `dev-sync read_agents` before editing to pull the latest version from the
   snippet store.
2. Make the edit to `devOS/AGENTS.md`.
3. Run `dev-sync write_agents` afterwards to push the updated file back to the
   snippet store.

`dev-sync` is a PowerShell alias. Look it up in
`CONFIGS/Microsoft.PowerShell_profile.ps1` to find the underlying commands and run
them directly in bash.

### Codex / Claude Sync

**Rule**: keep `AGENTS.md` and `CLAUDE.md` byte-identical. Edit `AGENTS.md`,
then run `python scripts/sync_harness_mirrors.py --write` to copy it to
`CLAUDE.md` and verify the harness skill folders. Run
`python scripts/sync_harness_mirrors.py` when you only need to check sync.

### Skill Naming & Sync

**Naming**: every personal skill folder uses the `my-[skillname]` name (e.g.
`my-word-doc`). This does not apply to `agents/` (agents are named plainly, e.g.
`coding`) or to imported third-party skills (e.g. `frontend-design`) — only to
skills that are ours.

**Folder sync**: `.agents/skills/` and `.claude/skills/` are the authoritative
skill locations. `.agents/skills/` is the Codex skill location and
`.claude/skills/` is the Claude Code skill location. They must hold the exact
same set of skill folders with byte-identical content, including
imported/third-party skills like `frontend-design`. This applies to every skill
regardless of the naming rule above. Create, edit, rename, or delete skills
under `.agents/skills/`, then run `python scripts/sync_harness_mirrors.py --write`
to copy the exact skill tree to `.claude/skills/` and verify byte identity.
Run `python scripts/sync_harness_mirrors.py` when you only need to check sync.

### Automation Pipelines Sync

**Rule**: `2 Activities/Automation Pipelines.md` is the one place every
automation_engine pipeline is documented for Kesler. Update the matching
section in the same pass as the change that triggers it, in the same style as
the surrounding entries:

- An edit to `agents/shared.md` or any `agents/<role>.md` that changes what
  its diagram in `## AI Agent Team` describes (a step added, removed, or
  reordered; a branch changed; the state-file schema or its source paths
  changed) — update that diagram, schema, and sources list.
- An edit to the deterministic ingestion or capture code (`use_cases/
  ingestion_engine.py`, `use_cases/ingestion/*.py`) or the execution code
  (`execution_engine.py`, `ai_workflow_execution_engine.py`,
  `etl_pipeline.py`) that adds, removes, or changes a pipeline's trigger,
  source, destination, or logic — update the matching diagram, table row,
  and prose in `## automation_engine Codebase Pipelines`.
- A new automation created anywhere (a new Zapier or Power Automate zap, a
  new ingestion/execution pipeline, a new GitHub Action) — add it to the
  matching section.

### Plan Mode: Leaf Note

**Rule**: whenever a plan is approved (normally via the `my-grill-me` skill, which
is Kesler's standard entry point into planning - see the active harness copy at
`.agents/skills/my-grill-me/SKILL.md` or `.claude/skills/my-grill-me/SKILL.md`
- but this applies equally if a plan is approved directly from Plan Mode), create or
update a plan leaf note for it.

Every plan drafted through `my-grill-me` or Plan Mode is tagged `[PLAN]` — this
covers everything: project/technical/research/personal work, and any one-off
agent-architecture or prompt change (adding a new agent, editing
`CLAUDE.md`/`AGENTS.md`/`agents/*.md`/`.agents/skills/*/SKILL.md`/
`.claude/skills/*/SKILL.md`). Some agents keep
their own differently-tagged recurring artefacts that don't go through this
rule at all — documented in that agent's own file, not here.

- Filename: `YYYY-MM-DD - [PLAN] <slug>.md` in
  `~/Protocol/00 PKM/3 Resources/Zettelkasten/Leaf Notes/`.
- Structure comes entirely from the `Plan Template.md` Obsidian template — read
  it and follow it as-is; do not duplicate its frontmatter fields or headings as
  prose elsewhere. If the structure needs to change, edit the template itself,
  not any caller. Write the new note
  directly at the target path (the Obsidian CLI's `create` is for read-only
  queries only, see Obsidian CLI above — don't use it to create files, it
  opens/focuses the note in Kesler's live window). Skip the template's
  `tp.file.move(...)` line (you already know the destination path) and resolve
  `tp.date.now(...)` to today's actual date yourself, since Templater expressions
  don't evaluate outside Obsidian.
- Immediately after writing the note from the template, fill in `source` (the
  plan file path or originating context) and every body section with real
  content.
- `## Steps` must include subtasks nested under each top-level step (mirror the
  actual TaskCreate breakdown used during execution, not just the top-level
  summary). Tick off each subtask's checkbox as it's completed, and the parent
  step once all its subtasks are done — this is a persistent, visible progress
  checklist in Obsidian, not just the ephemeral session task list.
- On approval, set `reviewed: true`. Update `status` to `In Progress` on starting
  execution and `Done` once every step is ticked.
- If resuming an existing `[PLAN] *.md` leaf note that already has
  `reviewed: false` (e.g. one Kesler drafted by hand), update it in place on
  approval — flip `reviewed`, set `status`, fill in remaining sections. Never
  re-run the template over an existing file.
