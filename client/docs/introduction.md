HitSave is a cloud service and python library for saving your data on the cloud
in a reproducible and hassle-free way.

The core object in HitSave is the `@memo` decorator. `@memo` behaves similarly
to `@functools.lru_cache` with a few key differences:

- Rather than storing previous function evalutations in memory, they are saved
  to disk. This is similar to `joblib.Memory` if you have used that. If enabled,
  HitSave can also save to the cloud so that other users of your library on
  other machines can make use of the cache.
- HitSave will analyse your codebase to determine the code-dependencies of your
  `@memo`d function. If you edit your code, HitSave will automatically
  invalidate the cache so that you always get correct values.

# Example

See more examples at [todo]

# When to use `@memo`

Not all functions are appropriate for `@memo`. A good rule-of-thumb is asking
whether the function is a good target for other forms of caching such as
`lru_cache`. Here are some considerations for whether a function can be useful
for saving:

- The function takes a long time to run. If the function was fast, it's hardly
  worth the overhead of hashing arguments and downloading the saved value.
- Are the arguments to the function easy to hash? If you pass a huge tensor to
  the function, hitsave will have to hash the entire object before it can
  determine if the function is already hashed.
- The output of the function is used in multiple places.
- The function doesn't cause side-effects. A side-effect is a change that the
  function makes to the environment that isn't in the function's return value.
  An example could be modifying a global value, or changing a file on disk.
- The function doesn't depend on a changing external resource (for example,
  polling a web API for the weather).
- The function doesn't implicitly depend on the state of the filesystem.

Hitsave will intelligently bulk-download cached results if it detects that a
function will be called frequently [todo]. You can also force a download of all
cached results by calling `f.download()` [todo].

# Overview of how it works

[todo]

# Next steps

[todo]
