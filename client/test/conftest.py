import pytest
from hitsave.session import Session


@pytest.fixture(scope="module")
def session():
    return Session.current()
