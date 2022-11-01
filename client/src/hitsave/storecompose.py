from typing import List
from hitsave.types import Eval, EvalKey, EvalStore, StoreMiss


class ComposeStore:
    """Composition of multiple stores to make a layered cache.
    Earlier stores are polled first."""

    _stores: List[EvalStore]

    def __init__(self, stores: List[EvalStore]):
        assert len(stores) > 0
        self._stores = stores

    def close(self):
        for s in self._stores:
            s.close()

    def get(self, key: EvalKey):
        if len(self._stores) == 0:
            return StoreMiss("No stores present")

        def rec(stores):
            store, rest = stores[0], stores[1:]
            r = store.get(key)
            if isinstance(r, StoreMiss) and len(rest) > 0:
                r = rec(rest)
                if not isinstance(r, StoreMiss):
                    assert isinstance(r, Eval)
                    store.set(r)
            else:
                # we hit, but we still want to tell later stores that
                # we used the eval again so that they can log metrics etc.
                for x in rest:
                    if hasattr(x, "poll"):
                        x.poll(key)
            return r

        return rec(self._stores)

    def set(self, e: Eval):
        for store in self._stores:
            # assume that store doesn't have the key
            store.set(e)
