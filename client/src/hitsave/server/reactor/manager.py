import asyncio
from dataclasses import dataclass
import inspect
from typing import Any, Callable, Optional

from .html import Html
from .vdom import (
    Id,
    Rendering,
    Vdom,
    dispose,
    fresh_id,
    reconcile_lists,
    render,
    normalise_html,
    set_vdom_context,
)
from .patch import ModifyChildrenPatch, Patch
from hitsave.util.asyncio import MessageQueue
from hitsave.console import logger, console


@dataclass
class EventArgs:
    element_id: Id
    name: str
    params: Optional[Any]


class Manager:
    id: Id

    event_table: dict[tuple[Id, str], Callable]
    event_tasks: set[asyncio.Task]
    root: list[Vdom]
    pending_patches: MessageQueue[Patch]

    def __init__(self):
        self.id = fresh_id()
        self.event_table = {}
        self.pending_patches = MessageQueue()

    def update(self, html: Html):
        with set_vdom_context(self):
            spec = normalise_html(html)
            new_root, reorder = reconcile_lists(self.root, spec)
            self.root = new_root
            self._patch(
                ModifyChildrenPatch(
                    element_id=self.id,
                    remove_these=reorder.remove_these,
                    then_insert_these=reorder.then_insert_these,
                )
            )

    @property
    def is_initialized(self):
        return hasattr(self, "root")

    def render(self) -> Rendering:
        self.pending_patches.clear()
        return render(self.root)

    def dispose(self):
        dispose(self.root)
        delattr(self, "root")
        self.pending_patches.clear()

    def _patch(self, patch: Patch):
        if patch.is_empty:
            return
        self.pending_patches.push(patch)
        logger.debug(f"pending patches: {len(self.pending_patches)}")

    def _register_event(self, id: Id, attr_name: str, handler: Callable):
        k = (id, attr_name)
        assert k not in self.event_table
        self.event_table[k] = handler

    def _unregister_event(self, id: Id, attr_name: str):
        k = (id, attr_name)
        assert k in self.event_table
        del self.event_table[k]

    def handle_event(self, params: EventArgs):
        with set_vdom_context(self):
            assert isinstance(params, EventArgs)
            logger.debug(f"handling {params.name}")
            k = (params.element_id, params.name)
            assert k in self.event_table
            handler = self.event_table[k]

            r = handler(params.params)
            if inspect.iscoroutine(r):
                et = asyncio.create_task(r)
                self.event_tasks.add(et)
                et.add_done_callback(self.event_tasks.discard)
                # note that we don't cancel event tasks if the handler gets replaced.

        # event handler will call code to invalidate components.
        # [todo] trigger a re-render

    async def wait_patches(self):
        return await self.pending_patches.pop_many()
