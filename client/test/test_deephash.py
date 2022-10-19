from decimal import Decimal
import numbers
import sys
from hypothesis import given, assume
import pytest
import json
import pprint
from hitsave import deepeq, deephash, reduce, reconstruct, traverse
import itertools
import math
import cmath
import hypothesis.strategies as hs
import datetime

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
]


def test_deephash_snapshot(snapshot):
    hs = [deephash(x) for x in examples]
    snapshot.assert_match(pprint.pformat(hs), "example_hashes.txt")
    hset = set(hs)
    assert len(hset) == len(hs), "Hash collision detected"


def test_hash_deterministic():
    for x in examples:
        assert deephash(x) == deephash(x)


def test_examples_traverse():
    for x in examples:
        y = traverse(x)
        assert deepeq(y, x), f"{repr(x)} ≠ {repr(y)}"


def test_noconflicts():
    hs = [(x, deephash(x)) for x in examples]
    for (x1, h1), (x2, h2) in itertools.combinations(hs, 2):
        assert h1 != h2, f"{x1} and {x2} produced same hash {h1}."


def test_eg_deepeq():
    for x1 in examples:
        assert deepeq(x1, x1)
    for x1, x2 in itertools.combinations(examples, 2):
        assert not deepeq(x1, x2)


def atoms(allow_nan=True):
    return hs.one_of(
        [
            hs.datetimes(),
            hs.dates(),
            hs.times(),
            hs.complex_numbers(allow_nan=allow_nan),
            hs.binary(),
            hs.decimals(allow_nan=allow_nan),
            hs.floats(allow_nan=allow_nan),
            hs.fractions(),
            hs.integers(),
            hs.booleans(),
            hs.from_type(str),
            # hs.from_type(type), # [todo] one day
        ]
    )


def compounds():
    return hs.one_of(
        [
            hs.sets(atoms(allow_nan=False)),
            hs.recursive(
                atoms(),
                lambda x: hs.one_of(
                    [
                        hs.dictionaries(atoms(allow_nan=False), x),
                        hs.lists(x),
                    ]
                ),
            ),
        ]
    )


@given(compounds())
def test_reduce_not_contain_self(a):
    rv = reduce(a)
    if rv is not None:
        for ((s, k), v) in rv:
            assert v is not a
            assert s is not a
            assert k is not a


@given(compounds())
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


@given(compounds())
def test_deepeq_compounds(a):
    assert deepeq(a, a), f"{a} : {type(a)}"


@given(atoms(), atoms())
def test_atoms_prop(a1, a2):
    assume(not deepeq(a1, a2))
    d1, d2 = map(deephash, (a1, a2))
    assert d1 != d2


def test_traverse_ld():
    a = [Decimal("sNaN")]
    b = traverse(a)
    assert deepeq(a, b)


@given(compounds())
def test_traverse_id(a):
    b = traverse(a)
    assert deepeq(a, b), f"{repr(a)} ≠ {repr(b)}"
