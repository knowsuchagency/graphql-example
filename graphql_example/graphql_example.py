
# coding: utf-8

# In[8]:


# package imports

# why all the try excepts?
# because weird stuff happens
# when this code is executed from a jupyter
# notebook vs as a module vs as __main__

from functools import partial
from datetime import date as Date
import asyncio
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

from graphql.execution.executors.asyncio import AsyncioExecutor
from aiohttp_graphql import GraphQLView
from aiohttp import web

import markdown


# # graphql + aiohttp

# [**slideshow**](http://nbviewer.jupyter.org/format/slides/github/knowsuchagency/graphql-example/blob/master/graphql_example/graphql_example.ipynb?flush_cache=true#/)

# ## Installation - requires Python 3.6
# 
# preferably within a virtualenv:
# 
# `pip3 install graphql-example`
# 
# ### to run the web-app
# 
# (after pip install)
# 
# `graphql_example runserver`
# 
# ### to run tests
# 
# ```
# git clone https://github.com/knowsuchagency/graphql-example
# pip3 install .[dev]
# fab test
# ```

# ### In the beginning... there was REST.

# Really Genesis, shortly thereafter followed by SOAP

# ### The Model

# Let's say we had a simple data model such as the following:
# 
# 

# In[2]:


class Author:
    first_name: str
    last_name: str
    age: int
    books: T.Optional[T.List['Book']]


class Book:
    title: str
    author: Author
    published: Date


# In a RESTful server, the endpoints used to retrieve that data might look something like this:
# 
# ---
# 
# /rest/author/{id}
# 
# /rest/authors?limit=5?otherParam=value
# 
# /rest/book/{id}
# 
# /rest/books?author="Jim"

# ### What's wrong with this?

# Well, let's say on the client-side, we wanted to retrieve a set of authors using a query like
# 
# `/rest/authors?age=34`
# 
# We may get a structure like the following
# 
# ```
# [
#     {
#         "first_name": "Amy",
#         "last_name: "Jones",
#         "age": 34,
#         "books": [{...}]
#     } ...
# ]
# ```

# However, maybe we're unconcerned with the books field, for any of the authors for this particular query,
# and all that extra information seems to be slowing down the rate at which the page loads, either because of unnecessary database calls on the server side, or the extra time it takes for the client to process the json returned from the server.
# 
# To mitigate this problem, maybe we add another filter to the authors endpoint to remove that field from the result like so `/rest/authors?age=34&no_books=true`
# 
# Great, so now we get something like the following
# 
# ```
# [
#     {
#         "first_name": "Amy",
#         "last_name: "Jones",
#         "age": 34,
#     } ...
# ]
# ```

# We still have some things to consider...
# 
# * What happens if we type `/rest/authors?age=34&no_books=True` or `/rest/authors?age=34&no_books=t`? In general, how do we define and interpret the arguments passed as query params and how to we enforce that contract with our clients and give them helpful feedback when mistakes are made?
# * What happens if we have a similar query to the one above, where we ARE interested in the book information for a given author, but only a subset of that data, such as `title`, but not `published`? Seems hardly worth creating another filter. We'll probably just suck it up and retrieve all the data in the book field and ignore what isn't needed on the client side.

# ### General considerations with REST
# 
# * How do we handle different data types and serialization between the client server for complex data types?
# * How do we ensure that our rest api documenation is up-to-date? How do we ensure it's documented at all?
# * How do we communicate to the client what data can be retrieved from the server a la HATEAOS? Again, this is something that's often not implented. We leave it up to backend engineers to document their API which ... yeah.
# * Under-fetching, Over-fetching, n+1

# ### Solutions have been proposed
# 
# Standards
# 
# * [JSON-API](http://jsonapi.org/)
# * [OData](http://www.odata.org/)
# * [Falcor](https://github.com/Netflix/falcor)
# * [GraphQL](https://github.com/facebook/graphql)
# 
# Frameworks
# 
# * [Eve](http://python-eve.org/)
# * [apistar](https://github.com/encode/apistar)
# * [hug](https://github.com/timothycrosley/hug)
# * [graphene](http://graphene-python.org/)

# ### What makes GraphQL different?

# **Buzz**
# 
# ![buzz](https://i.imgur.com/zE4WD0C.jpg)

# But really, GraphQL is first-and-foremost a declarative language specification for client-side data fetching. 
# 
# And, despite the snark, the buzz is important. GraphQL is created and backed by Facebook, and there is a rapidly growing community and ecosystem of libraries that make GraphQL compelling over other standards like JSON-API, Falcor, or OData.
# 
# GraphQL is a way of maintaining the contract between client and server as to what data can be sent or received and in what form.
# 
# Still, it's up to the backend engineer to correctly implement the spec, so it's not magic.

# Assuming the client is guaranteed to use GraphQL and the server is spec-compliant, however, there are several benefits beyond the server being self-documenting.
# 
# On the server-side, having the client describe the specific shape of data it wants can allow the server to make smarter decisions as to how to serve that data i.e. re-shaping SQL expressions or batching database queries.
# 
# On the client-side, it's great just to be able to introspect what's available and have a well-defined way of communicating with the server. Since the server will communicate what type of data can be sent/received, the client doesn't need to worry that the api documentation isn't up-to-date or doesn't exist.

# # Server
# 
# ---
# 
# ## Show me the code!
# 
# 
# We're going to implement a backend server that has a couple RESTful endpoints and one written in GraphQL to demonstrate our earlier points.
# 
# The framework we'll use to build our server will be [aiohttp](https://aiohttp.readthedocs.io/en/stable/), which works on top of asyncio. This will allow us to write our `views` or `controllers` (depending on how one interprets MVC) using co-routines. This means requests can be processed asynchronously without resorting to muti-tenant architecture or multi-threading. We can write asynchronous code and leverage the full power of asyncio's event loop. Cool.

# ## aiohttp views
# 
# aiohttp also allows one to add views to routes
# using decorators or explicitly i.e.
# 
# ```python3
# from aiohttp import web
# 
# app = web.Application()
# routes = web.RouteTableDef()
# 
# @routes.get('/get')
# async def index(request):
#     ...
#     
# #or
# 
# app.router.add_route('GET', '/', index)
# 
# # or
# 
# app.router.add_get('/', index)
# 
# ```

# In[9]:


template = """
# Welcome to the example page

## Rest routes

### Authors

For an individual author:

[/rest/author/{{id}}](/rest/author/1)

To query authors:

[/rest/authors?age={{number}}&limit={{another_number}}](/rest/authors?limit=3)

The following can be passed as query parameters to authors:

    limit: The amount of results you wish to be limited to
    age: The age of the author, as an integer
    first_name: The first name of the author as a string
    last_name: The last name of the author as a string
    no_books: Removes the {{books}} field from the resulting authors

### Books

For an individual book:

[/rest/book/{{id}}](/rest/book/1)

To query books:

[/rest/books?author_id={{number}}&limit={{another_number}}](/rest/books?limit=3)

The following can be passed as query parameters to books:

    limit: The amount of results you wish to be limiited to
    title: The title of the book
    published: The date published in the following format %m/%d/%Y
    author_id: The uuid of the author in the database
    
    
## [GraphQL](/graphql)

"""

html = markdown.markdown(template)


# In[3]:


#@routes.get('/')
async def index(request):
    """Redirect to greet route."""
    # this logging sexiness is a talk for another time
    # but it's a thin wrapper around eliot.start_action
    with log_request(request):

        response = web.Response(
                 text=html,
                 content_type='Content-Type: text/html'
             )
        
    with log_response(response):
        return response


# # Rest views
# 
# These def the logic for the restful routes we'll create on our application i.e.
# 
# For a single resource:
# 
# `/rest/author/{id}`
# 
# `/rest/book/{id}`
# 
# Or based on url query parameters:
# 
# `/rest/authors?age=42&no_books=true`
# 
# `/rest/books?author_id=3&limit=5`

# In[4]:


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


# In[ ]:


async def author(request):
    """Return a single author for a given id."""

    connection = request.app['connection']

    with log_request(request):
        try:
            
            # when using co-routines, it's important that each co-routine be non-blocking
            # meaning no individual action will take a long amount of time, preventing
            # the event loop from letting other co-routines execute
            
            # since our database query may not immediately return, we run it
            # in an "executor" (a thread pool) and await for it to finish
            
            # functools.partial allows us to create a callable that
            # bundles necessary positional and keyword arguments with it
            # print('hello', end=' ') == partial(print, 'hello', end= ' ')()
                        
            db_query = partial(
                fetch_authors, connection, id=int(request.match_info['id']))
            
            # * unpacks an arbitrary number of tuples (see pep-3132)

            author, *_ = await request.loop.run_in_executor(None, db_query)

        except ValueError:
            author = None

        if not author:
            log_message('Author not found', id=request.match_info['id'])
            raise web.HTTPNotFound

    response = web.json_response(author)

    with log_response(response):
        return response


# In[ ]:


async def books(request):
    """Return json response of books based on query params."""
    connection = request.app['connection']

    with log_request(request):

        # parse values from query params
        
        title = request.query.get('title')
        published = request.query.get('published')
        author_id = request.query.get('author_id')
        limit = int(request.query.get('limit', 0))

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


# In[5]:


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


# ## The GraphQL way
# 
# Since we're using [graphene](http://graphene-python.org/), we'll first need to use the library to create a schema describing our data.
# 
# This schema will then tell the library how to implement the GraphQL-compliant endpoint view.

# In[ ]:


import graphene as g
from graphql.execution.executors.asyncio import AsyncioExecutor



class Author(g.ObjectType):
    """This is a human being."""
    id = g.Int(description='The primary key in the database')
    first_name = g.String()
    last_name = g.String()
    age = g.Int()
    # we can't use g.List(Book)
    # directly since it's not
    # yet defined
    books = g.List(lambda: Book)


class Book(g.ObjectType):
    """A book, written by an author."""
    id = g.Int(description='The primary key in the database')
    title = g.String(description='The title of the book')
    published = g.String(description='The date it was published')
    author = g.Field(Author)
    


# In[6]:


async def configure_graphql(app):
    """
    Since our resolvers depend on the app's db connection, this
    co-routine must execute after that part of the application
    is configured
    """
    connection = app['connection']


    class Query(g.ObjectType):

        author = g.Field(Author)
        book = g.Field(Book)

        authors = g.List(
            Author,

            # the following will be passed as named
            # arguments to the resolver function.
            # Don't ask why; it took me forever to
            # figure it out. Depite its functionality,
            # graphene's design and especially its
            # documentation leave a lot to be desired

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

        async def resolve_books(self,
                          info,
                          id=None,
                          title=None,
                          published=None,
                          author_id=None,
                          limit=None):

            query_db = partial(
                fetch_books,
                
                connection,
                id=id,
                title=title,
                published=published,
                author_id=author_id,
                limit=limit)
            
            fetched = await app.loop.run_in_executor(None, query_db)

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

        async def resolve_authors(self,
                            info,
                            id=None,
                            first_name=None,
                            last_name=None,
                            age=None,
                            limit=None):

            query_db = partial(
                fetch_authors,
                
                connection,
                id=id,
                first_name=first_name,
                last_name=last_name,
                age=age,
                limit=limit)
            
            fetched = await app.loop.run_in_executor(None, query_db)

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
    
    # create the view
    
    executor = AsyncioExecutor(loop=app.loop)
    
    gql_view = GraphQLView(schema=schema,
                           executor=executor,
                           graphiql=True,
                           enable_async=True
                          )
    
    # attach the view to the app router
    
    app.router.add_route(
        '*',
        '/graphql',
        gql_view,
    )


# In[7]:


def app_factory(*args, db=':memory:', logfile='log.json', **config_params):

    # initialize app
    app = web.Application()

    # set top-level configuration
    app['config'] = {k: v 
                     for k, v in config_params.items()
                     if v is not None}
    if db:
        app['config']['db'] = db
    if logfile:
        app['config']['logfile'] = logfile

    # startup
    app.on_startup.append(configure_logging)
    app.on_startup.append(configure_database)
    app.on_startup.append(create_tables)
    app.on_startup.append(seed_db)
    app.on_startup.append(configure_graphql)

    # example routes
    app.router.add_get('/', index)
    
    # rest routes
    app.router.add_get('/rest/author/{id}', author)
    app.router.add_get('/rest/authors', authors)
    app.router.add_get('/rest/book/{id}', book)
    app.router.add_get('/rest/books', books)


    # cleanup
    app.on_cleanup.append(drop_tables)
    app.on_cleanup.append(close_db)

    return app


if __name__ == '__main__':

    app = app_factory()

    web.run_app(app, host='127.0.0.1', port=8080)

