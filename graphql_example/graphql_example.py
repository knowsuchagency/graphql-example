
# coding: utf-8

# In[1]:


from contextlib import contextmanager
import sys

from graphql_example.utils import to_file as log_to_file

from aiohttp import web
from aiohttp_graphql import GraphQLView
import graphene
from eliot import start_action
import eliot



# set up log
log_to_file(open('log.json', 'w'))
stdout_destination = log_to_file(sys.stdout)


# initialize app
app = web.Application()
routes = web.RouteTableDef()


# In[2]:


@contextmanager
def log_action(action_type, **kwargs):
    """A simple wrapper over eliot.start_action to make things less verbose."""
    with start_action(action_type=action_type, **kwargs):
        yield


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
    ):
        yield


# In[3]:


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
        
        name = request.match_info.get('name', 'anonymous')
                
        with log_action('sending response'):
            
            return web.Response(
                text=f'<html><h2>Hello {name}!</h2><html>',
                content_type='Content-Type: text/html'
            )
            
            
@routes.get('/sitemap', name='sitemap')
async def sitemap(request):
    """Not a real sitemap, but good enough."""
    with log_inbound_request(request):
        resources = '\n'.join(map(str, request.app.router.resources()))
        return web.Response(text=resources)


# In[ ]:


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


# In[ ]:


# add routes from decorators
app.router.add_routes(routes)

# add graphiql route from aiottp_graphql
gql_view = GraphQLView(schema=schema, graphiql=True)
app.router.add_route('*', '/graphql', gql_view, name='graphql')


if __name__ == '__main__':
    eliot.remove_destination(stdout_destination)
    web.run_app(app, host='127.0.0.1', port=8080)

