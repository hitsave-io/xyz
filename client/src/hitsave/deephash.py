from typing import Iterable, Union
from blake3 import blake3
from functools import singledispatch, lru_cache
from dataclasses import is_dataclass, fields
import struct
from hitsave.codegraph import CodeGraph, CodeVertex, ExternPackage, Vertex
from hitsave.deep import reduce
from hitsave.util import cache
import inspect


@singledispatch
def to_bytes(item) -> bytes:
    """Function for transforming atomic values to bytes.
    This is for the purpose of hashing, not for serialization.
    """

    return NotImplemented


@to_bytes.register(bytes)
def _to_bytes_bytes(x: bytes):
    return x


@to_bytes.register(str)
def _to_bytes_str(x: str):
    return x.encode("utf-8")


@to_bytes.register(int)
def _int_to_bytes(x: int):
    # https://docs.python.org/3/library/stdtypes.html#int.to_bytes
    # return (x.to_bytes(((x.bit_length() * 2 + 7) // 8), byteorder='little', signed = True))
    return _to_bytes_str(str(x))


@to_bytes.register(float)
def _float_to_bytes(x: float):
    return struct.pack("d", x)


@to_bytes.register(bool)
def _bool_to_bytes(x: bool):
    return struct.pack("b", x)


@to_bytes.register(type(None))
def _none_to_bytes(x):
    return b""


# [todo] register_deephash
# [todo] consider having it be recursive and cached instead.
# [todo] protection against cyclic datastructures? introduces overhead.
# [todo] consider having values also be cached by looking at the dependencies of their expression.


def run_deephash(item, hasher):
    hasher.update(_to_bytes_str(type(item).__name__))
    hasher.update(b"(")
    if hasattr(item, "__deephash__"):
        item.__deephash__(hasher)
    bs = to_bytes(item)
    if bs is not NotImplemented:
        hasher.update(bs)
    else:
        rv = reduce(item)
        if rv is not None:
            for (k1, k2), v in rv:
                # key sorting is guaranteed the same
                hasher.update(to_bytes(k1))
                run_deephash(k2, hasher)
                run_deephash(v, hasher)
        else:
            # [todo] here, if it's a function we call fn_hash.
            # some issues with cycles etc. need to rearchitect this.
            raise NotImplementedError(f"Don't know how to hash {type(item)}.")
    hasher.update(b")")


def deephash(item) -> str:
    hasher = blake3()
    run_deephash(item, hasher)
    return hasher.hexdigest()


def local_hash_Vertex(v: Vertex):
    if isinstance(v, CodeVertex):
        if v.is_import():
            # imported values need not have their content hashed
            # it will be hashed at the parent vertex.
            return deephash(repr(v))
        o = v.to_object()
        if inspect.isfunction(o):
            return fn_local_hash(o)
        elif hasattr(o, "__wrapped__") and inspect.isfunction(o.__wrapped__):
            return fn_local_hash(o.__wrapped__)
        else:
            return deephash(o)
    else:
        return deephash(v)


@cache
def fn_local_hash(fn):
    lines = inspect.getsource(fn)
    return deephash(lines)


def hash_function(g: CodeGraph, fn):
    local_hash = fn_local_hash(fn)
    g.eat_obj(fn)
    deps = {repr(v): local_hash_Vertex(v) for v in (g.get_dependencies_obj(fn))}
    return deephash((local_hash, deps))
