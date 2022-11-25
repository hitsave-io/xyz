"""

This file contains a variant of the reduce/reconstruct scheme
used by pickle and deepcopy.

References:
- https://github.com/python/cpython/blob/3.10/Lib/copy.py
- https://github.com/python/cpython/blob/3.10/Lib/copyreg.py
- https://docs.python.org/3/library/pickle.html#object.__reduce__

Related work:
- https://github.com/Suor/funcy


- [todo] namedtuple
- [todo] set
- [todo] frozenset
- [todo] range, slice

"""
import copyreg
from inspect import signature, BoundArguments
import datetime
from typing import Any, Callable, Iterator, List, Literal, Tuple, Type, Optional, Union
from functools import wraps
from pickle import DEFAULT_PROTOCOL
from dataclasses import dataclass, field, fields, is_dataclass, replace


def _uses_default_reductor(cls):
    return (getattr(cls, "__reduce_ex__", None) == object.__reduce_ex__) and (
        getattr(cls, "__reduce__", None) == object.__reduce__
    )


dispatch_table = copyreg.dispatch_table.copy()
""" Dispatch table for reducers. """


def register_reducer(type):
    def reg(func):
        dispatch_table[type] = func
        return func

    return reg


def register_opaque(type):
    global opaque
    """Register a type as not being reducible."""
    opaque.add(type)
    dispatch_table[type] = None  # type: ignore


@register_reducer(list)
def list_reductor(l: list) -> Tuple:
    return (list, (), None, l)


@register_reducer(dict)
def dict_reductor(d: dict) -> Tuple:
    return (dict, (), None, None, d)


@register_reducer(tuple)
def tuple_reductor(t: tuple) -> Tuple:
    return (tuple, t)


def _sortkey(x):
    # [note]: can't use hash because it is not stable.
    return (type(x).__name__, repr(x))


opaque = set(
    [
        type(None),
        type(Ellipsis),
        type(NotImplemented),
        int,
        float,
        bool,
        complex,
        bytes,
        str,
        type,
    ]
)
""" Set of scalar values that can't be reduced.
[todo] make these configurable. """


@dataclass
class ReductionValue:
    """Output of __reduce__.

    Slightly deviate from the spec in that listiter and dictiter can be
    sequences and dicts.
    The values are the same as the values in the tuple specified in the below
    reference: https://docs.python.org/3/library/pickle.html#object.__reduce__

    [todo] add support for kwargs on constructor.
    [todo] support the slots item.

    """

    func: Callable
    args: Tuple
    state: Optional[Union[dict, Tuple]] = field(default=None)
    listiter: Optional[list] = field(default=None)
    dictiter: Optional[dict] = field(default=None)

    def __post_init__(self):
        if self.listiter is not None and type(self.listiter) != list:
            self.listiter = list(self.listiter)
        if self.dictiter is not None and type(self.dictiter) != list:
            self.dictiter = dict(self.dictiter)

    def map(self, f) -> "ReductionValue":
        return self.walk(lambda v, k: f(v))

    def walk(self, f) -> "ReductionValue":
        if self.state and isinstance(self.state, dict):
            raise NotImplementedError(f"cannot map slots yet.")
        args = tuple(f(v, i) for i, v in enumerate(self.args))
        return replace(
            self,
            args=args,
            state=self.state and {k: f(v, k) for k, v in self.state.items()},  # type: ignore
            listiter=self.listiter and [f(v, i) for i, v in enumerate(self.listiter)],
            dictiter=self.dictiter and {k: f(v, k) for k, v in self.dictiter.items()},
        )

    def __len__(self):
        l = 0
        l += len(self.args)
        if self.state:
            l += len(self.state)
        if self.listiter:
            l += len(self.listiter)
        if self.dictiter:
            l += len(self.dictiter)
        return l

    def __iter__(self) -> Iterator[Tuple[Tuple[str, Any], Any]]:
        """Iterates on all of the child objects of the reduced value."""
        for i, arg in enumerate(self.args):
            yield (("args", i), arg)
        if self.state:
            if isinstance(self.state, dict):
                for k in sorted(self.state.keys(), key=_sortkey):
                    yield (("state", k), self.state[k])
            else:
                # [todo] if something is performance-sensitive enough to use slots
                # it should probably have a custom hashing and pickling algorithm.
                # and we shouldn't reach here. So always give a warning.
                raise NotImplementedError(f"cannot iter slots yet.")
        if self.listiter:
            for i, item in enumerate(self.listiter):
                yield (("listiter", i), item)
        if self.dictiter:
            for k in sorted(self.dictiter.keys(), key=_sortkey):
                yield (("dictiter", k), self.dictiter[k])

    """ Gets the type that this reduction will create when reconstructed. """

    @property
    def type(self) -> Type:
        if self.func.__name__ == "__newobj__":
            return self.args[0]
        elif isinstance(self.func, type):
            return self.func
        else:
            raise NotImplementedError(f"cannot get the class from {self}")


def reduce(obj) -> Optional[ReductionValue]:
    """Similar to `__reduce__()`.
    If `None` is returned, that means that reduce treats the given object as _opaque_.
    This means that it won't bother unfolding it any further.
    """

    def core(obj) -> Any:
        cls = type(obj)
        dt = dispatch_table
        if cls in dt:
            reductor = dt.get(cls)
            if reductor is not None:
                return reductor(obj)
        if cls in opaque:
            return None
        if _uses_default_reductor(cls) and is_dataclass(cls):
            # Custom reduction for dataclasses that's a bit nicer.
            # It's not technically correct because fields are mutable and so
            # should be states.
            # [todo] support dataclasses with hidden state?
            return (cls, tuple(getattr(obj, f.name) for f in fields(obj)))
        reductor = getattr(obj, "__reduce_ex__", None)
        if reductor is not None:
            return reductor(DEFAULT_PROTOCOL)
        reductor = getattr(obj, "__reduce__", None)
        if reductor is not None:
            return reductor()
        raise TypeError(f"cannot reduce a {cls}.")

    rv = core(obj)
    if type(rv) == tuple:
        return ReductionValue(*rv)
    elif type(rv) == str:
        raise NotImplementedError(
            f"not sure how to make reduction value from string '{rv}'."
        )
    else:
        return rv


"""
Based on: https://github.com/python/cpython/blob/442674e37eb84f9da5701412f8ad94e4eb2774fd/Lib/copy.py#L259
"""


def reconstruct(rv: ReductionValue):
    # short circuits
    if rv.func == list and rv.listiter is not None:
        return list(rv.listiter)
    elif rv.func == dict and rv.dictiter is not None:
        return dict(rv.dictiter)
    # main method
    func = rv.func
    y = func(*rv.args)
    if rv.state is not None:
        state = rv.state
        if hasattr(y, "__setstate__"):
            y.__setstate__(state)
        else:
            if isinstance(state, tuple) and len(state) == 2:
                state, slotstate = state
            else:
                slotstate = None
            if state is not None:
                y.__dict__.update(state)
            if slotstate is not None:
                for key, value in slotstate.items():
                    setattr(y, key, value)
    if rv.listiter is not None:
        if hasattr(y, "extend"):
            y.extend(rv.listiter)
        else:
            for item in rv.listiter:
                y.append(item)
    if rv.dictiter is not None:
        items = rv.dictiter.items() if isinstance(rv.dictiter, dict) else rv.dictiter
        for key, value in items:
            y[key] = value
    return y


@dataclass
class Step:
    value: Any


@dataclass
class Stop:
    value: Any


VisitFn = Callable[[Any, Tuple[Any]], Union[Step, Stop]]

""" Closure of walk """


def traverse(
    x,
    *,
    pre: VisitFn = lambda x, path: Step(x),
    post: VisitFn = lambda x, path: Stop(x),
):
    def err(n, r):
        return TypeError(
            f"result of calling `{n}` should be a `Step` or `Stop` but got {type(r)}, use `traverse.stop` and `traverse.step`."
        )

    def rec(x, path=()):
        r = pre(x, path)
        if isinstance(r, Stop):
            return r.value
        elif isinstance(r, Step):
            x = r.value
        else:
            raise err("pre", r)
        x = walk(x, lambda y, k: rec(y, (*path, k)))
        r = post(x, path)
        if isinstance(r, Stop):
            return r.value
        elif isinstance(r, Step):
            return rec(x, path=path)
        else:
            raise err("post", r)

    return rec(x)


traverse.step = Step
traverse.stop = Stop

""" Similar to https://funcy.readthedocs.io/en/stable/colls.html#walk

Main difference is that the input is always `(value, key)` and the output is always `value`.
We also treat dataclasses as walkable.
"""


def walk(x, fn):
    if hasattr(x, "__walk__"):
        return x.__walk__(fn)
    rv = reduce(x)
    if rv is None:
        return x
    rv = rv.walk(fn)
    return reconstruct(rv)


"""
todos:

- [ ] is_atomic
- [ ] iter_children -- ''

 """
