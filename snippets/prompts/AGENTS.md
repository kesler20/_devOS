Prefer minimal, localised diffs that are easy to review. Reuse existing components and state patterns as much as possible before creating new ones.

# Overall Programming

## 0. Before Planning a Change

Before proposing or making any specific change, read this guide, then look at the
codebase itself: the file being changed and its neighbouring files in the same
use case / adapter / domain folder (and the folders it composes with). This guide
sets the general philosophy; the codebase already in front of you is the source of
truth for how that philosophy has been instantiated here, and it wins whenever the
two disagree on a codebase-specific detail — an existing name for a domain concept,
an established file layout, the shape of an existing data class.

Concretely, before finalising a plan:

- Identify the existing use cases, data classes, and adapters that already model
  the domain the change touches. Reuse or extend them instead of introducing a
  parallel concept under a new name.
- Check how neighbouring files in the same domain area name things, structure
  classes, and split responsibilities, and match that pattern rather than the
  nearest example in this guide.
- For a change large enough that this exploration would consume significant
  context, spin up a sub-agent (or equivalent parallel research step) to read the
  surrounding files and report back the conventions in use, instead of skipping
  the check to save time.

## 1. Overview

This guide defines a programming philosophy built on two core ideas: **data classes** provide encapsulation and **behavioural classes** provide orchestration. Everything else flows from this distinction.

The approach is infrastructure and programming language agnostic. It applies equally to web services, mobile applications, desktop software, and embedded systems. The delivery mechanism — whether REST, WebSocket, MQTT, or a native event loop — is an infrastructure detail that never leaks into the core logic.

### 1.1. Core Abstractions

Every programme is composed from a small vocabulary of building blocks.

**Data classes** store data using fields and expose behaviour through methods that operate on that data. They are the nouns of the system: `AgentRunInput`, `Product`, `OrderStatus`.

**Behavioural classes, or Use Cases,** orchestrate the data passing between data classes. Each represents an independently meaningful application capability that a caller could request and receive a complete outcome from. A Use Case is not an internal workflow step extracted merely to shorten another Use Case. It need not be reused to qualify. Use Cases are named in the language of the problem domain and are the verbs of the system: `ToolCallingUseCase`, `StructuredOutputUseCase`, `StreamingResponseUseCase`.

**Adapters** translate between application language and a genuine external or variable dependency. They are justified by implementation substitution, protocol or schema translation, credentials or connection lifecycle, or dependency-specific failure handling. They interact with third-party services, databases, legacy systems, or other infrastructure boundaries: `TickTickBacklogAdapter`, `SQLDbAdapter`.

**Clients** wrap external libraries or services and manage low-level credentials, connections, and SDK details. Adapters expose application-specific infrastructure operations and may compose provider-specific clients: `OpenAIClient`, `AnthropicClient`, `RedisClient`.

**Ports/Interfaces** define contracts between Use Cases and adapters. They only exist when more than one adapter implements the same piece of infrastructure, otherwise the use case should interact directly with the adapter.

**Schemas and DTOs** define contracts at system boundaries. **DAOs** (Data Access Objects) represent the shape of objects persisted to storage (SQL rows, NoSQL documents, graph nodes). **DTOs** (Data Transfer Objects) are service-specific contracts with the outside world — the objects your API sends and receives, such as `CreateUserResponse` or `RefundRequest`. **Schemas** are third-party or infrastructure data transfer objects — the shapes dictated by external libraries, APIs, or protocols that you do not control, such as a Stripe webhook payload or an OAuth token response.

**DAOs** (Data Access Objects) represent entities that are persisted to storage.

### 1.2. Mental Model

We subscribe to **abstraction**, **composition**, and **encapsulation**. We do not use **implementation inheritance** — inheriting from a concrete class to reuse its code or to override its behaviour. The only acceptable reason to inherit from a class is to gain **framework behaviour**: inheriting from `BaseModel` for validation, `ABC` for defining interfaces, `DeclarativeBase` for ORM mapping, or similar framework-provided base classes. This means inheriting from an abstract port like `ChatModelPort(ABC)` to implement a concrete adapter is permitted — that is interface conformance, not implementation reuse. What is not permitted is creating a `BaseAdapter` with shared logic and having `PostgresAdapter(BaseAdapter)` and `MongoAdapter(BaseAdapter)` inherit from it. Use composition to share logic between concrete classes instead.

### 1.3. How Development Begins

Every programme starts in a single `main.py` file. Write the core logic directly inside a `main` function. As the routine takes shape, gradually refactor by extracting data classes that you identify within the routine. Once all data classes are identified, add methods for encapsulation following the tell-don't-ask principle. Then organise the remaining orchestration into behavioural classes by converting the `main` function into an `execute` method on a use case class.

```python
# src/agent_run/main.py
# Show how a small program evolves from one readable end-to-end routine.
import logging
from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple


logging.basicConfig(level=logging.INFO)


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


def main() -> None:
    run_input = AgentRunInput(prompt="Summarise the meeting notes", max_steps=3)
    logging.info("Created AgentRunInput: prompt=%s max_steps=%s", run_input.prompt, run_input.max_steps)

    raw_results = [
        ToolResult(tool_name="search_notes", output_text="  Notes about Q1 planning  "),
        ToolResult(tool_name="extract_actions", output_text="  1) send deck  2) confirm budget "),
    ]
    logging.info("Collected %s raw tool results", len(raw_results))

    cleaned_outputs = [result.output_text.strip() for result in raw_results]
    logging.info("Cleaned tool outputs: %s", cleaned_outputs)

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

### 1.4. Naming Conventions

Behavioural classes must be named using the abstractions provided by this guide. The only permitted names are **Adapter**, **UseCase**, and **Client**. Generic names like `handler`, `platform`, `processor`, `engine`, `executor`, `manager`, and `service` are not allowed. Use cases represent features of the software and should use language that is understandable in the problem domain.

```python
# Compare domain-specific names with prohibited generic abstractions.
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
comments after a persona, or after the language used to request the change, when
that term does not itself describe a domain concept. Follow the naming
conventions already used in the codebase instead, consistent with how it already
models and represents the domain.

**No leading underscores on module-level names.** Constants, module-level variables, and any name defined at the top of a file must never begin with `_`. Use plain `UPPER_CASE` for constants. The `__` prefix is only valid inside a class body for private methods and private instance attributes (see section 4.2).

```python
# Compare valid module-level names with invalid private-style prefixes.
# Good
ALLOWED_TOOLS = "Read,Write,Edit"
CLAUDE_WORKING_DIRECTORY = Path(configs.PROTOCOL_FOLDER) / "claude"

# Bad
_ALLOWED_TOOLS = "Read,Write,Edit"
_CLAUDE_WORKING_DIRECTORY = Path(configs.PROTOCOL_FOLDER) / "claude"
```

**Execute-local helper logic stays inside the public entry point.** If logic serves only one Use Case entry point, keep it inline or define it as a nested function subject to section 3.5. Do not promote it to a `__private_method` merely because the entry point is long. Kesler decides whether a nested function should become a class method. Standalone module-level helper functions are only acceptable when they are genuinely reused across multiple classes or modules.

```python
# Keep entry-point-specific behaviour local to the entry point.
# Good: helper remains local to the entry point that uses it
class AgenticWorkflowUseCase:
    def execute(self) -> None:
        def resolve_bash(env: dict[str, str]) -> str | None:
            ...

        bash = resolve_bash(os.environ.copy())


# Bad: helper exposed at module level just for one entry point
def _resolve_bash() -> str | None:
    ...

class AgenticWorkflowUseCase:
    def execute(self) -> None:
        bash = _resolve_bash()
```

---

## 2. Constraining State

Dynamic types like raw strings, bare dictionaries, and plain tuples create ambiguity. Constraining the possible state of the programme through the type system eliminates entire categories of bugs and makes the code self-documenting.

### 2.1. Strings and Numbers as Enums

Whenever a string or number represents a specific state, status code, or finite set of values, define it as an `Enum`. This groups related properties together, provides IDE autocomplete, and prevents invalid values at compile time.

```python
# Constrain domain states and protocol codes to explicit finite sets.
from enum import Enum


class OrderStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class HttpStatusCode(int, Enum):
    OK = 200
    NOT_FOUND = 404
    INTERNAL_SERVER_ERROR = 500
```

When a string must be one of a known set but does not warrant a full enum, use a `Literal` type.

```python
# Constrain a lightweight string setting without introducing a full enum.
import typing

LogLevel = typing.Literal["DEBUG", "INFO", "WARNING", "ERROR"]
```

### 2.2. Dictionaries as Data Classes

Never use naked dictionaries to pass data through the programme. Use `dataclass` by default, `pydantic.BaseModel` when you need contractual validation, or `TypedDict` when you only need the type signature without object instantiation.

```python
# Compare the three supported ways to replace ambiguous dictionaries.
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

### 2.3. Tuples as Named Tuples

Replace bare tuples with `NamedTuple` to give each position a descriptive name.

```python
# Replace positional tuples with named result fields.
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

## 3. Writing Functions

### 3.1. Comments and Logging

**Comments** describe the *intent* of a block before you write it. Write a comment explaining what you are about to do, then write the code. If the code is self-explanatory after you have written it, the comment can stay as a section label or be removed.

Every executable code example in this guide includes an ordinary comment that explains the example's purpose or the intent of its main block. Labels such as `Good` and `Bad` may supplement that comment but do not replace it.

Use banner comments only when a Use Case entry point implements a genuinely complex, multipart workflow with several distinct domain stages. Do not add banners to short or straightforward `execute()` methods. When banners are warranted, divide the entry point into major domain stages and add an ordinary comment beneath each banner describing the purpose of the whole block and the state it establishes. Comments should explain intent and domain progression, not translate individual lines. A long entry point with a visible workflow is preferable to a short one whose workflow is scattered across private methods.

```python
# Coordinate validation, stock, payment, and dispatch as one multipart workflow.
class FulfilOrderUseCase:
    def execute(self, order: Order) -> FulfilmentResult:
        # ============================ #
        #                              #
        #   VALIDATE ORDER CUSTOMER    #
        #                              #
        # ============================ #

        # Establish whether the customer and delivery address can fulfil the order.
        customer = self.customer_adapter.find_by_id(order.customer_id)
        address = self.address_adapter.validate(order.delivery_address)
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
            reservation = self.inventory_adapter.reserve(
                product_id=item.product_id,
                quantity=item.quantity,
            )
            if reservation is None:
                self.inventory_adapter.release_all(reserved_items)
                return FulfilmentResult.awaiting_stock(order.id, item.product_id)
            reserved_items.append(reservation)

        # ============================ #
        #                              #
        #   AUTHORISE ORDER PAYMENT    #
        #                              #
        # ============================ #

        # Calculate the final amount and release inventory if payment is declined.
        subtotal = sum(item.total_price for item in reserved_items)
        delivery_charge = self.delivery_adapter.quote(address, reserved_items)
        amount_due = subtotal + delivery_charge
        payment = self.payment_adapter.authorise(customer, amount_due)
        if not payment.is_authorised:
            self.inventory_adapter.release_all(reserved_items)
            return FulfilmentResult.payment_declined(order.id)

        # ============================ #
        #                              #
        #   ARRANGE ORDER DISPATCH     #
        #                              #
        # ============================ #

        # Schedule the shipment and project the completed workflow into the response.
        shipment = self.delivery_adapter.schedule(address, reserved_items)
        return FulfilmentResult.confirmed(
            order_id=order.id,
            payment_id=payment.id,
            shipment_id=shipment.id,
            amount_due=amount_due,
        )
```

**Logging** belongs at system boundaries, not after every operation. Log at the entry and exit of use case `execute` methods, when crossing adapter boundaries (external calls, database queries), and when errors or unexpected conditions occur. 


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


### 3.2. Descriptive Variable Names

Write variable names without abbreviations so that the code reads without comments. The name should describe what the variable holds, not how it was computed.

Name the current domain fact rather than the calculation or temporary mechanism that produced it. Prefer `order_is_ready_for_dispatch` and `current_batch_number` over names such as `condition_result`, `calculated_index`, or `assignment_data`.

```python
# Compare descriptive domain names with abbreviated equivalents.
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

### 3.3. Guard Clauses

When a function has multiple validation paths, use guard clauses at the top to exit early. This avoids deep nesting and makes the happy path immediately visible. For simple binary conditions, a single `if`/`else` is acceptable.

```python
# Keep invalid paths at the top so the successful workflow remains visible.
def process_order(order: Order) -> str:
    if not order.is_valid():
        return "Order is invalid."

    if not order.has_items():
        return "Order has no items."

    logging.info("Processing order...")
    return "Order processed successfully."
```

### 3.4. Storing Complex Expressions in Variables

When a boolean, arithmetic, indexing, or lookup expression requires mental calculation, store the result in a descriptively named variable. This turns opaque logic into readable intent and gives subsequent code a domain fact it can reuse.

```python
# Name availability once and reuse it when deciding whether to calculate a price.
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

For ordered physical or workflow processes, prefer explicit counters and state progression over repeatedly reconstructing state from a global index. Avoid modulo, floor division, nested offsets, or equivalent arithmetic when named state variables express the process more directly. Once a fact has been established during the current iteration, reuse it instead of independently recalculating it later.

```python
# Compare explicit production state with repeated index arithmetic.
# Good: the variables describe the production process directly
current_batch_number = 1
items_processed_in_batch = 0
buffer_steps_remaining = 0

for item in production_items:
    batch_is_being_processed = buffer_steps_remaining == 0
    if batch_is_being_processed:
        process(item, batch_number=current_batch_number)
        items_processed_in_batch += 1

        batch_is_complete = items_processed_in_batch == items_per_batch
        if batch_is_complete:
            current_batch_number += 1
            items_processed_in_batch = 0
            buffer_steps_remaining = configured_buffer_steps
    else:
        buffer_steps_remaining -= 1


# Bad: readers must repeatedly reconstruct the process from index arithmetic
for item_index, item in enumerate(production_items):
    position_in_cycle = item_index % (items_per_batch + configured_buffer_steps)
    batch_number = item_index // (items_per_batch + configured_buffer_steps) + 1
    if position_in_cycle < items_per_batch:
        process(item, batch_number=batch_number)
```

Do not create a helper function whose body is a single-expression return when it has only one caller. Assign the expression to a descriptively named variable directly in the code that uses it — the variable name does the job the function name would have done, without the indirection.

```python
# Compare an inline named expression with a single-use private helper.
# Good: the expression remains at its single use site.
class SendInvitationsUseCase:
    def execute(self, recipients: list[str]) -> list[str]:
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

### 3.5. Local Functions Inside Use-Case Entry Points

Keep use-case orchestration inside `execute()`, or inside the established public entry point for the Use Case. A long, readable entry point is always preferable to decomposition into class-private methods. Use the banner and intent-comment structure from section 3.1 only for genuinely complex, multipart workflows. Leave short and straightforward entry points unsectioned.

A public entry point may contain at most three nested functions, with at most one nested function in each banner section. These are maximums, not targets. A single-use nested function is acceptable when it names a substantial, cohesive operation and materially improves the readability of that section.

Keep simple expressions, state updates, sequential control flow, persistence calls, external calls, and response construction inline unless a nested function clearly improves the containing section. The public entry point must continue to show the workflow's control flow, state progression, external interactions, and final projection.

The public entry point calls each nested function directly. Nested functions do not call one another. If a fourth extraction appears useful, keep that logic inline. Do not promote nested functions to `__private` class methods for aesthetic reasons. Kesler decides whether any nested function should become a class method.

---

## 4. Writing Data Classes

Data classes are the foundation of every programme. They store data, enforce business rules, and expose behaviour through methods keeping orchestration code simple and readable.

### 4.1. Domain Ownership and Canonical State

Create a data class only for a domain concept with an independent identity, lifecycle, invariant, or boundary contract. Do not create models solely to bundle temporary values passed between adjacent blocks of one method.

Keep one canonical owner for each fact. Do not duplicate statuses, summaries, or parallel collections when they can be derived clearly from canonical state. Build DTOs as consumer-specific projections of that state rather than copying internal orchestration fields into the boundary contract.

```python
# Compare one canonical order lifecycle with duplicated temporary wrappers.
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

### 4.2. Private by Default

Write all class methods as private by default using double-underscore (`__`) name mangling. Only make a method public when it is required by an external consumer. Private instance properties are also declared with `__` prefix.

This rule applies only after behaviour has been shown to belong on the class. It does not authorise extracting execute-local logic into class-private methods. Apply section 3.5 first.

This convention applies **only within class definitions**. Never use underscore prefixes on module-level variables, standalone functions, or local variables inside functions.

```python
# Keep internal state and supporting behaviour private to the domain object.
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

### 4.3. Tell, Don't Ask

When client code calls multiple getters on the same object and then makes a decision based on the results, that behaviour belongs inside the data class. Move the logic into a method on the class so that consumers *tell* the object what to do rather than *asking* for its internals.

```python
# Compare caller-owned decisions with behaviour owned by the domain object.
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

A good rule of thumb: be suspicious when client code calls multiple methods on the same object, especially multiple getters. That is often a sign that behaviour belongs inside the data class. Keep behaviour in the orchestration layer only when multiple objects are involved.

### 4.4. Business Rules Close to Data

Business rules like formatting constraints, validation logic, and design decisions, should be defined as methods on the data class they modify. For classes inheriting from `pydantic.BaseModel`, use validators.

```python
# Keep invoice validation and presentation rules beside the invoice data.
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

### 4.5. Inheritance Rules for Data Classes

Data classes inherit from framework base classes only to gain specific behaviour, never for code reuse.

```python
# Match each data class to the framework behaviour it genuinely requires.
import abc
from dataclasses import dataclass
from pydantic import BaseModel


# DAOs inherit from ORMs when persisted to SQL
import sqlalchemy.orm as orm

class UserDAO(orm.DeclarativeBase):
    __tablename__ = "users"
    id: int
    name: str


# DAOs inherit from pydantic when persisted to NoSQL or JSON
class DocumentDAO(BaseModel):
    document_id: str
    content: dict


# DAOs use plain dataclass when not persisted
@dataclass
class TransientResult:
    query: str
    matches: list[str]


# Messages and events inherit from pydantic
class OrderPlacedEvent(BaseModel):
    order_id: str
    customer_id: str
    total_pence: int


# Ports/interfaces inherit from ABC
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

## 5. Writing Behavioural Classes

Behavioural classes orchestrate data classes and represent the concrete features of the programme. They are created by extracting the `main` function logic into an `execute` method.

### 5.1. The Execute Method

Every Use Case has an `execute` method as its primary entry point. Dependencies such as adapters, ports, clients, or other Use Cases are injected through the constructor, making the class easy to test with mocks. Create a Use Case only when its entry point represents an application capability a caller could meaningfully request and receive a complete outcome from. Do not create one merely to shorten another Use Case or name an internal processing step.

A capability does not need multiple callers to qualify. A Use Case may also expose additional public methods when they represent closely related operations on the same domain concept. All public methods on the class must share the same dependencies and belong to the same logical feature.

```python
# Orchestrate tool selection, model calls, and response projection in one capability.
from dataclasses import dataclass


@dataclass
class ToolCallingUseCase:
    chat_model_adapter: ChatModelAdapter
    tool_registry: ToolRegistryAdapter

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
### 5.2. Composing Use Cases

Because each Use Case is a class with injected dependencies, independently meaningful capabilities compose naturally. A higher-level Use Case may call a lower-level one when the lower-level entry point accepts meaningful application input and returns a complete result without depending on transient internal state owned by its caller. Reuse across several workflows is useful evidence, but it is not required. An internal workflow step that cannot stand alone remains inline or becomes a nested function under section 3.5.

```python
# Compose complete application capabilities through their public entry points.
@dataclass
class AgenticRunUseCase:
    tool_calling: ToolCallingUseCase
    structured_output: StructuredOutputUseCase

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

### 5.3. Adapters and Clients

Adapters translate application-specific operations into calls to genuine external or variable dependencies. Clients handle the low-level SDK, authentication, connection, and transport details. Adapters may import and compose clients, not the other way around.

Create an adapter when at least one real boundary exists: implementation substitution, an external protocol or schema, credentials or connection lifecycle, or dependency-specific failure handling. I/O alone does not justify an adapter. Do not wrap a stable direct library call or local operation solely for architectural symmetry. Keep it in the owning Use Case until a real boundary exists.

Classify extracted behaviour in this order:

1. Keep ordinary workflow logic inline.
2. Use a nested function under section 3.5 for a substantial cohesive operation local to one public entry point.
3. Create a Use Case only when the capability passes the independent-caller test in section 5.1.
4. Create an adapter for an application-facing infrastructure boundary.
5. Create a client for low-level SDK, credential, connection, or transport concerns used by an adapter.

```python
# Compare direct local work with an adapter that has no genuine boundary.
# Good: a stable local operation remains in the use case that owns it
class StartApplicationUseCase:
    def execute(self, settings_path: Path) -> ApplicationSettings:
        raw_settings = json.loads(settings_path.read_text(encoding="utf-8"))
        return ApplicationSettings.model_validate(raw_settings)


# Bad: an adapter adds indirection without a variable dependency or boundary
class LocalSettingsAdapter:
    def read(self, settings_path: Path) -> dict:
        return json.loads(settings_path.read_text(encoding="utf-8"))
```

```python
# Translate application database operations through a provider-specific client.
@dataclass
class PostgresDatabaseAdapter:
    __client: PostgresClient

    def save_user(self, user: UserDAO) -> None:
        logging.info("Saving user %s to PostgreSQL", user.name)
        self.__client.execute(
            "INSERT INTO users (id, name) VALUES (%s, %s)",
            (user.id, user.name),
        )
        logging.info("User %s saved successfully", user.name)

    def find_user_by_id(self, user_id: int) -> UserDAO | None:
        logging.info("Looking up user %d", user_id)
        row = self.__client.fetch_one(
            "SELECT id, name FROM users WHERE id = %s", (user_id,)
        )
        if row is None:
            return None
        return UserDAO(id=row["id"], name=row["name"])
```

### 5.4. Ports and Interfaces

Create a port only when more than one adapter implements the same functionality. The port holds the single source of truth for the method signature and docstring. Adapters implement the port but do not repeat the signature documentation.

```python
# Share one application contract across two provider-specific adapters.
import abc


class ChatModelPort(abc.ABC):
    @abc.abstractmethod
    def generate(self, prompt: str, tools: list[Tool] | None = None) -> ChatResponse:
        """
        Generate a response from a chat model.

        Parameters
        ----------
        prompt : str
            The input prompt to send to the model.
        tools : list[Tool] | None
            Optional list of tools the model may call.

        Returns
        -------
        ChatResponse
            The model's response, which may include tool calls.
        """
        ...


@dataclass
class OpenAIChatModelAdapter(ChatModelPort):
    __client: OpenAIClient

    def generate(self, prompt, tools=None):
        # Translate the OpenAI-specific response into the application contract.
        raw_response = self.__client.chat_completions_create(prompt, tools)
        return ChatResponse.from_openai(raw_response)


@dataclass
class AnthropicChatModelAdapter(ChatModelPort):
    __client: AnthropicClient

    def generate(self, prompt, tools=None):
        # Translate the Anthropic-specific response into the application contract.
        raw_response = self.__client.messages_create(prompt, tools)
        return ChatResponse.from_anthropic(raw_response)
```

When only one adapter exists for a piece of infrastructure, inject the adapter directly into the use case without creating a port.

---

## 6. Coding Style

### 6.1. PEP 8

Follow [PEP 8](https://pep8.org/) style guidelines throughout.

### 6.2. Docstrings

Use the NumPy format. Only add docstrings to functions that are not self-explanatory. Do not add docstrings to boilerplate functions such as router endpoints. When a method implements an interface, place the docstring only on the interface method, not the implementation.

Only include the `Side Effects` section when the function has side effects such as logging, printing, or writing to a database. Only include the `Examples` section for complex functions.

```python
# Demonstrate the required NumPy docstring sections on a non-trivial public function.
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

### 6.3. Imports

Import modules, not individual names. This keeps the origin of every symbol explicit and avoids namespace collisions.

```python
# Keep imported symbols qualified so their module of origin remains visible.
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

### 6.4. Section Dividers

When a file contains large groups of related code (such as routes grouped by resource or adapters grouped by client), use block comment dividers to create visual sections.

```python
# Group related OAuth routes while keeping the purpose of each group explicit.
from infrastructure.router.app import app
import use_cases.use_cases as use_cases
import infrastructure.adapters as adapters
import fastapi
import fastapi.responses as responses

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
    url = use_cases.oauth_login_use_case(adapters.TickTickConnectorAdapter(), state)
    return responses.RedirectResponse(url=url)


@app.get("/ticktick/callback")
async def ticktick_callback(request: fastapi.Request, code: str, state: str):
    if state != request.session.get("state"):
        raise fastapi.HTTPException(status_code=400, detail="Invalid state parameter")
    token_data = use_cases.oauth_callback_use_case(
        adapters.TickTickConnectorAdapter(), code
    )
    return token_data


# =======================#
#                        #
#   MENDELEY OAuth2      #
#                        #
# =======================#

# Handle the Mendeley login flow as a separate route group.

@app.get("/mendeley/login")
def mendeley_login(request: Request):
    state = "some_random_state_string"
    request.session["state"] = state
    url = use_cases.oauth_login_use_case(adapters.MendeleyConnectorAdapter(), state)
    return RedirectResponse(url=url)
```

### 6.5. Type Casting

When you are confident that a value has a specific type but the type checker cannot infer it, use `typing.cast` to make the assertion explicit. Never use `# type: ignore` or bare `Any` as a workaround — `typing.cast` documents the intent and keeps the type system honest.

```python
# Make justified type assertions visible without disabling type checking.
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

### 6.6. Backward Compatibility

Do not worry about backward compatibility. When renaming, removing, or changing an interface, update all call sites directly rather than adding shims, aliases, or deprecation layers. Delete unused code outright — do not leave it behind with comments or `_old` suffixes.

---

## 7. Testing Strategy

Every use case gets a test, and every adapter/client gets a test — not just
when a feature happens to touch one. Add smoke tests and regression tests as
their own categories on top of that, per 7.3 and 7.4 below. Prioritise tests at
the public interfaces between layers. Test a domain data class directly when it
owns non-trivial business rules, invariants, or validation that are clearer to
exercise on the object itself. Do not test passive field storage, ports, or
framework boilerplate in isolation.

Always add mocks and test infrastructure where possible, such as a test database, so use cases and adapters can be exercised without hitting real external systems.

```
tests/
    conftest.py            # Shared Fake*/Mock* test doubles used by 2+ test files
    test_use_cases.py       # Tests for use case execute methods
    test_adapters.py        # Tests for adapter integration
    test_routers.py         # Tests for API endpoints
    test_repo_hygiene.py    # Smoke tests: repo-wide invariants
    test_bugs.py            # Regression tests for fixed bugs
```

### 7.1. Testing Use Cases

Inject mock dependencies to test use cases in isolation.

```python
# Verify the Use Case through its application-facing adapter contract.
def test_tool_calling_use_case_returns_complete_summary():
    mock_chat_model_adapter = MockChatModelAdapter(responses=["search result"])
    mock_registry = MockToolRegistryAdapter(tools=[search_tool])

    use_case = ToolCallingUseCase(
        chat_model_adapter=mock_chat_model_adapter,
        tool_registry=mock_registry,
    )

    result = use_case.execute(AgentRunInput(prompt="find notes", max_steps=1))

    assert result.status == RunStatus.COMPLETE
    assert len(result.cleaned_outputs) == 1
```

### 7.2. Regression Tests for Bugs

Whenever a bug is discovered, write a test that reproduces it in `test_bugs.py`. Fix the bug. Keep the test permanently to prevent regression.

```python
# tests/test_bugs.py
# Preserve the corrected handling of empty tool output.

def test_empty_tool_result_does_not_crash():
    """Regression: empty output_text caused IndexError in strip pipeline."""
    result = ToolResult(tool_name="empty_tool", output_text="")
    cleaned = result.output_text.strip()
    assert cleaned == ""
```

### 7.3. Shared Test Doubles

A `Fake*`/`Mock*` class needed by two or more test files belongs in `conftest.py`, not copy-pasted into each one. A test double used by only one file stays local to that file — don't pre-emptively centralize something nothing else needs yet.

```python
# tests/conftest.py
# Share a response double used across multiple test modules.

class FakeResponse:
    def __init__(self, json_data: dict, status_code: int = 200) -> None:
        self.__json_data = json_data
        self.status_code = status_code

    def json(self) -> dict:
        return self.__json_data
```

### 7.4. Smoke Tests

A smoke test asserts a repo-wide invariant rather than one component's behavior — the kind of thing that silently rots (a renamed folder nothing reads from anymore, a config drifting out of sync) rather than failing loudly on its own. Keep these in `test_repo_hygiene.py`.

```python
# tests/test_repo_hygiene.py
# Protect repository-wide state-folder invariants from silent drift.

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

---

## 10. Expanding the Codebase

### 10.1. When main.py Outgrows Itself

When the `main.py` file accumulates too many classes, split into files within the `src/project_name/` directory.

```
src/project_name/
    main.py             # Entrypoint
    entities.py          # Domain data classes (or dao.py)
    use_cases.py         # Behavioural classes with execute methods
    adapters.py          # Infrastructure adapters
    clients.py           # External service clients
    schema.py            # DTOs and contracts with external libraries
    messages.py          # Events and messages for message buses
    ports.py             # Interfaces (ABC) for adapters
    routes.py            # API endpoint definitions
    app.py               # Application/server object creation
    errors.py            # Custom exception classes
```

### 10.2. When Files Outgrow Themselves

When individual files become too large, convert them into folders with semantically grouped modules.

```
src/project_name/
    main.py
    domain/
        entities.py
        dao.py
        crud_dao.py
        assoc_dao.py
    use_cases/
        tools.py
        services.py
        dtos.py
        ports.py
        schemas.py
        messages.py
        errors.py
    infrastructure/
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

### 10.3. Scaling to Multiple Services

This structure scales recursively. When a subsection of a service needs to scale independently, extract it into its own service following the same process: start from a new `main.py`, extract the use case with its `execute` method, define its adapters and clients. 
```
services/
    billing/
        src/billing/
            main.py
            use_cases.py
            adapters.py
    notifications/
        src/notifications/
            main.py
            use_cases.py
            adapters.py
```

### 10.4. Adding New Features

When adding a new feature, start from the end in mind: design the **route or message handler** first (how the feature is triggered and what the response looks like), then the **DTO** (what data crosses the boundary), then the **use case** (what logic orchestrates the feature), then the **adapter** (what infrastructure is needed). This outside-in approach gives you TDD-like benefits — you define the desired interface before building the internals, which prevents over-engineering and keeps the implementation focused on what the consumer actually needs. Reuse existing layers if they are available.

```python
# 1. Route: how is the feature triggered? What does the consumer see?
@app.post("/refunds")
def create_refund(request: RefundRequest) -> RefundConfirmation:
    return ProcessRefundUseCase(
        payment_adapter=StripePaymentAdapter()
    ).execute(request)


# 2. DTO: what data crosses the boundary?
class RefundRequest(BaseModel):
    order_id: str
    reason: str


# 3. Use case: what is the feature?
@dataclass
class ProcessRefundUseCase:
    payment_adapter: StripePaymentAdapter

    def execute(self, refund_request: RefundRequest) -> RefundConfirmation: ...


# 4. Adapter: what external service do we need?
class StripePaymentAdapter:
    def refund(self, transaction_id: str, amount_pence: int) -> RefundResult: ...
```

# Frontend

You are a code assistant working in a React + TypeScript codebase.
## 0. Prime Directive

This codebase uses a simple, event-driven React style:

* Users interact with UI elements (e.g. `onClick`, `onChange`, `onSubmit`).
* “Dumb” UI components are stateless and **only emit events** upward via props named `onEventXYZ(...)`.
* “Container” components (page/top level component) are stateful and handle all logic in functions named `handleEventXYZ(...)`.
* Each Page should have one Container component
* Each handler does one of two things:

  1. triggers a side-effect (API call, toast, navigation, etc.)
  2. updates state using small, predictable `setState` patterns.

When using `useReducer` or `xstate`, the page should still be the single container, but UI triggers call `send("event_name", payload)` instead of calling many `handleEventXYZ` functions.

When using react functions and when using libraries in general, try to import the library as follows:
`import * as React from "react"` this will allow you to access most of its functionality like the following: `React.useState`, `React.useEffect` etc... which I prefer more.

Overall keep React code boring, explicit, and easy to scan.

---

## 1. Project Structure

### 1.1 Stack (typical)

* React + TypeScript
* TailwindCSS
* Optional: `useReducer` / `xstate` when truly required

### 1.2 Folder structure (pattern)

* Pages: `src/pages/<page_name>/...` (pages can be recursive)
* Page components: `src/pages/<page_name>/<PageName>.tsx`
* Page-local components: `src/pages/<page_name>/components/...`
* Page-local reducer/machine: `src/pages/<page_name>/state/...`
* Shared components: `src/components/...`

Rule: **one reducer or one state machine per page** (not shared across multiple pages unless truly generic).

---

## 2. Naming Conventions

### 2.1 Events and handlers

* **UI component prop**: `onEventXYZ(...)`
* **Page handler**: `handleEventXYZ(...)`

Example:

* Child button: `onClick={() => props.onEventDeleteItem(itemId)}`
* Page function: `const handleEventDeleteItem = (itemId: string) => { ... }`

### 2.2 Entity-scoped handler grouping

Inside page components, handlers must be grouped by the entity being acted on.

Use headings like:

* `// ------------------------------------------------------ Collection`
* `// ------------------------------------------------------ Item`
* `// ------------------------------------------------------ Option`

---

## 3. Page Template (Block Comments + OBSERVE STATE + UTILS)

### 3.1 File Header Comment

Every file that exports a page or a component starts with a full-width block comment placed after the imports and before the export. This is separate from the internal section dividers in 3.3 — it documents the file as a whole, not a region within it.

Structure: border, blank line, the name in caps (matching the component/page name), blank line, a 2-4 line description, blank line, border. The description must say two things: what the component renders/does, and where it sits in the app — its relationship to parent/child components, which direction data or events flow, and any spec references (e.g. `PRD §5.2`) if they exist.

```tsx
// ============================================================ //
//                                                              //
//   NODE EDITOR PANEL                                          //
//                                                              //
//   Authoring surface for a single policy node (PRD §5.2). The //
//   body is edited as plain markdown; typed references are     //
//   parsed live into chips, and a palette inserts new tokens.  //
//   Edits are emitted upward — the page owns persistence.      //
//                                                              //
// ============================================================ //
```

A page's header additionally states what the page lists/renders and what the primary user actions do (e.g. "Pausing/resuming writes through the API; opening a session routes to the policy editor"). A leaf component's header states what it renders and, if it is not self-contained, how it communicates with its parent (e.g. "Dumb top navigation bar... Routing is the side-effect, so it leans on NavLink rather than emitting events upward").

```tsx
// ============================================================ //
//                                                              //
//   SESSIONS PAGE                                              //
//                                                              //
//   Lists agent-loop runs with summary tiles, status filters,  //
//   and search. Pausing/resuming writes through the API;       //
//   opening a session routes to the policy editor (PRD §5).    //
//                                                              //
// ============================================================ //
```

### 3.2 Page Body Sections

Use these sections in this order. Keep each section short.
Block comments MUST have exactly 5 lines. 3-line block comments are categorically forbidden.
```tsx
// Keep a complex page readable by separating its major lifecycle stages.
export default function SomePage() {
  
  // ====================== //
  //                        //
  //   STATE VARIABLES      //
  //                        //
  // ====================== //
  
  // const [state, setState] = useState()
  // or [state, send] = useReducer(machine)

  // ====================== //
  //                        //
  //   OBSERVE STATE        //
  //                        //
  // ====================== //
  
  // console.log(...) key states

  // ====================== //
  //                        //
  //   SIDE EFFECTS         //
  //                        //
  // ====================== //
  
  // useEffect(...) only when needed

  // ====================== //
  //                        //
  //   UI EVENT HANDLERS    //
  //                        //
  // ====================== //
  
  // group by entity
  // ------------------------------------------------------ EntityA
  // handleEventXYZ(...)

  // ------------------------------------------------------ EntityB
  // handleEventXYZ(...)

  // ====================== //
  //                        //
  //   UTILS METHODS        //
  //                        //
  // ====================== //
  
  // keep page-local helpers here (inside the component)

  // ====================== //
  //                        //
  //   UI COMPONENTS        //
  //                        //
  // ====================== //
  
  return <div />;
}
```

### 3.3 OBSERVE STATE

Keep an “OBSERVE STATE” section near the top of the page component and log the important state variables.

Example:

```ts
// Keep important page state visible together during development.
console.log("items", items);
console.log("selectedCollectionId", selectedCollectionId);
console.log("hasUnsavedChanges", hasUnsavedChanges);
```

### 3.4 UI Section Comments

Always add JSX comments to separate major UI regions.

Example:

```tsx
/* Separate the page's major visual regions in the JSX. */
return (
  <div>
    {/* Top bar */}

    {/* Main layout */}

    {/* Sidebar */}
  </div>
);
```

---

## 4. State Management Rules (Simple + Predictable)

### 4.1 Default: `useState`

Prefer `useState` unless the state transitions are genuinely complex.

### 4.2 Allowed `setState` patterns

#### Update an object by field (guard + shallow copy)

```ts
// Update one object only when the current entity matches the requested target.
setItem((prev) => {
  if (prev.id !== itemId) return prev;
  return { ...prev, [field]: value };
});
```

#### Update an array item (map + guard)

```ts
// Replace only the matching array item while preserving every other item.
setItems((prev) =>
  prev.map((it) => (it.id !== itemId ? it : { ...it, [field]: value }))
);
```

#### Append to an array

```ts
// Append a new item without mutating the existing array.
setItems((prev) => [...prev, newItem]);
```

#### Replace an object

```ts
// Replace the current object when no previous fields need to be retained.
setCollection(newCollection);
```

#### Delete from an array

```ts
// Remove the matching item without mutating the existing array.
setItems((prev) => prev.filter((it) => it.id !== itemId));
```

#### Append into an array field (within an object)

```ts
// Append a nested value while preserving the other object fields.
setItem((prev) => {
  if (prev.id !== itemId) return prev;
  return { ...prev, tags: [...prev.tags, newTag] };
});
```

Use more advanced patterns only when strictly necessary.

---

## 5. Dumb UI Components vs Stateful Containers

### 5.1 Dumb UI components

* Stateless (no business state).
* Render-only.
* Emit events upward via `onEventXYZ(...)` props.

### 5.2 Container components (pages)

* Own all state for the page.
* Own all side-effects.
* Own all event handlers (or `send(...)` when using `useReducer` / `xstate`).

Rule: each page is responsible for its own state. Avoid cross-page shared state unless absolutely required.

### 5.3 Prop Types: Always Inline

Define prop types inline on the component function. Never define a separate `type Props = { ... }` unless that type is explicitly referenced elsewhere in the code (e.g. passed to a utility function or imported by another module).

```tsx
// Compare inline props with an unnecessary single-use alias.
// CORRECT: inline
function ItemRow(props: {
  item: Item;
  onEventDeleteItem: (itemId: string) => void;
}) { ... }

// WRONG: separate type that is never referenced elsewhere
type ItemRowProps = { item: Item; onEventDeleteItem: (itemId: string) => void };
function ItemRow(props: ItemRowProps) { ... }
```

### 5.4 Layout and Structure Stay in the Page Component

Rows, groups, grids, and overall structural `div`/`span` wrappers belong in the page component's JSX, not inside dumb child components — unless strictly necessary (e.g. a component that is inherently a row or a card by design).

Keep the skeleton of the layout visible at the page level so the structure is easy to scan.

```tsx
// Compare page-owned layout with layout hidden inside a child component.
// CORRECT: structure is in the page
return (
  <div className="grid grid-cols-2 gap-4">
    {items.map((item) => (
      <ItemCard key={item.id} item={item} onEventSelect={handleEventSelectItem} />
    ))}
  </div>
);

// WRONG: grid is hidden inside ItemCard
function ItemCard(props: { ... }) {
  return (
    <div className="grid grid-cols-2 gap-4"> {/* structural layout belongs in the page */}
      ...
    </div>
  );
}
```

---

## 6. Data Access Pattern: `DatabaseInterface`

Use `DatabaseInterface` for backend calls.

Rules:

* Instantiate in the page (or in a small helper hook for that page).
* Pass generic types to strongly type `result`.
* Always handle both `{ result }` and `{ error }`.
* Always log errors with context: `console.log("Error ...:", error)`.
* Prefer user-visible feedback on failures (toast).

Example:

```ts
// Load typed backend data and surface either the result or a contextual failure.
import DatabaseInterface from "../../DatabaseInterface";
import toastFactory, { MessageSeverity } from "../../components/ToastMessage";
import * as Schema from "../../schema";

const db = new DatabaseInterface(import.meta.env.VITE_DEV_BACKEND_URL_V1);

db.READ<Schema.QuestionnaireListResponse>("questionnaires").then(
  ({ result, error }) => {
    if (result) {
      setQuestionnaires(result.entities);
    } else {
      console.log("Error loading questionnaires:", error);
      toastFactory("Failed to load questionnaires", MessageSeverity.ERROR);
    }
  }
);
```

Important Note: DO NOT Create the DatabaseInterface class if you can't find it, I will add it myself

---

## 7. Styling Rules (Tailwind, but simple)

* Prefer plain strings: `className="..."`.
* Do NOT build Tailwind classes using arrays + `.join(" ")`.
* For conditionals, use a simple ternary string.

Examples:

```tsx
/* Use direct Tailwind strings and a simple ternary for conditional styling. */
<div className="flex items-center gap-2" />

<button className={isActive ? "bg-slate-900 text-white" : "bg-white text-slate-900"} />
```

---

## 8. Example Pattern: Item Collection (Child Entity)

Default mental model:

* A **Collection** is a named container.
* An **Item** is a child entity of that collection.
* Items are rendered by dumb child components.
* The page is the container.

```tsx
// Keep state, lifecycle events, and page structure together in the container.
import * as React from "react";

type Item = { id: string; label: string; done: boolean };
type ItemCollection = { id: string; name: string; items: Item[] };

function ItemRow(props: {
  item: Item;
  onEventToggleDone: (itemId: string) => void;
  onEventChangeLabel: (itemId: string, label: string) => void;
  onEventDeleteItem: (itemId: string) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <input
        type="checkbox"
        checked={props.item.done}
        onChange={() => props.onEventToggleDone(props.item.id)}
      />
      <input
        className="border rounded px-2 py-1"
        value={props.item.label}
        onChange={(e) => props.onEventChangeLabel(props.item.id, e.target.value)}
      />
      <button
        type="button"
        className="border rounded px-2 py-1"
        onClick={() => props.onEventDeleteItem(props.item.id)}
      >
        Delete
      </button>
    </div>
  );
}

export default function ItemCollectionPage() {
  
  // ====================== //
  //                        //
  //   STATE VARIABLES      //
  //                        //
  // ====================== //

  const [collection, setCollection] = React.useState<ItemCollection>({
    id: "col-1",
    name: "My Collection",
    items: [],
  });

  // ====================== //
  //                        //
  //   OBSERVE STATE        //
  //                        //
  // ====================== //

  console.log("collection", collection);

  // ====================== //
  //                        //
  //   UI EVENT HANDLERS    //
  //                        //
  // ====================== //

  // ------------------------------------------------------ Collection
  const handleEventRenameCollection = (name: string) => {
    setCollection((prev) => ({ ...prev, name }));
  };

  // ------------------------------------------------------ Item
  const handleEventAddItem = () => {
    const newItem: Item = {
      id: crypto.randomUUID(),
      label: "New Item",
      done: false,
    };
    setCollection((prev) => ({ ...prev, items: [...prev.items, newItem] }));
  };

  const handleEventToggleDone = (itemId: string) => {
    setCollection((prev) => ({
      ...prev,
      items: prev.items.map((it) =>
        it.id !== itemId ? it : { ...it, done: !it.done }
      ),
    }));
  };

  const handleEventChangeLabel = (itemId: string, label: string) => {
    setCollection((prev) => ({
      ...prev,
      items: prev.items.map((it) => (it.id !== itemId ? it : { ...it, label })),
    }));
  };

  const handleEventDeleteItem = (itemId: string) => {
    setCollection((prev) => ({
      ...prev,
      items: prev.items.filter((it) => it.id !== itemId),
    }));
  };

  // ====================== //
  //                        //
  //   UTILS METHODS        //
  //                        //
  // ====================== //

  const getDoneCount = () => collection.items.filter((i) => i.done).length;

  // ====================== //
  //                        //
  //   UI COMPONENTS        //
  //                        //
  // ====================== //

  return (
    <div className="p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <input
          className="border rounded px-2 py-1"
          value={collection.name}
          onChange={(e) => handleEventRenameCollection(e.target.value)}
        />
        <button
          type="button"
          className="border rounded px-3 py-1"
          onClick={handleEventAddItem}
        >
          Add Item
        </button>
      </div>

      {/* Summary */}
      <div className="text-sm text-slate-600">Done: {getDoneCount()}</div>

      {/* Items */}
      <div className="space-y-2">
        {collection.items.map((item) => (
          <ItemRow
            key={item.id}
            item={item}
            onEventToggleDone={handleEventToggleDone}
            onEventChangeLabel={handleEventChangeLabel}
            onEventDeleteItem={handleEventDeleteItem}
          />
        ))}
      </div>
    </div>
  );
}
```

---

## 9. `useReducer` Pattern (Reducer Outside, Page Uses `send(...)`)

Use `useReducer` when:

* you have multiple event types, and
* it is cleaner to centralize transitions in a reducer.

Rules:

* Keep the reducer in a separate file under the page folder.
* The page should not contain dozens of `handleEventXYZ` functions.
* UI triggers should call `send("event_name", payload)`.

### 9.1 Example: `src/pages/item_collection/state/reducer.ts`

```ts
// Centralise related page transitions in one reducer.
export type Item = { id: string; label: string; done: boolean };
export type ItemCollection = { id: string; name: string; items: Item[] };

export type State = {
  collection: ItemCollection;
};

export type PageEvent =
  | { name: "collection.rename"; payload: { name: string } }
  | { name: "item.add"; payload: { item: Item } }
  | { name: "item.toggleDone"; payload: { itemId: string } }
  | { name: "item.changeLabel"; payload: { itemId: string; label: string } }
  | { name: "item.delete"; payload: { itemId: string } };

export function reducer(state: State, event: PageEvent): State {
  switch (event.name) {
    case "collection.rename":
      return { ...state, collection: { ...state.collection, name: event.payload.name } };

    case "item.add":
      return {
        ...state,
        collection: {
          ...state.collection,
          items: [...state.collection.items, event.payload.item],
        },
      };

    case "item.toggleDone":
      return {
        ...state,
        collection: {
          ...state.collection,
          items: state.collection.items.map((it) =>
            it.id !== event.payload.itemId ? it : { ...it, done: !it.done }
          ),
        },
      };

    case "item.changeLabel":
      return {
        ...state,
        collection: {
          ...state.collection,
          items: state.collection.items.map((it) =>
            it.id !== event.payload.itemId ? it : { ...it, label: event.payload.label }
          ),
        },
      };

    case "item.delete":
      return {
        ...state,
        collection: {
          ...state.collection,
          items: state.collection.items.filter((it) => it.id !== event.payload.itemId),
        },
      };

    default:
      return state;
  }
}
```

### 9.2 Example Page Usage

```tsx
// Drive the page through the reducer while keeping the rendered structure visible.
import * as React from "react";
import { reducer, State, PageEvent, Item } from "./state/reducer";

export default function ItemCollectionPage() {
  const [state, send] = React.useReducer(reducer, {
    collection: { id: "col-1", name: "My Collection", items: [] },
  } satisfies State);

  console.log("state", state);

  return (
    <div>
      {/* Header */}
      <input
        value={state.collection.name}
        onChange={(e) => send("collection.rename", { name: e.target.value })}
      />

      {/* Items */}
      <button
        type="button"
        onClick={() => {
          const newItem: Item = { id: crypto.randomUUID(), label: "New Item", done: false };
          send("item.add", { item: newItem });
        }}
      >
        Add Item
      </button>
    </div>
  );
}
```

---

## 10. `xstate` Pattern (One Machine per Page)

When using `xstate`:

* One machine per page.
* UI components remain dumb.
* Page uses `send("event_name", payload)`.
* Keep side-effects in machine actions/services or in a page-level bridge hook.

---

## 11. Common Code Smells (Avoid)

* Complex state transformations inside JSX event props
* Business logic inside presentational components
* Multiple sources of truth for the same data
* Large `useEffect` blocks that should be a handler or a small helper
* Multiple reducers/machines fighting over the same page state

## 12. No Unsolicited UI Copy

Do not add explanatory hint text, status captions, or helper descriptions next to a UI element unless specifically asked for. A control should be self-evident from its own label or icon; don't pair it with a sentence describing what it does or what state it's in.

```tsx
// Compare unsolicited helper copy with a self-explanatory control.
// WRONG: hint text nobody asked for
<p>Active diet: {activeDiet.name} {activeDiet.finalizedAt ? "(finalized)" : "(not finalized)"}</p>
<Button onClick={finalizeDiet}>Finalize Diet</Button>

// CORRECT: the control speaks for itself
<Switch checked={isActive} onChange={handleEventToggle} />
```

# Backend

### 1.1. Technology Stack

- FastAPI for the web framework
- SQLAlchemy for ORM
- pydantic for data validation

### 1.2. Software Architecture

- domain folder:
  - entities: contains the domain entities such as `User`, `Order`, `Inventor`, `Product`,
    etc..
    - these can be enforced either through `pydantic.BaseModel` (if there is no SQL database in the application),  or `SQLAlchemy` ORM (this is an opinionated way I prefer to set my entities because I don't like duplicating the class definition)
      models
  - messages: contains the domain messages such as `UserCreated`, `OrderPlaced`, etc..
  - errors: contains the domain errors such as `UserNotFound`, `OrderNotFound`, etc..
- `use_cases` folder:
  - contains Use Case classes such as `CreateUserUseCase` and `PlaceOrderUseCase`
  - each Use Case exposes `execute()` as its primary public entry point and follows
    the behavioural-class rules in section 5
  - Use Cases orchestrate domain entities, messages, DTOs, and injected adapters or
    ports without constructing clients or implementing infrastructure themselves
  - contains the schema file which defines the data transfer objects (DTOs) such as
    `CreateUserRequest` and `CreateUserResponse` using `pydantic.BaseModel`
- infrastructure folder:
  - contains the routers for the application such as user_router, order_router, etc..
  - contains a port only when multiple adapters implement the same application-facing
    capability
  - contains concrete adapters for technologies such as SQLAlchemy and Redis, which
    implement a port only when that shared port is justified
  - contains other infrastructure components such as auth, logging, and external
    configuration management, drivers, emails and notifications, etc... as such

### 1.3. Data Flow

Runtime flow should remain explicit and unidirectional:

route or message handler -> Use Case -> domain objects and injected adapters -> clients or external systems

### 1.4. Implementing Adapters

to implement adapters, first implement the various functions of the external module
or class in a separate file in the infrastructure folder, i.e. `MendeleyClient` in
`infrastructure/connectors/mendeley_client.py`, then implement the adapter in a
separate file in the infrastructure folder, i.e.
`MendeleyConnectorAdapter` in `infrastructure/adapters.py`

or another example: for a payment processor , first implement the payment processor
client in a separate file in the infrastructure folder, i.e. `StripeClient` in
`infrastructure/payment_processor/stripe_client.py`, then implement the adapter in a
separate file in the infrastructure folder, i.e.
`StripePaymentProcessorAdapter` in `infrastructure/adapters.py`.

Create a port only when multiple adapters implement the same application-facing
capability. When only one adapter exists, inject that concrete adapter directly into
the Use Case.

### 1.5. Implementing Routers

always add the version to the router path and the resource name in plural i.e.
`/v1/users/`, `/v1/orders/`, etc.

- the router should only implement the HTTP methods and call the use cases, it should
  not implement any business logic
- the router should use the data transfer objects (DTOs) defined in the
  use_cases/schema.py
- the router should use the adapters defined in the infrastructure/adapters.py
