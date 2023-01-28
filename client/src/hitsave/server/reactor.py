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

""" React, in Python. How hard can it be? """

logger = logging.getLogger("ui-driver")

P = ParamSpec("P")
T = TypeVar("T")
S = TypeVar("S")
R = TypeVar("R")
H = TypeVar("H", bound="Hook")


class Hook:
    fiber: "Fiber"

    def __init__(self, fiber: "Fiber"):
        self.fiber = fiber

    def reconcile(self, new_hook: "Hook"):
        raise NotImplementedError()

    def create(self):
        pass

    def dispose(self):
        pass

    def invalidate(self):
        # [todo] check: you shouldn't be allowed to call invalidate in the rendering
        # phase, because then we will just infinitely loop.
        self.fiber.invalidate()


class NoNeedToRerender(Exception):
    pass


class StateHook(Hook, Generic[S]):
    state: S

    def __init__(self, init: S):
        self.state = init

    def reconcile(self, new_hook: "StateHook") -> "StateHook":
        assert type(self) == type(new_hook)
        return self

    def set(self, item: S):
        self.state = item
        self.invalidate()
        return

    def pull(self):
        return (self.state, self.set)


class EffectHook(Hook):
    def __init__(self, callback, deps):
        self.callback = callback
        self.deps = deps
        self.disposal_fn = None

    def dispose(self):
        if self.disposal_fn is not None:
            self.disposal_fn()
            self.disposal_fn = None

    def evaluate(self):
        callback = self.callback
        assert callable(callback)
        if self.disposal_fn is not None:
            self.disposal_fn()
            self.disposal_fn = None
        # [todo] async callback. Promise.resolve() for python?
        disposal_fn = callback()
        if disposal_fn is not None:
            assert callable(disposal_fn)
            self.disposal_fn = disposal_fn

    def reconcile(self, new_hook: "EffectHook"):
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
                    update()
                    break
        return self


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

    def __init__(self, spec: "FiberSpec"):
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
            self.invalidated_event.clear()
            self.reconcile_core(self.component, self.props)

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
        self.invalidated_event.set()

    @property
    def key(self):
        return self.props.get("key", None)

    def reconcile_hook(self, hook: H) -> H:
        if self.hook_idx >= len(self.hooks):
            # initialisation case
            hook.create()
            self.hooks.append(hook)
            return hook

        old_hook: H = self.hooks[self.hook_idx]  # type: ignore
        if type(old_hook) != type(hook):

            raise TypeError(
                f"Hook reordering detected. Make sure that all hooks are run."
            )
            # [todo] just reinitialise hook in this case
            # tear down the old hook too.
        old_hook.reconcile(hook)
        return old_hook

    @property
    def id(self):
        return id(self)

    def reconcile_core(self, component: "Component", props: Any):
        t = fiber_context.set(self)
        self.hook_idx = 0
        try:
            spec = component(props)
        except NoNeedToRerender:
            assert hasattr(self, "rendered")
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
        self.component = new_spec.component
        self.props = new_spec.props
        self.reconcile_core(self.component, self.props)
        return self


fiber_context: ContextVar[Fiber] = ContextVar("fiber_context")


def useState(init: S) -> tuple[S, Callable[[S], None]]:
    ctx = fiber_context.get()
    hook: StateHook[S] = ctx.reconcile_hook(StateHook(init))
    return hook.pull()


def useEffect(callback: Callable[[], Optional[Callable[[], None]]], deps=None):
    ctx = fiber_context.get()
    ctx.reconcile_hook(EffectHook(callback, deps))


Component = Callable[[dict[str, Any]], "Spec"]


@dataclass
class FiberSpec:
    component: Component
    props: dict

    @property
    def name(self):
        return self.component.__name__

    @property
    def key(self):
        return self.props.get("key", None)


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

    @property
    def key(self):
        return self.attrs.get("key", None)

    @property
    def id(self):
        # [todo] probably use a deterministic counter?
        return id(self)

    @classmethod
    def create(cls, spec: ElementSpec):
        elt = cls(spec.tag, attrs=spec.attrs, children=create(spec.children))
        for k, v in elt.attrs.items():
            if callable(v):
                # event handler
                reactor_context.get().register(elt, k, v)
        return elt

    def dispose(self):
        # delete references to event handlers.
        for k, v in self.attrs:
            if callable(v):
                reactor_context.get().unregister(self, k)
        for c in self.children:
            c.dispose()

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

    def reconcile_attrs(self, new_attrs_spec):
        for k, v in self.attrs.items():
            if callable(v):
                reactor_context.get().unregister(self, k)
        for k, v in new_attrs_spec.attrs.items():
            if callable(v):
                reactor_context.get().register(self, k, v)
        diff = dict_diff(self.attrs, new_attrs_spec)
        remove = list(diff.rm)
        add = {k: self.render_attr(new_attrs_spec[k]) for k in diff.add}
        mod = {k: self.render_attr(v2) for k, (v1, v2) in diff.mod}
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
    for f in iter_fibers(v):
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
    if isinstance(x, Element):
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


def h(tag, attrs: dict, *children: Spec) -> Union[ElementSpec, FiberSpec]:
    attr_children: list = attrs.pop("children", [])
    all_children = normalise_spec(list(attr_children) + list(children))
    if type(tag) == str:
        return ElementSpec(tag=tag, attrs=attrs, children=all_children)
    elif callable(tag):
        if len(all_children) > 0:
            attrs["children"] = all_children
        return FiberSpec(component=tag, props=attrs)
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
            "id": id(v),
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


@dataclass
class ModifyChildrenPatch:
    element_id: int
    remove_these: dict
    then_insert_these: dict
    kind: str = field(default="modify-children")


@dataclass
class ReplaceElementPatch:
    element_id: int
    new_element: Any  # output of render
    kind: str = field(default="replace-element")


@dataclass
class ReplaceRootPatch:
    items: Any  # output of render
    kind: str = field(default="replace-root")


Patch = Union[
    ModifyAttributesPatch, ModifyChildrenPatch, ReplaceRootPatch, ReplaceElementPatch
]


@dataclass
class EventArgs:
    element_id: int
    name: str
    params: Any


class Reactor:
    event_table: dict
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
        self.pending_patches.append(patch)

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
            asyncio.create_task(r)

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


###### Example usage


if __name__ == "__main__":

    def Counter(props) -> Spec:
        i, set_i = useState(0)
        return h(
            "div",
            {},
            [
                h("button", dict(click=lambda: set_i(i + 1)), "+"),
                str(i),
                h("button", dict(click=lambda: set_i(i - 1)), "-"),
            ],
        )

    reactor = Reactor(h(Counter, {}))
    d = reactor.initialize()
    print(d)
