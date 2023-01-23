from hitsave.server.listdiff import diff, Reorder
from hypothesis import given, assume
import hypothesis.strategies as hs


def recover_prop(l1, l2):
    r = diff(l1, l2)
    l3 = r.apply(l1)
    assert len(l2) == len(l3)
    assert all(x is y for x, y in zip(l2, l3))


examples = ["", "a", "aa", "aaa", "ab", "ba", "baa", "bba", "aab"]
examples = [list(x) for x in examples]


def test_prop_explicit():
    for x in examples:
        for y in examples:
            recover_prop(x, y)


@given(hs.text("abcdefg"), hs.text("abcdefg"))
def test_prop_chars(x1: str, x2: str):
    recover_prop(list(x1), list(x2))


if __name__ == "__main__":
    for x in examples:
        for y in examples:
            r = diff(x, y)
            r.apply(x)
