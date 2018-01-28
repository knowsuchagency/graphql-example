
# coding: utf-8

# # A simple graphql backend implented in aiohttp

# ## Installation - requires Python 3.6
# 
# `pip install graphql-example`
# 
# ### to run the web-app
# 
# `graphql_example runserver`
# 
# Restful endpoints
# ---
# 
# http://localhost:8080/rest/author/{id}
# 
# http://localhost:8080/rest/author?limit=5
# 
# http://localhost:8080/rest/book/{id}
# 
# http://localhost:8080/rest/book?limit=7
# 
# Graphql endpoint
# http://localhost:8080/graphql
# 

# 1. imports from stdlib, web-framework, and logging framework
# 2. configure logging
# 3. initialize web application and route table
# 4. configure database connection

# In[1]:


# package imports

# why all the try excepts?
# because weird stuff happens
# when this code is executed from a jupyter
# notebook vs as a module vs as __main__

from functools import partial
import typing as T
import sqlite3

import pkg_resources

try:
    from graphql_example.logging_utilities import *
except ModuleNotFoundError:
    from logging_utilities import *

try:
    from graphql_example.on_startup import (
    configure_logging,
    configure_database,
    create_tables,
    seed_db
)
except ModuleNotFoundError:
    from on_startup import (
        configure_logging,
        configure_database,
        create_tables,
        seed_db
    )


try:
    from graphql_example.on_cleanup import drop_tables, close_db
except:
    from on_cleanup import drop_tables, close_db
    
try:
    from graphql_example.db_queries import fetch_authors, fetch_books
except ModuleNotFoundError:
    from db_queries import fetch_authors, fetch_books
    
    
from aiohttp_graphql import GraphQLView
from aiohttp import web


# ## Brief aiohttp route/view example w/eliot logging
# 
# Two simple view coroutines decorated with their routes
# 
# aiohttp also allows one to add routes and related views without
# using decorators or explicitly as such
# 
# ```python3
# 
# app.router.add_route('GET', '/', index)
# # or
# app.router.add_get('/', index)
# 
# ```
# 
# which is arguably better, if only because you could see
# the mapping of all your routes and related views in one
# place without resorting to programmatically iterate through the
# route table's resource map

# In[2]:


#@routes.get('/')
async def index_view(request):
    """Redirect to greet route."""
    with log_request(request):
        
        url = request.app.router['greet'].url_for(name='you')
        
        with log_action('redirect', to_url=str(url)):
            
            return web.HTTPFound(url)


#@routes.get('/greet/{name}', name='greet')
async def greet_view(request):
    """Say hello."""
    with log_request(request):
        
        name = request.match_info['name']
        
        response = web.Response(
                text=f'<html><h2>Hello {name}!</h2><html>',
                content_type='Content-Type: text/html'
            )

        with log_response(response):
            
            return response


# # The model

# In[3]:


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


# # Rest views
# 
# These def the logic for the routes we'll create on our application i.e.
# 
# For a single resource:
# 
# `/rest/author/{id}`
# `/rest/book/{id}`
# 
# Or based on url query parameters:
# 
# `/rest/author?age=42&no_books=true`
# `/rest/book?author_id=3&limit=5`

# In[5]:


async def author(request):
    """Return a single author for a given id."""

    connection = request.app['connection']

    with log_request(request):
        try:
            db_query = partial(
                fetch_authors, connection, id=int(request.match_info['id']))

            author, *_ = await request.loop.run_in_executor(None, db_query)

        except ValueError:
            author = None

        if not author:
            log_message('Author not found', id=request.match_info['id'])
            raise web.HTTPNotFound

    response = web.json_response(author)

    with log_response(response):
        return response


async def book(request):
    """Return a single book for a given id."""

    connection = request.app['connection']

    with log_request(request):
        try:

            db_query = partial(
                fetch_books, connection, id=int(request.match_info['id']))

            book, *_ = await request.loop.run_in_executor(None, db_query)

        except ValueError:
            book = None

        if not book:
            log_message('Book not found', id=request.match_info['id'])
            raise web.HTTPNotFound

    response = web.json_response(book)

    with log_response(response):
        return response


# In[4]:


async def books(request):
    """Return json response of books based on query params."""
    connection = request.app['connection']

    with log_request(request):

        # parse values from query params
        
        title = request.query.get('title')
        published = request.query.get('published')
        author_id = request.query.get('author_id')
        limit = int(request.query.get('limit', 0))
        
        # querying from the database is a potentially blocking function
        # so we run it in an executor

        query_db = partial(fetch_books,
            request.app['connection'],
            title=title,
            published=published,
            author_id=author_id,
            limit=limit)
        
        query_db_task = request.loop.run_in_executor(None, query_db)
        
        books: T.List[dict] = await query_db_task

        response = web.json_response(books)

        with log_response(response):

            return response

async def authors(request):
    """Return json response of authors based on query params."""
    connection = request.app['connection']

    with log_request(request):

        # parse values from query params

        first_name = request.query.get('first_name')
        last_name = request.query.get('last_name')
        age = None or int(request.query.get('age', 0))
        limit = int(request.query.get('limit', 0))
        # client may not want/need book information
        no_books = str(request.query.get('no_books','')).lower().startswith('t')

        query_db = partial(
            fetch_authors,
            request.app['connection'],
            first_name=first_name,
            last_name=last_name,
            age=age,
            limit=limit,
            no_books=no_books
        )
        
        query_db_task = request.loop.run_in_executor(None, query_db)
        
        authors: T.List[dict] = await query_db_task

        response = web.json_response(authors)

        with log_response(response):

            return response


# ## graphql schema definition

# In[6]:


from graphene import relay
import graphene as g
from pprint import pprint


class Author(g.ObjectType):
    """This is a human being."""
    id = g.Int(description='The primary key in the database')
    first_name = g.String()
    last_name = g.String()
    age = g.Int()
    books = g.List(lambda: Book)


class Book(g.ObjectType):
    """A book, written by an author"""
    id = g.Int(description='The primary key in the database')
    title = g.String(description='The title of the book')
    published = g.String(description='The date it was published')
    author = g.Field(Author)


class Query(g.ObjectType):

    db_filename = pkg_resources.resource_filename('graphql_example',
                                                  'library.sqlite')

    connection = sqlite3.connect(db_filename, check_same_thread=False)

    author = g.Field(Author)
    book = g.Field(Book)

    authors = g.List(
        Author,

        # the following will be passed as named
        # arguments to the resolver function

        # sadly, we can't assign None as a default value
        # for any of the arguments

        # graphene's design (not to mention documentation)
        # leaves a lot to be desired
        id=g.Int(),
        first_name=g.String(),
        last_name=g.String(),
        age=g.Int(),
        limit=g.Int(
            description='The amount of results you wish to be limited to'))

    books = g.List(
        Book,
        id=g.Int(),
        title=g.String(),
        published=g.String(),
        author_id=g.Int(
            description='The unique ID of the author in the database'),
        limit=g.Int(description='The amount of results you with to be limited to'))

    def resolve_books(self,
                      info,
                      id=None,
                      title=None,
                      published=None,
                      author_id=None,
                      limit=None):

        fetched = fetch_books(
            Query.connection,
            id=id,
            title=title,
            published=published,
            author_id=author_id,
            limit=limit)

        books = []

        for book_dict in fetched:

            author = Author(
                id=book_dict['author']['id'],
                first_name=book_dict['author']['first_name'],
                last_name=book_dict['author']['last_name'],
                age=book_dict['author']['age'])

            book = Book(
                id=book_dict['id'],
                title=book_dict['title'],
                published=book_dict['published'],
                author=author)

            books.append(book)

        return books

    def resolve_authors(self,
                        info,
                        id=None,
                        first_name=None,
                        last_name=None,
                        age=None,
                        limit=None):

        fetched = fetch_authors(
            Query.connection,
            id=id,
            first_name=first_name,
            last_name=last_name,
            age=age,
            limit=limit)

        authors = []

        for author_dict in fetched:

            books = [
                Book(id=b['id'], title=b['title'], published=b['published'])
                for b in author_dict['books']
            ]

            author = Author(
                id=author_dict['id'],
                first_name=author_dict['first_name'],
                last_name=author_dict['last_name'],
                age=author_dict['age'],
                books=books)

            authors.append(author)

        return authors


schema = g.Schema(query=Query, auto_camelcase=False)


# In[7]:


def app_factory(*args, db=':memory:', logfile='log.json', **config_params):

    # initialize app
    app = web.Application()

    # set top-level configuration
    app['config'] = {}
    for key, value in config_params.items():
        app['config'][key] = value

    # startup
    app.on_startup.append(configure_logging)
    app.on_startup.append(configure_database)
    app.on_startup.append(create_tables)
    app.on_startup.append(seed_db)

    # example routes
    app.router.add_get('/', index_view)
    app.router.add_get('/greet/{name}', greet_view, name='greet')
    # rest routes
    app.router.add_get('/rest/author/{id}', author)
    app.router.add_get('/rest/authors', authors)
    app.router.add_get('/rest/book/{id}', book)
    app.router.add_get('/rest/books', books)

    # graphql view/route
    gql_view = GraphQLView(schema=schema, graphiql=True, enable_async=True)

    app.router.add_route(
        '*',
        '/graphql',
        gql_view,
    )

    # cleanup
    app.on_cleanup.append(drop_tables)
    app.on_cleanup.append(close_db)

    return app


if __name__ == '__main__':

    app = app_factory()

    web.run_app(app, host='127.0.0.1', port=8080)

