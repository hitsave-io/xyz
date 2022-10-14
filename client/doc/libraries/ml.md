
This article describes how to use HitSave with various ML libraries.

# Pytorch

Pytorch is the leading machine learning framework for python.

Training pytorch `Model`s is inherently stateful: the weights of the model are updated.
Meanwhile, checkpoints and logs are written to disk. HitSave has special support for this ML workflow so that you can save your models, logs and checkpoints with minimal changes to your training code.

- HitSave hooks in to Pytorches model saving feature.

# Tensorboard

TensorBoard is a popular logging format and webapp for viewing the logs of ML experiments.
TensorBoard typically works by your training code saving logs to disk and a tensorboard local webapp running for viewing these logs.

HitSave has special support for working with TensorBoard logs.
We offer the ability to load and save logs.


# PyTorch Lightning

We support [PyTorch Lightning](https://www.pytorchlightning.ai) [todo]