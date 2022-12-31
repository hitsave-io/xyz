from dataclasses import dataclass, asdict
from test.deepeq import deepeq
from hitsave.util import ofdict


@dataclass
class Bar:
    cheese: int
    toast: str


@dataclass
class Foo:
    bar: Bar
    bar2: Bar
    blap: list[Bar]


def test_foo():
    x = Foo(Bar(2, "hello"), Bar(3, "world"), blap=[Bar(4, "whiz"), Bar(5, "pop")])
    y = asdict(x)
    z = ofdict(Foo, y)
    assert deepeq(x, z)
