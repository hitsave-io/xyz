from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Generic, TypeVar, Union
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

    remove_these: dict[int, str]
    then_insert_these: dict[int, Sum[str, A]]

    def apply(self, l: list[A]) -> list[A]:
        l2 = []
        removed = {}
        for i in range(len(l)):
            if i in self.remove_these:
                k = self.remove_these[i]
                removed[k] = l[i]
            else:
                l2.append(l[i])
        for j in sorted(self.then_insert_these.keys()):
            o = self.then_insert_these[j].match(lambda k: removed[k], lambda t: t)
            l2.insert(j, o)
        return l2


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
    inserts = {
        i: (Sum.inr(l2[i]) if h in new_inserts else Sum.inl(h))
        for i, h in co_removes.items()
    }

    return Reorder(remove_these=removes, then_insert_these=inserts)
