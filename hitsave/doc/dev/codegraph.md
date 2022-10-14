
# Code graphs

Each symbol in python can be written as `module#identifer`, where both module and identifier are `.`-separated names.

The purpose of the code graph is to assign to each function and constant a unique hash to enable caching of functions across
different versions of source.

To do this, take a function and look at the function body:

```py
import numpy as np
from .mymodule import h

def g(y):
    return y + y + h(y) + np.ones(3)

def f(x):
    return x + g(x)
```

Using the python symbol table, we can inspect the body of `f` at runtime and determine that it depends on the symbol `g`.
Hence, if the user changes the code of `g`, we should invalidate the cache at `f`.
Furthermore, `g` depends on a function definied in another file, so if the code of `h` changes, we should invalidate `f` and `g`.

The function `g` also depends on an external package `numpy`. Rather than traversing the entire numpy codebase, we instead treat external packages
opaquely and instead hash on the version number of the package. If the user installs a new version of numpy we need to invalidate the cache.

There are four kinds of symbol that we can encounter:
- local import, that is, the `h` in `from .mymodule import h` → hash the value in the denoted module.
- package import, that is, the `np` in `import numpy as np`. → hash by hashing the version of the package
- function
- constant, a value

To create a hash of a function:
1. Take the function body
2. hash the function sourcecode as text. This is called the __local hash__.
2. Take all of the symbols that the function depends on (this can be found using the `symtable` module). Including the function's closure (see below).
3. For each symbol, compute the hash and store them in a dictionary.
4. Compute the aggregate, final hash as the local hash ++ the hash of this dependency dictionary.

To create the hash of a constant:
1. run `deephash` on it, recursively hashing composite data.
2. If a function is encountered, hash the function using the recipe above.
3. If an instance of a class is encountered, there is a complication. We treat all of the class methods as part of the composite data (see note below on why).

## Function closures

Consider

```py
def f(x):
    def g(y):
        return x + y
    return g

h = f(4)
```

How should we hash `h`? `h` is a function with a __closure__, the closure is the set of captured values that the function depends on.
Here, `h`s closure is `{x : 4}`.
You can get the closure using the `__closure__` dunder ([todo] check).
Python closures can be a bit weird because python has strange variable scoping rules. But it's ok.

Note that lambda closures are also ok: `return lambda y: x + y` because lambdas are given auxillary names.

## How to deal with class methods

One fly in the ointment of the above scheme is it is not always possible to find all of the code dependencies for a function without running the function.

```py
class A:
    def foo(x):
        return x + x

class B extends A:
    def foo(x):
        return 3 * x

def f(a : A):
    return a.foo()
```

When `f` is hashed, which `foo` should it depend on?

I think the correct answer here is _neither_.
`f` does not depend on `foo`.
Instead, the data `a` depends on `foo`.
When we hash the value `x` fed to `foo(x)`, we need to also include a hash of `x.__class__`, where all of the methods are hashed.

This does mean that any instance of a class `A` depends on the function bodies of all of the methods on `C`, which might cause lots of
unneccessary invalidations if `A` has a lot of methods but `f` only uses `foo`. I think you just have to accept this, because in general you
can't know without running the function which methods are being called: eg you could have `getattr(a, complicated_fn(a))()`.

The simplest solution is the above one, and then recommend to developers that they don't use class methods if they can get away with standalone functions.

There may be a heuristic that we can deploy where if `a.foo` appears, we can drop the dependency on the entirety of `a.__class__` and just depend on `a.foo`.
However note that this heuristic can get complicated:

```py
def f(a : A):
    x = somefunc(a)
    return x.foo()
```

In order to figure out which `foo` we are depending on here we need to inspect the method body of `somefunc`.
It might still be possible to determine what code is being called by `x.foo()` statically in the majority of cases.

We have similar issues with `@singledispatch`, where now which function gets called depends on the type of the input.
The answer in this case is you have to include all of the overloads for the singledispatch method in the dependency graph.

## Function cycles

It's possible to have function cycles

```py
def f(x):
    return 0 if x == 0 else g(x)

def g(x):
    return 1 + f(x - 1)
```

A naive dependency-following algorithm would infinite loop.
The answer is that instead you store a directed graph, each vertex is a symbol, each edge is a symbol dependency.
When computing the final hash of a function you take the local hash and all of the local hashes of the dependency closure on `f`.

Note that even non-function symbols may have dependencies in the graph because they may contain functions.

It's going to be quite hard making sure that this whole system is fast and doesn't hang, but I think it's possible in theory.
There are lots of reasonable heuristics and function-writing guidelines that we can ask users to adhere to.

## Alternative approach

Another approach I considered was when you run a function `f` that you want to cache the results of, you attach a stack-tracer to `f`.
Then you use the resulting stack trace to determine which other functions were run under `f`'s frame. This is your set of function dependencies for `f`.
You can then invalidate `f`'s cache if any of these functions change their method body or their dependent constants change.
Note that you would need to then have a different set of dependencies for each value fed to `f`.

I didn't go with this approach in the end because I think there is some overhead involved with computing the stack trace (compare to the other method where dependencies are computed once when the app starts).
It can also get a bit finicky with constants, you still need to statically determine that `g` depends on `P` and `K` in the below example.

```py
K = {
    "hello": lambda x: x + x
}

P = "hello"

def g(x):
    return K[P](x)

def f(x):
    return g(x) + 2
```

## User overrides

If we cause a cache invalidation because a piece of code changed that wasn't actually run, we call this an __unneccessary invalidation__.
If there is a change to the code that causes the computation to change but which _doesn't_ invalidate the cache. Call this an __unsound cache__.

I reckon there is a corollary of halting-problem that you can't in general determine the code dependencies of arbitrary python code without running it.

We have to make tradeoffs between invalidating the cache on any change at all (also known as not caching), and causing cache unsoundness.
In general we can't avoid unsoundness on arbitrary code, but we can give users the diagnostics and tools to discover potential issues with their code that cause unsoundness.
This is a reasonable stance, developers use caches all the time and know that they can become unsound if you are not careful.

We just have to accept this and do the best we can with the main situations, and ask users to write code where we can determine the code dependencies.
Because of this, I think that is worth adding a feature where the users can explicitly block or add their own dependencies.


# References

- [symtable docs](https://docs.python.org/3/library/symtable.html)
- Python internals: Symbol tables, [part 1](https://eli.thegreenplace.net/2010/09/18/python-internals-symbol-tables-part-1/), [part 2](https://eli.thegreenplace.net/2010/09/20/python-internals-symbol-tables-part-2/).
- [the missing python ast docs](https://greentreesnakes.readthedocs.io/en/latest/)
- [ast docs](https://docs.python.org/3/library/ast.html)
