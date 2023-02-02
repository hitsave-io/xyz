from functools import singledispatch
from typing import Any, Literal, Optional, Sequence, TypeVar, Union, overload

from .textnode import TextNodeSpec
from .vdom import Html, NormSpec, normalise_html
from .element import ElementSpec
from .fiber import Component, FiberSpec


A = TypeVar("A", contravariant=True)



@overload
def h(tag: str, attrs: dict, *children: Html, key: Optional[str] = None) -> ElementSpec:
    ...


@overload
def h(tag: Component[A], attrs: A, *, key: Optional[str] = None) -> FiberSpec:
    ...


def h(tag, attrs, *children: Html, key=None) -> Union[ElementSpec, FiberSpec]:
    all_children = normalise_html(list(children))
    if type(tag) == str:
        assert isinstance(attrs, dict)
        if key is not None:
            attrs["key"] = key
        return ElementSpec(tag=tag, attrs=attrs, children=all_children)
    elif callable(tag):
        if len(all_children) > 0:
            attrs["children"] = all_children
        return FiberSpec(component=tag, props=attrs, key=key)
    else:
        raise TypeError(f"unrecognised tag: {tag}")
