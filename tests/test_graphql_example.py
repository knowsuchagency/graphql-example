#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Tests for `graphql_example` package."""
from graphql_example.graphql_example import app_factory

import pytest


@pytest.fixture
def client(loop, test_client):
    app = app_factory()
    app.setdefault('config', {})['testing'] = True
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
    resp = await client.get('/rest/author?limit=7')
    assert resp.status == 200
    authors = await resp.json()
    assert len(authors) == 7
    author, *_ = authors
    assert 'books' in author

    resp = await client.get('/rest/author?limit=1&no_books=true')
    authors = await resp.json()
    author, *_ = authors
    assert 'books' not in author


async def test_books(client):
    resp = await client.get('/rest/book?limit=7')
    assert resp.status == 200
    books = await resp.json()
    assert len(books) == 7
