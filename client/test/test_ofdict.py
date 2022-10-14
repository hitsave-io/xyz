from dataclasses import dataclass, asdict
from typing import List
from hitsave import deepeq
from hitsave.util import ofdict


@dataclass
class Bar:
    cheese: int
    toast: str


@dataclass
class Foo:
    bar: Bar
    bar2: Bar
    blap: List[Bar]


def test_foo():
    x = Foo(Bar(2, "hello"), Bar(3, "world"), blap=[Bar(4, "whiz"), Bar(5, "pop")])
    y = asdict(x)
    z = ofdict(Foo, y)
    assert deepeq(x, z)
