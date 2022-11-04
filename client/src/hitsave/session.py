from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import logging
from typing import Callable, Dict
from hitsave.codegraph import Binding, CodeGraph, Symbol, get_binding
from hitsave.config import Config
from hitsave.deephash import deephash
from hitsave.types import StoreAPI
import uuid
from hitsave.util import Current
import sqlite3

logger = logging.getLogger("hitsave")


class Session(Current):
    """This object contains all of the global state and connections about hitsave."""

    local_db: sqlite3.Connection
    codegraph: CodeGraph
    id: uuid.UUID
    # [todo] also background uploader event loop etc.
    # [todo] also connection state (eg socket, rpc etc) with cloud.

    def __init__(self):
        cfg = Config.current()
        # stores = []
        # [todo] reintroduce cloudstore.
        # if not cfg.no_cloud:
        #     stores.append(CloudStore())
        # if not cfg.no_local:
        #     stores.append(LocalStore())
        # if len(stores) == 0:
        #     logger.warn("No stores for evaluations.")
        # self.store = ComposeStore(stores)

        self.local_db = sqlite3.connect(cfg.local_db_path)
        self.codegraph = CodeGraph()
        self.id = uuid.uuid4()

    @classmethod
    def default(cls):
        return cls()

    def fn_hash(self, s: Symbol):
        return deephash(
            {
                str(dep): get_binding(dep).digest
                for dep in self.codegraph.get_dependencies(s)
            }
        )

    def fn_deps(self, s: Symbol) -> Dict[Symbol, Binding]:
        return {dep: get_binding(dep) for dep in self.codegraph.get_dependencies(s)}
