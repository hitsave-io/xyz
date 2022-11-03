from hitsave import memo
import numpy as np
import logging
from hitsave.decorator import SavedFunction


@memo
def f(x):
    # try changing the method body and witness the cache invalidating!
    return x + x + x


@memo
def g(y):
    return f(y) + y


@memo
def gg(y):
    x = g(y)
    return np.ones(2**y)


@memo()
def gggg(x: int):
    return 4 * x


@memo(local_only=True)
def ggg(y, x: int):
    return y + x + y


def test_fns_are_right_type():
    for f in [g, gg, gggg, ggg]:
        assert isinstance(f, SavedFunction)


def test_savesave():
    # [todo] view logs
    print(g(4))
    print(g(4))
    print(f(3))
    print(g(5))


def test_biggies():
    for x in range(20):
        print(len(gg(x)))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    test_biggies()
