from hitsave.deep import walk as wap
import hypothesis.strategies as hs
from hypothesis import given
import symtable
import pprint
from hitsave.codegraph import (
    CodeGraph,
    CodeVertex,
    ExternPackage,
    get_module_imports,
    pp_symbol,
    symtable_of_module_name,
)


def h(z):
    s = symtable
    l = list
    return given


def g(y):
    return y + h(y) + cc + FOP


def f(x: float):
    return x + g(x)


cc = 100
dd = 101


def outer(aa):
    def inner():
        bb = 1
        return aa + bb + cc

    return inner


FOP = {"x": lambda x: x + x + dd}


class Hello:
    def asdf(self):
        return self


THIS_MODULE = f.__module__


def test_module_imports(snapshot):
    mis = get_module_imports(THIS_MODULE)
    cvs = {k: v for k, v in mis.items() if isinstance(v, CodeVertex)}
    eps = {k: v.name for k, v in mis.items() if isinstance(v, ExternPackage)}
    snapshot.assert_match(pprint.pformat(cvs), "code_imports.txt")
    snapshot.assert_match(pprint.pformat(eps), "externs.txt")


def test_graph_snap(snapshot):
    gg = CodeGraph()
    ds = list(gg.get_dependencies_obj(f))
    interns = [d for d in ds if isinstance(d, CodeVertex)]
    # don't print version numbers for stability
    externs = [d.name for d in ds if isinstance(d, ExternPackage)]
    ss = pprint.pformat((interns, externs))
    snapshot.assert_match(ss, "test_graph_snap.txt")


def test_symtable(snapshot):
    st = symtable_of_module_name(THIS_MODULE)
    s = st.lookup("outer")
    snapshot.assert_match(pp_symbol(s), "test_symtable.txt")
