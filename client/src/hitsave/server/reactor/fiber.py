import asyncio
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    ClassVar,
    Coroutine,
    Generic,
    Optional,
    Protocol,
    TypeVar,
    Union,
    overload,
)
from .rendering import RenderedFragment, Rendering
from hitsave.console import logger, console
from hitsave.server.reactor.patch import ModifyChildrenPatch
from .vdom import (
    Html,
    NormSpec,
    Vdom,
    create,
    dispose,
    fresh_id,
    normalise_html,
    patch,
    reconcile_lists,
)


S = TypeVar("S")

SetterFn = Callable[[Union[S, Callable[[S], S]]], None]


class NoNeedToRerender(Exception):
    pass


class StateHook(Generic[S]):
    state: S

    def __init__(self, init: S, fiber: "Fiber"):
        self.state = init
        self.fiber = fiber

    def __str__(self):
        return f"<{type(self).__name__} {type(self.state)}>"

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

    def __str__(self):
        return f"<{type(self).__name__}>"

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

A = TypeVar("A", contravariant=True)


class Component(Protocol[A]):
    def __call__(self, props: A) -> Html:
        ...


@dataclass
class FiberSpec(Generic[A], NormSpec):
    component: Component[A]
    props: A
    key: Optional[str] = field(default=None)

    @property
    def name(self):
        return getattr(self.component, "__name__", "unknown")

    def create(self):
        return Fiber.create(self)

    def __str__(self):
        return self.name


H = TypeVar("H", bound="Hook")


class Fiber(Vdom):
    """Like React fibers."""

    spec_type: ClassVar = FiberSpec

    component: "Component"
    props: dict

    hooks: list[Hook]
    hook_idx: int
    rendered: list[Vdom]
    invalidated_event: asyncio.Event
    update_loop_task: asyncio.Task

    @property
    def name(self) -> str:
        return getattr(self.component, "__name__")

    def __str__(self) -> str:
        return f"<{self.name} {self.id}>"

    def __init__(self, spec: "FiberSpec"):
        self.id = fresh_id()
        self.key = spec.key  # type: ignore
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
        s = self.component(self.props)
        self.rendered = create(normalise_html(s))
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
            self.hook_idx += 1
            return hook

        old_hook: H = self.hooks[self.hook_idx]  # type: ignore
        if type(old_hook) != type(hook):
            logger.error(
                f"{self} {self.hook_idx}th hook changed type from {str(old_hook)} to {str(hook)}"
            )
            old_hook.dispose()
            self.hooks[self.hook_idx] = hook
        else:
            old_hook.reconcile(hook)  # type: ignore
        self.hook_idx += 1
        return old_hook

    def reconcile_core(self, component: Component[A], props: A):
        self.invalidated_event.clear()
        t = fiber_context.set(self)
        self.hook_idx = 0
        try:
            spec = component(props)
        except NoNeedToRerender:
            assert hasattr(self, "rendered")
            logger.debug(f"{str(self)} Skipping re-render")
            return
        except Exception as e:
            logger.error(f"{str(self)} Error while rendering component: {e}")
            console.print_exception()
            # [todo] inject a message into DOM here, or set the border colour.
            return
        finally:
            fiber_context.reset(t)
        spec = normalise_html(spec)
        children, reorder = reconcile_lists(self.rendered, spec)
        self.rendered = children
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
        assert isinstance(new_spec, FiberSpec)
        assert hasattr(self, "hooks") and hasattr(self, "rendered"), "not created"
        # if the identity of the component function has changed that
        # means we should rerender.
        if new_spec.name != self.name or self.component is not new_spec.component:
            self.dispose()
            new_fiber = Fiber(new_spec)
            return new_fiber
        # [todo] check whether the props have changed here
        if self.props == new_spec.props and not self.invalidated_event.is_set():
            logger.debug(f"{str(self)} has unchanged props. Skipping re-render.")
            return self
        self.props = new_spec.props
        self.reconcile_core(self.component, self.props)
        return self

    def render(self) -> Rendering:
        return RenderedFragment(
            id=self.id, children=[x.render() for x in self.rendered]
        )

    @classmethod
    def create(cls, spec: FiberSpec):
        return cls(spec)


fiber_context: ContextVar[Fiber] = ContextVar("fiber_context")


def useState(init: S) -> tuple[S, SetterFn[S]]:
    ctx = fiber_context.get()
    hook: StateHook[S] = ctx.reconcile_hook(StateHook(init, ctx))
    return hook.pull()  # type: ignore


def useEffect(callback: Callable[[], Coroutine[Any, Any, None]], deps=None):
    ctx = fiber_context.get()
    ctx.reconcile_hook(EffectHook(callback, deps))
