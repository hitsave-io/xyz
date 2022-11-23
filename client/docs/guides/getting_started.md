(getting_started)=
# How HitSave Works

## Prerequisites

If you haven't done so already, follow the steps in the [installation
guide](installation) to get setup with HitSave.

## The HitSave Decorators

The core object in HitSave is the `@memo` decorator. If you've used
[`@functools.lru_cache`](https://docs.python.org/3/library/functools.html#functools.lru_cache)
you'll be familiar with the notion of caching function executions.

### [`@memo`](hitsave.memo)

HitSave's `@memo` behaves similarly to `lru_cache` but incorporates a few
powerful additions:

- Rather than storing previous function evaluations in memory (where they
  are only available for the current execution session) they are instead
  persisted to disk and reusable in future execution sessions.
- HitSave syncs your cache to the cloud. Soon, HitSave will allow teams to have
  shared caches, so that if code has been run once on your team, no-one else
  has to wait for the results if they re-run the same code with the same
  inputs.
- HitSave uses a much more sophisticated caching algorithm than `lru_cache`.
  Before running your code, HitSave statically analyses the code dependency
  tree of your `@memo`'d function, and uses hash digests of both the code
  itself and the data you pass in. If you edit your code, or pass different
  arguments, HitSave automatically invalidates the cache so that you are
  always returned correct values.

With this abstraction, HitSave enables you to persistently memoize
long-running functions, and avoid manually saving intermediate results to
persistent disk storage.

For example, imagine you are ingesting a large dataset
through an ETL pipeline. Instead of using Python's native file API to save
the state of your dataset to your local machine at each step, you can
instead use `@memo` to persist the dataset to a managed local cache, as
well as automatically syncing this to the cloud where it can be accessed
by other team members. Now, if you need to edit a downstream step in your
ETL pipeline, there's no need to reload the previous step's output as a
starting point: simply running the whole pipeline again will have the
effect of immediately picking up from the latest unchanged step and
calculating the new results.
Because HitSave is on the cloud, this works even if earlier steps were run on different computers!

### [`@experiment`](hitsave.experiment)

An interesting side-effect of HitSave's caching mechanics is that we can
provide experiment management for free.

HitSave provides a second core decorator called [`@experiment`](hitsave.experiment).
The dirty little secret of `@experiment` is that it's really just `@memo`
under the hood! All we do in addition is add a boolean flag to the
memoized function evaluation to indicate that it's a result of interest
which should never be automatically wiped from your cache.

We've built a dashboard in the web interface where you can inspect
all your experiments and see visualized arguments and return values in
the browser.

Here's a rough example of how you could use this functionality to get
useful experiment tracking up and running in just a few lines of code.

```python
lr = 0.01
batch_size = 200

@experiment
def train_model(lr, batch_size):
    training_dataset, test_dataset = get_datasets()
    model = NeuralNetwork()
    writer = []
    for epoch in range(epochs):
        model.train(lr, training_dataset)
        writer.append([{
            'epoch': epoch,
            'accuracy': accuracy(test_dataset, model)
        }])

    df = pd.DataFrame(writer)
    fig = px.line(df, x='epoch', y='accuracy')

    return model, fig
```

Perhaps you already had some code which looked like this, minus the
`@experiment` decorator.

Here's what happens:

- You define parameters for your experiment like learning rate and batch
  size. These are passed into the function, so HitSave can interpret the
  relationship between input and output.
- You load in your datasets. The `get_datasets` function could even be
  an `@memo`'d function.
- You train the model for a number of epochs and calculate the accuracy
  performance on the test dataset at the end of each epoch.
- Along the way, you append the accuracy data to a writer (e.g.
  something like a Tensorboard log).
- At the end, you construct a figure, plotting the accuracy at each
  epoch.
- Finally, you return the model and the figure.

Now, when you visit the [cloud experiment tracker](https://hitsave.io/dashboard/experiments)
you'll see a row in the table displaying the experiment you ran. It
includes the values of the learning rate and batch size parameters passed
into the function, as well as displaying the returned accuracy plot on screen.

Now you can come back to the editor and try some different values of the
input parameters. Each time you run the code, you'll get a new row in
the table. You could even call the `@experiment` function many times in
the same execution session by nesting it in a for-loop - for example to
perform a hyperparameter sweep. Best of all, if you rerun the function
with the same parameters as a previous run, you'll get the output
instantaneously from the cache (well, at least as quickly as your
computer can download it from the cloud or local disk).

In the future, we're going to make it possible to share caches and
experiments among team members, as well as allowing you to directly
download cached artifacts into a Python session by referencing a unique
identifier which you'll be able to grab from the interface.

## When to Use `@memo`

Not all functions are appropriate for `@memo`. A good rule-of-thumb is asking
whether the function is a good target for other forms of caching such as
`lru_cache`. Here are some considerations for whether a function can be useful
for saving:

- Does the function takes a long time to run? If the function is fast, it's hardly
  worth the overhead of hashing arguments and downloading the saved value.
- Are the arguments to the function easy to hash? If you pass a huge tensor to
  the function, HitSave will have to hash the entire object before it can
  determine if the function is already hashed.
- Does the function cause [side-effects](<https://en.wikipedia.org/wiki/Side_effect_(computer_science)>)?
  A side-effect is a change that the function makes to the environment
  that isn't in the function's return value. Examples are: modifying
  a global value, or changing a file on disk.
- The function doesn't depend on a changing external resource (for example,
  polling a web API for the weather).
- The function doesn't implicitly depend on the state of the filesystem.
