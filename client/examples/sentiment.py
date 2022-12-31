"""
Sentiment Classification
========================

.. _torchtext: https://pytorch.org/text/stable/index.html
.. _pytorchtutorial: https://pytorch.org/tutorials/beginner/text_sentiment_ngrams_tutorial.html

In this tutorial we will train a `PyTorch Text <torchtext>`_ classifier to
guess the ratings of products from text reviews on Amazon.

During this tutorial you will learn how to do the following things in HitSave:
- reproducibly save datasets
- manage experiments

Let's create a new project folder

::

        cd $HOME
        mkdir sentiment
        cd sentiment
        touch pyproject.toml
        touch sentiment.py
        mkdir data

        # set up our python environment
        python -m venv .env
        source .env/bin/activate
        pip install torch torchdata torchtext


Here we created two files, our sourcefile sentiment.py and a pyproject.toml_
is needed  to tell HitSave what the root directory of your project is.
(Another way to do this is to initialise a git repository).

.. _pyproject.toml: https://pip.pypa.io/en/stable/reference/build-system/pyproject-toml/)

Before we start, make sure that you have installed HitSave by following the [installation instructions](installation)

"""

#%%

from collections.abc import Iterator
from typing import Literal
import torch
from itertools import islice
import time
import csv
from torch.utils.data import DataLoader, TensorDataset, Dataset, random_split
from torchtext.data.utils import get_tokenizer
from torchtext.vocab import build_vocab_from_iterator, Vocab
from torch import nn
from torchtext.data.functional import to_map_style_dataset

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

from hitsave import experiment, FileSnapshot, memo, restore

#%%
# Loading the data.
# ---------------------
# .. _drive: https://drive.google.com/drive/folders/0Bz8a_Dbh9Qhbfll6bVpmNUtUcFdjYmF2SEpmZUZUcVNiMUw1TWN6RDV3a0JHT3kxLVhVR2M
# .. _1509: https://arxiv.org/abs/1509.01626
# .. _SNAP: https://cseweb.ucsd.edu/~jmcauley/pdfs/recsys13.pdf
#
# First we have to get our hands on the dataset.
# We will use the Amazon Reviews for Sentiment Analysis dataset by `Xiang Zhang et al <1509_>`_,
# extracted from the `Stanford Network Analysis Project <SNAP_>`_.
#
# You can download the original dataset from `Xiang Zhang's Google Drive <drive_>`_ (amazon_review_polarity_csv.tar.gz).
# However, we are using HitSave and so we can use HitSave's snapshot-restore feature.

Split = Literal["test", "train"]
digests = {
    "test": "d4f01cbe4876739cfde1e5306d19bc73d5acde53a7b9b152219505292829ee46",
    "train": "8f6c92d72174ba3b5be9138ba435cbd41dcd8377f7775ce981ac9c9aa2c4f141",
}


def load_dataset(split: Split) -> Iterator[tuple[int, str]]:
    """Given a split, produces a list of rating, review pairs.

    Label 0 is a bad review (1-2 stars), label 1 is a good review (4-5 stars).
    """
    digest = digests[split]
    # This line downloads the needed CSV file from the HitSave data catalogue.
    # This download is cached in your home's cache directory.
    # You can clear your cache with `hitsave clear-local`
    path = restore(digest)
    with open(path, "rt") as f:
        # note: we limit the number of items to keep the demo fast on cpus.
        # if you have a GPU, delete the limit!
        items = islice(csv.reader(f, delimiter=","), 100000)
        for rating, title, body in items:
            yield (int(rating) - 1, title + ": " + body)


#%%
# You can learn more about saving and restoring files to the HitSave cloud in `Working with Files <../guides/files.html>`_.
#
# Creating the vocabulary
# ---------------------------
#
# We need to convert our text reviews into streams of integers that can be fed to the model.
# You can learn more about this in the PyTorch tutorial that this example is based off.
# We will use the same model that PyTorch recommend in `their tutorial <https://pytorch.org/tutorials/beginner/text_sentiment_ngrams_tutorial.html>`_.
# Creating a vocabulary can be time-consuming, but we can use `@memo` to memoise it so that you don't need to recompute it every time.

tokenizer = get_tokenizer("basic_english")


@memo
def make_vocab() -> Vocab:
    print("Building vocab")
    items = islice(load_dataset("train"), 10000)
    vocab = build_vocab_from_iterator(
        (tokenizer(text) for _, text in items),
        specials=["<unk>"],
    )
    vocab.set_default_index(vocab["<unk>"])
    print(f"Build vocab of {len(vocab)} items.")
    return vocab


vocab = make_vocab()

#%%
# Create the dataloaders
# -------------------------------
#


def text_pipeline(x):
    return vocab(tokenizer(x))


def collate_batch(batch):
    label_list, text_list, offsets = [], [], [0]
    for (_label, _text) in batch:
        label_list.append(_label)
        processed_text = torch.tensor(text_pipeline(_text), dtype=torch.int64)
        text_list.append(processed_text)
        offsets.append(processed_text.size(0))
    label_list = torch.tensor(label_list, dtype=torch.int64)
    offsets = torch.tensor(offsets[:-1]).cumsum(dim=0)
    text_list = torch.cat(text_list)
    return label_list.to(device), text_list.to(device), offsets.to(device)


def create_dataloader(dataset: Dataset, batch_size: int):
    return DataLoader(
        dataset, batch_size=batch_size, shuffle=True, collate_fn=collate_batch
    )


#%%
# Defining the model
# -----------------------------
#
# Now we define our model and the training logic. This is the same as in the torchtext tutorial.


class TextClassificationModel(nn.Module):
    def __init__(self, vocab_size, embed_dim, num_class):
        super(TextClassificationModel, self).__init__()
        self.embedding = nn.EmbeddingBag(vocab_size, embed_dim, sparse=True)
        self.fc = nn.Linear(embed_dim, num_class)
        self.init_weights()

    def init_weights(self):
        initrange = 0.5
        self.embedding.weight.data.uniform_(-initrange, initrange)
        self.fc.weight.data.uniform_(-initrange, initrange)
        self.fc.bias.data.zero_()

    def forward(self, text, offsets):
        embedded = self.embedding(text, offsets)
        return self.fc(embedded)


num_class = 2
vocab_size = len(vocab)
criterion = torch.nn.CrossEntropyLoss()


def train_epoch(
    dataloader: DataLoader, model: TextClassificationModel, optimizer, epoch: int
):
    model.train()
    total_acc, total_count = 0, 0
    log_interval = 500
    start_time = time.time()

    for idx, (label, text, offsets) in enumerate(dataloader):
        optimizer.zero_grad()
        predicted_label = model(text, offsets)
        loss = criterion(predicted_label, label)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 0.1)  # type: ignore
        optimizer.step()
        total_acc += (predicted_label.argmax(1) == label).sum().item()
        total_count += label.size(0)
        if idx % log_interval == 0 and idx > 0:
            elapsed = time.time() - start_time
            print(
                "| epoch {:3d} | {:5d}/{:5d} batches "
                "| accuracy {:8.3f}".format(
                    epoch, idx, len(dataloader), total_acc / total_count
                )
            )
            total_acc, total_count = 0, 0
            start_time = time.time()


def evaluate(dataloader, model):
    model.eval()
    total_acc, total_count = 0, 0
    total_loss = 0.0
    with torch.no_grad():
        for _, (label, text, offsets) in enumerate(dataloader):
            predicted_label = model(text, offsets)
            loss = criterion(predicted_label, label)
            total_acc += (predicted_label.argmax(1) == label).sum().item()
            total_count += label.size(0)
            total_loss += loss.item()
    return {"acc": total_acc / total_count, "avg_loss": total_loss / total_count}


#%%
# Now we write the core training loop. We have added the `@memo` decorator to the
# top of `train_model`, this means that if we call `train_model` with the same arguments and the same code-dependencies, rather than
# re-run the training loop, we simply return the trained model from the cloud cache.


@memo
def train_model(
    *,
    lr,
    epochs,
    emsize,
    batch_size,
):
    model = TextClassificationModel(vocab_size, emsize, num_class).to(device)

    optimizer = torch.optim.SGD(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, 1, gamma=0.1)
    total_accu = None
    train_dataset = to_map_style_dataset(load_dataset("train"))
    train_dataset, val_dataset = random_split(
        train_dataset, [0.95, 0.05], generator=torch.Generator().manual_seed(42)
    )
    train_dataloader = create_dataloader(train_dataset, batch_size)
    val_dataloader = create_dataloader(val_dataset, batch_size)

    for epoch in range(1, epochs + 1):
        epoch_start_time = time.time()
        train_epoch(train_dataloader, model, optimizer, epoch)
        ev = evaluate(val_dataloader, model)
        accu_val = ev["acc"]
        if total_accu is not None and total_accu > accu_val:
            scheduler.step()
        else:
            total_accu = accu_val
        print("-" * 59)
        print(
            "| end of epoch {:3d} | time: {:5.2f}s | "
            "valid accuracy {:8.3f} ".format(
                epoch, time.time() - epoch_start_time, accu_val
            )
        )
        print("-" * 59)

    return model


#%%
# Now we put it all together in an `@experiment` decorator.
# The `@experiment` decorator memoises the function similarly to `@memo`, but
# the cloud-cache will not clear out old values and you
# can view the results of previous evaluations at https://hitsave.io/dashboard.


@experiment
def test(
    lr=5.0,
    epochs=10,
    emsize=64,
    batch_size=64,
):
    model = train_model(lr=lr, epochs=epochs, emsize=emsize, batch_size=batch_size)
    test_dataloader = create_dataloader(
        to_map_style_dataset(load_dataset("test")), batch_size
    )

    print("Checking the results of test dataset.")
    results = evaluate(test_dataloader, model)
    return results


#%%
# Give this code a run and head to hitsave.io to see the results!
# Have a go at changing parameters and code, watch how HitSave only recomputes
# the code that depends on your changes!


if __name__ == "__main__":
    # try editing these values and watch the dashboard fill with values.
    results = test(batch_size=64, lr=5.0, epochs=5)
    print("test accuracy {:8.3f}".format(results["acc"]))


#%%
# Ready to learn more?
# Head over to `our discord <https://discord.gg/DfxGynVBcN>`_, let us know about your use case and we are happy to help!
