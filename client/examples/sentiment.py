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

from enum import Enum
from typing import List, Literal, Tuple
import torch
import time
import csv
from tqdm import tqdm
from torch.utils.data import DataLoader, TensorDataset, Dataset, random_split
from torchtext.data.utils import get_tokenizer
from torchtext.vocab import build_vocab_from_iterator, Vocab
from torch import nn
from torchtext.data.functional import to_map_style_dataset

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

from hitsave import experiment, FileSnapshot, memo, restore

#%%
# Loading the data.
# -----------------
# .. _drive: https://drive.google.com/drive/folders/0Bz8a_Dbh9Qhbfll6bVpmNUtUcFdjYmF2SEpmZUZUcVNiMUw1TWN6RDV3a0JHT3kxLVhVR2M
# .. _1509: https://arxiv.org/abs/1509.01626
# .. _SNAP: https://cseweb.ucsd.edu/~jmcauley/pdfs/recsys13.pdf
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


@memo
def load_dataset(split: Split) -> List[Tuple[int, str]]:
    """Given a split, produces a list of rating, review pairs.

    Label 0 is a bad review (1-2 stars), label 1 is a good review (4-5 stars).
    """
    digest = digests[split]
    path = restore(digest)
    with open(path, "rt") as f:
        items = [
            (int(rating) - 1, title + ": " + body)
            for rating, title, body in csv.reader(f, delimiter=",")
        ]
        return items[:1000]


load_dataset("test")[:10]

#%%
# You can learn more about saving and restoring files to the HitSave cloud in `Working with Files <../guides/files.html>`_.
#
# Creating the vocabulary
# -----------------------
#
# We need to convert our text reviews into streams of integers that can be fed to the model.
# You can learn more about this in the PyTorch tutorial that this example is based off
# We will use the same model that PyTorch recommend in `their tutorial <https://pytorch.org/tutorials/beginner/text_sentiment_ngrams_tutorial.html>`_.
# Creating a vocabulary is time-consuming, but we can use `@memo` to memoise it.

tokenizer = get_tokenizer("basic_english")


@memo
def make_vocab() -> Vocab:

    vocab = build_vocab_from_iterator(
        (tokenizer(text) for _, text in tqdm(load_dataset("train"))),
        specials=["<unk>"],
    )
    vocab.set_default_index(vocab["<unk>"])

    return vocab


vocab = make_vocab()

#%%
# Create the dataloaders
# -----------------
#

text_pipeline = lambda x: vocab(tokenizer(x))


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


BATCH_SIZE = 64  # batch size for training


@memo
def create_dataloader(split: Split):
    dataset = to_map_style_dataset(load_dataset(split))
    return DataLoader(
        dataset, batch_size=BATCH_SIZE, shuffle=True, collate_fn=collate_batch
    )


#%%
# Defining the model
# -----------------
#
# Now we define our model.


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


EPOCHS = 1
LR = 5  # learning rate
num_class = 2
vocab_size = len(vocab)
emsize = 64
criterion = torch.nn.CrossEntropyLoss()


def train_epoch(dataloader, model, optimizer, epoch):
    model.train()
    total_acc, total_count = 0, 0
    log_interval = 500
    start_time = time.time()

    for idx, (label, text, offsets) in enumerate(dataloader):
        optimizer.zero_grad()
        predicted_label = model(text, offsets)
        loss = criterion(predicted_label, label)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 0.1)
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


@experiment
def train_model():
    model = TextClassificationModel(vocab_size, emsize, num_class).to(device)

    optimizer = torch.optim.SGD(model.parameters(), lr=LR)
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, 1, gamma=0.1)
    total_accu = None
    train_dataloader = create_dataloader("train")
    test_dataloader = create_dataloader("test")

    for epoch in range(1, EPOCHS + 1):
        epoch_start_time = time.time()
        train_epoch(train_dataloader, model, optimizer, epoch)
        ev = evaluate(
            test_dataloader, model
        )  # [todo] this is naughty, use a validation split
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
# Now we put it all together


@experiment
def test():
    model = train_model()
    test_dataloader = create_dataloader("test")

    print("Checking the results of test dataset.")
    results = evaluate(test_dataloader, model)
    print("test accuracy {:8.3f}".format(results["acc"]))
    return results


test()
