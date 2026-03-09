
## 1. Overview

objects can take two fundamental forms
data classes
behavioural classes

data classes are used primarily to store data using fields
behavioural classes have attributes which represent the state that can be changed through their methods. (this is a description of the visitor pattern)

we don't believe in inheritance (only inherit the classes to give the class behaviour as we will show below) therefore no Inheritance and Polymorphism, but we subscribe to abstraction, composition & encapsulation

when writing programmes, try to identify all the dataclasses first and then implement methods for these data classes to transform and expose the data via the tell don't ask principles. For instance, if you have a behavioural class and you need to check if the account is valid, instead of writing an expression using the properties of the account object to check if its valid, you can create a method called `is_accound_valid` in the account dataclass and call if from the function or behavioural class.
### 1.1 Two Types of Classes
#### 1.1.1 data classes 
- **domain entities** (or data access objects (DAO)) can inherit from ORMs or dataclass (when you don't really save them) 
	- try to use private fields & methods by default and only expose fields that are required via setters and getters? if you also inject business rules this should make it more robust?
- **Messages or Events** (inherit from Pydantic)
- **ports** inherit from interfaces 
- **state machines**, codes & nomenclature (inherit from enums) 

#### 1.1.2 Behavioural Classes
- **use cases or interactors** or Controller (from [[Boundary Controller Entity (BCE) or Entity Boundary Interactor (EBI)]]), or Command (from design patterns) 
	- they usually only expose the execute method and provide functionality to the consumer of the application 
	- the difference between UseCases and Services is that the service can have more functionality (it can be added when you need to provide a totally new service) and can have the run function (they can abstract away more complex services such as ). UseCases are more atomic, such as (RegisterNodeToGraph) etc.. at the start use Services but if they get too large, break them down into UseCases
- **business rules** (these are functions that can be passed to the DTOs or handlers or data classes to validate the quality of the data being passed or apply some transformations/formatting that are predefined across the architecture, i.e. formatting an enpoint, a name or checking that the age is not negative) 
- **ports or interfaces** (implement these when you have more than one adapter implementing a piece of infrastructure for the same functionality) make sure that you fill in the signature primarily here (such that the adapters will not need to) as this will hold the single source of truth of the signature (use the ABC). When you write an adapter you don't need to write the signature, the signature should
be managed by the port such that you have a single source of truth
- **Handlers** (this is in event-driven applications where you have a handler that handles an event, such as a message from a queue or an event from a user interface, these are usually used to decouple the application from the infrastructure and allow for more flexibility in the application)
- **Repositories** (these are classes that implement the data access layer, they can be used to abstract away the data access logic from the application, they can be used to implement the data access layer for the domain entities, they can also be used to implement the data access layer for the use cases)
 - **Data transfer objects (DTOs)** or boundary or contract/schema
 - **Adapters** (classes that implement external APIs or infrastructure used by the application, or they interact with legacy systems outside of our system boundary)
 
**use template** classes to reuse code via composition
**use mediator** to hold the state of a chaotic data flow
**use observers** and event handlers (Chain of Responsibility) in event driven applications
**use factory** when you have to generate an object depending on upstream state (i.e. generate different buttons depending on user settings)
**use builder** when you need to dynamically compose an output/object (i.e .. a dashboard builder)
**use singletone** when you need to have a single source of truth in your programme (such as user credentials, database connection, user settings etc...)
**use small interfaces** (do not force the class to implement stuff it won't use)
**use composition** (dependency injection)
**use single responsibility** (ensure that every class has only one reason for changing)

>[!tip] Are you using the correct jargon?
>think a lot about the language and ensure that is understandable in the problem domain
> avoid using handler, platform, processor, engine, executor, manager, service

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
Only add side Effects when the function has side effects such as logging, printing,
write Examples for complex functions that are not self-explanatory.

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

