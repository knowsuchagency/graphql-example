import typing as T

try:
    from graphql_example.logging_utilities import *
except ModuleNotFoundError:
    from logging_utilities import *


def fetch_authors(
        connection,
        id=None,
        first_name=None,
        last_name=None,
        age=None,
        limit=None,
        no_books=False,
) -> T.List[dict]:
    # build sql query

    value_query = (
        (id, 'select * from author where id = ?'),
        (first_name, 'select * from author where first_name = ?'),
        (last_name, 'select * from author where last_name = ?'),
        (age, 'select * from author where age = ?'),
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

    with log_action('querying author table', sql=query_string, params=values):

        with connection:
            if values:
                rows = connection.execute(query_string, values)
            else:
                rows = connection.execute(query_string)

    authors = [{
        'id': id,
        'first_name': first_name,
        'last_name': last_name,
        'age': age,
    } for id, first_name, last_name, age in rows]

    if no_books:
        return authors

    # getting authors' books

    book_query = 'select b.id, b.title, b.published from book b where b.author_id = ?'

    with log_action('querying book table', sql=book_query):

        with connection:

            for author in authors:

                books = []

                book_rows = connection.execute(book_query, (author['id'], ))

                for book_id, book_title, book_published in book_rows:
                    books.append({
                        'id': book_id,
                        'title': book_title,
                        'published': book_published
                    })

                author['books'] = books

    return authors


def fetch_books(
        connection,
        id=None,
        title=None,
        published=None,
        author_id=None,
        limit=None,
) -> T.List[dict]:

    value_query = (
        (id, 'select * from book where id = ?'),
        (title, 'select * from book where title = ?'),
        (published, 'select * from book where published = ?'),
        (author_id, 'select * from book where author_id = ?'),
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

    with log_action('querying book table', sql=query_string, params=values):

        with connection:
            if values:
                book_rows = connection.execute(query_string, values)
            else:
                book_rows = connection.execute(query_string)

    books = []

    author_query = 'select * from author where author.id = ?'

    with log_action('querying author table', sql=author_query):

        with connection:
            for book_id, title, published, author_id in book_rows:

                author, *_ = connection.execute(author_query, (author_id, ))

                author_id, first_name, last_name, age = author

                book = {
                    'id': book_id,
                    'title': title,
                    'published': published,
                    'author': {
                        'id': author_id,
                        'first_name': first_name,
                        'last_name': last_name,
                        'age': age,
                    }
                }

                books.append(book)

    return books
