""" A little ORM for sqlite.

I think eventually this will need to use sqlalchemy core to store expressions and
to connect to other databases.

Existing ORMs just seem to be clunky overkill.

Related work:
- peewee http://docs.peewee-orm.com/en/latest/
- sqlalchemy

I didn't like peewee because it associates the schema with the table. But really
you could make multiple tables with the same schama. Also the schema definitions are clunky.

Also injection attacks are only defended with user data being inserted.
You are free to give a field in your schema dataclass a name like "; DROP TABLE" if you really want to.

"""
import logging
from typing import Callable, List, Union
from dataclasses import dataclass, is_dataclass, fields, field, Field
from contextlib import contextmanager
from datetime import datetime
import sqlite3
from hitsave.util import Current, as_optional
from typing import Any, Generic, Iterable, Iterator, Optional, Type, TypeVar, overload

logger = logging.getLogger("tinyorm")

T = TypeVar("T", bound="Schema")
S = TypeVar("S")


class Table(Generic[T]):
    schema: Type[T]

    def __init__(self, name: str):
        self.name = name

    @overload
    def select(self, *, where: bool = True) -> Iterator[T]:
        ...

    @overload
    def select(self, *, where: bool = True, select: S) -> Iterator[S]:
        ...

    def select(self, *, where=True, select=None):  # type: ignore
        raise NotImplementedError()

    @overload
    def update(
        self, update_dict, /, *, where: bool = True, returning: S
    ) -> Iterator[S]:
        ...

    @overload
    def update(self, update_dict, /, *, where: bool = True) -> None:
        ...

    def update(self, update_dict, /, where=True, returning=None):  # type: ignore
        def mk_setter(key, value) -> "Expr":
            assert isinstance(key, Column)  # [todo] strings for column names are ok too
            return Expr(f"{key.name} = ?", value)

        setters = Expr.binary(", ", [mk_setter(k, v) for k, v in update_dict.items()])
        query = Expr(f"UPDATE {self.name} SET ? ", setters)
        if where is not True:
            assert isinstance(where, Expr)
            query = query.append("WHERE", where)
        if returning is not None:
            p = Pattern(returning)
            query = query.append("RETURNING", p.to_expr())
            with transaction() as conn:
                for x in query.execute(conn):
                    yield p.outfn(x)
            return
        else:
            with transaction() as conn:
                query.execute(conn)

    def insert(self, *ts: Iterable[T]) -> None:
        raise NotImplementedError()


class Pattern(Generic[S]):
    items: List["Expr"]
    outfn: Callable[[List[str]], S]

    def __len__(self):
        return len(self.items)

    def __init__(self, obj: S):
        if isinstance(obj, Pattern):
            self.items = obj.items
            self.outfn = obj.outfn
        if isinstance(obj, Column):
            self.items = [Expr(obj)]
            # [todo] perform conversion here?
            self.outfn = lambda x: x[0]  # type: ignore
        elif isinstance(obj, (tuple, list)):
            self.items = []
            js = [0]
            ps = []
            for v in obj:
                p = Pattern(v)
                js.append(len(p))
                ps.append(p)
                self.items.extend(p.items)

            def blam(x) -> Any:
                acc = []
                for (p, i, j) in zip(ps, js[:-1], js[1:]):
                    assert j - i == len(p)
                    s = p.outfn(x[i:j])
                    acc.append(s)
                return type(obj)(acc)

            self.outfn = blam
        elif isinstance(obj, dict):
            self.items = []
            j = 0
            keys = list(obj.keys())
            jps = {}
            ps = []
            for k in keys:
                v = obj[k]
                p = Pattern(v)
                jps[k] = (j, p)
                j += len(p)
                self.items.extend(p.items)

            def blam(x) -> Any:
                acc = {}
                for k in keys:
                    (j, p) = jps[k]
                    j2 = j + len(p)
                    s = p.outfn(x[j:j2])
                    acc[k] = s
                return acc

            self.outfn = blam

        else:
            raise ValueError("bad pattern")

    def to_expr(self) -> "Expr":
        return Expr.binary(", ", self.items)


class Expr:
    """A sqlite expression."""

    expr: str
    values: List[Any]

    def __init__(self, obj: Union["Expr", "Column", Any], *params):
        if isinstance(obj, Expr):
            assert len(params) == 0
            self.expr = obj.expr
            self.values = obj.values
        elif isinstance(obj, Column):
            assert len(params) == 0
            self.expr = obj.name
            self.values = []
        elif isinstance(obj, str) and len(params) > 0:
            [head, *tail] = obj.split("?")
            assert len(tail) == len(params)
            self.expr = head
            self.values = []
            for c, p in zip(map(Expr, params), tail):
                self.expr += c.expr
                self.values.extend(c.values)
                self.expr += p
        elif len(params) == 0:
            self.expr = " ? "
            self.values = [obj]
        else:
            raise ValueError(f"Don't know how to make expression.")

    def __repr__(self):
        return f"Expr({repr(self.expr)}, {repr(self.values)}"

    def __str__(self):
        [x, *xs] = self.expr.split("?")
        acc = x
        for v, x in zip(self.values, xs):
            acc += f"⟨{str(v)}⟩"
            acc += x
        return acc

    @classmethod
    def binary(cls, op: str, args: List[Any]):
        return Expr(op.join(" ? " for _ in args), *args)

    def __add__(self, other):
        return Expr.binary(" + ", [self, other])

    def __radd__(self, other):
        return Expr.binary(" + ", [other, self])

    def __and__(self, other):
        return Expr.binary(" AND ", [self, other])

    def __eq__(self, other):
        return Expr.binary(" = ", [self, other])

    def execute(self, conn: sqlite3.Connection):
        logger.debug(f"Running:\n{str(self)}")
        e = self.expr
        if not e.rstrip().endswith(";"):
            e += ";"
        return conn.execute(e, tuple(self.values))

    def append(self, *values) -> "Expr":
        return Expr.binary(" ", *values)


class Column(Field, Expr):
    primary: bool

    @property
    def expr(self) -> str:
        return self.name

    @property
    def schema(self):
        s = f"{self.name} {get_sqlite_storage_type(self.type)}"
        if self.primary:
            s += " PRIMARY KEY"
        return s


def get_sqlite_storage_type(T: Type) -> str:
    def core(T: Type):
        if T == int:
            return "INTEGER"
        elif T == float:
            return "REAL"
        elif T == str:
            return "TEXT"
        elif T == datetime:
            return "TEXT"
        else:
            return ""

    X = as_optional(T)
    if X is None:
        return core(T) + " NOT NULL"
    else:
        return core(T)


def columns(x) -> Iterator[Column]:
    for f in fields(x):
        assert isinstance(f, Column)
        yield f


def col() -> Any:
    # raise NotImplementedError()
    return field()


class Connection(Current):
    conn: sqlite3.Connection

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn


@contextmanager
def transaction():
    conn = Connection.current().conn
    with conn:
        yield conn


class Schema:
    def create_table(self: T, name: str, clobber=False) -> "Table[T]":
        # [todo] run a sql query here.
        # if clobber is true then if the table exists but the schema has changed we
        # just brutally wipe everything.

        with transaction() as conn:
            fields = ",\n  ".join(c.schema for c in columns(self))
            conn.execute(f"CREATE TABLE IF NOT EXISTS {name} (\n  {fields}\n);")

        return Table(name)

    def __init_subclass__(cls):
        assert is_dataclass(cls)
        for field in fields(cls):
            assert isinstance(field, Column)
            setattr(cls, field.name, field)


if __name__ == "__main__":

    @dataclass
    class Blob(Schema):
        digest: str = col()
        length: int = col()
        label: Optional[str] = col()
