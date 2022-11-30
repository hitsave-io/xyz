from decimal import Decimal
from numbers import Number
import sys
from typing import Any
from hypothesis import given, assume
import pytest
import json
import pprint
from .deepeq import deepeq
from hitsave.deep import reduce, reconstruct, traverse
import itertools
import math
import cmath
import hypothesis.strategies as hs
import datetime

""" Strategies for hitsave. The idea is that this file contains

every kind of object, and hypothesis strategies for producing every kind of object,
that we consider to be supported by hitsave.

That means that all of these objects should be hashable, picklable and unpicklable with our system.


We define the following terms:
- A python object is __composite__ when its data contains references to other python objects.
- A python object is __atomic__ when it is not composite. Strings, ints, bools, and Numpy arrays are atomic.
- A python object is __builtin__ when you could make it without defining your own types or importing stuff.

## [todo]

- Include a set of custom-made types:
    - dataclasses
    - enums
    - classes with a state dict

- Include pytorch datatypes.
- numpy datatypes

- Include pathological types that shouldn't really make it in to a hitsave record.
  These should throw things.
    - logging.Logger.
 """


def numbers(allow_nan=True) -> hs.SearchStrategy[Number]:
    return hs.one_of(
        [
            hs.floats(allow_nan=allow_nan),
            hs.decimals(allow_nan=allow_nan),
            hs.complex_numbers(allow_nan=allow_nan),
            hs.fractions(),
            hs.integers(),
        ]
    )


def atoms(allow_nan=True) -> hs.SearchStrategy[Any]:
    """An atomic python object is one whose data does not refer to any other python objects.

    There is an allow_nan flag, because nans are not reflexive and this is really annoying."""
    return hs.one_of(
        [
            numbers(allow_nan=allow_nan),
            hs.datetimes(),
            hs.dates(),
            hs.times(),
            hs.binary(),
            hs.booleans(),
            hs.from_type(str),
            hs.just(None),
            # hs.from_type(type),
            # pytorch tensors
            # numpy arrays
            # pandas dataframes
        ]
    )


def objects():
    """Generates all python objects that hitsave supports."""
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
