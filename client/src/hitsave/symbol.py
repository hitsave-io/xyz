from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import importlib
from importlib.machinery import ModuleSpec
import importlib.util
import importlib.metadata
import builtins
import inspect
from pathlib import Path
import sys
import symtable as st
from symtable import SymbolTable
import ast
import pprint
import os.path
from types import ModuleType
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    Set,
    Tuple,
    Union,
)
from functools import cached_property

from hitsave.graph import DirectedGraph
from hitsave.config import Config, __version__
from hitsave.util import cache, digest_string
from hitsave.console import internal_error, logger


def get_origin(module_name: str) -> Optional[str]:
    """Returns a string with the module's file path as a string.

    If the module is not found, throw an error.
    If the module is a builtin, returns 'built-in'.
    """
    m = sys.modules.get(module_name)
    f = getattr(m, "__file__", None)
    if f is not None:
        return f
    spec = get_module_spec(module_name)
    return getattr(spec, "origin", None)


@cache
def get_source(module_name: str) -> Optional[str]:
    """Returns the sourcefile for the given module."""
    o = get_origin(module_name)
    if o is None:
        internal_error("No source for", module_name)
        return None
    # [todo] assert it's a python file with ast etc.
    with open(o, "rt") as f:
        return f.read()


@cache
def symtable_of_module_name(module_name: str) -> Optional[st.SymbolTable]:
    o = get_origin(module_name)
    src = get_source(module_name)
    if o is None or src is None:
        internal_error("No source or origin for", module_name)
        return None
    return st.symtable(src, o, "exec")


@cache
def get_module_spec(module_name: str) -> ModuleSpec:
    m = sys.modules.get(module_name)
    spec = None
    if m is not None:
        assert hasattr(m, "__spec__"), "all modules should have __spec__?"
        spec = getattr(m, "__spec__")
    if spec is None:
        # [todo] this can raise a value error if `module_name = '__main__'` and we are degubbing.
        spec = importlib.util.find_spec(module_name)
    assert spec is not None
    return spec


@cache
def module_name_of_file(path: str) -> Optional[str]:
    """Given a file location, gives a non-relative module name.

    This is supposed to be the inverse of the
    default [module finder](https://docs.python.org/3/glossary.html#term-finder)
    """
    path = os.path.abspath(path)
    # reference: https://stackoverflow.com/questions/897792/where-is-pythons-sys-path-initialized-from
    ps = [p for p in sys.path]
    ps.reverse()
    for p in ps:
        if p == "":
            continue
        if os.path.commonpath([p, path]) == p:
            r = os.path.relpath(path, p)
            r, ext = os.path.splitext(r)
            assert ext == ".py"
            r = r.split(os.path.sep)
            r = ".".join(r)
            return r
    return None


@dataclass
class Symbol:
    """Identifies a symbol for python objects."""

    module_name: str
    decl_name: Optional[str] = field(default=None)

    def __post_init__(self):
        assert isinstance(self.module_name, str)
        assert (self.decl_name is None) or isinstance(self.decl_name, str)

    @cached_property
    def display_module_name(self):
        """This is the same as self.module_name, but with a special case
        for when the module is __main__. In this case we make a guess as to what the module would be
        called if invoked from a different file."""
        if self.module_name == "__main__":
            m = sys.modules.get("__main__")
            assert m is not None
            if not hasattr(m, "__file__"):
                # this happens in an interactive session.
                # [todo] support for using hitsave in a python repl is not implemented yet.
                return "interactive"
            mf = getattr(m, "__file__")
            assert isinstance(mf, str)
            module = module_name_of_file(mf)
            assert module is not None
            assert module != "__main__"
            return module
        else:
            return self.module_name

    def __hash__(self):
        """Note this only hashes on the string value, not the binding."""
        return hash(self.__str__())

    def __str__(self):
        module_name = self.display_module_name
        if self.decl_name is None:
            return module_name
        else:
            return f"{module_name}:{self.decl_name}"

    def __rich__(self):
        """Pretty print with nice formatting."""
        module_name = self.display_module_name

        m = ".".join([f"[cyan]{n}[/]" for n in module_name.split(".")])
        d = (
            ".".join([f"[yellow]{n}[/]" for n in self.decl_name.split(".")])
            if self.decl_name is not None
            else ""
        )
        return f"{m}:{d}"

    def get_bound_object(self) -> object:
        """Returns the best-guess python object associated with the symbol."""
        m = self.get_module()
        if self.decl_name is None:
            return m
        if "." in self.decl_name:
            xs = self.decl_name.split(".")
            for x in xs:
                m = getattr(m, x)
            return m
        d = getattr(m, self.decl_name)
        return d

    def get_module(self) -> ModuleType:
        """Returns the module that this vertex lives in.

        This does not cause the module to be loaded.
        """
        module_name = self.module_name
        if module_name in sys.modules:
            return sys.modules[module_name]
        spec = self.get_module_spec()
        if spec is None:
            raise ModuleNotFoundError(name=module_name)
        return importlib.util.module_from_spec(spec)

    def get_module_spec(self):
        """Get the spec of the module that this vertex lives in."""
        return get_module_spec(self.module_name)

    @classmethod
    def of_str(cls, s):
        """Parse a code vertex from a string "module_name:decl_name"."""
        if ":" not in s:
            return cls(s, None)
        module_name, id = s.split(":")
        # [todo] validation
        return cls(module_name, id)

    @classmethod
    def of_object(cls, o):
        """Create a Symbol from a python object by trying to inspect what the Symbol and parent module are."""
        if inspect.ismodule(o):
            return cls(o.__name__)
        if not hasattr(o, "__qualname__") or not hasattr(o, "__module__"):
            raise ValueError(
                f"Object {o} does not have a __qualname__ or __module__ attribute."
            )
        module = o.__module__
        assert module is not None, f"Module for {o} not found."
        return cls(module, o.__qualname__)

    def get_st_symbol(self) -> Optional[st.Symbol]:
        """Return the SymbolTable Symbol for this vertex."""
        if self.decl_name is None:
            return None

        st = symtable_of_module_name(self.module_name)
        if st is None:
            internal_error(f"Failed to find symbol table for", self)
            return None
        try:
            if "." in self.decl_name:
                parts = self.decl_name.split(".")
                for part in parts[:-1]:
                    s = st.lookup(part)
                    if s.is_namespace():
                        st = s.get_namespace()
                s = st.lookup(parts[-1])
                return s
                # [todo] test this
            return st.lookup(self.decl_name)
        except KeyError as e:
            logger.debug(f"Failed to find symbol {str(self)}: {e}")
            return None

    def is_namespace(self) -> bool:
        """Returns true if the symbol is a namespace, which means that there is some
        internal structure; eg a function, a class, a module."""
        if self.decl_name is None:
            # all modules are namespaces
            return True
        sts = self.get_st_symbol()
        if sts is None:
            return False
        return sts.is_namespace()

    def is_module(self):
        return self.decl_name is None or inspect.ismodule(self.get_bound_object())

    def is_import(self) -> bool:
        """Returns true if the symbol was declared from an `import` statement."""
        if self.decl_name is None:
            return False
        sts = self.get_st_symbol()
        if sts is None:
            return False
        return sts.is_imported()
