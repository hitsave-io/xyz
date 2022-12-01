from decimal import Decimal
import numbers
import sys
from hypothesis import given, assume
import pytest
import json
import pprint
from hitsave.codegraph import value_digest, HashingPickler
from .deep import reduce, reconstruct, traverse
import itertools
import math
import cmath
from hitsave.session import Session
import hypothesis.strategies as hs
import datetime
from .strat import atoms, objects
from .deepeq import deepeq
import numpy as np

examples = [
    "hello",
    "",
    "0",
    0,
    1,
    -1,
    10 ^ 100,
    10 ^ 100 + 1,
    0.5,
    sys.float_info.epsilon,
    sys.float_info.max,
    sys.float_info.min,
    float("nan"),
    float("inf"),
    -float("inf"),
    [],
    [0, 1, 2],
    (0,),
    ["0"],
    {},
    {"x": 4, "y": 4},
    {"x": 4, "y": {"z": 4}},
    set(),
    set([1, 2, 3]),
    set([0]),
    Decimal("NaN"),
    Decimal("sNaN"),
    {datetime.date(2000, 1, 1): {}, 0: {}},
    {7.0, Decimal("Infinity")},
    # primitive types
    int,
    float,
    list,
    str,
    bytes,
    # numpy
    np.int32,
    np.array([]),
    np.array([[]]),
    np.array(4),
    np.zeros((0, 4)),
    np.zeros((0, 5)),
]


def test_deephash_snapshot(snapshot):
    hs = [(repr(x), value_digest(x)) for x in examples]
    snapshot.assert_match(pprint.pformat(hs), "example_hashes.txt")
    hset = set(x[1] for x in hs)
    assert len(hset) == len(hs), "Hash collision detected"


def test_hash_deterministic():
    for x in examples:
        a = value_digest(x)
        b = value_digest(x)
        assert a == b


def test_examples_traverse():
    for x in examples:
        y = traverse(x)
        assert deepeq(y, x), f"{repr(x)} ≠ {repr(y)}"


def test_noconflicts():
    hs = [(x, value_digest(x)) for x in examples]
    for (x1, h1), (x2, h2) in itertools.combinations(hs, 2):
        assert h1 != h2, f"{x1} and {x2} produced same hash {h1}."


def test_eg_deepeq():
    for x1 in examples:
        assert deepeq(x1, x1)
    for x1, x2 in itertools.combinations(examples, 2):
        assert not deepeq(x1, x2)


@given(objects())
def test_reduce_not_contain_self(a):
    rv = reduce(a)
    if rv is not None:
        for ((s, k), v) in rv:
            assert v is not a
            assert s is not a
            assert k is not a


@given(objects())
def test_reduce_reconstruct(a):
    rv = reduce(a)
    if rv is not None:
        b = reconstruct(rv)
        assert deepeq(a, b)


def test_deepeq_date():
    d1 = datetime.date(2000, 1, 1)
    d2 = datetime.date(2000, 1, 2)
    assert not deepeq(d1, d2)


@given(atoms())
def test_deepeq_atoms(a):
    assert deepeq(a, a), f"{a} : {type(a)}"


@given(objects())
def test_deepeq_compounds(a):
    assert deepeq(a, a), f"{a} : {type(a)}"


@given(atoms(), atoms())
def test_atoms_prop(a1, a2):
    assume(not deepeq(a1, a2))
    d1, d2 = map(value_digest, (a1, a2))
    assert d1 != d2


def test_traverse_ld():
    a = [Decimal("sNaN")]
    b = traverse(a)
    assert deepeq(a, b)


@given(objects())
def test_traverse_id(a):
    b = traverse(a)
    assert deepeq(a, b), f"{repr(a)} ≠ {repr(b)}"


"""
[TODO]:
- [ ] dependencies are found if they are only referenced in lambdas or other namespaces

"""
