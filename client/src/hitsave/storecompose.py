from typing import Any, Dict, List, Union
from hitsave.types import Eval, EvalKey, StoreAPI, StoreMiss


class ComposeStore(StoreAPI):
    """Composition of multiple stores to make a layered cache.
    Earlier stores are polled first."""

    _stores: List[StoreAPI]

    def __init__(self, stores: List[StoreAPI]):
        assert len(stores) > 0
        self._stores = stores

    def close(self):
        for s in self._stores:
            if hasattr(s, "close"):
                s.close()  # type: ignore

    def poll_eval(self, key: EvalKey, **kwargs) -> Union[Eval, StoreMiss]:
        if len(self._stores) == 0:
            return StoreMiss("No stores present")

        def rec(stores: List[StoreAPI]) -> Union[Eval, StoreMiss]:
            store, rest = stores[0], stores[1:]
            r = store.poll_eval(key, **kwargs)
            if isinstance(r, StoreMiss) and len(rest) > 0:
                r = rec(rest)
                if not isinstance(r, StoreMiss):
                    assert isinstance(r, Eval)
                    # [todo] propagate result to later stores.
                    # store.set(r)
            else:
                # we hit, but we still want to tell later stores that
                # we used the eval again so that they can log metrics etc.
                for x in rest:
                    if hasattr(x, "poll"):
                        # [todo] poll without downloading result.
                        # x.poll(key)
                        pass
            return r

        return rec(self._stores)

    def start_eval(self, key: EvalKey, **kwargs):
        for store in self._stores:
            store.start_eval(key, **kwargs)

    def resolve_eval(self, key: EvalKey, **kwargs):
        for store in self._stores:
            store.resolve_eval(key, **kwargs)
