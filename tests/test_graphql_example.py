#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for `graphql_example` package."""
from functools import partial

from graphql_example.graphql_example import app_factory
import os

import pytest


@pytest.fixture
def client(loop, test_client):
    app = app_factory(logfile=os.devnull, )
    return loop.run_until_complete(test_client(app))


async def test_index(client):
    resp = await client.get('/')
    assert resp.status == 200


async def test_author(client):
    resp = await client.get('/rest/author/1')
    assert resp.status == 200
    author: dict = await resp.json()
    assert author['id'] == 1
    assert all(
        key in author for key in ('first_name', 'last_name', 'age', 'books'))


async def test_book(client):
    resp = await client.get('/rest/book/1')
    assert resp.status == 200
    book: dict = await resp.json()
    assert book['id'] == 1
    assert all(key in book for key in ('title', 'published', 'author'))


async def test_authors(client):
    resp = await client.get('/rest/authors?limit=7')
    assert resp.status == 200
    authors = await resp.json()
    assert len(authors) == 7
    author, *_ = authors
    assert 'books' in author

    resp = await client.get('/rest/authors?limit=1&no_books=true')
    authors = await resp.json()
    author, *_ = authors
    assert 'books' not in author


async def test_books(client):
    resp = await client.get('/rest/books?limit=7')
    assert resp.status == 200
    books = await resp.json()
    assert len(books) == 7


async def test_graphql(client):
    resp = await client.get('/graphql')

    assert resp.status == 200

    async def get_json(query):
        """
        GraphQL will return the results of the query
        in the 'data' field of the json response.
        """
        resp = await client.get(
            '/graphql',
            headers={'Accept': 'application/json'},
            params={
                'query': query
            })

        return (await resp.json()).get('data')

    query = """
        {
          authors(limit: 20) {
            first_name
            last_name
            age
            books {
              title
              published
            }
          }
        }
        """

    json = await get_json(query)

    assert 'authors' in json

    author, *_ = json['authors']

    first_name, last_name, age, books = author.values()

    assert isinstance(first_name, str)
    assert isinstance(last_name, str)
    assert isinstance(age, int)

    for author in json['authors']:
        if author['books']:
            book, *_ = author['books']
            assert 'title' in book
            assert 'published' in book
            break

    query = """
    {
      books(id:1) {
        title
        published
        author {
          first_name
          last_name
        }
      }
    }
    """

    json = await get_json(query)

    book, *_ = json['books']

    assert all(key in book for key in (
        'title',
        'published',
        'author',
    ))

    author = book['author']

    assert 'first_name' in author
    assert 'last_name' in author
