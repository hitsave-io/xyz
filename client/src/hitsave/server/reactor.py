import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
import inspect
import logging
from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    Iterator,
    Optional,
    ParamSpec,
    Protocol,
    Sequence,
    TypeGuard,
    TypeVar,
    Union,
    overload,
)
from typing_extensions import override
from uuid import UUID, uuid4

from hitsave.server.jsonrpc import Dispatcher, RpcServer
from hitsave.util.listdiff import Reorder, diff as listdiff
from hitsave.util.misc import dict_diff
from hitsave.console import logger, console

""" React, in Python. How hard can it be? """

P = ParamSpec("P")
T = TypeVar("T")
S = TypeVar("S")
R = TypeVar("R")
H = TypeVar("H", bound="Hook")

A = TypeVar("A", contravariant=True)

ID_COUNTER = 100


def fresh_id() -> int:
    global ID_COUNTER
    ID_COUNTER += 1
    return ID_COUNTER


class NoNeedToRerender(Exception):
    pass


class StateHook(Generic[S]):
    state: S

    def __init__(self, init: S, fiber: "Fiber"):
        self.state = init
        self.fiber = fiber

    def reconcile(self, new_hook: "StateHook") -> "StateHook":
        assert type(self) == type(new_hook)
        return self

    def dispose(self):
        self.fiber = None

    @overload
    def set(self, item: S) -> None:
        ...

    @overload
    def set(self, item: Callable[[S], S]) -> None:
        ...

    def set(self, item: Union[S, Callable[[S], S]]) -> None:
        old_state = self.state
        if callable(item):
            self.state = item(old_state)
        else:
            self.state = item
        if self.fiber is not None:
            self.fiber.invalidate()
        logger.debug(f"{str(self.fiber)}: {old_state} -> {self.state}")
        return

    def pull(self):
        return (self.state, self.set)


class EffectHook:
    def __init__(self, callback, deps):
        self.task = None
        self.callback = callback
        self.deps = deps

    def dispose(self):
        if self.task is not None:
            self.task.cancel()
            self.task = None

    def evaluate(self):
        callback = self.callback
        assert callable(callback)
        self.dispose()
        if asyncio.iscoroutinefunction(callback):
            self.task = asyncio.create_task(callback())
        else:
            callback()

    def reconcile(self, new_hook: "EffectHook"):
        assert type(new_hook) == type(self)

        def update():
            self.deps = new_hook.deps
            self.callback = new_hook.callback
            self.evaluate()

        if self.deps is None and new_hook.deps is None:
            update()
        elif len(self.deps) != len(new_hook.deps):
            update()
        else:
            for old_dep, new_dep in zip(self.deps, new_hook.deps):
                if old_dep != new_dep:
                    logger.debug(f"Dep changed {old_dep} -> {new_dep}")
                    update()
                    break
        return self


Hook = Union[StateHook, EffectHook]

SetterFn = Callable[[Union[S, Callable[[S], S]]], None]


class Fiber:
    """Like React fibers."""

    component: "Component"
    props: dict

    hooks: list[Hook]
    hook_idx: int
    rendered: list["Vdom"]
    invalidated_event: asyncio.Event
    update_loop_task: asyncio.Task

    @property
    def name(self) -> str:
        return getattr(self.component, "__name__")

    def __str__(self) -> str:
        return f"<{self.name} {self.id}>"

    def __init__(self, spec: "FiberSpec"):
        self.id = fresh_id()
        self.key = spec.key
        self.invalidated_event = asyncio.Event()
        component = spec.component
        if not hasattr(component, "__name__"):
            logger.warning(f"Please name component {component}.")
        self.component = component
        self.props = spec.props
        assert not hasattr(self, "rendered") and not hasattr(
            self, "hooks"
        ), "already created"
        self.hooks = []
        self.hook_idx = 0
        t = fiber_context.set(self)
        s: Spec = self.component(self.props)
        self.rendered = create(normalise_spec(s))
        fiber_context.reset(t)
        self.update_loop_task = asyncio.create_task(self.update_loop())

    async def update_loop(self):
        while True:
            await self.invalidated_event.wait()
            logger.debug(f"{str(self)} rerendering.")
            self.invalidated_event.clear()
            try:
                self.reconcile_core(self.component, self.props)
            except Exception as e:
                logger.error(e)
                console.print_exception()

    def dispose(self):
        # [todo] can I just use GC?
        assert hasattr(self, "hooks")
        assert hasattr(self, "rendered"), "fiber is not rendered"
        dispose(self.rendered)
        for hook in reversed(self.hooks):
            hook.dispose()
        self.update_loop_task.cancel()

    def invalidate(self):
        """Called when a hook's callback is invoked, means that a re-render must occur."""
        logger.debug(f"{str(self)} invalidated.")
        self.invalidated_event.set()

    def reconcile_hook(self, hook: H) -> H:
        if self.hook_idx >= len(self.hooks):
            # initialisation case
            self.hooks.append(hook)
            return hook

        old_hook: H = self.hooks[self.hook_idx]  # type: ignore
        if type(old_hook) != type(hook):
            logger.error("Hook reordering detected. Make sure that all hooks are run.")
            old_hook.dispose()
            self.hooks[self.hook_idx] = hook
        else:
            old_hook.reconcile(hook)  # type: ignore
        return old_hook

    def reconcile_core(self, component: "Component", props: Any):
        self.invalidated_event.clear()
        t = fiber_context.set(self)
        self.hook_idx = 0
        try:
            spec = component(props)
        except NoNeedToRerender:
            assert hasattr(self, "rendered")
            return
        except Exception as e:
            logger.error(f"Error while rendering component {str(self)}: {e}")
            console.print_exception()
            # [todo] inject a message into DOM here, or set the border colour.
            return
        finally:
            fiber_context.reset(t)
        spec = normalise_spec(spec)
        children, reorder = reconcile_lists(self.rendered, spec)
        self.render = children
        l = self.hook_idx + 1
        old_hooks = self.hooks[l:]
        self.hooks = self.hooks[:l]
        for hook in reversed(old_hooks):
            hook.dispose()
        patch(
            ModifyChildrenPatch(
                element_id=self.id,
                remove_these=reorder.remove_these,
                then_insert_these=reorder.then_insert_these,
            )
        )
        return

    def reconcile(self, new_spec: "FiberSpec") -> "Fiber":
        assert hasattr(self, "hooks") and hasattr(self, "rendered"), "not created"
        # if the identity of the component function has changed that
        # means we should rerender.
        if new_spec.name != self.name or self.component is not new_spec.component:
            self.dispose()
            new_fiber = Fiber(new_spec)
            return new_fiber
        # [todo] check whether the props have changed here
        if self.props == new_spec.props and not self.invalidated_event.is_set():
            return self
        self.props = new_spec.props
        self.reconcile_core(self.component, self.props)
        return self


fiber_context: ContextVar[Fiber] = ContextVar("fiber_context")


def useState(init: S) -> tuple[S, SetterFn[S]]:
    ctx = fiber_context.get()
    hook: StateHook[S] = ctx.reconcile_hook(StateHook(init, ctx))
    return hook.pull()  # type: ignore


def useEffect(callback: Callable[[], Optional[Callable[[], None]]], deps=None):
    ctx = fiber_context.get()
    ctx.reconcile_hook(EffectHook(callback, deps))


class Component(Protocol[A]):
    def __call__(self, props: A) -> "Spec":
        ...


@dataclass
class FiberSpec(Generic[A]):
    component: Component
    props: A
    key: Optional[str] = field(default=None)

    @property
    def name(self):
        return getattr(self.component, "__name__", "unknown")


@dataclass
class ElementSpec:
    tag: str
    attrs: dict
    children: list["NormSpec"]

    @property
    def key(self):
        return self.attrs.get("key", None)


@dataclass
class Element:
    tag: str
    attrs: dict
    children: list["Vdom"]
    id: int

    @property
    def key(self):
        return self.attrs.get("key", None)

    @classmethod
    def create(cls, spec: ElementSpec):
        elt = cls(
            spec.tag, attrs=spec.attrs, children=create(spec.children), id=fresh_id()
        )
        for k, v in elt.attrs.items():
            if callable(v):
                # event handler
                reactor_context.get().register(elt, k, v)
        return elt

    def dispose(self):
        # delete references to event handlers.
        for k, v in self.attrs.items():
            if callable(v):
                reactor_context.get().unregister(self, k)
        dispose(self.children)

    def render_attr(self, value):
        if callable(value):
            # it's an event handler
            return {"__handler__": self.id}
        else:
            return value

    def render(self):
        return {
            "kind": "Element",
            "id": self.id,
            "tag": self.tag,
            "attrs": {k: self.render_attr(v) for k, v in self.attrs.items()},
            "children": render(self.children),
        }

    def reconcile_attrs(self, new_attrs_spec: dict) -> dict:
        for k, v in self.attrs.items():
            if callable(v):
                reactor_context.get().unregister(self, k)
        for k, v in new_attrs_spec.items():
            if callable(v):
                reactor_context.get().register(self, k, v)
        diff = dict_diff(self.attrs, new_attrs_spec)
        remove = list(diff.rm)
        add = {k: self.render_attr(new_attrs_spec[k]) for k in diff.add}
        mod = {k: self.render_attr(v2) for k, (v1, v2) in diff.mod.items()}
        patch(
            ModifyAttributesPatch(remove=remove, add={**add, **mod}, element_id=self.id)
        )
        self.attrs = new_attrs_spec
        return self.attrs

    def reconcile(self, new_spec: ElementSpec) -> "Element":
        if (
            not isinstance(new_spec, ElementSpec)
            or (self.key != new_spec.key)
            or (self.tag != new_spec.tag)
        ):
            self.dispose()
            new_elt = Element.create(new_spec)
            patch(ReplaceElementPatch(self.id, new_elt))
            return new_elt
        self.reconcile_attrs(new_spec.attrs)
        children, r = reconcile_lists(self.children, new_spec.children)
        patch(
            ModifyChildrenPatch(
                element_id=self.id,
                remove_these=r.remove_these,
                then_insert_these=r.then_insert_these,
            )
        )
        self.tag = new_spec.tag
        self.children = children
        return self
        # [todo] reconcile attrs? need to update event handlers?


NormSpec = Union[str, ElementSpec, FiberSpec]
Spec = Optional[Union[str, ElementSpec, FiberSpec, list["Spec"]]]
Vdom = Union[str, Element, Fiber]


def iter_fibers_and_elts(v: Union[Vdom, list[Vdom]]) -> Iterator[Union[Fiber, Element]]:
    if isinstance(v, Fiber):
        yield v
    elif isinstance(v, list):
        for vv in v:
            yield from iter_fibers_and_elts(vv)
    elif isinstance(v, Element):
        yield v
    elif isinstance(v, str):
        return
    else:
        raise TypeError(f"Unrecognised vdom {v}")


def iter_fibers(v: Union[Vdom, list[Vdom]]) -> Iterator[Fiber]:
    if isinstance(v, Fiber):
        yield v
    elif isinstance(v, list):
        for vv in v:
            yield from iter_fibers(vv)
    elif isinstance(v, Element):
        for c in v.children:
            yield from iter_fibers(c)
    elif isinstance(v, str):
        return
    else:
        raise TypeError(f"Unrecognised vdom {v}")


def dispose(v: Union[Vdom, list["Vdom"]]):
    for f in iter_fibers_and_elts(v):
        f.dispose()


@overload
def create(s: NormSpec) -> Vdom:
    ...


@overload
def create(s: list[NormSpec]) -> list[Vdom]:
    ...


def create(s):
    if isinstance(s, list):
        return list(map(create, s))
    if isinstance(s, FiberSpec):
        return Fiber(s)
    elif isinstance(s, ElementSpec):
        return Element.create(s)
    elif isinstance(s, str):
        return s
    else:
        raise TypeError(f"Unrecognised {s}")


def normalise_spec(c: Spec) -> list[NormSpec]:
    def norm_list(cs) -> Any:
        for c in cs:
            if isinstance(c, (list, tuple)):
                yield from norm_list(c)
            elif isinstance(c, Element):
                yield c
            elif c is None or c is False or not c:
                continue
            else:
                yield c

    return list(norm_list([c]))


def keyof(x: Union[NormSpec, Vdom]) -> Any:
    if isinstance(x, (Element, ElementSpec)):
        return ("elt", x.tag, x.key)
    elif isinstance(x, Fiber) or isinstance(x, FiberSpec):
        return ("fib", x.name, x.key)
    elif isinstance(x, str):
        return x
    else:
        return None


def reconcile_lists(
    old: list[Vdom], new: list[NormSpec]
) -> tuple[list[Vdom], Reorder[Vdom]]:
    r: Reorder = listdiff(list(map(keyof, old)), list(map(keyof, new)))
    for ri in r.deletions:
        dispose(old[ri])
    new_vdom: list[Any] = [None] * len(new)
    for i, j in r.moves:
        assert new_vdom[j] is None
        new_vdom[j] = reconcile(old[i], new[j])
    for j in r.creations:
        assert new_vdom[j] is None
        new_vdom[j] = create(new[j])
    # [todo] can also compute the DOM patch here.
    r = r.map_inserts(lambda j, _: new_vdom[j])

    return new_vdom, r


def reconcile(old: Vdom, new: NormSpec) -> Vdom:
    if isinstance(old, Element) and isinstance(new, ElementSpec):
        return old.reconcile(new)
    elif isinstance(old, Fiber) and isinstance(new, FiberSpec):
        return old.reconcile(new)
    dispose(old)
    return create(new)


@overload
def h(tag: str, attrs: dict, *children: Spec, key: Optional[str] = None) -> ElementSpec:
    ...


@overload
def h(tag: Component[T], attrs: T, *, key: Optional[str] = None) -> FiberSpec:
    ...


def h(tag, attrs, *children: Spec, key=None) -> Union[ElementSpec, FiberSpec]:
    all_children = normalise_spec(list(children))
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


def render(v: Union[Vdom, list[Vdom]]):
    """Convert Vdom member to wire protocol."""
    if isinstance(v, list):
        return list(map(render, v))
    elif isinstance(v, str):
        return {"kind": "Text", "value": v}
    elif isinstance(v, Element):
        return v.render()
    elif isinstance(v, Fiber):
        return {
            "kind": "Fiber",
            "name": v.name,
            "id": v.id,
            "children": render(v.rendered),
        }
    else:
        raise TypeError(f"unrecognised vdom: {v}")


@dataclass
class ModifyAttributesPatch:
    remove: list[str]
    add: dict[str, Any]
    element_id: int
    kind: str = field(default="modify-attrs")

    @property
    def is_empty(self) -> bool:
        return len(self.remove) == 0 and len(self.add) == 0


@dataclass
class ModifyChildrenPatch:
    element_id: int
    remove_these: dict
    then_insert_these: dict
    kind: str = field(default="modify-children")

    @property
    def is_empty(self) -> bool:
        return len(self.remove_these) == 0 and len(self.then_insert_these) == 0


@dataclass
class ReplaceElementPatch:
    element_id: int
    new_element: Any  # output of render
    kind: str = field(default="replace-element")

    @property
    def is_empty(self) -> bool:
        return False


@dataclass
class ReplaceRootPatch:
    items: Any  # output of render
    kind: str = field(default="replace-root")

    @property
    def is_empty(self) -> bool:
        return False


# [todo] RPC-encoding for patches
Patch = Union[
    ModifyAttributesPatch, ModifyChildrenPatch, ReplaceRootPatch, ReplaceElementPatch
]


@dataclass
class EventArgs:
    element_id: int
    name: str
    params: Optional[Any]


class Reactor:
    event_table: dict
    event_tasks: set[asyncio.Task]
    root: list[Vdom]
    pending_patches: list[Patch]
    patches_ready: asyncio.Event

    def __init__(self, spec: Spec):
        self.spec = normalise_spec(spec)
        self.event_table = {}
        self.pending_patches = []
        self.patches_ready = asyncio.Event()

    async def get_patches(self):
        await self.patches_ready.wait()
        self.patches_ready.clear()
        patches = self.pending_patches
        self.pending_patches = []
        return patches

    def patch(self, patch: Patch):
        if patch.is_empty:
            return
        self.pending_patches.append(patch)
        self.patches_ready.set()

    def initialize(self):
        logger.debug("Initialising reactor.")
        t = reactor_context.set(self)
        self.root = create(self.spec)
        reactor_context.reset(t)
        return render(self.root)

    def render(self):
        """Re-compute the whole tree."""
        self.pending_patches = []
        self.patches_ready.clear()
        return render(self.root)

    def handle_event(self, params: EventArgs):
        assert isinstance(params, EventArgs)
        logger.debug(f"handling {params.name}")
        k = (params.element_id, params.name)
        assert k in self.event_table
        handler = self.event_table[k]
        t = reactor_context.set(self)
        r = handler(params.params)
        if inspect.iscoroutine(r):
            et = asyncio.create_task(r)
            self.event_tasks.add(et)
            et.add_done_callback(self.event_tasks.discard)
            # note that we don't cancel event tasks if the handler gets replaced.

        reactor_context.reset(t)
        # event handler will call code to invalidate components.
        # [todo] trigger a re-render

    def register(self, elt: Element, attr_name: str, handler: Callable):
        k = (elt.id, attr_name)
        assert k not in self.event_table
        self.event_table[k] = handler

    def unregister(self, elt: Element, attr_name: str):
        k = (elt.id, attr_name)
        assert k in self.event_table
        del self.event_table[k]


reactor_context: ContextVar[Reactor] = ContextVar("reactor_context")


def patch(patch: Patch):
    return reactor_context.get().patch(patch)
