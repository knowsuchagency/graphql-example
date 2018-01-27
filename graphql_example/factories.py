try:
    from graphql_example.model import Author, Book
except ModuleNotFoundError:
    from model import Author, Book

from mimesis import Generic

# fake data generator
generate = Generic('en')


def author_factory(**replace):
    kwargs = dict(
        first_name=generate.personal.name(),
        last_name=generate.personal.last_name(),
        age=generate.personal.age(),
        books=None
    )

    kwargs.update(replace)

    return Author(**kwargs)


def book_factory(**replace):
    kwargs = dict(
        title=generate.text.title(),
        author=author_factory(),
        published=generate.datetime.date()
    )

    kwargs.update(replace)

    return Book(**kwargs)
