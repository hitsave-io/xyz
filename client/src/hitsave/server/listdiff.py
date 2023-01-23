from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Generic, Iterable, Optional, TypeVar, Union
from difflib import SequenceMatcher

A = TypeVar("A")
B = TypeVar("B")
R = TypeVar("R")


@dataclass
class Sum(Generic[A, B]):
    is_left: bool
    value: Any

    @classmethod
    def inl(cls, value: A):
        return cls(True, value)

    @classmethod
    def inr(cls, value: B):
        return cls(False, value)

    def match(self, left: Callable[[A], R], right: Callable[[B], R]) -> R:
        if self.is_left:
            return left(self.value)
        else:
            return right(self.value)


@dataclass
class Reorder(Generic[A]):
    """Represents a patch of removing and inserting items."""

    l1_len: int
    l2_len: int
    remove_these: dict[int, Optional[str]]
    then_insert_these: dict[int, Sum[str, A]]

    def apply(self, l: list[A]) -> list[A]:
        l2 = []
        removed = {}
        for i in range(len(l)):
            if i in self.remove_these:
                k = self.remove_these[i]
                if k is not None:
                    removed[k] = l[i]
            else:
                l2.append(l[i])
        for j in sorted(self.then_insert_these.keys()):
            o = self.then_insert_these[j].match(lambda k: removed[k], lambda t: t)
            l2.insert(j, o)
        return l2

    @property
    def deletions(self):
        """Get the indices of items in the first list that are deleted."""
        for i in self.remove_these.keys():
            if self.remove_these[i] is None:
                yield i

    @property
    def creations(self):
        for j, v in self.then_insert_these.items():
            if not v.is_left:
                yield j

    @property
    def moves(self) -> Iterable[tuple[int, int]]:
        """Get pairs of i,j indices of all pairs of values that appear in both lists."""
        rm = {}
        count = 0
        for i in range(self.l1_len):
            if i in self.remove_these:
                t = self.remove_these[i]
                if t is None:
                    continue
                else:
                    rm[t] = i
            else:
                rm[count] = i
                count += 1
        rm_count = count
        count = 0
        for j in range(self.l2_len):
            if j in self.then_insert_these:
                v = self.then_insert_these[j]
                if v.is_left:
                    k = v.value
                    i = rm.pop(k)
                    yield (i, j)
                else:
                    continue
            else:
                i = rm.pop(count)
                yield (i, j)
                count += 1
        assert count == rm_count
        assert len(rm) == 0


def dedep_values(d: dict):
    acc = {}
    c = Counter()
    for k, v in d.items():
        n = c[v]
        acc[k] = (v, n)
        c[v] += 1
    return acc


def diff(l1: list[A], l2: list[A]) -> Reorder[A]:
    removes = dict()
    co_removes = dict()
    codes = SequenceMatcher(None, l1, l2).get_opcodes()
    for (tag, i1, i2, j1, j2) in codes:
        if tag == "replace" or tag == "delete":
            for i in range(i1, i2):
                removes[i] = hash(l1[i])
        if tag == "replace" or tag == "insert":
            for j in range(j1, j2):
                assert j not in co_removes
                co_removes[j] = hash(l2[j])
    # deduplicate
    removes = dedep_values(removes)
    co_removes = dedep_values(co_removes)
    # if a new item is inserted we need to include a copy of the item.
    new_inserts = set(co_removes.values()).difference(removes.values())
    deletions = set(removes).difference(co_removes.values())
    remove_these: Any = {i: None if h in deletions else h for i, h in removes.items()}
    inserts = {
        i: (Sum.inr(l2[i]) if h in new_inserts else Sum.inl(h))
        for i, h in co_removes.items()
    }

    return Reorder(
        len(l1), len(l2), remove_these=remove_these, then_insert_these=inserts
    )
