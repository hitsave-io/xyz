from contextvars import ContextVar
from dataclasses import dataclass, replace
import logging
from typing import Any, Callable, Generic, Iterable, Iterator, Optional, ParamSpec, Sequence, TypeGuard, TypeVar, Union, overload
from typing_extensions import override
from uuid import UUID, uuid4
from .listdiff import diff as listdiff

""" React, in Python. How hard can it be? """

logger = logging.getLogger('ui-driver')

P = ParamSpec("P")
T = TypeVar('T')
S = TypeVar('S')
R = TypeVar('R')
H = TypeVar('H', bound = "Hook")

class Hook:
    fiber : "Fiber"

    def __init__(self, fiber : "Fiber"):
        self.fiber = fiber


    def reconcile(self, new_hook : "Hook"):
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
    state : S
    def __init__(self, init : S):
        self.state = init

    def reconcile(self, new_hook : "StateHook") -> "StateHook":
        assert type(self) == type(new_hook)
        return self

    def set(self, item : S):
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

    def reconcile(self, new_hook : "EffectHook"):
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
    component : "Component"
    props : dict
    id : str

    hooks : list[Hook]
    hook_idx : int
    rendered : list["Vdom"]

    @property
    def name(self) -> str:
        return getattr(self.component, "__name__")

    def __init__(self, spec: "FiberSpec"):
        component = spec.component
        if not hasattr(component, "__name__"):
            logger.warning(f'Please name component {component}.')
        self.component = component
        self.props = spec.props
        self.id = uuid4().hex

    def dispose(self):
        assert hasattr(self, 'hooks')
        assert hasattr(self, 'rendered'), 'fiber is not rendered'
        dispose(self.rendered)
        for hook in reversed(self.hooks):
            hook.dispose()


    def invalidate(self):
        """ Called when a hook's callback is invoked, means that a re-render must occur. """
        ...

    @property
    def key(self):
        return self.props.get("key", None)

    def create(self):
        assert not hasattr(self, "rendered") and not hasattr(self, 'hooks'), "already created"
        self.hooks = []
        self.hook_idx = 0
        t = fiber_context.set(self)
        spec = self.component(self.props)
        spec = normalise_spec(spec)
        self.rendered = create(spec)
        fiber_context.reset(t)

    def reconcile_hook(self, hook : H) -> H:
        if self.hook_idx >= len(self.hooks):
            # initialisation case
            hook.create()
            self.hooks.append(hook)
            return hook

        old_hook : H = self.hooks[self.hook_idx] # type: ignore
        if type(old_hook) != type(hook):

            raise TypeError(f"Hook reordering detected. Make sure that all hooks are run.")
            # [todo] just reinitialise hook in this case
            # tear down the old hook too.
        old_hook.reconcile(hook)
        return old_hook

    def reconcile(self, new_spec : "FiberSpec") -> "Fiber":
        assert hasattr(self, 'hooks') and hasattr(self, 'rendered'), "not created"
        if new_spec.name != self.name:
            self.dispose()
            new_fiber = Fiber(new_spec)
            new_fiber.create()
            return new_fiber
        # [todo] check whether the props have changed here
        t = fiber_context.set(self)
        self.hook_idx = 0
        try:
            spec = new_spec.component(new_spec.props)
            spec = normalise_spec(spec)
            self.rendered = reconcile_lists(self.rendered, spec)
        except NoNeedToRerender:
            assert hasattr(self, 'rendered')
            return self
        finally:
            fiber_context.reset(t)
        l = self.hook_idx + 1
        old_hooks = self.hooks[l:]
        self.hooks = self.hooks[:l]
        for hook in reversed(old_hooks):
            hook.dispose()
        return self

fiber_context : ContextVar[Fiber] = ContextVar('fiber_context')

def useState(init : S) -> tuple[S, Callable[[S], None]]:
    ctx = fiber_context.get()
    hook : StateHook[S] = ctx.reconcile_hook(StateHook(init))
    return hook.pull()

def useEffect(callback : Callable[[], Optional[Callable[[], None]]], deps = None):
    ctx = fiber_context.get()
    ctx.reconcile_hook(EffectHook(callback, deps))


Component = Callable[[dict[str, Any]], "Spec"]

@dataclass
class FiberSpec:
    component : Component
    props : dict

    @property
    def name(self):
        return self.component.__name__

    @property
    def key(self):
        return self.props.get("key", None)

@dataclass
class Element(Generic[S]):
    tag : str
    attrs : dict
    children : list[S]

    @property
    def key(self):
        return self.attrs.get('key', None)

NormSpec = Union[str, "Element[NormSpec]", FiberSpec]
Spec = Optional[Union[str, "Element[NormSpec]", FiberSpec, list['Spec']]]
Vdom = Union[str, "Element[Vdom]", Fiber]


def iter_fibers(v : Union[Vdom, list[Vdom]]) -> Iterator[Fiber]:
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
        raise TypeError(f'Unrecognised vdom {v}')


def dispose(v : Union[Vdom, list["Vdom"]]):
    for f in iter_fibers(v):
        f.dispose()



@overload
def create(s : NormSpec) -> Vdom:
    ...

@overload
def create(s : list[NormSpec]) -> list[Vdom]:
    ...

def create(s):
    if isinstance(s, list):
        return list(map(create, s))
    if isinstance(s, FiberSpec):
        return Fiber(s)
    elif isinstance(s, Element):
        cs = list(map(create, s.children))
        return Element(tag = s.tag, attrs = s.attrs, children = cs)
    elif isinstance(s, str):
        return s
    else:
        raise TypeError(f"Unrecognised {s}")


def normalise_spec(c : Spec) -> list[NormSpec]:
    def norm_elt(e : Element[Spec]) -> Element[NormSpec]:
        children = normalise_spec(e.children)
        return replace(e, children = children) # type: ignore
    def norm_list(cs):
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

def keyof(x : Union[NormSpec, Vdom]):
    if isinstance(x, Element):
        return ('elt', x.tag, x.key)
    elif isinstance(x, Fiber) or isinstance(x, FiberSpec):
        return ('fib', x.name, x.key)
    elif isinstance(x, str):
        return x
    else:
        return None

def reconcile_lists(old : list[Vdom], new : list[NormSpec]) -> list[Vdom]:
    r = listdiff(list(map(keyof, old)), list(map(keyof, new)))
    for ri in r.deletions:
        dispose(old[ri])
    new_vdom : list[Any] = [None] * len(new)
    for i, j in r.moves:
        assert new_vdom[j] is None
        new_vdom[j] = reconcile(old[i], new[j])
    for j in r.creations:
        assert new_vdom[j] is None
        new_vdom[j] = create(new[j])
    # [todo] can also compute the DOM patch here.
    return new_vdom

def reconcile(old : Vdom, new : NormSpec) -> Vdom:
    if isinstance(old, Element) and isinstance(new, Element):
        if old.key != new.key or old.tag != new.tag:
            return create(new)
        children = reconcile_lists(old.children, new.children)
        return Element[Vdom](
            tag = new.tag,
            attrs = new.attrs,
            children = children,
        )
        # [todo] reconcile attrs? need to update event handlers?
    elif isinstance(old, Fiber) and isinstance(new, FiberSpec):
        return old.reconcile(new)
    dispose(old)
    return create(new)

def h(tag, attrs: dict, children : Iterable[Spec]) -> Union[Element[NormSpec], FiberSpec]:
    attr_children : list = attrs.pop('children', [])
    all_children = normalise_spec(list(attr_children) + list(children))
    if type(tag) == str:
        return Element(tag = tag, attrs = attrs, children = all_children)
    elif callable(tag):
        if len(all_children) > 0:
            attrs['children'] = all_children
        return FiberSpec(component = tag, props = attrs)
    else:
        raise TypeError(f"unrecognised tag: {tag}")

def render(v : Union[Vdom, list[Vdom]]):
    """ Convert Vdom member to wire protocol. """
    if isinstance(v, list):
        return list(map(render, v))
    elif isinstance(v, str):
        return {"kind": "Text", "value": v}
    elif isinstance(v, Element):
        return {"kind" : "Element", "tag" : v.tag, "attrs" : v.attrs, "children" : render(v.children)}
    elif isinstance(v, Fiber):
        return {"kind" : "Fiber", "name" : v.name, "children" : render(v.rendered)}
    else:
        raise TypeError(f"unrecognised vdom: {v}")


###### Example usage

def Counter(props) -> Spec:
    i, set_i = useState(0)
    return h(
        "div",
        {}, [
            h('button', dict(click = lambda: set_i(i + 1)), "+"),
            str(i),
            h('button', dict(click = lambda: set_i(i - 1)), "-")
        ]
    )

render(id = 'react_root', Counter)