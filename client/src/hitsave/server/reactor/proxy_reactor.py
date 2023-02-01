""" [todo] """

from typing import Protocol

from .manager import EventArgs
from .patch import Patch


class ReactorLike(Protocol):
    async def wait_patches(self) -> list[Patch]:
        ...

    async def initialize(self):
        ...

    async def render(self) -> dict:
        ...

    async def handle_event(self, args: EventArgs):
        ...

    async def dispose(self):
        ...
