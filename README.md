
# A simple graphql backend implented in aiohttp

1. imports from stdlib, web-framework, and logging framework
2. configure logging
3. initialize web application and route table
4. configure database connection


```python
from contextlib import contextmanager
import sqlite3
import typing as T
import sys

from aiohttp import web
from aiohttp_graphql import GraphQLView

from IPython import get_ipython

from eliot import start_action, to_file, use_asyncio_context



# set up logging

use_asyncio_context()

to_file(open('log.json', 'w'))

_ipython = str(type(get_ipython()))

in_jupyter_notebook = 'ipython' in _ipython and not 'zmqshell' in _ipython

if not in_jupyter_notebook:
    # we don't want lots of output in a jupyter notebook
    stdout_destination = to_file(sys.stdout)


# initialize app

app = web.Application()
routes = web.RouteTableDef()

# configure database
connection = sqlite3.connect(':memory:')
# here be dragons
connection.execute('PRAGMA synchronous = OFF')
# avoid globals
app['connection'] = connection
```




    <sqlite3.Cursor at 0x106230ce0>



## Logging shortcuts

Some simple context managers to make logging less verbose


```python
@contextmanager
def log_action(action_type, **kwargs):
    """A simple wrapper over eliot.start_action to make things less verbose."""
    with start_action(action_type=action_type, **kwargs) as action: 
        yield action


@contextmanager
def log_inbound_request(request, **kwargs):
    """A logging shortcut for when we receive requests."""
    with log_action(
        'inbound request',
        
        method=request.method,
        resource=str(request.rel_url),
        https_enabled=request.secure,
        from_ip=request.remote,
        
        **kwargs
        
    ) as action:
        
        yield action
```

## Brief aiohttp route/view example w/eliot logging

Two simple view coroutines decorated with their routes

Note, aiohttp also allows one to add routes and related views without
the use of decorators as flask does

```python3

app.router.add_route('GET', '/', index)
# or
app.router.add_get('/', index)

```

This is arguably better, if only because you could see
the mapping of all your routes and related views in one
place without resorting to programmatically iterate through the
route table's resource map


```python
@routes.get('/')
async def index(request):
    """Redirect to greet route."""
    with log_inbound_request(request):
        
        url = request.app.router['greet'].url_for(name='you')
        
        with log_action('redirect', to_url=str(url)):
            
            return web.HTTPFound(url)


@routes.get('/greet/{name}', name='greet')
async def greet(request):
    """Say hello."""
    with log_inbound_request(request):
        
        name = request.match_info['name']
                
        with log_action('sending response'):
            
            return web.Response(
                text=f'<html><h2>Hello {name}!</h2><html>',
                content_type='Content-Type: text/html'
            )
```

## Domain Model

Aspects of a **library** in terms of:
* Books
* Authors
* Catalogs


```python
from datetime import date as Date
from enum import Enum
import random

# the PEP 557 future is now
from attr import dataclass
from attr import attrib as field

from mimesis import Generic

# fake data generator
generate = Generic('en')

class Floor(Enum):
    """Describes the floors in the library."""
    Zero = 0
    One = 1
    Two = 2
    Three = 3


@dataclass
class Author:
    first_name: str
    last_name: str
    age: int
        

@dataclass
class Book:
    title: str
    author: Author
    published: Date
        
        
@dataclass
class Catalog:
    genre: str
    floor:  Floor
    books: T.List[Book]
        
```

## Factory functions

For generating fake data


```python
def author_factory(**replace):
    kwargs = dict(
        first_name = generate.personal.name(),
        last_name = generate.personal.last_name(),
        age = generate.personal.age(),
    )
    
    kwargs.update(replace)
    
    return Author(**kwargs)


def book_factory(**replace):
    kwargs = dict(
        title = generate.text.title(),
        author = author_factory(),
        published = generate.datetime.date()
    )
    
    kwargs.update(replace)
    
    return Book(**kwargs)
    
def catalog_factory(**replace):
    kwargs = dict(
        genre = random.choice(('history', 'biography', 'thriller', 'romance')),
        floor = random.choice(tuple(Floor)),
        books = [book_factory() for _ in range(5)]
    )
    
    kwargs.update(replace)
    
    return Catalog(**kwargs)
```

## sql


```python
## create the tables

CREATE_TABLES = """

CREATE TABLE IF NOT EXISTS author(
    id         INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    first_name TEXT NOT NULL,
    last_name  TEXT NOT NULL,
    age        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS book(
    id        INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    published TEXT NOT NULL,
    author_id INTEGER NOT NULL REFERENCES author(id)

);

CREATE TABLE IF NOT EXISTS catalog(
    id    INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    genre TEXT NOT NULL,
    floor INTEGER CHECK (floor IN (0, 1, 2, 3)) NOT NULL
    
);

CREATE TABLE IF NOT EXISTS catalog_book(
    catalog_id INTEGER NOT NULL REFERENCES catalog(id),
    book_id    INTEGER NOT NULL REFERENCES book(id)
);

"""

connection.executescript(CREATE_TABLES)
```




    <sqlite3.Cursor at 0x106b81490>




```python
# seed the db
```

## graphql schema definition


```python
import graphene

class Query(graphene.ObjectType):
    hello = graphene.String(description='A typical hello world')

    def resolve_hello(self, info):
        return 'World'

schema = graphene.Schema(query=Query)

query = '''
    query SayHello {
      hello
    }
'''

dict(schema.execute(query).data)
```




    {'hello': 'World'}



## rest routes/views


```python
## code
```

## graphql routes/view


```python
gql_view = GraphQLView(schema=schema, graphiql=True)
app.router.add_route('*', '/graphql', gql_view, name='graphql')
```




    <ResourceRoute [*] <PlainResource 'graphql'  /graphql -> <function AbstractRoute.__init__.<locals>.handler_wrapper at 0x106bf3510>




```python
# add routes from decorators
app.router.add_routes(routes)


# if __name__ == '__main__':    
#     web.run_app(app, host='127.0.0.1', port=8080)

```
