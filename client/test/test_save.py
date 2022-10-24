from hitsave import save
import numpy as np

from hitsave.decorator import SavedFunction


@save
def f(x):
    # try changing the method body and witness the cache invalidating!
    return x + x + x


@save
def g(y):
    return f(y) + y


@save
def gg(y):
    return np.random.rand(2**y)


@save()
def gggg(x: int):
    return 4 * x


@save(local_only=True)
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
    for x in range(25):
        print(len(gg(x)))


if __name__ == "__main__":
    test_biggies()
