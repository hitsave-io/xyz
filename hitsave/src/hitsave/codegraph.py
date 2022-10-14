from dataclasses import dataclass, field
import importlib
from importlib.machinery import ModuleSpec
import importlib.util
import builtins
import inspect
import sys
from symtable import symtable, Symbol, SymbolTable, Function
import functools
import ast
import pprint
import os.path
import logging
from typing import Any, Dict, Optional, Tuple, Union
from hitsave.graph import DirectedGraph
from hitsave.util import cache, decorate_ansi

logger = logging.getLogger("hitsave/codegraph")


@dataclass
class ExternPackage:
    name: str
    version: str

    def __hash__(self):
        return hash(repr(self))


@dataclass
class CodeVertex:
    module_name: str
    decl_name: Optional[str] = field(default=None)

    def __hash__(self):
        return hash(self.__str__())

    def __str__(self):
        if self.decl_name is None:
            return self.module_name
        else:
            return f"{self.module_name}:{self.decl_name}"

    def __repr__(self):
        return self.__str__()

    def pp(self):
        """Pretty print with nice formatting."""
        m = ".".join([decorate_ansi(n, fg="cyan") for n in self.module_name.split(".")])
        d = (
            ".".join([decorate_ansi(n, fg="yellow") for n in self.decl_name.split(".")])
            if self.decl_name is not None
            else ""
        )
        return f"{m}:{d}"

    def to_object(self):
        """Returns the best-guess python object associated with the name."""
        m = self.module
        if self.decl_name is None:
            return m
        d = getattr(m, self.decl_name)
        return d

    @property
    def module(self):
        """Returns the module without executing it."""
        # [note] this loads the module but _does not execute it_ and doesn't add to sys.modules.
        if self.module_name in sys.modules:
            return sys.modules[self.module_name]
        spec = self.module_spec
        if spec is None:
            raise ModuleNotFoundError(name=self.module_name)
        return importlib.util.module_from_spec(spec)

    @property
    def module_spec(self):
        return get_module_spec(self.module_name)

    @property
    def value(self):
        m = self.module
        if self.decl_name is None:
            return m
        else:
            return getattr(m, self.decl_name)

    @classmethod
    def of_str(cls, s):
        if ":" not in s:
            return cls(s, None)
        module_name, id = s.split(":")
        # [todo] validation
        return cls(module_name, id)

    @classmethod
    def of_object(cls, o):
        assert hasattr(o, "__qualname__")
        assert hasattr(o, "__module__")
        return cls(o.__module__, o.__qualname__)

    @property
    def symbol(self) -> Symbol:
        assert self.decl_name is not None, "No symbol for entire module."

        mst = symtable_of_module_name(self.module_name)
        if "." in self.decl_name:
            # [todo]
            raise NotImplementedError(
                f"cannot yet work with nested symbols {self.decl_name}."
            )
        return mst.lookup(self.decl_name)

    """ Returns true if the symbol is a namespace, which means that there is some
    internal structure; eg a function, a class. """

    def is_namespace(self) -> bool:
        assert self.decl_name is not None
        return self.symbol.is_namespace()

    """ Returns true if the symbol was declared from an `import` statement. """

    def is_import(self) -> bool:
        if self.decl_name is None:
            return False
        return self.symbol.is_imported()

    def get_edges(self):
        p = module_as_external_package(self.module_name)
        if p is not None:
            yield p
            return
        if self.is_import():
            imports = get_module_imports(self.module_name)
            assert self.decl_name in imports
            yield imports[self.decl_name]
            return
        if self.is_namespace():
            nss = self.symbol.get_namespaces()
            for ns in nss:
                if isinstance(ns, Function):
                    globals = ns.get_globals()
                    for decl_name in globals:
                        if hasattr(builtins, decl_name):
                            # ignore builtins
                            continue
                        yield CodeVertex(self.module_name, decl_name)
                else:
                    raise NotImplementedError(
                        f"Don't know how to explore deps of {self}"
                    )
        # constants have no edges.


Vertex = Union[CodeVertex, ExternPackage]


class CodeGraph:
    dg: DirectedGraph[Vertex, Any]

    def __init__(self):
        self.dg = DirectedGraph()

    def eat_obj(self, o):
        v = CodeVertex.of_object(o)
        return self.eat(v)

    def eat(self, v: Vertex):
        if self.dg.has_vertex(v):
            # assume already explored
            return
        self.dg.add_vertex(v)
        if isinstance(v, CodeVertex):
            for v2 in v.get_edges():
                self.eat(v2)
                self.dg.set_edge(v, v2, ())

    def get_dependencies(self, v: Vertex):
        self.eat(v)
        yield from self.dg.reachable_from(v)

    def get_dependencies_obj(self, o):
        yield from self.get_dependencies(CodeVertex.of_object(o))

    def clear(self):
        self.dg = DirectedGraph()


"""
Each time the sourcefiles change, all of these
cached functions need to be invalidated:

Also if the sourcefile is in an intermediate state and hence is not valid python,
we should keep the cached values and code graph unchanged.

module_name
→ version
→ ExternPackage
→ ModuleSpec
→ sourcefile
→ sourcetext
→ symtable
→ imports

sourcefile → module_name

 """


@cache
def module_version(module_name: str) -> str:
    m = sys.modules.get(module_name)
    assert m is not None
    if hasattr(m, "__version__"):
        v = m.__version__
        assert v is not None
        return v
    print(f"module has no version!")
    return "???"


@cache
def module_as_external_package(module_name: str) -> Optional[ExternPackage]:
    o = get_origin(module_name)
    assert o is not None
    if "site-packages" in o:
        # [todo] there was a way more canonical way to do this.
        return ExternPackage(module_name, module_version(module_name))
    if "lib/python3" in o:
        v = sys.version_info
        v = f"{v.major}.{v.minor}"
        return ExternPackage("__builtin__", v)


@cache
def get_module_spec(module_name: str) -> ModuleSpec:
    m = sys.modules.get(module_name)
    if m is not None:
        assert hasattr(m, "__spec__")
        spec = getattr(m, "__spec__")
    else:
        spec = importlib.util.find_spec(module_name)
    assert spec is not None
    return spec


def is_subpath(path1: str, path2: str):
    """Returns true if there is a `q` such that `path2 = path1 + q`"""
    return os.path.commonpath([path1, path2]) == path1


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


def get_origin(module_name: str) -> str:
    """Returns a string with the modules file location."""
    m = sys.modules.get(module_name)
    if m is not None:
        o = getattr(m, "__file__", None)
        assert o is not None
        return o
    else:
        s = get_module_spec(module_name)
        assert s is not None
        o = s.origin
        assert o is not None
        return o


@cache
def get_source(module_name: str) -> str:
    """Returns the sourcefile for the given module."""
    o = get_origin(module_name)
    assert o is not None
    # [todo] assert it's a python file with ast etc.
    with open(o, "rt") as f:
        return f.read()


@cache
def symtable_of_module_name(module_name: str) -> SymbolTable:
    o = get_origin(module_name)
    assert o is not None
    return symtable(get_source(module_name), o, "exec")


"""
Parses the given module name, finds all of the constants in the module's source that are imported.
"""


@cache
def get_module_imports(module_name: str) -> Dict[str, Vertex]:
    """Returns all of the vertices that are imported from the given module name."""
    t = ast.parse(get_source(module_name))
    r = {}

    def mk_vertex(module_name, fn_name=None) -> Vertex:
        p = module_as_external_package(module_name)
        if p is not None:
            return p
        else:
            return CodeVertex(module_name, fn_name)

    class V(ast.NodeVisitor):
        def visit_Import(self, node: ast.Import):
            for alias in node.names:
                asname = alias.asname or alias.name
                assert asname not in r, f"multiple imports of same symbol {asname}"
                r[asname] = mk_vertex(alias.name)

        def visit_ImportFrom(self, node: ast.ImportFrom):
            assert node.module is not None
            module_name: str = node.module
            for alias in node.names:
                asname = alias.asname or alias.name
                assert (
                    asname not in r
                ), f"multiple imports introducing the same name {asname} are not yet implemented"
                r[asname] = mk_vertex(module_name, alias.name)

    V().visit(t)
    return r


def pp_symbol(sym: Symbol):
    assert type(sym) == Symbol
    print("Symbol:", sym.get_name())
    ps = [
        "referenced",
        "imported",
        "parameter",
        "global",
        "declared_global",
        "local",
        "free",
        "assigned",
        "namespace",
    ]
    ps = ",".join([p for p in ps if getattr(sym, "is_" + p)()])
    return f"Symbol({sym.get_name()}, {ps})"


def pp_symtable(st: SymbolTable):
    assert isinstance(st, SymbolTable)

    def rec(st):
        s = f"SymbolTable(type={st.get_type()}, id={st.get_id()}, name={st.get_name()}, nested={st.is_nested()})"
        return (s, ", ".join(st.get_identifiers()), [rec(x) for x in st.get_children()])

    return pprint.pformat(rec(st))
