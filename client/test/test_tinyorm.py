from enum import Enum
from datetime import datetime
from dataclasses import dataclass
import logging
import sqlite3
from typing import Optional

from hitsave.util.tinyorm import col, Schema, transaction, Connection


class BlobStatus(Enum):
    foo = 1
    bar = 2


@dataclass
class Blob(Schema):
    digest: str = col(primary=True)
    length: int = col()
    label: Optional[str] = col()
    status: BlobStatus = col()
    created: datetime = col()
    accesses: int = col()


def test_it():
    con = Connection(sqlite3.connect(":memory:"))
    Connection.set_current(con)

    logging.basicConfig(level=logging.DEBUG)

    blobs = Blob.create_table(name="blobs")

    blobs.insert_one(
        Blob(
            digest="cabbage",
            length=1000,
            label=None,
            status=BlobStatus.foo,
            created=datetime.now(),
            accesses=0,
        )
    )

    blob = blobs.select_one(where=Blob.digest == "cabbage")
    assert blob is not None
    assert isinstance(blob, Blob)
    assert blob.digest == "cabbage"
    assert blob.label is None
    assert blob.length == 1000

    t = datetime.now()

    i = blobs.update(
        {
            Blob.accesses: Blob.accesses + 1,
            Blob.created: t,
            Blob.status: BlobStatus.bar,
        },
        where=Blob.digest == blob.digest,
    )
    assert i == 1

    blob2 = blobs.select_one(where=Blob.digest == blob.digest)
    assert blob2 is not None
    assert blob2.status == BlobStatus.bar
    assert blob2.accesses == blob.accesses + 1
    assert blob2.created == t

    for (status, label) in blobs.select(
        where=(Blob.label == "hello"), select=(Blob.status, Blob.label)
    ):
        print(status, label)


if __name__ == "__main__":
    test_it()
