try:
    from graphql_example.logging_utilities import *
except ModuleNotFoundError:
    from logging_utilities import *


async def drop_tables(app):
    with log_action('dropping tables'):

        connection = app['connection']

        with connection:
            connection.executescript("""
            DROP TABLE author;
            DROP TABLE book;
            """)


async def close_db(app):
    with log_action('closing database connection'):
        app['connection'].close()
