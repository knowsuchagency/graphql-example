async def drop_tables(app):
    print('dropping table')

    connection = app['connection']

    with connection:
        connection.executescript("""
        DROP TABLE author;
        DROP TABLE book;
        """)

    print('tables dropped')


# close the database connection on shutdown
async def close_db(app):
    print('closing database connection')
    app['connection'].close()
    print('database connection closed')
