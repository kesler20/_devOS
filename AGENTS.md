# Python Development

## Project Context

Read this repository's `AGENTS.md` and `docs/product/prd.md`,
`docs/product/decision-log.md`, and `docs/product/design.md` before changing code.
Follow automation_engine's `wiki/SOPs/Software Development.md` for product-document
ownership, project folders, and task status. Use the PRD's nomenclature consistently.
Respect Kesler's design constraints. Agents may update source-table descriptions
only in the design document. Keep decisions and their rationale in the decision log.

A programme grows through **stages**. It starts as a single flat file — one entry
function, its helper functions, and its data classes. Orchestration begins life as a
plain function and becomes a class only when something else in the codebase needs to
call it. Data classes provide encapsulation at every stage.

Read section 2 before writing any code. Most programmes are, and should remain, at
stage 1.

The approach is infrastructure agnostic. It applies equally to web services, mobile
applications, desktop software, and embedded systems. The delivery mechanism —
REST, WebSocket, MQTT, or a native event loop — is an infrastructure detail that
never leaks into the core logic.

---

## 1. How to Work

### 1.1. Read the Codebase Before Changing It

Before proposing or making any specific change, read this guide, then read the
codebase itself: the file being changed, its neighbouring files, and the folders it
composes with.

This guide sets the general philosophy. The codebase in front of you is the source of
truth for how that philosophy has been instantiated here, and **it wins whenever the
two disagree on a codebase-specific detail** — an existing name for a domain concept,
an established file layout, the shape of an existing data class.

For a change large enough that this exploration would consume significant context,
spin up a sub-agent (or equivalent parallel research step) to read the surrounding
files and report back the conventions in use. Do not skip the check to save time.

### 1.2. Minimal, Localised Diffs

Prefer minimal, localised diffs that are easy to review. Reuse existing components,
layers, and state patterns as much as possible before creating new ones.

### 1.3. Runtime Configuration

For runnable project scripts, use editable module-level configuration values. Do not
add argument parsers or environment-variable reads unless Kesler explicitly requests
one of those mechanisms.

### 1.4. Delete, Don't Deprecate

Do not worry about backward compatibility. When renaming, removing, or changing an
interface, update all call sites directly rather than adding shims, aliases, or
deprecation layers. Delete unused code outright — do not leave it behind with
comments or `_old` suffixes.

---

## 2. Growth Stages

Three stages, two promotion gates. Establish which stage the code is in before you
decide where anything goes.

| Stage | Shape | Entry point |
| --- | --- | --- |
| **1** | One file: `main.py` or `feature_name.py`. Entry function, module-level helpers, and data classes all together. No behavioural classes. | `main()` |
| **2** | `use_cases/feature_name.py` per feature, still plain functions. Data classes moved into their own files. | `main()` |
| **3** | `FeatureNameUseCase` class, dependencies injected through the constructor. | `execute()` |

### 2.1. Stage 1: One Flat File

Every programme starts in a single `main.py` or `feature_name.py` file. Write the core
logic directly inside a `main` function. As the routine takes shape, gradually refactor
by extracting the data classes you identify within it. Once all data classes are
identified, add methods for encapsulation following tell-don't-ask (section 6.3).

That is the whole of stage 1. **Do not create a use case, an adapter, a client, or a
port.** Helper functions live at module level in the same file, alongside `main` and the
data classes.

```python
# src/agent_run/main.py

import logging
from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple


logging.basicConfig(level=logging.INFO)

# ================== #
#                    #
#   DATA CLASSES     #
#                    #
# ================== #

class RunStatus(str, Enum):
    PENDING = "pending"
    COMPLETE = "complete"


class ToolResult(NamedTuple):
    tool_name: str
    output_text: str


@dataclass
class AgentRunInput:
    prompt: str
    max_steps: int


@dataclass
class AgentRunSummary:
    prompt: str
    cleaned_outputs: list[str]
    status: RunStatus


# ================== #
#                    #
#   MAIN ROUTINE     #
#                    #
# ================== #

def main() -> None:
    # Create the requested run input and log the starting state.
    run_input = AgentRunInput(prompt="Summarise the meeting notes", max_steps=3)
    logging.info("Created AgentRunInput: prompt=%s max_steps=%s", run_input.prompt, run_input.max_steps)

    # Collect the raw outputs produced by the tool-calling steps.
    raw_results = [
        ToolResult(tool_name="search_notes", output_text="  Notes about Q1 planning  "),
        ToolResult(tool_name="extract_actions", output_text="  1) send deck  2) confirm budget "),
    ]
    logging.info("Collected %s raw tool results", len(raw_results))

    # Normalise the tool output text before framing the final summary.
    cleaned_outputs = [result.output_text.strip() for result in raw_results]
    logging.info("Cleaned tool outputs: %s", cleaned_outputs)

    # Build the summary object with the cleaned results and a completed status.
    summary = AgentRunSummary(
        prompt=run_input.prompt,
        cleaned_outputs=cleaned_outputs,
        status=RunStatus.COMPLETE,
    )
    logging.info("Built AgentRunSummary with status=%s", summary.status)

    print(summary)


if __name__ == "__main__":
    main()
```

### 2.2. The Two Gates

**Gate one — leave the flat file.** Fires when either:

- a **second feature** appears, or
- **another part of the codebase needs to call** `main` or one of its helper functions.

**Gate two — become a class.** Fires when the feature is **called from a different part
of the codebase**.

Both gates are **mandatory checkpoints, not opportunities**. You may not add the second
feature, and you may not add the second caller, until the corresponding split has been
made. Do the split first, in its own change, then add the thing that triggered it.

Three clarifications, each of which closes a loophole:

**Tests are not a qualifying caller.** A test wanting to exercise the logic in isolation
fires neither gate. If tests counted, stage 1 would never exist. Stage 1 is tested by
calling `main()` directly (section 14).

**There is no line-count trigger.** No length of `main`, and no size of file, obliges you
to create a behavioural class. A long entry point whose workflow is visible top to bottom
is better than a short one whose workflow is scattered across private methods. If `main`
is hard to read, fix the naming and the comments, not the structure.

**Gate two often fires at the same time as gate one.** When the reason you are leaving the
flat file *is* a second caller, go straight to stage 3. Stage 2 is reached by way of the
second-feature path.

### 2.3. Stage 2: One File per Feature

Each feature gets `use_cases/feature_name.py`. Its entry point is still called `main`, and
it is still a plain function. Dependencies — adapters and clients — are **explicit
parameters**, constructed by the caller and passed in. That keeps the feature testable
with fakes without a class, and makes the eventual promotion to stage 3 mechanical: the
parameters become constructor fields.

Data classes move out of the feature file at this point into their own files (section
10.1). The feature file holds the feature's orchestration and its helper functions, not
its data.

Only `main.py` carries the `if __name__ == "__main__"` guard. Feature files define `main`
but are not independently runnable.

```python
# src/agent_run/use_cases/tool_calling.py

import logging

import agent_run.adapters as adapters
import agent_run.domain as domain


# Module-level helpers are welcome here: this file is still function-shaped.
def clean_outputs(results: list[domain.ToolResult]) -> list[str]:
    return [result.output_text.strip() for result in results]


def main(
    run_input: domain.AgentRunInput,
    chat_model_adapter: adapters.ChatModelAdapter,
    tool_registry: adapters.ToolRegistryAdapter,
) -> domain.AgentRunSummary:
    logging.info("Starting tool calling for prompt: %s", run_input.prompt)

    # Run the bounded tool-calling loop and retain each completed result.
    available_tools = tool_registry.list_tools()
    raw_results = []
    for step in range(run_input.max_steps):
        response = chat_model_adapter.generate(run_input.prompt, available_tools)
        if not response.has_tool_call():
            break
        result = tool_registry.invoke(response.tool_call)
        raw_results.append(result)
        logging.info("Step %d: called %s", step, result.tool_name)

    cleaned_outputs = clean_outputs(raw_results)
    logging.info("Cleaned %d tool outputs", len(cleaned_outputs))

    return domain.AgentRunSummary(
        prompt=run_input.prompt,
        cleaned_outputs=cleaned_outputs,
        status=domain.RunStatus.COMPLETE,
    )
```

```python
# src/agent_run/main.py

import agent_run.adapters as adapters
import agent_run.clients as clients
import agent_run.domain as domain
import agent_run.use_cases.tool_calling as tool_calling


def main() -> None:
    # Construct the dependencies here so each feature stays testable with fakes.
    run_input = domain.AgentRunInput(prompt="Summarise the meeting notes", max_steps=3)
    summary = tool_calling.main(
        run_input,
        adapters.ChatModelAdapter(clients.OpenAIClient()),
        adapters.ToolRegistryAdapter(),
    )
    print(summary)


if __name__ == "__main__":
    main()
```

### 2.4. Stage 3: Class Form

Once a feature is called from a different part of the codebase — a route, a message
handler, a scheduled job, or another feature — it becomes a class named
`FeatureNameUseCase` with an `execute` method, and its parameters become constructor
fields. Section 12 covers this form; the adapters, clients, and ports it composes are
covered in section 11, which is not stage-gated. Do not read section 12 as a template
for new code until a gate has fired.

---

## 3. Core Abstractions

Every programme is composed from a small vocabulary of building blocks. Data classes
exist from the first line of code. The rest appear only when a gate in section 2.2 or a
rung of the ladder in section 4 admits them.

**Data classes** store data using fields and expose behaviour through methods that
operate on that data. They are the nouns of the system: `AgentRunInput`, `Product`,
`OrderStatus`.

**Use Cases** are the features of the application. A Use Case is whatever `main` of a
stage-2 feature file does, or the `execute` of a stage-3 class — never an internal
workflow step. There should be few of them, and each should name something the
application actually does, in the language a user or an operator would use:
`tool_calling`, `structured_output`, `streaming_response`.

**Adapters** are concrete implementations of **infrastructure you own** — a capability
you control the semantics of and could swap out: a database, a cache, a bucket, a message
queue, an authentication provider. `S3ObjectStorageAdapter`,
`Auth0AuthenticationAdapter`, `RedisCacheAdapter`.

**Clients** are interfaces to a **service someone else owns**, reached across an
ownership boundary. The service may be internal to your organisation (`OrderClient` for
another team's order service) or external (`OpenAIClient`, `TikTokAdsClient`,
`AWSClient`). A Client holds that service's coordinates — base URL, bucket name,
credentials — as instance properties set in its constructor, and exposes methods that
tell the service what you want from it.

The cut between the two is **ownership, not vendor**. The same technology appears as
either, depending on the role it plays: S3 as your own storage is
`S3ObjectStorageAdapter`; S3 as the pipe to another team's data exhaust is that team's
`Client`'s business. Section 11 covers both in full.

**Composition runs in either direction.** A Client may import Adapters — when reaching
the service requires infrastructure. An Adapter may import Clients — when your own
infrastructure is reached through a vendor's service. **Neither may import a use case.**
Both declare schemas for their request and response (section 11.4).

**Use Cases, Adapters, and Clients declare an explicit `__init__`.** `@dataclass` and
`pydantic.BaseModel` are for data classes (section 5.2), never for behavioural or
boundary classes: a constructor is where dependencies are taken and where coordinates are
validated or derived from one another.

**Ports/Interfaces** define contracts between Use Cases and adapters. They exist only
when more than one **adapter** implements the same piece of infrastructure. Ports are
adapter-only; a substitutable service provider gets an adapter over its client.

**Schemas, DAOs and DTOs** define contracts at system boundaries. **DAOs** (Data
Access Objects) represent the shape of objects persisted to storage (SQL rows, NoSQL
documents, graph nodes). **DTOs** (Data Transfer Objects) are service-specific
contracts with the outside world — the objects your API sends and receives, such as
`CreateUserResponse` or `RefundRequest`. **Schemas** are third-party or
infrastructure data transfer objects — shapes dictated by external libraries, APIs, or
protocols that you do not control, such as a Stripe webhook payload or an OAuth token
response.

### 3.1. Naming

The only permitted names for behavioural classes are **Adapter**, **UseCase**, and
**Client**. Generic names like `handler`, `platform`, `processor`, `engine`, `executor`,
`manager`, and `service` are not allowed. The `UseCase` suffix is a **stage-3 suffix**:
at stages 1 and 2 the feature is a function called `main`, in a file named after the
feature, and nothing carries `use_case` in its name.

```python
# Good: domain-specific, uses permitted abstractions
class ToolCallingUseCase: ...
class StructuredOutputUseCase: ...
class RedisTimeSeriesDbAdapter: ...
class GoogleCalendarClient: ...

# Bad: generic, infrastructure-flavoured names
class EventProcessor: ...
class JobManager: ...
class DataHandler: ...
```

**No prompt or persona nomenclature.** Never name identifiers, docstrings, or
comments after a persona, or after the language used to request the change, when that
term does not itself describe a domain concept. Follow the naming conventions already
used in the codebase instead.

**No leading underscores on module-level names, at any stage.** Constants, module-level
variables, module-level helper functions, and any name defined at the top of a file must
never begin with `_`. Use plain `UPPER_CASE` for constants. The `__` prefix is valid only
inside a class body, for private methods and private instance attributes (see section
6.2).

```python
# Good
ALLOWED_TOOLS = "Read,Write,Edit"
CLAUDE_WORKING_DIRECTORY = Path(configs.PROTOCOL_FOLDER) / "claude"

# Bad
_ALLOWED_TOOLS = "Read,Write,Edit"
_CLAUDE_WORKING_DIRECTORY = Path(configs.PROTOCOL_FOLDER) / "claude"
```

### 3.2. Domain Language, Not Implementation Language

Every signature — class name, function name, parameter name — is named for what it
means in the problem domain, never for how the code happens to be built. Before
naming anything, ask what an operator or domain expert would call this thing or this
action, not what data structure or mechanism implements it.

**Function and method names are always verbs or verb phrases**, naming the action
taken and the domain fact it produces. A noun phrase is never a function name, however
descriptive it reads as a variable.

```python
# Good: verb phrases naming the domain action and what they return
def get_total_skus_of_mw_cohort(cohort: domain.Cohort) -> int: ...
def get_total_boxes_per_mw_cohort(menu_week: domain.MenuWeek) -> list[domain.CohortTarget]: ...
def calculate_n_of_stations(scenario: domain.OptimalScenario) -> int: ...

# Bad: noun phrases, and named after the code shape rather than the domain question
def cohort_sku_totals(cohort: domain.Cohort) -> int: ...
def derive_cohort_targets(menu_week: domain.MenuWeek) -> list[domain.CohortTarget]: ...
def build_capps_scenario(...) -> dict[str, typing.Any]: ...
```

Do not create a data class merely to pair up two other domain concepts as a lookup or
join key. If the only reason `CohortKey` exists is to combine a `DeliveryBatch` and a
`LeadTimeCohort` into something a dictionary or a database can key on, that shape
belongs in the schema layer (section 11.4), not as a domain data class. Section 6.1
already governs this: a data class earns its place through an independent identity,
lifecycle, or invariant, not through convenience of composition.

A Client or Adapter method that is a plain internal function call — not a request
over the network and not an endpoint the network exposes — takes domain values as
parameters, the same as any other function. Do not pass it a wire schema object; wire
schemas exist only at the actual network or storage boundary (section 11.4).

### 3.3. Composition, Not Implementation Inheritance

We subscribe to **abstraction**, **composition**, and **encapsulation**. We do not use
**implementation inheritance** — inheriting from a concrete class to reuse its code or
override its behaviour.

The only acceptable reason to inherit is to gain **framework behaviour**: `BaseModel`
for validation, `ABC` for defining interfaces, `DeclarativeBase` for ORM mapping, or
similar. Inheriting from an abstract port like `ChatModelPort(ABC)` to implement a
concrete adapter is permitted — that is interface conformance, not implementation
reuse. What is not permitted is creating a `BaseAdapter` with shared logic and having
`PostgresAdapter(BaseAdapter)` and `MongoAdapter(BaseAdapter)` inherit from it. Use
composition to share logic between concrete classes instead.

```python
import abc
from dataclasses import dataclass
from pydantic import BaseModel
import sqlalchemy.orm as orm


# Framework behaviour only: ORM mapping, validation, plain data, interface definition.
class UserDAO(orm.DeclarativeBase):
    __tablename__ = "users"
    id: int
    name: str


class OrderPlacedEvent(BaseModel):
    order_id: str
    customer_id: str
    total_pence: int


@dataclass
class TransientResult:
    query: str
    matches: list[str]


class ChatModelPort(abc.ABC):
    @abc.abstractmethod
    def generate(self, prompt: str) -> str:
        """
        Generate a response from the chat model.

        Parameters
        ----------
        prompt : str
            The input prompt to send to the model.

        Returns
        -------
        str
            The generated response text.
        """
        ...
```

---

## 4. The Extraction Ladder

This is the single decision procedure for "where does this code go?". Climb it only as
far as the evidence forces you to, and never further.

0. **At stage 1, everything stays in the one file.** Entry function, module-level
   helpers, and data classes. Rungs 1 to 6 do not apply until a gate in section 2.2 has
   fired.
1. **Keep ordinary workflow logic inline** in the entry point. Simple expressions, state
   updates, sequential control flow, persistence calls, external calls, and response
   construction stay inline.
2. **Extract a helper function** for a substantial, cohesive operation. At stages 1 and 2
   it is a module-level function in the same file (section 7.1). At stage 3 it is a
   nested function inside `execute`, capped at three (section 12.1).
3. **Create a Use Case** only when a gate in section 2.2 has fired: a second feature
   exists, or another part of the codebase calls the logic. An internal step that nothing
   else calls is not a Use Case, however substantial it is.
4. **Create an adapter** for **infrastructure you own** — a capability you control the
   semantics of and could swap — and only when a real boundary exists: implementation
   substitution, an external protocol or schema, credentials or connection lifecycle, or
   dependency-specific failure handling. I/O alone does not justify an adapter. Do not
   wrap a stable direct library call or local operation for architectural symmetry.
5. **Create a client** for an **interface to a service someone else owns**, internal or
   external. Rungs 4 and 5 are unordered: either may compose the other (section 11.6).
6. **Create a port** only when a second adapter implements the same functionality.

```python
# Good: a stable local operation remains in the feature that owns it
def main(settings_path: Path) -> ApplicationSettings:
    raw_settings = json.loads(settings_path.read_text(encoding="utf-8"))
    return ApplicationSettings.model_validate(raw_settings)


# Bad: an adapter adds indirection without a variable dependency or boundary
class LocalSettingsAdapter:
    def read(self, settings_path: Path) -> dict:
        return json.loads(settings_path.read_text(encoding="utf-8"))
```

Never climb the ladder merely because an entry point is long. **A long entry point with
a visible workflow is preferable to a short one whose workflow is scattered across
private methods.** Kesler decides whether a helper should become a class method.

---

## 5. Constraining State

Dynamic types like raw strings, bare dictionaries, and plain tuples create ambiguity.
Constraining the possible state of the programme through the type system eliminates
entire categories of bugs and makes the code self-documenting. This applies from the
first line of stage 1.

### 5.1. Strings and Numbers as Enums

Whenever a string or number represents a specific state, status code, or finite set of
values, define it as an `Enum`. When a string must be one of a known set but does not
warrant a full enum, use a `Literal`.

```python
import typing
from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class HttpStatusCode(int, Enum):
    OK = 200
    NOT_FOUND = 404
    INTERNAL_SERVER_ERROR = 500


LogLevel = typing.Literal["DEBUG", "INFO", "WARNING", "ERROR"]
```

### 5.2. Dictionaries as Data Classes

Never use naked dictionaries to pass data through the programme, and never return one
from an entry point. Use `dataclass` by default, `pydantic.BaseModel` when you need
contractual validation, or `TypedDict` when you only need the type signature without
object instantiation.

```python
from dataclasses import dataclass
from pydantic import BaseModel
from typing import TypedDict


# Default choice: dataclass
@dataclass
class ProductPrices:
    price: float
    discount: float = 0.0


# When you need validation on input boundaries
class ApiRequestPayload(BaseModel):
    user_id: int
    query: str
    max_results: int = 10


# When you only need the signature (e.g. for function parameters)
class FilterOptions(TypedDict):
    category: str
    min_price: float
    max_price: float
```

### 5.3. Tuples as Named Tuples

Replace bare tuples with `NamedTuple` to give each position a descriptive name.

```python
from typing import NamedTuple


class Coordinate(NamedTuple):
    latitude: float
    longitude: float


class ToolResult(NamedTuple):
    tool_name: str
    output_text: str


# Now field access is self-documenting
result = ToolResult(tool_name="search", output_text="found 3 items")
print(result.tool_name)  # instead of result[0]
```

---

## 6. Writing Data Classes

Data classes are the foundation of every programme and exist at every stage. They store
data, enforce business rules, and expose behaviour through methods, keeping orchestration
code simple and readable.

### 6.1. Domain Ownership and Canonical State

Create a data class only for a domain concept with an independent identity, lifecycle,
invariant, or boundary contract. Do not create models solely to bundle temporary values
passed between adjacent blocks of one method.

Keep one canonical owner for each fact. Do not duplicate statuses, summaries, or
parallel collections when they can be derived clearly from canonical state. Build DTOs
as consumer-specific projections of that state rather than copying internal
orchestration fields into the boundary contract.

```python
# Good: one domain object owns the fulfilment lifecycle
@dataclass
class OrderState:
    order_id: str
    reserved_items: list[OrderItem]
    dispatched_items: list[OrderItem]

    @property
    def is_complete(self) -> bool:
        return len(self.dispatched_items) == len(self.reserved_items)


class OrderResponse(BaseModel):
    order_id: str
    is_complete: bool


# Bad: temporary wrappers duplicate the same order facts
@dataclass
class OrderAssignment:
    order_id: str
    reserved_items: list[OrderItem]


@dataclass
class OrderProgress:
    order_id: str
    dispatched_items: list[OrderItem]
    is_complete: bool
```

### 6.2. Private by Default

Write all class methods as private by default using double-underscore (`__`) name
mangling. Only make a method public when an external consumer requires it. Private
instance properties also take the `__` prefix.

This rule applies only after behaviour has been shown to belong on the class. It does
**not** authorise extracting entry-point logic into class-private methods; apply section
4 first. The convention applies **only within class definitions** — never on
module-level variables, module-level helper functions, or local variables.

```python
from dataclasses import dataclass


@dataclass
class Account:
    __balance: float
    __currency: str
    __is_active: bool

    def __has_positive_balance(self) -> bool:
        return self.__balance > 0

    def is_valid(self) -> bool:
        return self.__is_active and self.__has_positive_balance()
```

### 6.3. Tell, Don't Ask

When client code calls multiple getters on the same object and then makes a decision
based on the results, that behaviour belongs inside the data class. Move the logic into
a method on the class so that consumers _tell_ the object what to do rather than
_asking_ for its internals.

Be suspicious whenever client code calls multiple methods on the same object,
especially multiple getters. Keep behaviour in the orchestration layer only when
multiple objects are involved.

```python
# Bad: the caller interrogates the object and decides
def check_account(account: Account) -> bool:
    return account.balance > 0 and account.is_active and account.currency == "GBP"


# Good: the object knows how to answer
@dataclass
class Account:
    __balance: float
    __currency: str
    __is_active: bool

    def is_valid_for_withdrawal(self, required_currency: str) -> bool:
        return (
            self.__is_active
            and self.__balance > 0
            and self.__currency == required_currency
        )
```

### 6.4. Business Rules Close to Data

Business rules — formatting constraints, validation logic, design decisions — are
defined as methods on the data class they modify. For classes inheriting from
`pydantic.BaseModel`, use validators.

```python
from pydantic import BaseModel, field_validator


class Invoice(BaseModel):
    reference: str
    amount_pence: int

    @field_validator("reference")
    @classmethod
    def reference_must_be_uppercase(cls, value: str) -> str:
        if value != value.upper():
            raise ValueError("Invoice reference must be uppercase")
        return value

    def formatted_amount(self) -> str:
        pounds = self.amount_pence / 100
        return f"£{pounds:,.2f}"
```

---

## 7. Writing Functions

### 7.1. Module-Level Helpers by Stage

At **stages 1 and 2** the code is function-shaped, and module-level helper functions in
the same file are allowed, uncapped, and *preferred* over nested functions. Give them
plain names with no leading underscore. Keep them in the same file as the `main` they
serve, immediately above it.

At **stage 3** the rules tighten: helpers become nested functions inside `execute`,
capped at three (section 12.1), and a standalone module-level helper is acceptable only
when it is genuinely reused across multiple classes or modules.

```python
# Good, stage 1 or 2: the helper sits beside the main it serves
def resolve_bash(env: dict[str, str]) -> str | None:
    ...


def main(run_input: AgentRunInput) -> None:
    bash = resolve_bash(os.environ.copy())


# Bad at any stage: a leading underscore on a module-level name
def _resolve_bash() -> str | None:
    ...
```

### 7.2. Descriptive Variable Names

Write variable names without abbreviations so that the code reads without comments.
The name should describe what the variable holds, not how it was computed. Name the
current domain fact rather than the calculation or temporary mechanism that produced
it: prefer `order_is_ready_for_dispatch` and `current_batch_number` over
`condition_result`, `calculated_index`, or `assignment_data`.

```python
# Good: reads like prose
def calculate_discounted_price(original_price: float, discount_percentage: float) -> float:
    discount_amount = original_price * (discount_percentage / 100)
    discounted_price = original_price - discount_amount
    return discounted_price


# Bad: requires mental parsing and inline comments
def calc_price(op: float, dp: float) -> float:
    da = op * (dp / 100)  # discount amount
    return op - da
```

### 7.3. Guard Clauses

When a function has multiple validation paths, use guard clauses at the top to exit
early. This avoids deep nesting and makes the happy path immediately visible. For
simple binary conditions, a single `if`/`else` is acceptable.

```python
def process_order(order: Order) -> str:
    if not order.is_valid():
        return "Order is invalid."

    if not order.has_items():
        return "Order has no items."

    logging.info("Processing order...")
    return "Order processed successfully."
```

### 7.4. Storing Complex Expressions in Variables

When a boolean, arithmetic, indexing, or lookup expression requires mental calculation,
store the result in a descriptively named variable. This turns opaque logic into
readable intent and gives subsequent code a domain fact it can reuse.

```python
def calculate_price_if_available(product: Product, quantity: int) -> float | None:
    product_is_available = (
        product.qty > 0
        and product.prices is not None
        and product.prices.price is not None
    )

    if product_is_available:
        total_price = product.prices.price * quantity
        return total_price

    logging.info("Product is not available or price is not set.")
    return None
```

Do not create a helper function whose body is a single-expression return when it has
only one caller. This holds at every stage. Assign the expression to a descriptively
named variable directly at the use site — the variable name does the job the function
name would have done, without the indirection.

```python
# Good: the expression remains at its single use site.
def main(recipients: list[str]) -> list[str]:
    # Validate each cleaned address while keeping the workflow visible.
    valid_recipients = []
    for recipient in recipients:
        clean_recipient = recipient.strip()
        is_valid_email = bool(
            re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean_recipient)
        )
        if not is_valid_email:
            raise ValueError(f"Invalid recipient email address: {clean_recipient}")
        valid_recipients.append(clean_recipient)
    return valid_recipients


# Bad: the private helper hides a simple expression used by one entry point.
class IndirectSendInvitationsUseCase:
    def execute(self, recipients: list[str]) -> list[str]:
        # Route every address through an unnecessary layer of indirection.
        return [recipient for recipient in recipients if self.__is_valid_email(recipient)]

    def __is_valid_email(self, value: str) -> bool:
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value))
```

### 7.5. Explicit State Progression

For ordered physical or workflow processes, prefer explicit counters and state
progression over repeatedly reconstructing state from a global index. Avoid modulo,
floor division, nested offsets, or equivalent arithmetic when named state variables
express the process more directly. Once a fact has been established during the current
iteration, reuse it instead of independently recalculating it later.

```python
# Good: the variables describe the production process directly
current_batch_number = 1
items_processed_in_batch = 0
buffer_steps_remaining = 0

for item in production_items:
    # Start a new batch when the buffer has been cleared.
    batch_is_being_processed = buffer_steps_remaining == 0
    if batch_is_being_processed:
        # Process the current item in the active batch.
        process(item, batch_number=current_batch_number)
        items_processed_in_batch += 1

        # Move to the next batch once the configured number of items has been processed.
        batch_is_complete = items_processed_in_batch == items_per_batch
        if batch_is_complete:
            current_batch_number += 1
            items_processed_in_batch = 0
            buffer_steps_remaining = configured_buffer_steps
    else:
        # Hold the current batch while the configured buffer period elapses.
        buffer_steps_remaining -= 1


# Bad: readers must repeatedly reconstruct the process from index arithmetic
for item_index, item in enumerate(production_items):
    position_in_cycle = item_index % (items_per_batch + configured_buffer_steps)
    batch_number = item_index // (items_per_batch + configured_buffer_steps) + 1
    if position_in_cycle < items_per_batch:
        process(item, batch_number=batch_number)
```

---

## 8. Comments, Logging, and Docstrings

### 8.1. Comments

Comments describe the _intent_ of a block before you write it. Write a comment
explaining what you are about to do, then write the code. If the code is
self-explanatory afterwards, the comment can stay as a section label or be removed.
Comments explain intent and domain progression; they do not translate individual lines.

Use **banner comments** only when an entry point implements a genuinely complex,
multipart workflow with several distinct domain stages. Do not add banners to short or
straightforward entry points. When banners are warranted, divide the entry point into
major domain stages and add an ordinary comment beneath each banner describing the
purpose of the whole block and the state it establishes.

```python
def main(order: Order) -> FulfilmentResult:
    # ============================ #
    #                              #
    #   VALIDATE ORDER CUSTOMER    #
    #                              #
    # ============================ #

    # Establish whether the customer and delivery address can fulfil the order.
    customer = customer_adapter.find_by_id(order.customer_id)
    address = address_adapter.validate(order.delivery_address)
    order_can_be_fulfilled = customer.is_active and address.is_serviceable
    if not order_can_be_fulfilled:
        return FulfilmentResult.rejected(order.id)

    # ============================ #
    #                              #
    #   RESERVE INVENTORY ITEMS    #
    #                              #
    # ============================ #

    # Reserve every item while retaining enough state to release partial work.
    reserved_items = []
    for item in order.items:
        reservation = inventory_adapter.reserve(
            product_id=item.product_id,
            quantity=item.quantity,
        )
        if reservation is None:
            inventory_adapter.release_all(reserved_items)
            return FulfilmentResult.awaiting_stock(order.id, item.product_id)
        reserved_items.append(reservation)

    # ============================ #
    #                              #
    #   AUTHORISE ORDER PAYMENT    #
    #                              #
    # ============================ #

    # Calculate the final amount and release inventory if payment is declined.
    subtotal = sum(item.total_price for item in reserved_items)
    delivery_charge = delivery_adapter.quote(address, reserved_items)
    amount_due = subtotal + delivery_charge
    payment = payment_adapter.authorise(customer, amount_due)
    if not payment.is_authorised:
        inventory_adapter.release_all(reserved_items)
        return FulfilmentResult.payment_declined(order.id)

    # ============================ #
    #                              #
    #   ARRANGE ORDER DISPATCH     #
    #                              #
    # ============================ #

    # Schedule the shipment and project the completed workflow into the response.
    shipment = delivery_adapter.schedule(address, reserved_items)
    return FulfilmentResult.confirmed(
        order_id=order.id,
        payment_id=payment.id,
        shipment_id=shipment.id,
        amount_due=amount_due,
    )
```

Banner dividers are also used at file scope when a file contains large groups of
related code — routes grouped by resource, or adapters grouped by client.

```python
# =========================#
#                          #
#   TICKTICK OAuth2        #
#                          #
# =========================#

# Handle the TickTick login and callback flow as one route group.

@app.get("/ticktick/login")
def ticktick_login(request: fastapi.Request):
    state = "some_random_state_string"
    request.session["state"] = state
    url = oauth_login.main(adapters.TickTickConnectorAdapter(), state)
    return responses.RedirectResponse(url=url)


# =======================#
#                        #
#   MENDELEY OAuth2      #
#                        #
# =======================#

# Handle the Mendeley login flow as a separate route group.

@app.get("/mendeley/login")
def mendeley_login(request: fastapi.Request):
    state = "some_random_state_string"
    request.session["state"] = state
    url = oauth_login.main(adapters.MendeleyConnectorAdapter(), state)
    return responses.RedirectResponse(url=url)
```

### 8.2. Logging

Logging belongs at system boundaries, not after every operation. Log at the entry and
exit of feature entry points, when crossing adapter boundaries (external calls,
database queries), and when errors or unexpected conditions occur.

```python
def enrich_user_profile(user: User, metadata: Metadata) -> EnrichedProfile:
    logging.info("Enriching profile for user %s", user.id)

    # Resolve the user's location from their raw coordinates.
    resolved_location = geocoder.reverse(metadata.latitude, metadata.longitude)

    # Fetch the user's historical preferences for personalisation.
    preference_history = preferences_adapter.fetch(user.id)

    # Build the enriched profile combining user, location, and preferences.
    enriched_profile = EnrichedProfile(
        user=user,
        location=resolved_location,
        preferences=preference_history,
    )

    logging.info("Enriched profile built for user %s: location=%s, preferences=%d",
                 user.id, resolved_location.city, len(preference_history))

    return enriched_profile
```

### 8.3. Docstrings

Use the NumPy format. Only add docstrings to functions that are not self-explanatory,
and never to boilerplate such as router endpoints. When a method implements an
interface, the docstring lives on the interface method only.

Include the `Side Effects` section only when the function has side effects such as
logging, printing, or writing to a database. Include the `Examples` section only for
complex functions.

```python
def add_numbers(param_1: int, param_2: int) -> str:
    """
    Add two numbers.

    Parameters
    ----------
    param_1 : int
        The first number to add.
    param_2 : int
        The second number to add.

    Returns
    -------
    str
        The sum of the two numbers as a string.

    Examples
    --------
    >>> add_numbers(2, 3)
    '5'
    >>> add_numbers(-1, 1)
    '0'

    Side Effects
    ------------
    This function triggers a process that logs the addition operation.
    """
    return str(param_1 + param_2)
```

---

## 9. Coding Style

### 9.1. PEP 8

Follow [PEP 8](https://pep8.org/) style guidelines throughout.

### 9.2. Imports

Import modules, not individual names. This keeps the origin of every symbol explicit
and avoids namespace collisions.

```python
import typing
import abc

import domain.entities as entities
import use_cases.schema as schema
import infrastructure.ports as ports


def foo(test: str) -> typing.Any:
    pass


class MyClass(abc.ABC):
    @abc.abstractmethod
    def my_method(self) -> None:
        pass
```

### 9.3. Type Casting

When you are confident a value has a specific type but the type checker cannot infer
it, use `typing.cast` to make the assertion explicit. Never use `# type: ignore` or
bare `Any` as a workaround — `typing.cast` documents the intent and keeps the type
system honest.

```python
import typing


# When a dict lookup returns a value you know is a specific type
raw_config = load_config()
timeout = typing.cast(int, raw_config["timeout"])

# When narrowing from a base class to a known subclass
event = get_next_event()
order_placed = typing.cast(OrderPlacedEvent, event)

# When a third-party library returns Any but the shape is known
response_data = typing.cast(dict[str, list[str]], api_client.fetch())
```

---

## 10. File Layout as It Grows

### 10.1. Stage 2: Features and Layer Files

When gate one fires, features move into `use_cases/` — one file per feature — and the
data classes leave the flat file for their own layer files.

```
src/project_name/
    main.py              # Entrypoint; constructs dependencies, calls features
    use_cases/
        feature_one.py   # One feature, entry point named main()
        feature_two.py
    domain.py            # Domain data classes (dao.py instead, when there is storage)
    dtos.py              # Contracts with the outside world that we own
    adapters.py          # Adapters for infrastructure you own
    clients.py           # Clients for services someone else owns
    schema.py            # Wire request/response shapes, owned by clients and adapters
    errors.py            # Custom exception classes
```

Add `adapters.py`, `clients.py`, and `errors.py` only when a rung of the ladder in
section 4 admits them — not pre-emptively because the tree above lists them.

### 10.2. When Files Outgrow Themselves

Convert them into folders with semantically grouped modules. `use_cases/` gains the
use-case-layer files — DTOs, ports, messages, errors — alongside its feature files.
Domain data classes and DAOs stay outside it. Wire schemas move to `infrastructure/`,
beside the clients and adapters that own them.

```
src/project_name/
    main.py
    domain/
        entities.py
        dao.py
        crud_dao.py
        assoc_dao.py
    use_cases/
        feature_one.py
        feature_two.py
        dtos.py
        ports.py
        messages.py
        errors.py
    infrastructure/
        schema.py
        routes/
            crud_routes.py
            auth_routes.py
            app.py
        adapters/
            sql_adapter.py
            nosql_adapter.py
            graph_adapter.py
            email_adapter.py
            auth.py
        clients/
            google_client.py
            aws_client.py
            redis_client.py
```

`ls use_cases/` should read as a list of things the application does. If it does not,
you have created use cases that are internal steps rather than features.

### 10.3. Scaling to Multiple Services

This structure scales recursively. When a subsection of a service needs to scale
independently, extract it into its own service following the same process: start from a
new `main.py` at stage 1 and let the gates promote it from there.

```
services/
    billing/
        src/billing/
            main.py
            use_cases/
            adapters.py
    notifications/
        src/notifications/
            main.py
            use_cases/
            adapters.py
```

---

## 11. Clients, Adapters, and Ports

These are the boundary classes. **They are not stage-gated** — a stage-2 feature
function takes them as parameters just as a stage-3 class takes them as constructor
fields. They are admitted by rungs 4 to 6 of the ladder in section 4, and by nothing
else.

The cut between an Adapter and a Client is **ownership**:

| | Owns it | Gets |
| --- | --- | --- |
| **Adapter** | You do. A capability you control the semantics of and could swap. | `S3ObjectStorageAdapter`, `PostgresOrderStoreAdapter`, `RedisCacheAdapter`, `Auth0AuthenticationAdapter` |
| **Client** | Someone else does. A service reached across an ownership boundary, internal or external. | `OrderClient`, `OpenAIClient`, `TikTokAdsClient`, `AWSClient` |

The test is *who owns this*, not *who supplies it*. The same technology appears as
either depending on its role: S3 holding your own documents is
`S3ObjectStorageAdapter`; S3 as the pipe to another team's published data is that
service's Client's business. Postgres holding your own tables is an Adapter; Postgres
that belongs to the order service is reached through `OrderClient`.

### 11.1. Adapters

An Adapter translates application-facing operations into calls on infrastructure you
own. It takes its dependencies and connection details in its constructor, and hides the
driver, the SDK, and the failure modes behind a method the rest of the programme can
read.

```python
class ChatModelAdapter:
    def __init__(self, client: OpenAIClient) -> None:
        self.client = client

    def generate(self, prompt: str, tools: list[Tool] | None = None) -> ChatResponse:
        # Convert the OpenAI response into the application-facing chat contract.
        response = self.client.chat_completions_create(prompt, tools)
        return ChatResponse.from_openai(response)
```

### 11.2. Clients

A Client sits on top of a service: it holds that service's coordinates as instance
properties and exposes methods that tell the service what you want from it.

A Client's coordinates — base URL, bucket name, table name, region — are set in its
constructor and are **public** properties. Section 6.2's private-by-default governs
methods and domain data classes; a Client's coordinates exist precisely so that a caller
or a test can override them.

The common case is a service reached over HTTP.

```python
# src/project_name/clients.py

import datetime

import requests

import project_name.adapters as adapters
import project_name.domain as domain
import project_name.schema as schema


class OrderClient:
    """The order service, reached over its HTTP API."""

    def __init__(self, base_url: str = "http://production-orderservice.internal") -> None:
        self.base_url = base_url

    def get_order(self, order_id: str) -> domain.Order:
        # GET /orders/{id} — the wire response is validated, then projected.
        response = requests.get(f"{self.base_url}/orders/{order_id}")
        response.raise_for_status()
        wire_order = schema.OrderResponse.model_validate(response.json())
        return domain.Order.from_wire(wire_order)
```

A service is just as often reached **through infrastructure** — a bucket it publishes
to, or a database it owns. The Client still represents the service; it composes the
Adapter it needs as its transport, and still holds the coordinates itself.

```python
class OrderExhaustClient:
    """The order service, reached through the object store it publishes to."""

    def __init__(
        self,
        object_storage: adapters.S3ObjectStorageAdapter,
        bucket_name: str = "order-service-exhaust",
    ) -> None:
        self.object_storage = object_storage
        self.bucket_name = bucket_name

    def list_orders(self, delivery_date: datetime.date) -> list[domain.Order]:
        # The exhaust file's shape belongs to the order service, not to us.
        key = f"{self.bucket_name}/{delivery_date.isoformat()}/orders.json"
        raw_exhaust = self.object_storage.read_object(key)
        exhaust = schema.OrderExhaustFile.model_validate_json(raw_exhaust)
        return [domain.Order.from_wire(record) for record in exhaust.records]
```

A Client should **translate and validate**. The moment it starts *deciding* anything —
which orders matter, what to do when one is missing — that logic belongs in the feature
that called it.

### 11.3. Mirroring Endpoints

Build a Client by mirroring the service's own surface, then extend it.

**Mirror only the useful subset, and ask which.** Look the endpoints up first — vendor
docs for an external service, the service's own codebase for an internal one — then
**ask Kesler which ones to mirror**. Do not mirror the whole API on principle: a method
with no caller is dead code by section 1.3 and an untested method by section 14.

**Mirrored methods are named 1:1 with their endpoint**, so no invented vocabulary appears
at the boundary.

| Endpoint | Method |
| --- | --- |
| `GET /orders/{id}` | `get_order(order_id)` |
| `GET /orders` | `list_orders(...)` |
| `POST /orders` | `create_order(...)` |
| `GET /healthcheck` | `healthcheck()` |

**Derived queries come second**, in domain language, after the mirrored ones. These are
the methods that make the Client useful rather than merely faithful:
filters, aggregations, and combinations the service does not expose directly.

```python
class OrderClient:
    def __init__(self, base_url: str = "http://production-orderservice.internal") -> None:
        self.base_url = base_url

    def get_order(self, order_id: str) -> domain.Order: ...

    def list_orders(self, delivery_date: datetime.date) -> list[domain.Order]: ...

    # Combine mirrored calls into the questions the application actually asks.
    def count_orders_by_factory(self, delivery_date: datetime.date) -> dict[str, int]:
        orders = self.list_orders(delivery_date)
        counts: dict[str, int] = {}
        for order in orders:
            counts[order.factory_id] = counts.get(order.factory_id, 0) + 1
        return counts
```

### 11.4. Request and Response Schemas

Every Client and every Adapter declares schemas for its request and its response — and
**both schemas stay inside the method**.

- The **request schema** models the payload actually sent on the wire. It is not the
  method's parameter type.
- The **response schema** models what the service or the database actually returns. It is
  not the method's return type.
- The method takes **domain values** and returns a type **you choose**. Callers never
  learn the wire shape, so a vendor changing their payload is invisible outside the
  Client.

```python
# Good: the wire shapes are built and validated inside; the return type is chosen.
def create_order(self, basket: domain.Basket) -> domain.Order:
    wire_request = schema.CreateOrderRequest(
        customer_id=basket.customer_id,
        line_items=[{"sku": line.sku, "qty": line.quantity} for line in basket.lines],
    )
    response = requests.post(
        f"{self.base_url}/orders", json=wire_request.model_dump(mode="json")
    )
    response.raise_for_status()
    wire_order = schema.OrderResponse.model_validate(response.json())
    return domain.Order.from_wire(wire_order)


# Bad: the wire request is the parameter and the wire response is the return value.
# Every caller is now coupled to the order service's payload format.
def create_order(self, request: schema.CreateOrderRequest) -> schema.OrderResponse:
    response = requests.post(
        f"{self.base_url}/orders", json=request.model_dump(mode="json")
    )
    response.raise_for_status()
    return schema.OrderResponse.model_validate(response.json())
```

Wire schemas live beside the clients and adapters that own them — `schema.py` at the flat
stage, `infrastructure/schema.py` at the folder stage (section 10). They are never bare
dictionaries; section 5.2 applies at the boundary most of all.

### 11.5. Ports

**Ports are adapter-only.** Create a port when a second **Adapter** implements the same
contract. A substitutable *service* provider therefore gets an Adapter over each Client,
and the port sits over the Adapters — `ChatModelPort` implemented by
`OpenAIChatModelAdapter(OpenAIClient)` and `AnthropicChatModelAdapter(AnthropicClient)`.

The port holds the single source of truth for the method signature and docstring;
adapters implement it without repeating the signature documentation. When only one
adapter exists, inject the adapter directly and write no port.

```python
import abc


class DocumentStoragePort(abc.ABC):
    @abc.abstractmethod
    def save(self, document: Document) -> StorageReceipt:
        """
        Save a document to durable storage.

        Parameters
        ----------
        document : Document
            The document to persist.

        Returns
        -------
        StorageReceipt
            The stable identifier and location of the persisted document.
        """
        ...


class S3DocumentStorageAdapter(DocumentStoragePort):
    def __init__(self, client: AWSClient) -> None:
        self.client = client

    def save(self, document):
        # Translate the document into the S3 request and receipt contract.
        response = self.client.put_object(document.key, document.content)
        return StorageReceipt.from_s3(response)


class GoogleCloudDocumentStorageAdapter(DocumentStoragePort):
    def __init__(self, client: GoogleCloudStorageClient) -> None:
        self.client = client

    def save(self, document):
        # Translate the document into the Google Cloud request and receipt contract.
        response = self.client.upload_blob(document.key, document.content)
        return StorageReceipt.from_google_cloud(response)
```

### 11.6. Imports Between Boundary Classes

**Composition runs in either direction.** A Client may import Adapters, when reaching the
service requires infrastructure. An Adapter may import Clients, when your own
infrastructure is reached through a vendor's service — `S3DocumentStorageAdapter` above
composes `AWSClient` for exactly that reason.

**Neither may import a use case.** The dependency always points away from the features.

**Avoid circular imports.** In practice this means imports run one way for any given pair
of modules. If you hit a genuine bidirectional dependency between a client and an
adapter, **ask Kesler** — do not reach for `typing.TYPE_CHECKING` or a local import to
work around it.

---

## 12. Writing Behavioural Classes

**This section applies at stage 3 only.** Do not write a behavioural class until gate
two in section 2.2 has fired — until the feature is called from a different part of the
codebase. Until then it is a function called `main`, and this section is not a template
for new code.

Once a class is warranted, it takes an `execute` method as its primary entry point.
Dependencies — adapters, clients, ports, or other Use Cases — move from function
parameters to constructor fields, which is what makes the promotion mechanical. Those
dependencies are covered in section 11, and reaching stage 3 does not by itself admit
any of them.

A Use Case may expose additional public methods when they represent closely related
operations on the same domain concept. All public methods on the class must share the
same dependencies and belong to the same logical feature.

### 12.1. Local Functions Inside Entry Points

Keep orchestration inside `execute()`, or inside the established public entry point.

A public entry point may contain **at most three nested functions**, with at most one
per banner section. These are maximums, not targets. A single-use nested function is
acceptable when it names a substantial, cohesive operation and materially improves the
readability of that section.

The entry point calls each nested function directly; nested functions do not call one
another. If a fourth extraction appears useful, keep that logic inline. The entry point
must continue to show the workflow's control flow, state progression, external
interactions, and final projection.

At this stage, standalone module-level helper functions are acceptable only when
genuinely reused across multiple classes or modules. Do not promote a nested function to
a `__private` class method for aesthetic reasons.

```python
class ToolCallingUseCase:
    def __init__(
        self,
        chat_model_adapter: ChatModelAdapter,
        tool_registry: ToolRegistryAdapter,
    ) -> None:
        self.chat_model_adapter = chat_model_adapter
        self.tool_registry = tool_registry

    def execute(self, run_input: AgentRunInput) -> AgentRunSummary:
        logging.info("Starting tool calling for prompt: %s", run_input.prompt)

        # Run the bounded tool-calling loop and retain each completed result.
        def call_tools(tools: list[Tool]) -> list[ToolResult]:
            results = []
            for step in range(run_input.max_steps):
                response = self.chat_model_adapter.generate(run_input.prompt, tools)
                if response.has_tool_call():
                    result = self.tool_registry.invoke(response.tool_call)
                    results.append(result)
                    logging.info("Step %d: called %s", step, result.tool_name)
                else:
                    break
            return results

        available_tools = self.tool_registry.list_tools()
        logging.info("Found %d available tools", len(available_tools))

        raw_results = call_tools(available_tools)
        cleaned_outputs = [result.output_text.strip() for result in raw_results]
        logging.info("Cleaned %d tool outputs", len(cleaned_outputs))

        return AgentRunSummary(
            prompt=run_input.prompt,
            cleaned_outputs=cleaned_outputs,
            status=RunStatus.COMPLETE,
        )
```

### 12.2. Composing Use Cases

Because each Use Case is a class with injected dependencies, independently meaningful
capabilities compose naturally. A higher-level Use Case may call a lower-level one when
the lower-level entry point accepts meaningful application input and returns a complete
result without depending on transient internal state owned by its caller.

```python
class AgenticRunUseCase:
    def __init__(
        self,
        tool_calling: ToolCallingUseCase,
        structured_output: StructuredOutputUseCase,
    ) -> None:
        self.tool_calling = tool_calling
        self.structured_output = structured_output

    def execute(self, run_input: AgentRunInput) -> AgenticRunResult:
        tool_results = self.tool_calling.execute(run_input)
        logging.info("Tool calling complete with %d outputs", len(tool_results.cleaned_outputs))

        structured_result = self.structured_output.execute(
            StructuredOutputInput(raw_text="\n".join(tool_results.cleaned_outputs))
        )
        logging.info("Structured output parsing complete")

        return AgenticRunResult(
            tool_summary=tool_results,
            parsed_output=structured_result,
        )
```

---

## 13. Adding a New Feature: Outside-In

This section applies from stage 3 onward. A route or message handler is itself another
part of the codebase calling the logic, so by the time you are designing one, gate two
has already fired and the feature is class-shaped.

Start from the end in mind. Design the **route or message handler** first (how the
feature is triggered and what the response looks like), then the **DTO** (what data
crosses the boundary), then the **use case** (what logic orchestrates the feature), then
the **adapter** (what infrastructure is needed).

This outside-in approach gives you TDD-like benefits: you define the desired interface
before building the internals, which prevents over-engineering and keeps the
implementation focused on what the consumer actually needs. Reuse existing layers where
they are available.

```python
@app.post("/refunds")
def create_refund(request: RefundRequest) -> RefundConfirmation:
    return ProcessRefundUseCase(
        payment_adapter=StripePaymentAdapter()
    ).execute(request)


class RefundRequest(BaseModel):
    order_id: str
    reason: str


class ProcessRefundUseCase:
    def __init__(self, payment_adapter: StripePaymentAdapter) -> None:
        self.payment_adapter = payment_adapter

    def execute(self, refund_request: RefundRequest) -> RefundConfirmation: ...


class StripePaymentAdapter:
    def refund(self, transaction_id: str, amount_pence: int) -> RefundResult: ...
```

---

## 14. Testing Strategy

Quick code in `scripts/` is exempt from automated tests. Do not write or run tests
for it. Move maintained product features into the appropriate source folder before
applying this testing strategy. Notebook and experiment code have no folder-based
test exemption.

**Every feature gets a test, and every adapter and client gets a test** — not just when
a change happens to touch one. Smoke tests and regression tests are their own categories
on top of that. Prioritise tests at the public interfaces between layers.

Test a domain data class directly when it owns non-trivial business rules, invariants,
or validation that are clearer to exercise on the object itself. Do not test passive
field storage, ports, or framework boilerplate in isolation.

Always add mocks and test infrastructure where possible, such as a test database, so
features and adapters can be exercised without hitting real external systems.

Because a client's wire schemas are internal to its methods (section 11.4), a client
test asserts the **chosen return type**, never the wire response. Fake the layer beneath
the client — the adapter it composes, or the HTTP call itself — not the schema.

A client's coordinates default to production (section 11.2), so **every test passes an
explicit base URL, bucket, or fake adapter**. Never let a test fall through to the
default.

**Testing by stage.** The shape of the test follows the shape of the code:

- **Stage 1**: call `main()` directly, and call its module-level helpers directly where
  they own non-trivial logic.
- **Stage 2**: call the feature's `main()` and pass fakes in as the dependency
  parameters. This is why those dependencies are parameters rather than constructed
  inside the function.
- **Stage 3**: inject mocks through the constructor and call `execute()`.

Needing a test never fires a promotion gate (section 2.2). If a test is awkward to
write, pass a fake in as a parameter — do not create a class to make the test tidier.

```
tests/
    conftest.py             # Shared Fake*/Mock* test doubles used by 2+ test files
    test_use_cases.py       # Tests for feature entry points
    test_adapters.py        # Tests for adapter integration
    test_routers.py         # Tests for API endpoints
    test_repo_hygiene.py    # Smoke tests: repo-wide invariants
    test_bugs.py            # Regression tests for fixed bugs
```

### 14.1. Testing Features

Pass fakes or mocks for the dependencies so the feature runs in isolation.

```python
# Stage 2: dependencies are parameters
def test_tool_calling_returns_complete_summary():
    summary = tool_calling.main(
        domain.AgentRunInput(prompt="find notes", max_steps=1),
        FakeChatModelAdapter(responses=["search result"]),
        FakeToolRegistryAdapter(tools=[search_tool]),
    )

    assert summary.status == domain.RunStatus.COMPLETE
    assert len(summary.cleaned_outputs) == 1


# Stage 3: dependencies are constructor fields
def test_tool_calling_use_case_returns_complete_summary():
    use_case = ToolCallingUseCase(
        chat_model_adapter=MockChatModelAdapter(responses=["search result"]),
        tool_registry=MockToolRegistryAdapter(tools=[search_tool]),
    )

    result = use_case.execute(AgentRunInput(prompt="find notes", max_steps=1))

    assert result.status == RunStatus.COMPLETE
    assert len(result.cleaned_outputs) == 1
```

### 14.2. Regression Tests for Bugs

Whenever a bug is discovered, write a test that reproduces it in `test_bugs.py`. Fix
the bug. Keep the test permanently to prevent regression.

```python
# tests/test_bugs.py

def test_empty_tool_result_does_not_crash():
    """Regression: empty output_text caused IndexError in strip pipeline."""
    result = ToolResult(tool_name="empty_tool", output_text="")
    cleaned = result.output_text.strip()
    assert cleaned == ""
```

### 14.3. Smoke Tests

A smoke test asserts a repo-wide invariant rather than one component's behaviour — the
kind of thing that silently rots (a renamed folder nothing reads from anymore, a config
drifting out of sync) rather than failing loudly on its own. Keep these in
`test_repo_hygiene.py`.

```python
# tests/test_repo_hygiene.py

def test_agent_state_folder_exists() -> None:
    assert (ROOT / "@db").is_dir()


def test_no_stray_db_folder() -> None:
    """Agent state belongs in `@db`, never in a folder named `db`.

    Dropping the leading at-sign silently creates a `db` folder that nothing
    ever reads, so accumulated state is lost until someone notices. This test
    makes that mistake fail loudly.
    """
    stray = ROOT / "db"
    assert not stray.exists()
```

### 14.4. Shared Test Doubles

A `Fake*`/`Mock*` class needed by two or more test files belongs in `conftest.py`, not
copy-pasted into each one. A test double used by only one file stays local to that file
— do not pre-emptively centralise something nothing else needs yet.

```python
# tests/conftest.py

class FakeResponse:
    def __init__(self, json_data: dict, status_code: int = 200) -> None:
        self.__json_data = json_data
        self.status_code = status_code

    def json(self) -> dict:
        return self.__json_data
```

---

## 15. Before You Finish

Check the work against the rules that get broken most often. The first three are the
ones that matter most.

- **Are you at the right stage?** Has a gate in section 2.2 actually fired, or did you
  write a behavioural class because it felt tidy? Length is not a gate. Needing a test
  is not a gate.
- **Does every file in `use_cases/` name something the application actually does**, in
  the language a user or an operator would use? If one names an internal step, it should
  be a helper function in the feature that uses it.
- **Did you climb the extraction ladder further than the evidence forced you to?** No
  adapter without a real boundary, no port with one implementation, no `__private`
  method to shorten an entry point (section 4).
- **Is each new boundary class on the right side of the cut?** Infrastructure you own is
  an Adapter; a service someone else owns is a Client. The test is who owns it, not who
  supplies it (section 11).
- **Do clients and adapters declare wire schemas, kept out of their signatures?** The
  method takes domain values and returns a type you chose (section 11.4).
- **Did you ask which endpoints to mirror**, rather than mirroring the whole API or
  guessing at a subset? (section 11.3)
- **Any circular import between a client and an adapter?** Ask rather than working around
  it (section 11.6).
- **Did you read the neighbouring files?** The codebase wins on codebase-specific
  details (section 1.1).
- **Is the workflow still visible in the entry point?** Long and readable beats short
  and scattered (section 12.1).
- **Any bare dicts, bare tuples, or magic strings left?** Including as a return type
  (section 5).
- **Any behaviour that should have moved onto the data class?** Multiple getters on one
  object is the tell (section 6.3).
- **Any generic class names** — handler, manager, service, processor? Any `UseCase`
  suffix on something that is not yet a stage-3 class? (section 3.1)
- **Any leading underscores at module level?** (section 3.1)
- **Does every feature, adapter, and client have a test?** Every fixed bug a regression
  test? (section 14)
- **Did you delete the old code**, rather than leaving a shim or alias? (section 1.3)

## 16. Configs and Credentials

This is the default `configs.py`/`credentials.py` pair for a project that reads
environment-backed settings and devOS-stored secrets. It is distinct from section
1.3's module-level constants for one-off runnable scripts — use this section for a
project's actual settings/secrets loading, section 1.3 for ad-hoc script parameters.

The canonical, reusable copy lives at
`automation_engine/wiki/Snippets/python/config/configs.py` and
`automation_engine/wiki/Snippets/python/config/credentials.py`. Follow [[Snippets]]
to install the complete bundle, including adapted offline tests, dependencies and
setup instructions. This project's infrastructure config pair is a worked example
of the architecture adapted to its environment variables and folder constants.

### 16.1. `credentials.py`: load the devOS bundle, never edit per project

Copy `credentials.py` byte-for-byte into every new project. It is infrastructure
this owns collectively across projects, not something to fork or customise:

- `LoadCredentialsUseCase.from_environment()` builds a Redis client from the
  `devos_redis_*` bootstrap variables (`devos_redis_url`, or the
  host/port/username/password/db/ssl set), resolves the project's credential
  bundle name (`devos_project_name` env var, else the git remote name, else the
  directory name, each with a warning), and reads the JSON object stored at
  `devos:projects:<name>` in Redis.
- `.execute()` overlays that bundle's keys onto `os.environ`, skipping any key
  that is `null` in the bundle (falls back to whatever the shell/`.env` already
  set) or that starts with the reserved `devos_` prefix.
- With no Redis reachable, or no bundle stored, it logs a warning and leaves the
  environment as `.env`/the shell set it — the same file works with or without
  devOS configured for that project.

### 16.2. `configs.py`: bootstrap, one settings object, per-integration Enums

```python
import dotenv
from . import credentials

dotenv.load_dotenv()
credentials.LoadCredentialsUseCase.from_environment().execute()
```

This ordering is load-bearing: overlay the bundle before constructing the
`pydantic_settings.BaseSettings` object, otherwise Pydantic snapshots the
environment as it was before the bundle landed.

- One `EnvironmentVariables(BaseSettings)` class lists every environment variable
  the project reads, typed, with `pydantic.SecretStr` for anything secret and a
  plain default for everything else. `.env` itself only needs the `devos_redis_*`
  bootstrap lines — every other value lives in the Redis bundle.
- A shared `unwrap_secret`/`_unwrap_secret` helper is the only place
  `.get_secret_value()` is called.
- Group related settings into small `enum.Enum` classes per integration (e.g.
  `TickTickCreds`, `RedisConfigsCreds`), each member built from the one settings
  instance, unwrapping secrets through that helper. Call sites read
  `TickTickCreds.CLIENT_ID.value`, never the raw settings object or `os.environ`
  directly.
- Non-secret configuration that isn't a per-integration credential (folder paths,
  constants, feature flags) stays as plain module-level values in the same file,
  not forced into the Enum-per-credential shape.

### 16.3. Adding or changing a secret

Store and retrieve values with the devOS CLI (`dev set secrets <KEY> <VALUE>` /
`dev get secrets <KEY>`, see the Confidential Information reference), never by
hand-editing `.env` with a real value or committing one. Add the field to
`EnvironmentVariables` with the right type, then add or extend its `Enum`.

## Rationale
