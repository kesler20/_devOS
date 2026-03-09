from __future__ import annotations
import typing
from functools import wraps
import typing
from typing import Callable
import pydantic
from concurrent.futures import ThreadPoolExecutor

T = typing.TypeVar("T")  # Generic Type variable for items in the array
V = typing.TypeVar("V")


class array(typing.Generic[T]):
    """This is an array which can be used for building pipelines.

    # Example
    ```python

    # Build a pipeline
    pipeline = array(1,2,3,4,5).reverse().insert(2,10).sort().append(5).sum().build(0)
    print(pipeline)

    # OUTPUT: 30

    # Debugging the pipeline
    debug_array = array(list(i for i in range(20)))
    debug_array.set_debug(True)
    print(debug_array.reverse().insert(0, 10))

    # You can also initialise an empty array
    empty_array = array()
    print(empty_array.append(1).append(2).append(3).build())

    # Example of validating, filtering, sorting, reversing, and building in one pipeline
    from pydantic import BaseModel, ValidationError

    class User(BaseModel):
        name: str
        age: int

    users = array(
        {"name": "Alice", "age": 20},
        {"name": "Bob", "age": 30},
        {"name": "Carol", "age": 40},
        {"name": "Dave", "age": 25}
    )

    try:
        result = (
            users
            .validate(User)  # Validate each dict as a User
            .filter(lambda user: user.age > 25)  # Keep users older than 25
            .sort(lambda user: user.age)         # Sort by age ascending
            .reverse()                           # Reverse the order
            .build()                             # Get the final list
        )
        print(result)
    except ValidationError as e:
        print(e)
    ```

    # Output
    ```txt
    [User(name='Carol', age=40), User(name='Bob', age=30)]
    ```
    """

    debug_active = False  # Class attribute to control debugging

    def __init__(self, *args: T) -> None:
        if len(args) == 0:
            self.items: typing.List[T] = []
        elif len(args) == 1 and isinstance(
            args[0], (list, tuple, set)
        ):  # Check if arg is a list or tuple
            self.items = list(args[0])  # Cast args[0] to List[T]
        else:
            self.items = [arg for arg in args]

    def __str__(self) -> str:
        item_strs = []
        for item in self.items:
            try:
                # Attempt to convert the item to a string representation
                item_strs.append(str(item))
            except Exception as e:
                # If an error occurs, append a placeholder or a simplified representation
                item_strs.append(f"<Unrepresentable Object: {e}>")
        return "[" + ", ".join(item_strs) + "]"

    def __repr__(self) -> str:
        return f"""{self.items}"""

    @classmethod
    def activate_debug_mode(cls):
        cls.debug_active = True

    @staticmethod
    def debug(func):
        @wraps(func)
        def wrapper_debug(self: array[T], *args, **kwargs):
            if self.__class__.debug_active:
                safe_items_str = ", ".join(self.safe_repr(item) for item in self.items)
                print(f"[BEFORE] 🔻: {func.__name__}: [{safe_items_str}]", "\n")
            result = func(self, *args, **kwargs)
            if self.__class__.debug_active:
                safe_items_str = ", ".join(self.safe_repr(item) for item in self.items)
                print(f"[AFTER] ✅: {func.__name__}: [{safe_items_str}]", "\n")
            return result

        return wrapper_debug

    def safe_repr(self, item) -> str:
        try:
            return repr(item)
        except Exception as e:
            return f"<Unrepresentable Object: {e}>"

    @debug
    def map(self, foo: typing.Callable[[T], T]) -> array[T]:
        self.items = list(map(foo, self.items))
        return self

    @debug
    def filter(self, foo: Callable[[T], bool]) -> array[T]:
        self.items = list(filter(foo, self.items))
        return self

    @debug
    def sum(self) -> array[T]:
        self.items = [sum(self.items)]  # type: ignore
        return self

    @debug
    def max(self, key: typing.Optional[typing.Callable[[T], bool]] = None):
        if key:
            self.items = [max(self.items, key=key)]
        else:
            self.items = [max(self.items)]  # type: ignore
        return self

    @debug
    def append(self, item: T) -> array[T]:
        self.items.append(item)
        return self

    @debug
    def insert(self, index: int, item: T) -> array[T]:
        self.items.insert(index, item)
        return self

    @debug
    def extend(self, iterable: typing.Iterable[T]) -> array[T]:
        self.items.extend(iterable)
        return self

    @debug
    def validate(self, schema: typing.Type[V]) -> "array[V]":
        validated_items: typing.List[V] = []
        for item in self.items:
            # Assuming each item is a dict that can be unpacked into the Pydantic model
            try:
                if isinstance(item, dict):
                    validated_item = schema(**item)
                elif isinstance(item, schema):
                    validated_item = item
                else:
                    raise TypeError(
                        f"Item must be a dict or {schema.__name__} instance, got {type(item)}"
                    )
                validated_items.append(validated_item)
            except pydantic.ValidationError as e:
                print(
                    "Validation error\n",
                    f"Item: {item}",
                    f"error: {e}",
                    "--------------\n",
                )
                # Handle the validation error (e.g., skip the item, raise an exception, etc.)
        # Return a new array instance with the validated items, now typed as array[V]
        return array(*validated_items)

    @debug
    def remove(self, item: T) -> array[T]:
        self.items.remove(item)
        return self

    @debug
    def pop(self, index: int = -1) -> array[T]:
        self.items = [self.items.pop(index)]
        return self

    @debug
    def apply_in_parallel(self, foo: typing.Callable[[T], T]) -> array[T]:
        with ThreadPoolExecutor() as executor:
            self.items = list(executor.map(foo, self.items))

        return self

    @debug
    def sort(
        self,
        key: typing.Optional[typing.Callable[[T], bool]] = None,
        reverse: bool = False,
    ) -> array[T]:
        self.items.sort(key=key, reverse=reverse)
        return self

    @debug
    def reverse(self) -> array[T]:
        self.items.reverse()
        return self

    @debug
    def for_each(self, foo: typing.Callable[[T], T]) -> array[T]:
        self.items = [foo(item) for item in self.items]
        return self

    @debug
    def flatten(self) -> array[T]:
        def unpack(array_of_arrays) -> typing.List[T]:
            if not isinstance(array_of_arrays, list):
                return [array_of_arrays]

            return [item for sublist in array_of_arrays for item in unpack(sublist)]  # type: ignore

        self.items = unpack(self.items)
        return self

    @debug
    def remove_duplicates(self) -> array[T]:
        self.items = list(set(self.items))
        return self

    def build(
        self, index_of_item: typing.Optional[int] = None
    ) -> typing.Union[T, typing.List[T]]:
        return self.items if index_of_item is None else self.items[index_of_item]
