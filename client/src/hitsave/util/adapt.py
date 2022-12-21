"""
I got inspired by PEP 246.
https://peps.python.org/pep-0246

The philosophy behind the adapter pattern is like:
I have a protocol `P` and an object `x` that doesn't conform to `P`.

So you have an adapter registry so that you can write `adapt(x, P)` and it will dispatch
a wrapper around `x` that makes it in to a `P`.
"""


from collections import defaultdict
from typing import (
    Any,
    Callable,
    DefaultDict,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
)
from hitsave.util.dispatch import Dispatcher


class AdaptationError(TypeError):
    pass


class LiskovViolation(AdaptationError):
    pass


F = TypeVar("F")

AdapterFactory = Callable[[Any, Type, Any], Any]
_adapter_factory_registry: DefaultDict[Type, Dispatcher[AdapterFactory]] = defaultdict(
    Dispatcher
)


def registerAdapterFactory(objtype, protocol, factory: AdapterFactory):
    _adapter_factory_registry[protocol].register(cls=objtype, f=factory)


def adapter(objtype: Type, protocol: Type):
    """Decorator version of registerAdapterFactory"""

    def core(factory: AdapterFactory):
        registerAdapterFactory(objtype, protocol, factory)
        return factory

    return core


def _adapt_by_registry(obj, protocol, alternate=AdaptationError):
    t = type(obj)
    d: Dispatcher = _adapter_factory_registry.get(protocol)  # type: ignore
    factory = d.dispatch(t)
    if factory is None:
        adapter = alternate
    else:
        adapter = factory(obj, protocol, alternate)

    if adapter is AdaptationError:
        raise AdaptationError
    else:
        return adapter


def adapt(obj, protocol: Type, alternate=AdaptationError):
    """Implementation of PEP 246. https://peps.python.org/pep-0246"""
    t = type(obj)

    # (a) first check to see if object has the exact protocol
    if t is protocol:
        return obj

    try:
        # (b) next check if t.__conform__ exists & likes protocol
        conform = getattr(t, "__conform__", None)
        if conform is not None:
            result = conform(obj, protocol)
            if result is not None:
                return result

        # (c) then check if protocol.__adapt__ exists & likes obj
        adapt = getattr(type(protocol), "__adapt__", None)
        if adapt is not None:
            result = adapt(protocol, obj)
            if result is not None:
                return result
    except LiskovViolation:
        pass
    else:
        # (d) check if object is instance of protocol
        if isinstance(obj, protocol):
            return obj

    # (e) last chance: try the registry
    return _adapt_by_registry(obj, protocol, alternate)
