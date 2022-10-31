from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import logging
from typing import Callable
from hitsave.codegraph import CodeGraph
from hitsave.config import Config
from hitsave.storecompose import ComposeStore
from hitsave.types import EvalStore
import uuid
from hitsave.cloudstore import CloudStore
from hitsave.localstore import LocalStore

current_session_var: ContextVar["Session"] = ContextVar("current_session")
logger = logging.getLogger("hitsave")


class Session:
    """This object contains all of the global state about hitsave."""

    store: EvalStore
    codegraph: CodeGraph
    id: uuid.UUID
    # [todo] also background uploader
    # [todo] also connection state (eg socket, rpc etc) with cloud.

    def __init__(self):
        cfg = Config.current()
        stores = []
        if not cfg.no_cloud:
            stores.append(CloudStore())
        if not cfg.no_local:
            stores.append(LocalStore())
        if len(stores) == 0:
            logger.warn("No stores for evaluations.")
        self.store = ComposeStore([LocalStore(), CloudStore()])
        self.codegraph = CodeGraph()
        self.id = uuid.uuid4()

    @classmethod
    def get_current_session(cls) -> "Session":
        return current_session_var.get()


current_session_var.set(Session())


@contextmanager
def use_session(sess: Session):
    t = current_session_var.set(sess)
    yield sess
    current_session_var.reset(t)
