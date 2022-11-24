from dataclasses import dataclass, fields
from typing import List, Optional, Union
from hitsave.util import (
    Current,
    as_list,
    human_size,
    is_optional,
    as_optional,
)
from pytest import raises


def test_human_size(snapshot):
    sizes = [
        1,
        100,
        999,
        1000,
        1024,
        2000,
        2048,
        3000,
        9999,
        10000,
        2048000000,
        9990000000,
        9000000000000000000000,
    ]
    snapshot.assert_match("\n".join(map(human_size, sizes)) + "\n", "bytes")


def test_isoptional():
    assert is_optional(Optional[int])
    assert not is_optional(int)
    assert is_optional(Union[type(None), int])
    assert is_optional(Union[int, type(None)])
    assert not is_optional(Union[int, int])


def test_asoptional():
    assert as_optional(Optional[int]) is int
    assert as_optional(int) is None
    assert as_optional(Union[type(None), int]) is int
    assert as_optional(Union[int, type(None)]) is int
    assert as_optional(Union[int, int]) is None
    assert as_optional(Optional[Optional[int]]) is int
    assert Union[int, float] == Union[float, int]
    assert as_optional(Optional[type(None)]) is None
    assert as_optional(Union[int, float, type(None)]) == Union[int, float]


def test_aslist():
    assert as_list(List[int]) is int
    assert as_list(int) is None


def test_current():
    @dataclass
    class Hello(Current):
        x: int

        @classmethod
        def default(cls):
            return cls(x=100)

    assert "_tokens" not in [f.name for f in fields(Hello)]
    assert "CURRENT" in vars(Hello)
    assert Hello.current().x == 100

    with Hello(5):
        assert Hello.current().x == 5

    assert Hello.current().x == 100

    h = Hello(10)

    assert "CURRENT" not in vars(h)

    with h:
        assert Hello.current().x == 10
        with h:
            assert Hello.current().x == 10
        assert Hello.current().x == 10

    assert Hello.current().x == 100

    try:
        with h:
            raise Exception("oops")
    except Exception:
        pass

    assert Hello.current().x == 100

    @dataclass
    class World(Current):
        y: str

    assert World.CURRENT != Hello.CURRENT

    with raises(NotImplementedError):
        World.current()
