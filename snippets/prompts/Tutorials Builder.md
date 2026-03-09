You are a senior engineer and systems thinker.

I want a **minimum viable tutorial** for learning and using: <TECHNOLOGY_NAME>.

The tutorial must:

* Focus only on core concepts and minimal viable commands.
* Prioritise operational understanding over theory.
* Avoid marketing language, history, or non-essential features.
* Be structured for practical execution.
* Be concise but technically precise.
* Be suitable for converting into Obsidian flashcards.
* Be written in a natural technical tone (no meta commentary, no “as an AI” phrasing).

Structure the tutorial EXACTLY as follows:

---

## Installation

Show only what is required to get the tool running.

Include:

* Installation command(s)
* Verification command
* First run command
* Default configuration or state directory (if relevant)

Keep this minimal and executable.

---

## Main Commands

List only the core commands required for day‑to‑day usage.

For each command:

* What it does (1 line)
* When to use it
* Concrete example

Exclude rarely used flags and edge cases.

---

## Overview

Explain briefly:

* What category of tool/system this is
* The core problem it solves
* When to use it
* When NOT to use it

Keep this tight and practical.

---

## Core Abstraction

List and explain only the essential abstractions.

For each abstraction:

* Definition (1–2 lines)
* Why it exists
* How it interacts with other abstractions
* Small concrete example

Do NOT include edge-case abstractions.

---

## Minimum Viable Workflow

Describe the smallest complete workflow:

* Step 1
* Step 2
* Step 3
* Expected output/result

Include real commands or code.

---

## Operational Modes (if applicable)

If the tool has modes (e.g. local vs cloud, sync vs async, dev vs prod):
Explain:

* What changes between modes
* When to use each
* Risks/tradeoffs

If not applicable, omit this section entirely.

---

## Configuration Model

Explain:

* Where configuration lives
* Override hierarchy (CLI > env > config file, etc.)
* How to temporarily override config
* Common safe defaults

Keep it practical.

---

## Execution Model

Explain in systems terms:

* What happens internally when you run a command
* What state changes
* What it reads
* What it writes
* What can break

---

## Minimal Safe Usage Pattern

Provide a safe default pattern for using this tool in real projects.

Example structure:

* Planning mode
* Implementation mode
* Review mode

Include real commands.

---

## Common Failure Modes

List:

* Top 5 misuse patterns
* What causes them
* How to prevent them

Keep them concrete.

---

## One Concrete End-to-End Example

Provide a small but realistic example from start to finish.
Must include:

* Setup
* Action
* Verification
* Expected result

---

Formatting rules:

* Use clean markdown.
* Use short sections.
* Use code blocks for commands.
* No emojis.
* No fluff.
* No repetition.
* No long historical explanations.
* No unnecessary theoretical depth.
