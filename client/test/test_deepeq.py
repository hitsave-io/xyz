from copy import deepcopy
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
from .test_deephash import examples

""" Testing for the test.deep and test.deepeq modules. """


def test_examples_traverse():
    for x in examples:
        y = traverse(x)
        assert deepeq(y, x), f"{repr(x)} ≠ {repr(y)}"


def test_eg_deepeq():
    for x1 in examples:
        assert deepeq(x1, x1)
    for x1, x2 in itertools.combinations(examples, 2):
        assert not deepeq(x1, x2)


@given(objects())
def test_reduce_reconstruct(a):
    rv = reduce(a)
    if rv is not None:
        b = reconstruct(rv)
        assert deepeq(a, b)


@given(objects())
def test_reduce_not_contain_self(a):
    rv = reduce(a)
    if rv is not None:
        for ((s, k), v) in rv:
            assert v is not a
            assert s is not a
            assert k is not a


def test_deepeq_date():
    d1 = datetime.date(2000, 1, 1)
    d2 = datetime.date(2000, 1, 2)
    assert not deepeq(d1, d2)


def test_traverse_ld():
    a = [Decimal("sNaN")]
    b = traverse(a)
    assert deepeq(a, b)


@given(objects())
def test_traverse_id(a):
    b = traverse(a)
    assert deepeq(a, b), f"{repr(a)} ≠ {repr(b)}"


@given(objects())
def test_deepeq_compounds(a):
    assert deepeq(a, a), f"{a} : {type(a)}"


@given(atoms())
def test_deepeq_atoms(a):
    assert deepeq(a, a), f"{a} : {type(a)}"
