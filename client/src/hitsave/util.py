import dataclasses
from enum import Enum
import enum
import functools
from functools import singledispatch
from dataclasses import is_dataclass, Field, fields
import json
from typing import Any, TypeVar, get_origin, get_args, Type, Optional, Union, List

if hasattr(functools, "cache"):
    cache = functools.cache
else:
    cache = functools.lru_cache(maxsize=None)


""" Similar to `singledispatch`, except treats the first argument as a class to be dispatched on. """


def classdispatch(func):
    funcname = getattr(func, "__name__", "class dispatch function")
    sdfunc = singledispatch(func)

    def dispatch(cls):
        g = sdfunc.registry.get(cls)
        if g is not None:
            return g
        orig = get_origin(cls)
        if orig is not None:
            g = sdfunc.registry.get(orig)
            if g is not None:
                return g
            cls = orig
        try:
            return sdfunc.dispatch(cls)
        except Exception:
            return sdfunc.dispatch(object)

    def wrapper(*args, **kwargs):
        if not args:
            raise TypeError(f"{funcname} requires at leat one positional argument.")
        cls = args[0]
        return dispatch(cls)(*args, **kwargs)

    for n in ["register", "registry"]:
        setattr(wrapper, n, getattr(sdfunc, n))
    setattr(wrapper, "dispatch", dispatch)
    functools.update_wrapper(wrapper, func)
    return wrapper


def is_optional(T: Type) -> bool:
    return as_optional(T) is not None


def as_optional(T: Type) -> Optional[Type]:
    # https://stackoverflow.com/questions/56832881/check-if-a-field-is-typing-optional
    if get_origin(T) is Union:
        args = get_args(T)
        if type(None) in args:
            args = [a for a in args if a is not type(None)]
            if len(args) == 1:
                return args[0]
    return None


""" If `T = List[X]`, return `X`, otherwise return None. """


def as_list(T: Type) -> Optional[Type]:
    if get_origin(T) is list:
        return get_args(T)[0]
    return None


class MyJsonEncoder(json.JSONEncoder):
    """Python → Json"""

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

        raise NotImplementedError(f"Don't know how to encode {type(o)}.")


""" Similar to [cattrs.structure](https://cattrs.readthedocs.io/en/latest/structuring.html#what-you-can-structure-and-how)
But I don't want to take on more dependencies. """

T = TypeVar("T")


@classdispatch
def ofdict(A: Type[T], a: Any) -> T:
    """Converts an `a` to an instance of `A`, calling recursively if necessary.
    We assume that `a` is a nested type made of dicts, lists and scalars."""
    if A is Any:
        return a
    X = as_optional(A)
    if X is not None:
        if a is None:
            return None  # type: ignore
        else:
            return ofdict(X, a)
    if is_dataclass(A):
        d2 = {}
        for f in fields(A):
            k = f.name
            if k not in a:
                if f.type is not None and is_optional(f.type):
                    v = None
                else:
                    raise Exception(f"Missing {f.name} on input dict.")
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
    """Json → Python"""

    def __init__(self, T: Type):
        self.T = T

    def decode(self, j):
        jj = super().decode(j)
        return ofdict(self.T, jj)


# ref: https://stackoverflow.com/questions/4842424/list-of-ansi-color-escape-sequences


class AnsiColor(Enum):
    black = 0
    red = 1
    green = 2
    yellow = 3
    blue = 4
    magenta = 5
    cyan = 6
    white = 7


class AnsiCode(Enum):
    reset = 0
    bold = 1
    underline = 4
    fg = 30
    fg_bright = 90
    bg = 40
    bg_bright = 100


def ansiseq(params: List[int]) -> str:
    ps = ";".join([str(p) for p in params])
    return f"\033[{ps}m"


def decorate_ansi(
    x: str,
    fg: Optional[Union[AnsiColor, str]] = None,
    bg: Optional[Union[AnsiColor, str]] = None,
    fg_bright=False,
    bg_bright=True,
    bold=False,
    underline=False,
):
    params = []
    if fg is not None:
        code = AnsiCode.fg_bright if fg_bright else AnsiCode.fg
        c = getattr(AnsiColor, fg) if isinstance(fg, str) else fg
        code = code.value + c.value
        params.append(code)
    if bg is not None:
        code = AnsiCode.bg_bright if bg_bright else AnsiCode.bg
        c = getattr(AnsiColor, bg) if isinstance(bg, str) else bg
        code = code.value + c.value
        params.append(code)
    if bold:
        params.append(AnsiCode.bold.value)
    if underline:
        params.append(AnsiCode.underline.value)
    return ansiseq(params) + x + ansiseq([AnsiCode.reset.value])
