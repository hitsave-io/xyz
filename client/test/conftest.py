import pytest
from hitsave.session import Session
from sqlite3 import Connection
import sqlite3


@pytest.fixture(scope="module")
def session():
    return Session.current()


@pytest.fixture()
def sqlite_con():
    with sqlite3.connect(":memory:") as con:
        yield con
