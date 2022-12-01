# HitSave

Effortless data.

Optimize your team's workflow with cloud memoization, experiment tracking and effortless data versioning.
Find out more at https://hitsave.io.

# Quickstart

```sh
pip install hitsave
```

Take any functon in your project, decorate it with `@memo`.

```py
from hitsave import memo

def dependency(y):
  # try changing the method body!
  return y + y

@memo
def long_running_function(x):
  print(f"Running {x}!")
  return x + 2 + dependency(x)

long_running_function(3)
long_running_function(4)
```

When you run this python file, `@memo` will cache the results to disk (and to
our cloud service). When you run the file again, the cache will be used rather
than re-running the function. `@memo` analyses the code-dependencies of your
code and determines when to invalidate the cache. You can add `@memo` to any
function where the output is picklable.
