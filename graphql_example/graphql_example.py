
# coding: utf-8

# # A simple graphql backend implented in aiohttp

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

try:
    from graphql_example.domain_model import Author as AuthorModel
    from graphql_example.domain_model import Book as BookModel
except ModuleNotFoundError:
    from domain_model import Author as AuthorModel
    from domain_model import Book as BookModel
    
    
    
from aiohttp import web


# In[2]:


# initialize app
app = web.Application()
routes = web.RouteTableDef()

# configure web app

# configure database
import sqlite3
connection = sqlite3.connect(':memory:')
# here be dragons
connection.execute('PRAGMA synchronous = OFF')
# avoid globals
app['connection'] = connection

app.on_startup.append(configure_logging)
#app.on_startup.append(configure_database)
app.on_startup.append(create_tables)
app.on_startup.append(seed_db)


app.on_cleanup.append(drop_tables)
app.on_cleanup.append(close_db)


# ## Brief aiohttp route/view example w/eliot logging
# 
# Two simple view coroutines decorated with their routes
# 
# Note, aiohttp also allows one to add routes and related views without
# the use of decorators as flask does
# 
# ```python3
# 
# app.router.add_route('GET', '/', index)
# # or
# app.router.add_get('/', index)
# 
# ```
# 
# This is arguably better, if only because you could see
# the mapping of all your routes and related views in one
# place without resorting to programmatically iterate through the
# route table's resource map

# In[3]:


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


# ## The domain model

# In[4]:


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

# In[5]:


@routes.get('/rest/author')
async def author(request):
    connection = request.app['connection']

    with log_request(request):

        # parse values from query params

        id = None or int(request.query.get('id', 0))
        first_name = request.query.get('first_name')
        last_name = request.query.get('last_name')
        age = None or int(request.query.get('age', 0))
        limit = int(request.query.get('limit', 0))

        authors = fetch_authors(
            request.app['connection'],
            id=id,
            first_name=first_name,
            last_name=last_name,
            age=age,
            limit=limit)

        response = web.json_response(authors)

        with log_response(response):

            return response


@routes.get('/rest/book')
async def book(request):
    connection = request.app['connection']

    with log_request(request):

        # parse values from query params

        id = None or int(request.query.get('id', 0))
        published = request.query.get('published')
        author_id = request.query.get('author_id')
        limit = int(request.query.get('limit', 0))

        # build sql query

        books = fetch_books(
            request.app['connection'],
            id=id,
            published=published,
            author_id=author_id,
            limit=limit
        )

        response = web.json_response(books)

        with log_response(response):

            return response


# ## graphql schema definition

# In[6]:


from graphene import relay
import graphene as g
from pprint import pprint


class Author(g.ObjectType):
    id = g.Int(description='The primary key in the database')
    first_name = g.String()
    last_name = g.String()
    age = g.Int()   
    


class Query(g.ObjectType):
    
    authors = g.List(
        
        Author,
        
        # these will be passed as named arguments
        # to the resolver function for the authors
        # scalar because graphene has terrible design
        id=g.Int(default_value=-1),
        first_name=g.String(default_value=''),
        last_name=g.String(default_value=''),
        age=g.Int(default_value=0),
        limit=g.Int(default_value=0)

    )
    
    def resolve_authors(
        self,
        info,
        id,
        first_name,
        last_name,
        age,
        limit
    ):
        """Resolve the arguments"""
        kwargs = dict(
            id = id if id != -1 else None,
            first_name = None or first_name,
            last_name = None or last_name,
            age = None or age,
            limit = None or limit
        )
        
        authors = fetch_authors(connection, **kwargs)
        
        return [
            Author(
                a['id'],
                a['first_name'],
                a['last_name'],
                a['age'],
            ) for a in authors
        ]
        
    


schema = g.Schema(query=Query)


# ## graphql route/view

# In[ ]:


from aiohttp_graphql import GraphQLView

gql_view = GraphQLView(schema=schema, graphiql=True)

app.router.add_route('*', '/graphql', gql_view, name='graphql')


# In[ ]:


# add routes from decorators
app.router.add_routes(routes)

if __name__ == '__main__':
    
    #stdout_destination = to_file(sys.stdout)
    
    web.run_app(app, host='127.0.0.1', port=8080)

