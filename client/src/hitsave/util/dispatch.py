from abc import get_cache_token
from typing import Dict, Generic, Optional, Type, TypeVar, Union, get_origin
from functools import singledispatch, update_wrapper
from functools import _find_impl  # type: ignore
from weakref import WeakKeyDictionary

F = TypeVar("F")


class Dispatcher(Generic[F]):
    """Reimplementation of the dispatching logic for functools.singledispatch."""

    registry: Dict[Type, F]
    cache: WeakKeyDictionary
    cache_token: Optional[object]

    def __init__(self):
        self.registry = {}
        self.cache = WeakKeyDictionary()

    def register(self, cls: Type, f=None):
        # [todo] method override
        if f is not None:
            self.registry[cls] = f
        else:

            def x(f):
                self.registry[cls] = f
                return f

            return x

    def __contains__(self, cls):
        return self.dispatch(cls) is not None

    def dispatch(self, cls) -> Union[F, None]:
        """generic_func.dispatch(cls) -> <function implementation>

        Runs the dispatch algorithm to return the best available implementation
        for the given *cls* registered on *generic_func*.

        """
        if self.cache_token is not None:
            current_token = get_cache_token()
            if self.cache_token != current_token:
                self.cache.clear()
                self.cache_token = current_token
        try:
            impl = self.cache[cls]
        except KeyError:
            try:
                impl = self.registry[cls]
            except KeyError:
                impl = _find_impl(cls, self.cache)
            self.cache[cls] = impl
        return impl


def classdispatch(func):
    """Dynamic dispatch on a class.

    Similar to ``functools.singledispatch``, except treats the first argument as a class to be dispatched on.
    [todo] switch to using dispatcher
    """
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
    update_wrapper(wrapper, func)
    return wrapper
