"""
This file contains the code that statically determines the dependencies of a SavedFunction.

Each python module is a dictionary of declarations, some of which may themselves be dictionaries of declarations.
The general name for these dictionaries is a __namespace__.

Hence, every symbol in Python's execution environment can be written as a dot-separated module_name and dot-separated decl_name.
The ``Symbol`` dataclass is defined by these two fields.

Given a ``s : Symbol``, we need to find the dependency graph of the symbol.
How to do this depends on the python object that the symbol is __bound__ to.

For the purposes of computing dependencies, we distinguish between bindings as follows:

- functions
- classes
- constants
- imports; the ``x`` in ``from numpy import x``
- external modules; eg `numpy:array`




"""
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
import logging
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
from hitsave.config import Config, __version__
from hitsave.deephash import deephash
from hitsave.graph import DirectedGraph
from hitsave.util import cache, decorate_ansi

logger = logging.getLogger("hitsave/codegraph")


@dataclass
class Symbol:
    """Identifies a symbol for python objects."""

    module_name: str
    decl_name: Optional[str] = field(default=None)

    def __hash__(self):
        """Note this only hashes on the string value, not the binding."""
        return hash(self.__str__())

    def __str__(self):
        if self.decl_name is None:
            return self.module_name
        else:
            return f"{self.module_name}:{self.decl_name}"

    def pp(self):
        """Pretty print with nice formatting."""
        m = ".".join([decorate_ansi(n, fg="cyan") for n in self.module_name.split(".")])
        d = (
            ".".join([decorate_ansi(n, fg="yellow") for n in self.decl_name.split(".")])
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
        # [note] this loads the module but _does not execute it_ and doesn't add to sys.modules.
        if self.module_name in sys.modules:
            return sys.modules[self.module_name]
        spec = self.get_module_spec()
        if spec is None:
            raise ModuleNotFoundError(name=self.module_name)
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
        assert hasattr(o, "__qualname__")
        assert hasattr(o, "__module__")
        # [todo] more helpful error.
        return cls(o.__module__, o.__qualname__)

    def get_st_symbol(self) -> st.Symbol:
        """Return the SymbolTable Symbol for this vertex."""
        assert self.decl_name is not None, "No symbol for entire module."

        st = symtable_of_module_name(self.module_name)
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

    def is_namespace(self) -> bool:
        """Returns true if the symbol is a namespace, which means that there is some
        internal structure; eg a function, a class, a module."""
        assert self.decl_name is not None
        return self.get_st_symbol().is_namespace()

    def is_import(self) -> bool:
        """Returns true if the symbol was declared from an `import` statement."""
        if self.decl_name is None:
            return False
        return self.get_st_symbol().is_imported()


class BindingKind(Enum):
    """Information about the kind of thing that the symbol is bound to."""

    fun = 0
    """ A function, including class methods. """
    cls = 1
    """ A class """
    val = 2
    """ A value. These are hashed by their python object value. """
    imp = 3
    """ Imported symbol. """
    constant = 4
    """ A constant, defining expression is hashed. """
    external = 5
    """ External package """


class Binding(ABC):
    kind: BindingKind
    deps: Set[Symbol]
    diffstr: str
    """ A string that can be diffed with other versions of the binding to show the user what changed. """
    digest: str
    """ A string to uniquely identify the binding object. Note that this doesn't have to be a hex hash if not needed. """

    def __hash__(self):
        return self.digest


@dataclass
class ImportedBinding(Binding):
    kind = BindingKind.imp
    symb: Symbol

    @property
    def digest(self):
        return str(self.symb)

    @property
    def deps(self):
        return set([self.symb])

    @property
    def diffstr(self):
        # [todo] would be cool to show a diff of the line of sourcecode here.
        return str(self.symb)


@dataclass
class FnBinding(Binding):
    kind = BindingKind.fun
    sourcetext: str
    deps: Set[Symbol]

    @property
    def digest(self):
        return deephash(self.sourcetext)

    @property
    def diffstr(self):
        return self.sourcetext


@dataclass
class ClassBinding(Binding):
    kind = BindingKind.cls
    sourcetext: str
    code_deps: Set[Symbol]
    methods: List[Symbol]

    @property
    def deps(self):
        return self.code_deps.union(self.methods)

    @property
    def digest(self):
        return deephash(self.sourcetext)

    @property
    def diffstr(self):
        return self.sourcetext


@dataclass
class ValueBinding(Binding):
    kind = BindingKind.val
    repr: str
    digest: str

    @property
    def deps(self):
        return set()

    @property
    def diffstr(self):
        return self.repr


@dataclass
class ExternalBinding(Binding):
    kind = BindingKind.external
    name: str
    version: str

    @property
    def diffstr(self):
        return self.version

    @property
    def deps(self):
        return set()

    @property
    def digest(self):
        vs = self.version.split(".")
        amt = ["none", "major", "minor", "patch"].index(
            Config.current().version_sensitivity
        )
        v = ".".join(vs[:amt])
        return v


class CodeGraph:
    dg: DirectedGraph[Symbol, Any]

    def __init__(self):
        self.dg = DirectedGraph()

    def eat_obj(self, o):
        v = Symbol.of_object(o)
        return self.eat(v)

    def eat(self, v: Symbol):
        if self.dg.has_vertex(v):
            # assume already explored
            return
        self.dg.add_vertex(v)
        if isinstance(v, Symbol):
            b = get_binding(v)
            for v2 in b.deps:
                self.eat(v2)
                self.dg.set_edge(v, v2, b)

    def get_dependencies(self, v: Symbol):
        self.eat(v)
        yield from self.dg.reachable_from(v)

    def get_dependencies_obj(self, o):
        yield from self.get_dependencies(Symbol.of_object(o))

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
def module_version(module_name: str) -> Optional[str]:
    try:
        return importlib.metadata.version(module_name)
    except:
        pass
    m = sys.modules.get(module_name)
    assert m is not None, module_name
    if hasattr(m, "__version__"):
        v = m.__version__
        assert v is not None
        return v
    return None


def is_relative_import(module_name: str) -> bool:
    return module_name.startswith(".")


def head_module(module_name) -> str:
    """Given a dot-separated module name such as ``torch.nn.functional``,
    returns the 'head module' name ``torch``."""
    if "." in module_name:
        parts = module_name.split(".")
        head = parts[0]
        assert head != "", "relative imports not supported"
        return head
    return module_name


def _mk_extern_package_from_site_package(module_name: str):
    v = module_version(module_name)
    if v is not None:
        return ExternalBinding(name=module_name, version=v)
    if "." in module_name:
        head = head_module(module_name)
        v = module_version(head)
        if v is not None:
            return ExternalBinding(name=head, version=v)
    raise ValueError(f"Can't find a module version for {module_name}.")


@cache
def module_as_external_package(module_name: str) -> Optional[ExternalBinding]:
    """Looks at the module name and tries to determine whether the module should be considered as being
    external for the project.

    An ExternPackage is a leaf of the code dependency DAG, rather than exploring the source of an external package, we instead
    hash it according to the package version.
    """
    if not is_relative_import(module_name) and head_module(module_name) == "hitsave":
        # special case, hitsave is always an extern package
        return ExternalBinding("hitsave", __version__)
    m = sys.modules.get(module_name)
    o = get_origin(module_name)
    assert o is not None
    if "site-packages" in o:
        # [todo] there should be a canonical way to do this.
        return _mk_extern_package_from_site_package(module_name)
    if ("lib/python3" in o) or (o == "built-in"):
        v = sys.version_info
        v = f"{v.major}.{v.minor}"
        return ExternalBinding("__builtin__", v)
    # [todo] another case is packages that have been installed by the user using `pip install -e ...`
    # the rule should be configurable, but we treat it as an extern package iff
    # - it has to be a package (module has a __path__ attr)
    # - it has a __version__ attribute
    return None


@cache
def get_module_spec(module_name: str) -> ModuleSpec:
    m = sys.modules.get(module_name)
    spec = None
    if m is not None:
        assert hasattr(m, "__spec__")
        spec = getattr(m, "__spec__")
    if spec is None:
        # [todo] this can raise a value error if `module_name = '__main__'` and we are degubbing.
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
    """Returns a string with the module's file path as a string.

    If the module is not found, throw an error.
    If the module is a builtin, returns 'built-in'.
    """
    m = sys.modules.get(module_name)
    f = getattr(m, "__file__", None)
    if f is not None:
        return f
    spec = get_module_spec(module_name)
    assert hasattr(spec, "origin")
    return getattr(spec, "origin")


@cache
def get_source(module_name: str) -> str:
    """Returns the sourcefile for the given module."""
    o = get_origin(module_name)
    assert o is not None
    # [todo] assert it's a python file with ast etc.
    with open(o, "rt") as f:
        return f.read()


@cache
def symtable_of_module_name(module_name: str) -> st.SymbolTable:
    o = get_origin(module_name)
    assert o is not None
    return st.symtable(get_source(module_name), o, "exec")


@cache
def _get_namespace_binding(s: Symbol) -> Binding:
    """Return a binding for the case of s being a namespace.
    This is it's own method because we can safely cache namespace bindings.
    """
    assert s.is_namespace()

    ns = s.get_st_symbol().get_namespace()
    # [todo] what are some cases where there are multiple namespaces?
    if isinstance(ns, st.Function):
        deps = [
            Symbol(s.module_name, decl_name)
            for decl_name in ns.get_globals()
            if not hasattr(builtins, decl_name)
        ]
        src = getsource(s)
        assert src is not None, f"failed to find sourcecode for {str(s)}"
        return FnBinding(deps=set(deps), sourcetext=src)
    if isinstance(ns, st.Class):
        assert s.decl_name is not None
        methods = [
            Symbol(s.module_name, s.decl_name + "." + mn) for mn in ns.get_methods()
        ]
        src = getsource(s)
        assert src is not None, f"failed to find sourcecode for {str(s)}"

        return ClassBinding(
            sourcetext=src,
            code_deps=set(),  # [todo] get field deps, get baseclass deps.
            methods=methods,
        )

    raise NotImplementedError(f"Don't know how to get deps of namespace {str(s)}")


def get_binding(s: Symbol) -> Binding:
    """Returns the binding for a particular symbol.

    We make an assumption to allow us to cache bindings:
    If the symbol is in the symbol-table for the module's source file, we assume that the
    symbol is still bound to that source declaration at runtime. However this is not necessarily true,
    since some code later in the module could re-bind the name.

    This is the difference between symbols and names in python; a symbol is a compile-time binding and a
    name is a runtime binding.
    """
    p = module_as_external_package(s.module_name)
    if p is not None:
        return p

    if s.is_import():
        imports = get_module_imports(s.module_name)
        assert s.decl_name in imports
        i = imports[s.decl_name]
        return ImportedBinding(symb=i)

    if s.is_namespace():
        # a namespace means that s is a function, class or module and contains references to symbols.
        return _get_namespace_binding(s)
    else:  # not a namespace
        o = s.get_bound_object()
        digest = deephash(o)
        repr = pprint.pformat(o)
        return ValueBinding(repr=repr, digest=digest)


def get_digest(s: Symbol):
    return get_binding(s).digest


@cache
def get_module_imports(module_name: str) -> Dict[str, Symbol]:
    """Returns all of the vertices that are imported from the given module name."""
    t = ast.parse(get_source(module_name))
    r = {}

    def mk_vertex(module_name, fn_name=None) -> Symbol:
        return Symbol(module_name, fn_name)

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


def pp_symbol(sym: st.Symbol):
    assert type(sym) == st.Symbol
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


@cache
def getsource(s: Symbol) -> Optional[str]:
    o: Any = s.get_bound_object()
    if inspect.isfunction(o) or inspect.isclass(o):
        return inspect.getsource(o)
    elif hasattr(o, "__wrapped__") and inspect.isfunction(o.__wrapped__):
        return inspect.getsource(o.__wrapped__)
    else:
        return None


def hash_function(g: CodeGraph, fn: Callable):
    g.eat_obj(fn)
    deps = {}
