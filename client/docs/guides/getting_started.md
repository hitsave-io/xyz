# Getting Started with HitSave


## Setting up your project

This article gives a tour of HitSave's features. Be sure to read the [installation guide](installation.md). Let's create a new python project in the terminal:

```sh
mkdir hello-hitsave
cd hello-hitsave
git init
touch hello.py
```

````{admonition} Projects
HitSave uses Git to determine the root directory of a Python project. If no Git project is present then
````


## Hello HitSave!

Let's start with a simple function `fibo` in `hello.py`

```python
# hello.py
def fibo(n):
  print(f"computing fibo({n})")
  return 1 if n < 3 else fibo(n - 1) + fibo(n - 2)

fibo(10)

```

This computes the `n`th Fibonacci number, but note that it is inefficient because it needs to repeatedly recompute the inner `fibo` calls.
The classic way to fix this is with _memoisation_ of `fibo`. This is where you decorate `fibo` with `functools.cache`:


```python
import functools

@functools.cache
def fibo(n):
  print(f"computing fibo({n})")
  return 1 if n < 3 else fibo(n - 1) + fibo(n - 2)

fibo(10)
```

This is nice. But you need to repopulate the memoisation cache every time you run your python code.
That is, if you run the above code twice, it will recompute all of the `fibo(n)` values.


What if, instead, the cache was saved to disk so that the numbers could be used on later runs?
What if, this cache was on the cloud, so anyone using your code would also have access to the cache?
This is what HitSave does.
HitSave is `@functools.cache` with super powers. We take this simple idea of a cloud-backed cache and use it to build streamlined data infrastructure for you and your team.

```python
from hitsave import experiment

@experiment
def fibo(n):
  print(f"computing fibo({n})")
  return 1 if n < 3 else fibo(n - 1) + fibo(n - 2)

fibo(10)
```

If you run this code multiple times, it only needs to compute `fibo(n)` exactly once for each `n`. Each value is stored to the HitSave local database _and_ to the cloud. Head over to https://hitsave.io/dashboard/experiments to see the results.

## Changing your code

While holding a cache of your function in memory is useful to avoid recomputation, we need to know when to throw away the cache when our code changes.
Let's edit our `fibo` function to be the sum of the last _three_ values:

```python
from hitsave import experiment

@experiment
def fibo(n):
  print(f"computing fibo({n})")
  return 1 if n < 3 else fibo(n - 1) + fibo(n - 2) + fibo(n - 3)

fibo(10)
```

Now, our cached values are invalid! HitSave looks at the code that is about to run and figures out whether any code has changed by diffing the code with the code that executed when the function was run.

What if the `fibo` code depends on variables and functions outside of `fibo`?
HitSave tracks the dependencies of `fibo` using fancy code analysis to figure out when it needs to invalidate the cache:

```python
from hitsave import experiment

C = 4

def g(x):
    return x * x

@experiment
def fibo(n):
  print(f"computing fibo({n})")
  return 1 if n < 3 else fibo(n - 1) + g(fibo(n - 2)) + C

fibo(10)
```

Try editing the value of `C` or the contents of `g` and re-running. The cache is invalidated when the dependencies change.

## Next up: Using HitSave to level-up your workflow.

That is all there is to HitSave! It's just cloud-backed memoisation and some nice code dependency tracking.
While the core mechanic is as simple as you can get, there are some wide-reaching ramifications for data science and data engineering.

The above `fibo` example showed how cloud-memoisation works, but the `@memo` and `@experiment` decorators were built to wrap heavy computation where you want to avoid recomputing from scratch.
Think analytics on large amounts of data, or running an optimisation, or training an ML model.

In the coming guides, we will see how to use `@memo` and `@experiment` for working with large amounts of data.

## Where next?

- [How HitSave works](how_it_works.md).
- Managing experiments with HitSave (coming soon)
- Creating data pipelines with HitSave (coming soon)
- Try out the [Sentiment analysis example project](https://docs.hitsave.io/examples/sentiment.html).
- Jump on [the Discord](https://discord.gg/DfxGynVBcN) and talk to us about your ideas and use cases.