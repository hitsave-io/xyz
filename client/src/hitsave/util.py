from contextlib import contextmanager
from contextvars import ContextVar
from enum import Enum
import functools
from functools import singledispatch, lru_cache
from blake3 import blake3
from dataclasses import dataclass, is_dataclass, Field, fields
from itertools import filterfalse, tee
import json
from datetime import datetime, timezone
from subprocess import check_output, CalledProcessError
from typing import (
    IO,
    Any,
    BinaryIO,
    Callable,
    Dict,
    Generic,
    Iterable,
    Iterator,
    Set,
    Tuple,
    TypeVar,
    get_origin,
    get_args,
    Type,
    Optional,
    Union,
    List,
)
import sys
from functools import partial
import math

if hasattr(functools, "cache"):
    cache = functools.cache
else:
    cache = functools.lru_cache(maxsize=None)


def classdispatch(func):
    """Similar to ``functools.singledispatch``, except treats the first argument as a class to be dispatched on."""
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
    """Returns true if ``T == Union[NoneType, _] == Optional[_]``."""
    return as_optional(T) is not None


def as_optional(T: Type) -> Optional[Type]:
    """If we have ``T == Optional[X]``, returns ``X``, otherwise returns ``None``.

    Note that because ``Optional[X] == Union[X, type(None)]``, so
    we have ``as_optional(Optional[Optional[X]]) ↝ X``
    ref: https://stackoverflow.com/questions/56832881/check-if-a-field-is-typing-optional
    """
    if get_origin(T) is Union:
        args = get_args(T)
        if type(None) in args:
            ts = tuple(a for a in args if a is not type(None))
            if len(ts) == 0:
                return None
            if len(ts) == 1:
                return ts[0]
            else:
                return Union[ts]  # type: ignore
    return None


def as_list(T: Type) -> Optional[Type]:
    """If `T = List[X]`, return `X`, otherwise return None."""
    if get_origin(T) is list:
        return get_args(T)[0]
    return None


class MyJsonEncoder(json.JSONEncoder):
    """Converts Python objects to Json. We have additional support for dataclasses and enums that are not present in the standard encoder."""

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


T = TypeVar("T")


@classdispatch
def ofdict(A: Type[T], a: Any) -> T:
    """Converts an ``a`` to an instance of ``A``, calling recursively if necessary.
    We assume that ``a`` is a nested type made of dicts, lists and scalars.

    The main usecase is to be able to treat dataclasses as a schema for json.
    Ideally, ``ofdict`` should be defined such that ``ofdict(type(x), json.loads(MyJsonEncoder().dumps(x)))`` is deep-equal to ``x`` for all ``x``.

    Similar to ` cattrs.structure <https://cattrs.readthedocs.io/en/latest/structuring.html#what-you-can-structure-and-how/>`_.
    """
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
    """Given a python type T, this will decode a json object to an instance of `T`, or fail otherwise. It
    makes use of the `ofdict` function defined above to convert plain json dictionaries to native python types."""

    def __init__(self, T: Type):
        self.T = T

    def decode(self, j):
        jj = super().decode(j)
        return ofdict(self.T, jj)


@classdispatch
def validate(t: Type, item) -> bool:
    """Validates that the given item is of the given type."""
    # [todo] type assertion `bool ↝ item is t`
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


def get_git_root():
    """
    Gets the git root for the current working directory.

    source: https://github.com/maxnoe/python-gitpath/blob/86973f112b976a87e2ffa734fa2e43cc76dfe90d/gitpath/__init__.py
    (MIT licenced)
    """
    try:
        base = check_output(["git", "rev-parse", "--show-toplevel"])
        return base.decode().strip()
    # [todo] stop the error from being printed to the terminal. contextlib?
    except CalledProcessError:
        return None


def human_size(bytes: int, units=[" bytes", "KB", "MB", "GB", "TB", "PB", "EB"]):
    """Returns a human readable string representation of bytes.

    [todo] use humanize library (so you can localise too)
    """
    if bytes == 1:
        return "1 byte"
    if bytes < (2**10):
        return str(bytes) + units[0]
    ll = math.log2(bytes)
    i = int(ll // 10)
    if i >= len(units):
        return "2^" + str(math.ceil(math.log2(bytes))) + " bytes"
    f = bytes / (2 ** (i * 10))
    return f"{f:.1f}{units[i]}"


def chunked_read(x: IO[bytes], block_size=2**20) -> Iterator[bytes]:
    """Repeatededly read in BLOCK_SIZE chunks from the BufferedReader until it's empty."""
    # iter(f, x) will call f repeatedly until x is returned and then stop
    # https://docs.python.org/3/library/functions.html#iter
    return iter(partial(x.read, block_size), b"")


T = TypeVar("T", bound="Current")


class Current:
    """A mixin for classes where you want there to be a 'current' instance.
    You can get the current instance by calling ``cls.current``
    """

    CURRENT: ContextVar
    _tokens: List

    @classmethod
    def default(cls):
        """Override this to create a default value for current."""
        # [todo] whatever abc magic is needed here for static analysis.
        raise NotImplementedError(f"{cls.__qualname__}.default() is not implemented.")

    def __init_subclass__(cls):
        cls.CURRENT = ContextVar(cls.__qualname__ + ".CURRENT")
        # ref: https://docs.python.org/3/reference/datamodel.html#object.__init_subclass__

    def __enter__(self):
        if not hasattr(self, "_tokens"):
            self._tokens = []
        self._tokens.append(self.__class__.CURRENT.set(self))
        return self

    def __exit__(self, ex_type, ex_value, ex_trace):
        assert hasattr(self, "_tokens")
        assert len(self._tokens) > 0
        t = self._tokens.pop()
        self.__class__.CURRENT.reset(t)

    @classmethod
    def current(cls: Type[T]) -> T:
        """The current value of the singleton class."""
        c = cls.CURRENT.get(None)
        if c is None:
            c = cls.default()
            cls.CURRENT.set(c)
        return c


X = TypeVar("X")
Y = TypeVar("Y")


@dataclass
class DictDiff(Generic[X, Y]):
    add: Set[str]
    rm: Set[str]
    mod: Dict[str, Tuple[X, Y]]

    def is_empty(self):
        return len(self.add) == 0 and len(self.rm) == 0 and len(self.mod) == 0


def dict_diff(d1: Dict[str, X], d2: Dict[str, Y]) -> DictDiff[X, Y]:
    k1 = set(d1.keys())
    k2 = set(d2.keys())
    return DictDiff(
        add=k2.difference(k1),
        rm=k1.difference(k2),
        mod={k: (v1, d2[k]) for k, v1 in d1.items() if (k in d2) and (d2[k] != v1)},
    )


def partition(
    pred: Callable[[T], bool], iterable: Iterable[T]
) -> Tuple[Iterable[T], Iterable[T]]:
    """Use a predicate to partition entries into false entries and true entries.

    ref: https://docs.python.org/3/library/itertools.html
    """
    # partition(is_odd, range(10)) --> 0 2 4 6 8   and  1 3 5 7 9
    t1, t2 = tee(iterable)
    return filterfalse(pred, t1), filter(pred, t2)


def datetime_now() -> datetime:
    """Get the current datetime.

    There are lots of caveats with making datetimes and converting to/from iso strings.
    So I'm making an interface for the operations that hitsave uses."""
    return datetime.now(timezone.utc)


def datetime_to_string(dt: datetime) -> str:
    """Converting to/from a datetime to an iso string is broken in python because of the trailing Zs."""
    return dt.isoformat()


def digest_string(x: str) -> str:
    """String to blake3 hex-digest"""
    h = blake3()
    h.update(x.encode())
    return h.hexdigest()


def digest_dictionary(d: Dict[str, str]):
    h = blake3()
    h.update(b"{")
    for k in sorted(d.keys()):
        h.update(k.encode())
        h.update(b":")
        v = d[k]
        if isinstance(v, str):
            v = v.encode()
        assert isinstance(v, bytes)
        h.update(v)
        h.update(b",")
    h.update(b"}")
    return h.hexdigest()
