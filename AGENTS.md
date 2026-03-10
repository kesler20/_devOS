# Overall Programming

## 1. Overview

This guide defines a programming philosophy built on two core ideas: **data classes** provide encapsulation and **behavioural classes** provide orchestration. Everything else flows from this distinction.

The approach is infrastructure and programming language agnostic. It applies equally to web services, mobile applications, desktop software, and embedded systems. The delivery mechanism — whether REST, WebSocket, MQTT, or a native event loop — is an infrastructure detail that never leaks into the core logic.

### 1.1. Core Abstractions

Every programme is composed from a small vocabulary of building blocks.

**Data classes** store data using fields and expose behaviour through methods that operate on that data. They are the nouns of the system: `AgentRunInput`, `Product`, `OrderStatus`.

**Behavioural classes** orchestrate the data passing between data classes. They represent concrete features of the programme and are named in the language of the problem domain. They are the verbs of the system: `ToolCallingUseCase`, `StructuredOutputUseCase`, `StreamingResponseUseCase`.

**Adapters** implement external APIs or infrastructure used by the application. They interact with third-party services, databases, legacy systems, or anything outside the system boundary: `TickTickBacklogAdapter`, `SQLDbAdapter`. Unlike clients, adapters represent concrete implementation of an infrastructure component such as a database, authentication provider, email service, etc...

**Clients** wrap external libraries or services, managing credentials and connection details: `GoogleClient`, `AWSClient`, `RedisClient`.

**Ports/Interfaces** define contracts between Use Cases and adapters. They only exist when more than one adapter implements the same piece of infrastructure, otherwise the use case should interact directly with the adapter.

**Schemas and DTOs** define contracts at system boundaries. **DAOs** (Data Access Objects) represent the shape of objects persisted to storage (SQL rows, NoSQL documents, graph nodes). **DTOs** (Data Transfer Objects) are service-specific contracts with the outside world — the objects your API sends and receives, such as `CreateUserResponse` or `RefundRequest`. **Schemas** are third-party or infrastructure data transfer objects — the shapes dictated by external libraries, APIs, or protocols that you do not control, such as a Stripe webhook payload or an OAuth token response.

**DAOs** (Data Access Objects) represent entities that are persisted to storage.

### 1.2. Mental Model

We subscribe to **abstraction**, **composition**, and **encapsulation**. We do not use **implementation inheritance** — inheriting from a concrete class to reuse its code or to override its behaviour. The only acceptable reason to inherit from a class is to gain **framework behaviour**: inheriting from `BaseModel` for validation, `ABC` for defining interfaces, `DeclarativeBase` for ORM mapping, or similar framework-provided base classes. This means inheriting from an abstract port like `ChatModelPort(ABC)` to implement a concrete adapter is permitted — that is interface conformance, not implementation reuse. What is not permitted is creating a `BaseAdapter` with shared logic and having `PostgresAdapter(BaseAdapter)` and `MongoAdapter(BaseAdapter)` inherit from it. Use composition to share logic between concrete classes instead.

### 1.3. How Development Begins

Every programme starts in a single `main.py` file. Write the core logic directly inside a `main` function. As the routine takes shape, gradually refactor by extracting data classes that you identify within the routine. Once all data classes are identified, add methods for encapsulation following the tell-don't-ask principle. Then organise the remaining orchestration into behavioural classes by converting the `main` function into an `execute` method on a use case class.

```python
# src/agent_run/main.py
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

---

## 2. Constraining State

Dynamic types like raw strings, bare dictionaries, and plain tuples create ambiguity. Constraining the possible state of the programme through the type system eliminates entire categories of bugs and makes the code self-documenting.

### 2.1. Strings and Numbers as Enums

Whenever a string or number represents a specific state, status code, or finite set of values, define it as an `Enum`. This groups related properties together, provides IDE autocomplete, and prevents invalid values at compile time.

```python
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
import typing

LogLevel = typing.Literal["DEBUG", "INFO", "WARNING", "ERROR"]
```

### 2.2. Dictionaries as Data Classes

Never use naked dictionaries to pass data through the programme. Use `dataclass` by default, `pydantic.BaseModel` when you need contractual validation, or `TypedDict` when you only need the type signature without object instantiation.

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

### 2.3. Tuples as Named Tuples

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

## 3. Writing Functions

### 3.1. Comments and Logging

**Comments** describe the *intent* of a block before you write it. Write a comment explaining what you are about to do, then write the code. If the code is self-explanatory after you have written it, the comment can stay as a section label or be removed.

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

```python
# Good: reads like prose, no comments needed
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
def process_order(order: Order) -> str:
    if not order.is_valid():
        return "Order is invalid."

    if not order.has_items():
        return "Order has no items."

    logging.info("Processing order...")
    return "Order processed successfully."
```

### 3.4. Storing Complex Expressions in Variables

When an expression returns a boolean or truthy value and involves multiple conditions, store the result in a descriptively named variable. This turns opaque logic into readable intent.

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

### 3.5. Nested Functions for Local Extraction

When a function grows large, refactor by extracting helper functions *inside* the parent function. This avoids polluting the class with private methods that only serve one caller. Promote an inner function to a private class method only when it needs to be reused by other methods.

**Testability trade-off:** Inner functions cannot be tested in isolation. This is acceptable when the parent function's tests exercise all edge cases of the inner logic through the parent's public interface. The goal is to test *behaviour*, not individual functions. If you find that the inner function has complex branching logic that is difficult to cover through the parent, promote it to a private method or a standalone function so it can be tested directly.

```python
class ReportGenerator:
    def generate_monthly_report(self, transactions: list[Transaction]) -> Report:
        def categorise_transaction(transaction: Transaction) -> str:
            if transaction.amount > 1000:
                return "high_value"
            if transaction.is_recurring:
                return "recurring"
            return "standard"

        def build_summary_line(category: str, total: float) -> str:
            return f"{category}: £{total:.2f}"

        categorised = {}
        for transaction in transactions:
            category = categorise_transaction(transaction)
            categorised.setdefault(category, []).append(transaction)

        summary_lines = []
        for category, group in categorised.items():
            total = sum(t.amount for t in group)
            summary_lines.append(build_summary_line(category, total))

        return Report(lines=summary_lines)
```

---

## 4. Writing Data Classes

Data classes are the foundation of every programme. They store data, enforce business rules, and expose behaviour through methods keeping orchestration code simple and readable.

### 4.1. Private by Default

Write all methods as private by default. Only make a method public when it is required by an external consumer. This minimises the surface area of the class and makes dependencies explicit.

```python
from dataclasses import dataclass


@dataclass
class Account:
    _balance: float
    _currency: str
    _is_active: bool

    def is_valid(self) -> bool:
        return self._is_active and self._has_positive_balance()

    def _has_positive_balance(self) -> bool:
        return self._balance > 0
```

### 4.2. Tell, Don't Ask

When client code calls multiple getters on the same object and then makes a decision based on the results, that behaviour belongs inside the data class. Move the logic into a method on the class so that consumers *tell* the object what to do rather than *asking* for its internals.

```python
# Bad: the caller interrogates the object and decides
def check_account(account: Account) -> bool:
    return account.balance > 0 and account.is_active and account.currency == "GBP"


# Good: the object knows how to answer
@dataclass
class Account:
    _balance: float
    _currency: str
    _is_active: bool

    def is_valid_for_withdrawal(self, required_currency: str) -> bool:
        return (
            self._is_active
            and self._balance > 0
            and self._currency == required_currency
        )
```

A good rule of thumb: be suspicious when client code calls multiple methods on the same object, especially multiple getters. That is often a sign that behaviour belongs inside the data class. Keep behaviour in the orchestration layer only when multiple objects are involved.

### 4.3. Business Rules Close to Data

Business rules like formatting constraints, validation logic, and design decisions, should be defined as methods on the data class they modify. For classes inheriting from `pydantic.BaseModel`, use validators.

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

### 4.4. Inheritance Rules for Data Classes

Data classes inherit from framework base classes only to gain specific behaviour, never for code reuse.

```python
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

Every use case has an `execute` method as its primary entry point. Dependencies (such as adapters, ports, clients or other use cases) are injected through the constructor, making the class easy to test with mocks. While `execute` is the main public method, a use case may expose additional public methods when they represent closely related operations on the same domain concept. This avoids an explosion of single-method use case classes for every minor variation. The key constraint is that all public methods on the class should share the same dependencies and belong to the same logical feature.

```python
from dataclasses import dataclass


@dataclass
class ToolCallingUseCase:
    chat_client: ChatModelClient
    tool_registry: ToolRegistryAdapter

    def execute(self, run_input: AgentRunInput) -> AgentRunSummary:
        logging.info("Starting tool calling for prompt: %s", run_input.prompt)

        available_tools = self.tool_registry.list_tools()
        logging.info("Found %d available tools", len(available_tools))

        raw_results = self._call_tools(run_input, available_tools)
        cleaned_outputs = [result.output_text.strip() for result in raw_results]
        logging.info("Cleaned %d tool outputs", len(cleaned_outputs))

        return AgentRunSummary(
            prompt=run_input.prompt,
            cleaned_outputs=cleaned_outputs,
            status=RunStatus.COMPLETE,
        )

    def _call_tools(
        self, run_input: AgentRunInput, tools: list[Tool]
    ) -> list[ToolResult]:
        results = []
        for step in range(run_input.max_steps):
            response = self.chat_client.generate(run_input.prompt, tools)
            if response.has_tool_call():
                result = self.tool_registry.invoke(response.tool_call)
                results.append(result)
                logging.info("Step %d: called %s", step, result.tool_name)
            else:
                break
        return results
```
### 5.2. Composing Use Cases

Because each use case is a class with injected dependencies, they compose naturally. A higher-level use case can use lower-level ones with their own state objects. This composability is important for several reasons: each use case encapsulates its own state and dependencies, so the higher-level orchestrator does not need to know the internals of the steps it coordinates. It also means each use case can be tested independently with its own mocks, and reused across different contexts.

```python
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

Adapters wrap infrastructure concerns. Clients wrap external libraries and manage credentials. Adapters import clients, not the other way around.

```python
@dataclass
class PostgresDatabaseAdapter:
    _client: PostgresClient

    def save_user(self, user: UserDAO) -> None:
        logging.info("Saving user %s to PostgreSQL", user.name)
        self._client.execute(
            "INSERT INTO users (id, name) VALUES (%s, %s)",
            (user.id, user.name),
        )
        logging.info("User %s saved successfully", user.name)

    def find_user_by_id(self, user_id: int) -> UserDAO | None:
        logging.info("Looking up user %d", user_id)
        row = self._client.fetch_one(
            "SELECT id, name FROM users WHERE id = %s", (user_id,)
        )
        if row is None:
            return None
        return UserDAO(id=row["id"], name=row["name"])
```

### 5.4. Ports and Interfaces

Create a port only when more than one adapter implements the same functionality. The port holds the single source of truth for the method signature and docstring. Adapters implement the port but do not repeat the signature documentation.

```python
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


class OpenAIChatAdapter(ChatModelPort):
    def generate(self, prompt, tools=None):
        # No docstring here — the port is the single source of truth.
        raw_response = self._client.chat_completions_create(prompt, tools)
        return ChatResponse.from_openai(raw_response)


class AnthropicChatAdapter(ChatModelPort):
    def generate(self, prompt, tools=None):
        raw_response = self._client.messages_create(prompt, tools)
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
from infrastructure.router.app import app
import use_cases.use_cases as use_cases
import infrastructure.adapters as adapters
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse

# =========================#
#                          #
#   TICKTICK OAuth2        #
#                          #
# =========================#


@app.get("/ticktick/login")
def ticktick_login(request: Request):
    state = "some_random_state_string"
    request.session["state"] = state
    url = use_cases.oauth_login_use_case(adapters.TickTickConnectorAdapter(), state)
    return RedirectResponse(url=url)


@app.get("/ticktick/callback")
async def ticktick_callback(request: Request, code: str, state: str):
    if state != request.session.get("state"):
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    token_data = use_cases.oauth_callback_use_case(
        adapters.TickTickConnectorAdapter(), code
    )
    return token_data


# =======================#
#                        #
#   MENDELEY OAuth2      #
#                        #
# =======================#


@app.get("/mendeley/login")
def mendeley_login(request: Request):
    state = "some_random_state_string"
    request.session["state"] = state
    url = use_cases.oauth_login_use_case(adapters.MendeleyConnectorAdapter(), state)
    return RedirectResponse(url=url)
```

---

## 7. Testing Strategy

Write tests when implementing new features or fixing bugs. Only test at the interface between layers — never test internal data classes, ports, or framework boilerplate in isolation.

```
tests/
    test_use_cases.py     # Tests for use case execute methods
    test_adapters.py      # Tests for adapter integration
    test_routers.py       # Tests for API endpoints
    test_bugs.py          # Regression tests for fixed bugs
```

### 7.1. Testing Use Cases

Inject mock dependencies to test use cases in isolation.

```python
def test_tool_calling_use_case_returns_complete_summary():
    mock_client = MockChatModelClient(responses=["search result"])
    mock_registry = MockToolRegistryAdapter(tools=[search_tool])

    use_case = ToolCallingUseCase(
        chat_client=mock_client,
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

def test_empty_tool_result_does_not_crash():
    """Regression: empty output_text caused IndexError in strip pipeline."""
    result = ToolResult(tool_name="empty_tool", output_text="")
    cleaned = result.output_text.strip()
    assert cleaned == ""
```

---

## 8. Design Patterns

Software design patterns like decorators have been largely absorbed by modern programming languages. The following patterns remain valuable when complexity demands them, but should only be introduced during refactoring — never as upfront architecture.

### 8.1. Factory

Use when you need to generate different objects depending on upstream state.

```python
def create_notification(user_preference: NotificationPreference) -> Notification:
    if user_preference == NotificationPreference.EMAIL:
        return EmailNotification(template="default")
    if user_preference == NotificationPreference.SMS:
        return SmsNotification(phone_format="international")
    return PushNotification(priority="normal")
```

### 8.2. Builder

Use when you need to dynamically compose an output or object, such as a dashboard or report.

```python
class DashboardBuilder:
    def __init__(self) -> None:
        self._widgets: list[Widget] = []

    def add_chart(self, chart: Chart) -> "DashboardBuilder":
        self._widgets.append(ChartWidget(chart=chart))
        return self

    def add_metric(self, metric: Metric) -> "DashboardBuilder":
        self._widgets.append(MetricWidget(metric=metric))
        return self

    def build(self) -> Dashboard:
        return Dashboard(widgets=self._widgets)
```

### 8.3. Singleton

Use when you need a single source of truth in the programme, such as user credentials, a database connection pool, or application settings. Prefer a module-level factory function with explicit lifecycle control over `__new__` tricks, which silently ignore arguments on subsequent calls.

```python
import typing
from dataclasses import dataclass


@dataclass
class DatabaseConnection:
    connection_string: str

    def query(self, sql: str) -> list[dict]:
        ...


_db_connection: DatabaseConnection | None = None


def get_database_connection(connection_string: str | None = None) -> DatabaseConnection:
    global _db_connection
    if _db_connection is None:
        if connection_string is None:
            raise RuntimeError("DatabaseConnection has not been initialised. Provide a connection_string.")
        _db_connection = DatabaseConnection(connection_string=connection_string)
    return _db_connection


def reset_database_connection() -> None:
    """For testing: tear down the singleton so the next call re-initialises it."""
    global _db_connection
    _db_connection = None
```

The factory makes initialisation explicit and raises when the singleton is accessed before setup. The `reset` function exists solely for test teardown.

### 8.4. Mediator and Observer

Use the mediator to hold the state of a chaotic data flow. Use observers and event handlers (chain of responsibility) in event-driven applications.

Constrain the event system with the type system. Use typed event classes and generic handlers to ensure handlers match their event payloads at definition time rather than failing silently at runtime.

```python
import typing
from dataclasses import dataclass, field


T = typing.TypeVar("T")


@dataclass
class EventBus:
    _handlers: dict[type, list[typing.Callable]] = field(default_factory=dict)

    def subscribe(self, event_type: type[T], handler: typing.Callable[[T], None]) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def publish(self, event: object) -> None:
        for handler in self._handlers.get(type(event), []):
            handler(event)


# Events are typed data classes, not strings.
@dataclass
class OrderPlaced:
    order_id: str
    total_pence: int


@dataclass
class OrderShipped:
    order_id: str
    tracking_code: str


# Usage: subscriptions are checked against event types.
bus = EventBus()
bus.subscribe(OrderPlaced, lambda e: print(f"New order: {e.order_id}"))
bus.subscribe(OrderShipped, lambda e: print(f"Shipped: {e.tracking_code}"))
bus.publish(OrderPlaced(order_id="123", total_pence=5000))
```

### 8.5. Template (via Composition)

Use template classes to reuse code through composition, not inheritance. Define the skeleton in a shared class and inject the varying steps.

```python
@dataclass
class DataPipeline:
    extractor: DataExtractor
    transformer: DataTransformer
    loader: DataLoader

    def execute(self, source: str) -> None:
        raw_data = self.extractor.extract(source)
        transformed_data = self.transformer.transform(raw_data)
        self.loader.load(transformed_data)
```

---

## 9. SOLID Principles

Apply these principles during refactoring, not as upfront constraints.

### 9.1. Single Responsibility

Every class and function should have only one reason to change. If a class handles both database access and email formatting, split it.

```python
# Bad: two reasons to change
class UserManager:
    def save_to_database(self, user: User) -> None: ...
    def format_welcome_email(self, user: User) -> str: ...


# Good: each class has one responsibility
class UserDatabaseAdapter:
    def save(self, user: User) -> None: ...


class WelcomeEmailFormatter:
    def format(self, user: User) -> str: ...
```

### 9.2. Small Interfaces

Do not force a class to implement methods it will not use. Prefer multiple small interfaces over one large one.

```python
import abc

# Bad: forces every implementer to support both read and write
class StoragePort(abc.ABC):
    @abc.abstractmethod
    def read(self, key: str) -> str: ...

    @abc.abstractmethod
    def write(self, key: str, value: str) -> None: ...


# Good: separate concerns into small interfaces
class ReadableStoragePort(abc.ABC):
    @abc.abstractmethod
    def read(self, key: str) -> str: ...


class WritableStoragePort(abc.ABC):
    @abc.abstractmethod
    def write(self, key: str, value: str) -> None: ...
```

### 9.3. Dependency Injection (Composition)

Inject dependencies through the constructor. This makes classes composable and testable.

```python
@dataclass
class OrderProcessingUseCase:
    payment_adapter: PaymentAdapter
    inventory_adapter: InventoryAdapter

    def execute(self, order: Order) -> OrderConfirmation:
        self.inventory_adapter.reserve(order.items)
        payment_result = self.payment_adapter.charge(order.total)
        return OrderConfirmation(
            order_id=order.id,
            payment_id=payment_result.id,
        )
```

### 9.4. Open for Extension, Closed for Change

When new functionality is needed, extend through new classes rather than modifying existing ones. This is where ports, adapters, and factories work together.

```python
# Adding a new chat model provider does not require changing existing code.
# Just create a new adapter that implements the existing port.
class CohereAdapter(ChatModelPort):
    def generate(self, prompt, tools=None):
        raw_response = self._client.generate(prompt)
        return ChatResponse.from_cohere(raw_response)
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
