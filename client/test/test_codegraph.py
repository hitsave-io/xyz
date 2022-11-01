from hitsave.deep import walk as wap
import hypothesis.strategies as hs
from hypothesis import given
import symtable
import pprint
import torch
import torch.nn as nn
import torch.nn.functional as F
from hitsave.codegraph import (
    CodeGraph,
    CodeVertex,
    ExternPackage,
    get_module_imports,
    pp_symbol,
    symtable_of_module_name,
    get_origin,
    get_module_spec,
    module_as_external_package,
)
from test.strat import numbers


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
    def __init__(self):
        self.x = 4
        self.y = f(10)

    def asdf(self):
        return self


def hhh():
    h = Hello()
    return h.asdf()


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


def test_origin_builtin():
    o = get_origin("itertools")
    assert o == "built-in"


def test_module_as_external_package():
    e1 = module_as_external_package("hitsave")
    assert isinstance(e1, ExternPackage)
    assert e1.name == "hitsave"


# [todo] these tests are tricky because __main__ depends on how tests are entered.

# def test_main():
#     o = get_origin("__main__")
#     assert o is not None
# def test_get_module_spec_main():
#     s = get_module_spec("__main__")
#     assert s is not None
# def test_module_as_external_package2():
#     e1 = module_as_external_package("__main__")
#     assert e1 is None


def test_module_as_external_package3():
    e1 = module_as_external_package("itertools")
    assert isinstance(e1, ExternPackage)
    assert e1.name == "__builtin__"


def test_torch_versions():

    e1 = module_as_external_package("torch")
    e2 = module_as_external_package("torch.nn")
    e3 = module_as_external_package("torch.nn.functional")
    assert isinstance(e1, ExternPackage)
    assert isinstance(e2, ExternPackage)
    assert isinstance(e3, ExternPackage)
    assert e1.name == "torch"
    assert e2.name == "torch"
    assert e3.name == "torch"
    assert e1.version == e2.version == e3.version
