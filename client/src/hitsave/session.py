from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Callable
from hitsave.codegraph import CodeGraph
from hitsave.storecompose import ComposeStore
from hitsave.types import EvalStore
from hitsave.cloudstore import CloudStore
from hitsave.localstore import LocalStore

current_session_var: ContextVar["Session"] = ContextVar("current_session")


@dataclass
class Session:
    """This object contains all of the global state about hitsave."""

    store: EvalStore = field(
        default_factory=lambda: ComposeStore([LocalStore(), CloudStore()])
    )
    codegraph: CodeGraph = field(default_factory=CodeGraph)

    @classmethod
    def get_current_session(cls) -> "Session":
        return current_session_var.get()


current_session_var.set(Session())


@contextmanager
def use_session(sess: Session):
    t = current_session_var.set(sess)
    yield sess
    current_session_var.reset(t)
