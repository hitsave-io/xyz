from dataclasses import dataclass
from typing import ClassVar

from .rendering import RenderedText, Rendering
from .patch import InvalidatePatch
from .vdom import Id, patch, fresh_id, to_html


@dataclass
class TextNodeSpec:
    value: str

    def create(self):
        return TextNode(key=self.key, id=fresh_id(), value=self.value)

    @property
    def key(self):
        return hash(("text", self.value))


@dataclass
class TextNode:
    spec_type: ClassVar = TextNodeSpec
    key: int
    id: Id
    value: str

    def __str__(self) -> str:
        return self.value

    def dispose(self):
        return

    def render(self) -> Rendering:
        return RenderedText(self.value)

    def reconcile(self, new_spec: TextNodeSpec) -> "TextNode":
        assert isinstance(new_spec, TextNodeSpec)
        # [todo] patch
        patch(InvalidatePatch())
        self.dispose()
        return new_spec.create()


@to_html.register(str)
def to_html_str(value: str):
    return TextNodeSpec(value)
