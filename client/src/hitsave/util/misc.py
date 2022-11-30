from blake3 import blake3
from dataclasses import dataclass, is_dataclass, Field, fields
from itertools import filterfalse, tee
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
)
from functools import partial
import math
import functools

if hasattr(functools, "cache"):
    cache = functools.cache
else:
    cache = functools.lru_cache(maxsize=None)


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
    pred: Callable[[X], bool], iterable: Iterable[X]
) -> Tuple[Iterable[X], Iterable[X]]:
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
