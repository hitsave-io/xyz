import logging
from typing import Callable, Dict, Set
from hitsave.codegraph import Binding, CodeGraph, Symbol, ValueBinding, get_binding
from hitsave.config import Config
from blake3 import blake3
import uuid
from hitsave.util import Current, digest_dictionary
import sqlite3


class Session(Current):
    """This object contains all of the global state and connections about hitsave."""

    local_db: sqlite3.Connection
    codegraph: CodeGraph
    id: uuid.UUID

    def __init__(self):
        cfg = Config.current()

        self.local_db = sqlite3.connect(cfg.local_db_path)
        self.codegraph = CodeGraph()
        self.id = uuid.uuid4()

    @classmethod
    def default(cls):
        return cls()

    def fn_hash(self, s: Symbol):
        return digest_dictionary(
            {
                str(dep): get_binding(dep).digest
                for dep in self.codegraph.get_dependencies(s)
            }
        )

    def fn_deps(self, s: Symbol) -> Dict[Symbol, Binding]:
        return {dep: get_binding(dep) for dep in self.codegraph.get_dependencies(s)}

    def deephash(self, obj):
        b = ValueBinding.from_object(obj)
        d: Set[Symbol] = set()
        for s in b.deps:
            d.add(s)
            for ss in self.codegraph.get_dependencies(s):
                d.add(ss)
        dep_dict = {str(s): get_binding(s).digest for s in d}
        dep_dict["___SELF___"] = b.digest
        return digest_dictionary(dep_dict)
