from dataclasses import dataclass
from typing import ClassVar, Union
from hitsave.util.misc import dict_diff
import logging
from .patch import ModifyAttributesPatch, ModifyChildrenPatch, ReplaceElementPatch
from .vdom import (
    Id,
    NormSpec,
    Vdom,
    VdomContext,
    create,
    dispose,
    fresh_id,
    patch,
    reconcile_lists,
    vdom_context,
)
logger = logging.getLogger('reactor')

@dataclass
class ElementSpec(NormSpec):
    tag: str
    attrs: dict
    children: list[NormSpec]

    @property
    def key(self):
        return hash(("element", self.tag, self.attrs.get("key", None)))

    def __str__(self) -> str:
        return f"<{self.tag}/>"

    def create(self) -> "Element":
        return Element.create(self)


@dataclass
class EventHandler:
    element_id: Id

    def render(self):
        return {"__handler__": self.element_id}

    def __eq__(self, other):
        if not isinstance(other, EventHandler):
            return False
        return self.element_id == other.element_id


@dataclass
class Element(Vdom):
    spec_type: ClassVar = ElementSpec
    tag: str
    attrs: dict[str, Union[EventHandler, str]]
    children: list[Vdom]
    id: Id
    key: int

    def __str__(self) -> str:
        return f"<{self.tag} {self.id}>"

    @classmethod
    def create(cls, spec: ElementSpec):
        id = fresh_id()
        attrs = {}
        for k, v in spec.attrs.items():
            if callable(v):
                vdom_context.get()._register_event(id, k, v)
                v = EventHandler(id)
            attrs[k] = v
        elt = cls(
            spec.tag, attrs=attrs, children=create(spec.children), id=id, key=spec.key
        )
        return elt

    def dispose(self):
        # delete references to event handlers.
        for k, v in self.attrs.items():
            if isinstance(v, EventHandler):
                vdom_context.get()._unregister_event(self.id, k)
        dispose(self.children)

    def render_attr(self, value):
        if isinstance(value, EventHandler):
            # it's an event handler
            return value.render()
        else:
            return value

    def render(self):
        return {
            "kind": "Element",
            "id": self.id,
            "tag": self.tag,
            "attrs": {k: self.render_attr(v) for k, v in self.attrs.items()},
            "children": [c.render() for c in self.children],
        }

    def reconcile_attrs(self, new_attrs_spec: dict) -> dict:
        for k, v in self.attrs.items():
            if isinstance(v, EventHandler):
                vdom_context.get()._unregister_event(self.id, k)
        new_attrs = {}
        for k, v in new_attrs_spec.items():
            if callable(v):
                vdom_context.get()._register_event(self.id, k, v)
                v = EventHandler(self.id)
            new_attrs[k] = v
        diff = dict_diff(self.attrs, new_attrs)
        remove = list(diff.rm)
        add = {k: self.render_attr(new_attrs[k]) for k in diff.add}
        mod = {k: self.render_attr(v2) for k, (v1, v2) in diff.mod.items()}
        patch(
            ModifyAttributesPatch(remove=remove, add={**add, **mod}, element_id=self.id)
        )
        self.attrs = new_attrs
        return self.attrs

    def reconcile(self, new_spec: ElementSpec) -> "Element":
        assert isinstance(new_spec, ElementSpec)
        logger.debug(f"reconcile {str(self)} ← {str(new_spec)}")
        if (self.key != new_spec.key) or (self.tag != new_spec.tag):
            self.dispose()
            v = new_spec.create()
            logger.debug(f"replacing {str(self)} → {str(v)}")
            patch(ReplaceElementPatch(self.id, v.render()))
            return v
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
