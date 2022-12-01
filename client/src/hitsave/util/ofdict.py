from dataclasses import fields, is_dataclass
from enum import Enum
import json
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

from hitsave.util.dispatch import classdispatch
from hitsave.util.type_helpers import as_list, as_optional, is_optional

JsonLike = Optional[Union[str, float, int, List["JsonLike"], Dict[str, "JsonLike"]]]

T = TypeVar("T")


@classdispatch
def ofdict(A: Type[T], a: JsonLike) -> T:
    """Converts an ``a`` to an instance of ``A``, calling recursively if necessary.

    We assume that ``a`` is a nested type made of dicts, lists and scalars.

    The main usecase is to be able to treat dataclasses as a schema for json.
    Ideally, ``ofdict`` should be defined such that ``ofdict(type(x), json.loads(MyJsonEncoder().dumps(x)))`` is deep-equal to ``x`` for all ``x``.

    Similar to ` cattrs.structure <https://cattrs.readthedocs.io/en/latest/structuring.html#what-you-can-structure-and-how/>`_.
    """
    if A is Any:
        return a  # type: ignore
    X = as_optional(A)
    if X is not None:
        if a is None:
            return None  # type: ignore
        else:
            return ofdict(X, a)
    if is_dataclass(A):
        d2 = {}
        for f in fields(A):
            if not isinstance(a, dict):
                raise TypeError(
                    f"Error while decoding dataclass {A}, expected a dict but got {a} : {type(a)}"
                )
            k = f.name
            if k not in a:
                if f.type is not None and is_optional(f.type):
                    v = None
                else:
                    raise ValueError(f"Missing {f.name} on input dict. Decoding {A}.")
            else:
                v = a[k]
            if f.type is not None:
                d2[k] = ofdict(f.type, v)
            else:
                d2[k] = v
        return A(**d2)
    if A in [float, str, int, bytes]:  # [todo] etc
        if isinstance(a, A):
            return a
        else:
            raise TypeError(f"Expected an {A} but was {type(a)}")

    raise NotImplementedError(f"No implementation of ofdict for {A}.")


@ofdict.register(list)
def _list_ofdict(A, a):
    if not isinstance(a, list):
        raise TypeError(f"Expected a list but got a {type(a)}")
    X = as_list(A)
    if X is not None:
        return [ofdict(X, y) for y in a]
    else:
        return a


@ofdict.register(Enum)
def _ofdict_enum(A, a):
    return A[a]


class TypedJsonDecoder(json.JSONDecoder):
    """Given a python type T, this will decode a json object to an instance of `T`, or fail otherwise.

    It makes use of the `ofdict` function defined above to convert plain json dictionaries to native python types."""

    def __init__(self, T: Type):
        self.T = T

    def decode(self, j):
        jj = super().decode(j)
        return ofdict(self.T, jj)


@classdispatch
def validate(t: Type, item) -> bool:
    """Validates that the given item is of the given type."""
    # [todo] type assertion `bool ↝ item is t`
    if t == Any:
        return True
    o = as_optional(t)
    if o is not None:
        if t is None:
            return True
        else:
            return validate(o, item)
    X = as_list(t)
    if X is not None:
        assert isinstance(item, list)

        return all([validate(X, x) for x in item])

    if isinstance(item, t):
        if is_dataclass(item):
            return all(
                [
                    validate(field.type, getattr(item, field.name))
                    for field in fields(item)
                ]
            )
        return True
    raise NotImplementedError(f"Don't know how to validate {t}")


class MyJsonEncoder(json.JSONEncoder):
    """Converts Python objects to Json.

    We have additional support for dataclasses and enums that are not present in the standard encoder."""

    # [todo] needs to handle `None` by not setting json field.
    def default(self, o):
        if isinstance(o, Enum):
            return o.value
        if is_dataclass(o):
            r = {}
            for field in fields(o):
                k = field.name
                v = getattr(o, k)
                if is_optional(field.type) and v is None:
                    continue
                r[k] = v
            return r
        return json.JSONEncoder.default(self, o)
