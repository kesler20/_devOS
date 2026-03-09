
## 1. Overview
The backend application is built using a clean architecture approach

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
  - contains the use case services for the application such as `create_user`,
    `place_order`, etc..
    - the use cases are pure functions that are decoupled from the infrastructure,
      they transform data transfer objects (DTOs) such as `CreateUserRequest` and
      `CreateUserResponse`
    - as such the use cases should never implement adapters or external dependencies,
      they should only use the domain entities, messages, data transfer objects and
      interfaces such as ports
  - contains the schema file which defines the data transfer objects (DTOs) such as
    `CreateUserRequest` and `CreateUserResponse` using `pydantic.BaseModel`
- infrastructure folder:
  - contains the routers for the application such as user_router, order_router, etc..
  - contains the ports which are interfaces for the application using abstract base
    classes (ABCs) such as Repository, Connector, etc..
  - contains the adapters which are implementations of the ports for the application
    using different technologies such as SQLAlchemy, Redis, etc..
  - contains other infrastructure components such as auth, logging, and external
    configuration management, drivers, emails and notifications, etc... as such

### 1.3. Data Flow

dataflow should be unidirectional:

domain -> use_cases -> infrastructure

### 1.4. Example of each layer
```python
# domain/entities.py
import pydantic
import uuid

class User(pydantic.BaseModel):
    id: str = pydantic.Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: str

# use_cases/schema.py
import pydantic

class CreateUserRequest(pydantic.BaseModel):
    name: str
    email: str

class CreateUserResponse(pydantic.BaseModel):
    id: str
    name: str
    email: str

# use_cases/use_cases.py
import domain.entities as entities
import use_cases.schema as schema
import infrastructure.ports as ports

def create_user(request:schema.CreateUserRequest, db: ports.Repository) -> schema.CreateUserResponse:
    user = entities.User(name=request.name, email=request.email)
    db.add(user)
    return schema.CreateUserResponse(id=user.id, name=user.name, email=user.email)

# infrastructure/ports.py
import abc
import typing

class Repository(abc.ABC):
    """
    Abstract base class for repository.
    """

    @abc.abstractmethod
    def add(self, entity: typing.Any) -> None:
        """
        Add an entity to the repository.

        Parameters
        ----------
        entity : Any
            The entity to add to the repository.
        """
        pass

    @abc.abstractmethod
    def get(self, model_class: type, entity_id: str) -> typing.Any:
        """
        Get an entity from the repository by its ID.

        Parameters
        ----------
        model_class: type
	        The type of the entity object.
        entity_id : str
            The ID of the entity to get from the repository.

        Returns
        -------
        Any
            The entity from the repository.
        """
        pass

# infrastructure/adapters.py
from sqlalchemy.orm import Session
import infrastructure.ports as ports
	

class SQLAlchemyRepositoryAdapter(ports.Repository):

    def __init__(self, session: Session):
        self.session = session

    def add(self, entity):
        self.session.add(entity)
        self.session.commit()

    def get(self, model_class, entity_id: str):
        return self.session.get(model_class, entity_id)

def get_db():
    """
    Dependency to get the SQLAlchemy session.

    Returns
    -------
    SQLAlchemyRepositoryAdapter
        An instance of the SQLAlchemyRepositoryAdapter.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///./test.db")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield SQLAlchemyRepositoryAdapter(db)
    finally:
        db.close()

# infrastructure/routers.py
import fastapi
import uvicorn 
import use_cases.schema as schema
import use_cases.use_cases as use_cases
import infrastructure.adapters as adapters

app = fastapi.FastAPI()

@app.post("/v1/users/", response_model=schema.CreateUserResponse)
def create_user(
    request: schema.CreateUserRequest,
    db: adapters.SQLAlchemyRepositoryAdapter = fastapi.Depends(adapters.get_db)
):
    return use_cases.create_user(request, db)

if __name__ == "__main__":
    uvicorn.run(app, port=8000)
```

### 1.5. Implementing Adapters

to implement adapters, first implement the various functions of the external module
or class in a separate file in the infrastructure folder, i.e. `MendeleyClient` in
`infrastructure/connectors/mendeley_client.py`, then implement the adapter in a
separate file in the infrastructure folder, i.e.
`MendeleyConnectorAdapter(ports.Connector)` in `infrastructure/adapters.py`

or another example: for a payment processor , first implement the payment processor
client in a separate file in the infrastructure folder, i.e. `StripeClient` in
`infrastructure/payment_processor/stripe_client.py`, then implement the adapter in a
separate file in the infrastructure folder, i.e.
`StripePaymentProcessorAdapter(ports.PaymentProcessor)` in
`infrastructure/adapters.py`.

### 1.6. Implementing Routers

always add the version to the router path and the resource name in plural i.e.
`/v1/users/`, `/v1/orders/`, etc.

- the router should only implement the HTTP methods and call the use cases, it should
  not implement any business logic
- the router should use the data transfer objects (DTOs) defined in the
  use_cases/schema.py
- the router should use the adapters defined in the infrastructure/adapters.py

## 2. Coding Style

- Use [PEP 8](https://pep8.org/) style guidelines.

### 2.1. Docstrings

for docstrings, use the Numpy format

```python
def add_numbers(param_1: int, param_2: int) -> str:
    """
    add two numbers.

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
    """
    return str(param_1 + param_2)
```

if you are adding docstring to a method, ensure that the class is not implementing an
interface, otherwise, only add the docstring to the interface method, not the
implementation. if you are writing a new router or any boilerplate function, do not
add docstrings

### 2.2. Commenting

instead of using comments, try to log or print messages explaining what the block is
doing. for instance:

```python
def process_data(data):
    # Process the data
    print("Processing data...")
    processed_data = data.upper()  # Convert data to uppercase
    print("Data processed successfully.")
    return processed_data
```

only use comments when there is a complex logic that needs explanation, or when the
code is not self-explanatory.

if there are large sections of code such as adapters from the same client, endpoints from the resources etc..., I like to group them together using section dividers or "block comments" such as the Following.

```python
from automation_engine.infrastructure.router.app import app
import automation_engine.use_cases.schema as schema
import automation_engine.use_cases.use_cases as use_cases
import automation_engine.infrastructure.adapters as adapters
from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse

# =========================#
#                          #
#   TICKTICK OAuth2        #
#                          #
# =========================#


# Register and update the application with TickTick
# https://developer.ticktick.com/manage
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
    token_data = use_cases.oauth_callback_use_case(adapters.TickTickConnectorAdapter(), code)
    return token_data


# =======================#
#                        #
#   MENDELEY Oauth2      #
#                        #
# =======================#


# Register and update the application with Mendeley
# https://dev.mendeley.com/myapps.html#access_token=MSwxNzEyNDE3NjUxNzY2LDc1MjY4Mzg1MSw3MTIsYWxsLCwsZjFiYzMyMDI1MTYzZDI0NDRlOTk2YzQzNmU4MWYyNmY2ZThiZ3hycWIsZGU4MmQ3ZTUtN2E5ZS0zZjYwLTliZGMtZGEyYjNmMmNkZTNlLFpUNWd5QnR4SmZmR3haRHk1dUJwZmMyZDUwbw
@app.get("/mendeley/login")
def mendeley_login(request: Request):
    state = "some_random_state_string"
    request.session["state"] = state
    url = use_cases.oauth_login_use_case(adapters.MendeleyConnectorAdapter(), state)
    return RedirectResponse(url=url)


@app.get("/mendeley/callback")
async def mendeley_callback(request: Request, code: str, state: str):
    if state != request.session.get("state"):
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    use_cases.oauth_callback_use_case(adapters.MendeleyConnectorAdapter(), code)
    return RedirectResponse(url="/docs")
```

### 2.3. Expressions and Statements

when you have complex expressions or statements store their contents in a variable

```python
def calculate_price_if_available(product, quantity):
    """
    Calculate the price if the product is available.

    Parameters
    ----------
    product : Product
        The product to check.
    quantity : int
        The quantity of the product.

    Returns
    -------
    float
        The total price if available, otherwise None.
    """
    product_is_available = product.qty > 0 and product.prices is not None and product.prices.get('price') is not None
    if product_is_available:
        total_price = product.prices['price'] * quantity
        return total_price
    else:
        print("Product is not available or price is not set.")
    return None
```

additionally, use guard clauses to avoid deep nesting of if statements, for instance:

```python
def process_order(order):
    """
    Process the order if it is valid.

    Parameters
    ----------
    order : Order
        The order to process.

    Returns
    -------
    str
        A message indicating the result of the order processing.
    """
    if not order.is_valid():
        return "Order is invalid."

    if not order.has_items():
        return "Order has no items."

    print("Processing order...")
    return "Order processed successfully."
```

### 2.4. Data classes and States

when writing code, we want to constrain the possible state of the programme. This can
be done by enforcing a particular structure for dynamic types such as string and
dictionaries.

As such for any dictionaries within our programme, store them using a dataclass
(pydantic or dataclass)

```python
from pydantic import BaseModel

class ProductPrices(BaseModel):
    price: float
    discount: float = 0.0

class Product(BaseModel):
    id: int
    name: str
    qty: int
    prices: ProductPrices
```

and for strings or numbers, especially when they represent a specific state or
status code etc.. use an enum to define the possible values:

```python
from enum import Enum
class OrderStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
```

### 2.5. Importing Libraries

when importing libraries import them as follows:

```python
import typing

def foo(test) -> typing.Any:
    pass

import abc

class MyClass(abc.ABC):
    @abc.abstractmethod
    def my_method(self):
        pass

# even importing internal modules should follow the same pattern
import domain.entities as entities
import use_cases.schema as schema
import infrastructure.ports as ports
# etc...
```

## 3. Testing Strategy

Always write tests when implementing new features or fixing bugs. Only test at the
interface between different layers:

- if you implement a new use cases, create a test in the `tests/test_use_cases.py`
  file
- if you implement a new adapter, create a test in the `tests/test_adapters.py` file
- if you implement a new router, create a test in the `tests/test_routers.py` file

this is not required for interfaces and dataclasses such as ports, adapters, entities
and messages as well as external libraries such as SQLAlchemy, FastAPI, etc.

whenever you have a new bug, write a test that reproduces the bug in the
`tests/test_bugs.py` file, then fix the bug and keep the test to ensure that the bug
does not reappear in the future.
