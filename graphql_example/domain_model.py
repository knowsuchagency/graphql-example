import typing as T
from datetime import date as Date

# the PEP 557 future is now
from attr import dataclass


@dataclass
class Author:
    first_name: str
    last_name: str
    age: int
    books: T.Optional[T.List['Book']]


@dataclass
class Book:
    title: str
    author: Author
    published: Date
