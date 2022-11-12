# Why HitSave?

We have done a lot of experimental data science.

We've worked with a lot of data science, ML training and analytics in the past,
and used many tools for handling large datasets such as dagster, airflow,
weights and biases, even Microsoft Excel. However we always found existing tools
had something to learn from Excel:

> Pipelines depend on code.

Our solution is to admit that data depends on code and to tie data directly to
the code that created it, rather than using arbitrary versioning schemes and
configs.

You don't appreciate how important a run is going to be until after you have
done it. Maybe you were just trying something out and didn't bother to
`git commit` your changes before you tried something out, and now you have lost
the exact set of changes that created the result. HitSave tracks exactly the
code that ran when a piece of data is created.

These other tools highjack a larger part of your thinking capacity while you are
working; ooh did I set the

- We can all agree that experiment tracking and management is important to do
  well.
- There are lots of existing experiment managers: idsia/sacred, guild, aimstack,
  wandb, polyaxon, clear.ml, mlflow.org. Why are we different?
- Existing tools fundamentally miss the point of what an experiment manager can
  be. They put you on rails, give you a rigid workflow, lots of typing,
  boilerplate. Everything needs to fit into the ontology of Models, Metrics,
  Artefacts, Configs.
- What they are failing to realise is that everything boils down to quite a
  simple notion, which is that experiments are the results of computation.
- HitSave replaces

## Our approach to code versioning

The core concept that sets HitSave apart is granular code versioning. Consider
the below example of a simple regression experiment.

// Example here: eg simple regression

Suppose that we want to see whether performance is improved by changing the size
of X. In existing systems, you would have to make X a config parameter and feed
it through from the top-level experiment. You would then also have to commit the
change to your repo. Then run it to get a new run of the experiment.

In contrast, with HitSave, you can just _change the code_ and HitSave will
automatically track the code changes. Running the experiment again will
automatically show you what changed.

// screenshot showing the new experiment run, there is a special diff column
showing what code changed.

Furthermore, HitSave intelligently traverses the code dependencies of your
experiment, so if instead you changed some code that was irrelevant to the
experiment, this would not trigger a re-run.

// Another paragraph that drives home why this is good

## Back to experiment managing

With HitSave's unique approach to code versioning, we can simplify how we manage
experiments. We can think of an experiment as a function, with inputs and
outputs. The inputs are the arguments, config variables and other aspects of the
environment such as the dataset on disk.

- configs are arguments
- artefacts are just returned values
- metrics are just returned values
