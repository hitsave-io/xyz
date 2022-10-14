from typing import Optional, Union
from hitsave.types import Eval, EvalKey, EvalStore, StoreMiss
from hitsave.config import local_store_path
from diskcache import Cache


class LocalStore(EvalStore):
    _store: Cache

    def __init__(self, store_dir=local_store_path):
        self._store = Cache(store_dir)

    def close(self):
        self._store.close()

    def get(self, key: EvalKey) -> Union[Eval, StoreMiss]:
        ks = str(key)
        e = self._store.get(ks, None)
        if e is None:
            return StoreMiss("Not found in local store.")
        assert isinstance(e, Eval)
        return e

    def set(self, e: Eval):
        ks = str(e.key)
        if ks in self._store:
            raise KeyError(
                f"Key {e} already exists in local store {self._store.directory}"
            )
        self._store[ks] = e

    def clear(self):
        self._store.clear()
