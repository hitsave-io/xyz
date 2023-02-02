import asyncio
from collections import deque
from typing import Callable, Generic, Iterable, TypeVar

T = TypeVar("T")


class StateStream(Generic[T]):
    value: T
    _events: set[asyncio.Event]

    def __init__(
        self,
        initial: T = None,
        should_update: Callable[[T, T], bool] = lambda x, y: True,
    ):
        self.value = initial
        self._events = set()
        self.should_update = should_update

    async def __aiter__(self):
        return self

    async def next(self):
        """Waits until the state's value changes. Always returns the most recent value."""
        return await self.__anext__()

    async def __anext__(self) -> T:
        e = asyncio.Event()
        self._events.add(e)
        await e.wait()
        self._events.discard(e)
        return self.value

    def set(self, value: T) -> None:
        if not self.should_update(self.value, value):
            return
        self.value = value
        for e in self._events:
            e.set()

    def update(self, modify: Callable[[T], T]) -> None:
        self.set(modify(self.value))


class MessageQueue(Generic[T]):
    """Simple message queue where you can push messages to the queue.

    Messages are popped exactly once (ie this is not fanout or pub/sub).
    Not thread safe.
    """

    _items: deque[T]
    _event: asyncio.Event

    def __init__(self):
        self._items = deque()
        self._event = asyncio.Event()

    def push(self, *items: T) -> None:
        self.pushes(items)

    def pushes(self, items: Iterable[T]):
        self._items.extend(items)
        if len(self) > 0:
            self._event.set()

    def __len__(self):
        return len(self._items)

    async def pop_many(self, limit=None):
        if len(self._items) == 0:
            await self._event.wait()
        assert len(self._items) > 0
        if (limit is None) or (0 < len(self._items) <= limit):
            result = list(self._items)
            self._items.clear()
        else:
            assert limit > 0
            result = []
            while len(result) < limit:
                result.append(self._items.popleft())
        if len(self._items) == 0:
            self._event.clear()
        return result

    async def pop(self):
        xs = await self.pop_many(limit=1)
        assert len(xs) == 1
        return xs[0]

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.pop()

    def clear(self):
        self._event.clear()
        self._items.clear()
