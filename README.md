
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

import aiohttp
from aiohttp import web
from aiohttp_graphql import GraphQLView

from IPython import get_ipython

from eliot import (
    start_action,
    Message,
    to_file,
    use_asyncio_context
)
```


```python
# set up logging

use_asyncio_context()

to_file(open('log.json', 'w'))

_ipython = str(type(get_ipython()))

in_jupyter_notebook = 'ipython' in _ipython or 'zmqshell' in _ipython

if not in_jupyter_notebook:
    # we don't want lots of output in a jupyter notebook
    stdout_destination = to_file(sys.stdout)
```


```python
# initialize app

app = web.Application()
routes = web.RouteTableDef()

# configure database
connection = sqlite3.connect('library.sqlite')
# here be dragons
connection.execute('PRAGMA synchronous = OFF')
# avoid globals
app['connection'] = connection
```




    <sqlite3.Cursor at 0x10918cf10>



## Logging shortcuts

Some simple context managers to make logging less verbose


```python
@contextmanager
def log_action(action_type: str, **kwargs):
    """A simple wrapper over eliot.start_action to make things less verbose."""
    with start_action(action_type=action_type, **kwargs) as action: 
        yield action


@contextmanager
def log_request(request: aiohttp.web.Request, **kwargs):
    """A logging shortcut for when we receive requests."""
    with log_action(
        'processing request',
        
        method=request.method,
        resource=str(request.rel_url),
        https_enabled=request.secure,
        from_ip=request.remote,
        query=dict(request.query) or None,
        
        **kwargs
        
    ) as action:
        
        yield action

@contextmanager
def log_response(response: aiohttp.web.Response, **kwargs):
    with log_action(
        'sending response',
        
        status=response.status,
        headers=dict(response.headers),
        
        **kwargs
        
    ) as action:
        
        yield action
        
def log_message(message: str, **kwargs):
    """Log the message in the current action context."""
    Message.log(message_type=message, **kwargs)
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
    with log_request(request):
        
        url = request.app.router['greet'].url_for(name='you')
        
        with log_action('redirect', to_url=str(url)):
            
            return web.HTTPFound(url)


@routes.get('/greet/{name}', name='greet')
async def greet(request):
    """Say hello."""
    with log_request(request):
        
        name = request.match_info['name']
        
        response = web.Response(
                text=f'<html><h2>Hello {name}!</h2><html>',
                content_type='Content-Type: text/html'
            )
                
        with log_response(response):
            
            return response
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
import attr


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
    books: T.Optional[T.List['Book']]
        

@dataclass
class Book:
    title: str
    author: Author
    published: Date
        
        
@dataclass
class Catalog:
    genre: str
    floor:  Floor
    books: T.Optional[T.List[Book]]
        
```

## Factory functions

For generating fake data


```python
from mimesis import Generic

# fake data generator
generate = Generic('en')


def author_factory(**replace):
    kwargs = dict(
        first_name = generate.personal.name(),
        last_name = generate.personal.last_name(),
        age = generate.personal.age(),
        books = None
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
        books = None
    )
    
    kwargs.update(replace)
    
    return Catalog(**kwargs)
```

## sql


```python
## create the tables

async def create_tables(app):
    print('creating tables')

    CREATE_TABLES = """

    CREATE TABLE IF NOT EXISTS author(
        id         INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
        first_name TEXT NOT NULL,
        last_name  TEXT NOT NULL,
        age        INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS book(
        id        INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
        title     TEXT NOT NULL,
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

    app['connection'].executescript(CREATE_TABLES)
    
    print('tables created')
```


```python
# seed the db

async def seed_db(app):
    print('seeding database')

    connection = app['connection']

    authors: T.Tuple[T.Tuple] = tuple(
        (a.first_name, a.last_name, a.age)
        for a in (author_factory() for _ in range(200)))

    with connection:
        # insert 200 authors
        connection.executemany(
            'INSERT INTO author (first_name, last_name, age) VALUES (?, ?, ?)',
            authors)

        # insert 500 books
        author_ids = tuple(
            row[0] for row in connection.execute('SELECT id FROM author'))

        books = ((book.title, book.published, random.choice(author_ids))
                 for book in (book_factory() for _ in range(500)))

        connection.executemany(
            'INSERT INTO book (title, published, author_id) VALUES (?, ?, ?)', books)

        # insert 50 catalogs
        catalogs = ((c.genre, c.floor.value)
                    for c in (catalog_factory() for _ in range(50)))

        connection.executemany(
            'INSERT INTO catalog (genre, floor) VALUES (?, ?)', catalogs)

    print('database seeded')

```


```python
@routes.get('/author')
async def author(request):

    connection = request.app['connection']

    with log_request(request):

        # parse values from query params
        
        id = None or int(request.query.get('id', 0))
        first_name = request.query.get('first_name')
        last_name = request.query.get('last_name')
        age = None or int(request.query.get('age', 0))
        limit = int(request.query.get('limit', 0))

        # build sql query
        
        id_query = 'select * from author where id = ?'
        first_name_query = 'select * from author where first_name = ?'
        last_name_query = 'select * from author where last_name = ?'
        age_query = 'select * from author where age = ?'

        value_query = (
            (id, id_query),
            (first_name, first_name_query),
            (last_name, last_name_query),
            (age, age_query),
        )

        query_string = ' UNION '.join(
            query for value, query in value_query if value if not None)

        # select all authors if query string is empty

        query_string = query_string if query_string else 'select * from author'

        # limit

        if limit:
            query_string += f' limit {limit}'

        # the iterator of values to be passed to the query string

        values = tuple(v for v, q in value_query if v)

        with log_action('querying authors table', sql=query_string, params=values):

            with connection:
                if values:
                    rows = connection.execute(query_string, values)
                else:
                    rows = connection.execute(query_string)
        
            authors = [
                {
                    'id': id,
                    'first_name': first_name,
                    'last_name': last_name,
                    'age': age
                } for id, first_name, last_name, age in rows
            ]
            
        
        # get books
        
#         book_sql_query = 'select (title, published, author_id) from book where author_id = ?'
        
#         with log_action('querying books table', sql=book_sql_query):
            
#             with connection:
#                 ids = (author['id'] for author in authors)
#                 rows = connection.execute_many(book_sql_query, ids)
        
#             books = list(rows)
        
        
#         # update authors
#         # this is all bad
        
        
#         authors = [
#             {
#                 'id': author['id'],
#                 'first_name': author['first_name'],
#                 'last_name': author['last_name'],
#                 'books': [
#                     {
#                         'title': title,
#                         'published': published
#                     } for title, published, author_id in books
#                       if author_id == author_id
#                 ]
#             } for author in authors
#         ]

        response = web.json_response(authors)

        with log_response(response):

            return response

```


```python
@routes.get('/book')
async def book(request):

    connection = request.app['connection']

    with log_request(request):

        # parse values from query params
        
        id = None or int(request.query.get('id', 0))
        published = request.query.get('published')
        author_id = request.query.get('author_id')
        limit = int(request.query.get('limit', 0))
        

        # build sql query
        
        id_query = 'select * from book where id = ?'
        published_query = 'select * from book where published = ?'
        author_id_query = 'select * from book where author_id = ?'

        value_query = (
            (id, id_query),
            (published, published_query),
            (author_id, author_id_query),
        )

        query_string = ' UNION '.join(
            query for value, query in value_query if value if not None)

        # get all books if empty query string

        query_string = query_string if query_string else 'select * from book'

        # limit

        if limit:
            query_string += f' limit {limit}'

        # the iterator of values to be passed to the query string

        values = tuple(v for v, q in value_query if v)

        with log_action('querying db', sql=query_string, params=values):

            with connection:
                if values:
                    rows = connection.execute(query_string, values)
                else:
                    rows = connection.execute(query_string)

        books = [
            {
                'id': id,
                'published': published,
                'author_id': author_id
            } for id, published, author_id in rows
        ]

        response = web.json_response(books)

        with log_response(response):

            return response
```


```python
@routes.get('/catalog')
async def catalog(request):

    connection = request.app['connection']

    with log_request(request):

        # parse values from query params
        
        id = None or int(request.query.get('id', 0))
        published = request.query.get('published')
        author_id = request.query.get('author_id')
        limit = int(request.query.get('limit', 0))
        

        # build sql query
        
        id_query = 'select * from book where id = ?'
        published_query = 'select * from book where published = ?'
        author_id_query = 'select * from book where author_id = ?'

        value_query = (
            (id, id_query),
            (published, published_query),
            (author_id, author_id_query),
        )

        query_string = ' UNION '.join(
            query for value, query in value_query if value if not None)

        # get all books if empty query string

        query_string = query_string if query_string else 'select * from book'

        # limit

        if limit:
            query_string += f' limit {limit}'

        # the iterator of values to be passed to the query string

        values = tuple(v for v, q in value_query if v)

        with log_action('querying db', sql=query_string, params=values):

            with connection:
                if values:
                    rows = connection.execute(query_string, values)
                else:
                    rows = connection.execute(query_string)

        books = [
            {
                'id': id,
                'published': published,
                'author_id': author_id
            } for id, published, author_id in rows
        ]

        response = web.json_response(books)

        with log_response(response):

            return response
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

## graphql route/view


```python
gql_view = GraphQLView(schema=schema, graphiql=True)

app.router.add_route('*', '/graphql', gql_view, name='graphql')
```




    <ResourceRoute [*] <PlainResource 'graphql'  /graphql -> <function AbstractRoute.__init__.<locals>.handler_wrapper at 0x109af7f28>




```python
# add routes from decorators
app.router.add_routes(routes)

# create tables and seed the database
app.on_startup.append(create_tables)
app.on_startup.append(seed_db)

# drop tables
async def drop_tables(app):
    print('dropping table')
    
    connection = app['connection']
    
    with connection:
        connection.executescript("""
        DROP TABLE author;
        DROP TABLE book;
        DROP TABLE catalog;
        DROP TABLE catalog_book;
        """)
    
    print('tables dropped')

app.on_cleanup.append(drop_tables)

# close the database connection on shutdown
async def close_db(app):
    print('closing database connection')
    app['connection'].close()
    print('database connection closed')
    
app.on_cleanup.append(close_db)


if __name__ == '__main__':
    
    stdout_destination = to_file(sys.stdout)
    
    web.run_app(app, host='127.0.0.1', port=8080)

```

    creating tables
    tables created
    seeding database
    database seeded
    ======== Running on http://127.0.0.1:8080 ========
    (Press CTRL+C to quit)

