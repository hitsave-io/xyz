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
from typing import Callable, List, Sequence, Union
from dataclasses import dataclass, is_dataclass, fields, field, Field
from contextlib import contextmanager
from datetime import datetime
import sqlite3
from hitsave.session import Session
from hitsave.util import Current, as_optional
from typing import Any, Generic, Iterable, Iterator, Optional, Type, TypeVar, overload

logger = logging.getLogger("tinyorm")

T = TypeVar("T", bound="Schema")
S = TypeVar("S")
R = TypeVar("R")


class Table(Generic[T]):
    schema: Type[T]

    def __init__(self, name: str, schema: Type[T]):
        self.name = name
        self.schema = schema

    @overload
    def select(self, *, where: bool = True) -> Iterator[T]:
        ...

    @overload
    def select(self, *, where: bool = True, select: S) -> Iterator[S]:
        ...

    def select(self, *, where=True, select=None):  # type: ignore
        p = Pattern(select) if select is not None else self.schema.pattern()
        query = Expr(f"SELECT ? FROM {self.name} ", [p.to_expr()])
        if where is not True:
            assert isinstance(where, Expr)
            query = query.append("WHERE ?", where)
        with transaction() as conn:
            xs = query.execute(conn)
            return map(p.outfn, xs)

    @overload
    def select_one(self, *, where: bool = True, select: S) -> Optional[S]:
        ...

    @overload
    def select_one(self, *, where: bool = True) -> Optional[T]:
        ...

    def select_one(self, *, where=True, select=None):
        return next(self.select(where=where, select=select), None)

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
            return Expr(f"{key.name} = ?", [value])

        setters = Expr.binary(", ", [mk_setter(k, v) for k, v in update_dict.items()])
        query = Expr(f"UPDATE {self.name} SET ? ", [setters])
        if where is not True:
            assert isinstance(where, Expr)
            query = query.append("WHERE", where)
        if returning is not None:
            p = Pattern(returning)
            query = query.append("RETURNING", p.to_expr())
            with transaction() as conn:
                xs = query.execute(conn)
                return map(p.outfn, xs)
        else:
            with transaction() as conn:
                query.execute(conn)

    def insert_one(self, item: T, returning=None):
        if returning is not None:
            return list(self.insert_many([item], returning))[0]
        else:
            return self.insert_many(items=[item], returning=returning)

    def insert_many(self, items: Iterable[T], returning=None):
        cs = list(columns(self.schema))
        qfs = ", ".join(c.name for c in cs)
        qqs = ", ".join("?" for _ in cs)
        q = f"INSERT INTO {self.name} ({qfs}) VALUES ({qqs}) "
        if returning is not None:
            p = Pattern(returning)
            rq = Expr("RETURNING ? ;", [p.to_expr()])
            with transaction() as conn:
                cur = conn.executemany(
                    q + rq.expr,
                    [[getattr(item, c.name) for c in cs] + rq.values for item in items],
                )
                return map(p.outfn, cur)
        else:
            q += ";"
            with transaction() as conn:
                vs = [[getattr(item, c.name) for c in cs] for item in items]
                logger.debug(f"Running {len(vs)}:\n{q}")
                conn.executemany(q, vs)
            return


class Pattern(Generic[S]):
    items: List["Expr"]
    outfn: Callable[[List[Any]], S]

    def __len__(self):
        return len(self.items)

    @overload
    def __init__(self, obj: S):
        ...

    @overload
    def __init__(self, items: List["Expr"], outfn: Callable[[List[Any]], S]):
        ...

    def __init__(self, obj: S, outfn=None):  # type: ignore
        if isinstance(obj, list) and isinstance(outfn, Callable):
            assert all(isinstance(x, Expr) for x in obj)
            self.items = obj
            self.outfn = outfn
            return
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

    def map(self, fn: Callable[[S], R]) -> "Pattern":
        def comp(x):
            return fn(self.outfn(x))

        return Pattern(self.items, comp)

    def to_expr(self) -> "Expr":
        return Expr.binary(", ", self.items)


class Expr:
    """A sqlite expression."""

    expr: str
    values: List[Any]

    @classmethod
    def const(cls, expr: str):
        return Expr(expr, [])

    def __init__(
        self, obj: Union["Expr", "Column", Any], values: Optional[List[Any]] = None
    ):
        if isinstance(obj, Expr):
            assert values is None
            self.expr = obj.expr
            self.values = obj.values
        elif isinstance(obj, Column):
            assert values is None
            self.expr = obj.name
            self.values = []
        elif isinstance(obj, str) and values is not None:
            [head, *tail] = obj.split("?")
            assert len(tail) == len(values)
            self.expr = head
            self.values = []
            for c, p in zip(map(Expr, values), tail):
                self.expr += c.expr
                self.values.extend(c.values)
                self.expr += p
        elif values is None:
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
        return Expr(op.join(" ? " for _ in args), args)

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
        return Expr.binary(" ", list(values))


class Column(Expr):
    field: Field

    @property
    def name(self):
        return self.field.name

    @property
    def type(self):
        return self.field.type

    @property
    def primary(self):
        return self.field.metadata.get("primary", False)

    def __init__(self, f: Field):
        self.field = f

    @property
    def expr(self) -> str:
        return self.name

    @property
    def values(self) -> List[Any]:
        return []

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
            return "timestamp"
        else:
            return ""

    X = as_optional(T)
    if X is None:
        return core(T) + " NOT NULL"
    else:
        return core(T)


def columns(x) -> Iterator[Column]:
    return map(Column, fields(x))


def col(primary=False) -> Any:
    # raise NotImplementedError()
    return field(metadata={"primary": primary})


class Connection(Current):
    conn: sqlite3.Connection

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    @classmethod
    def default(cls):
        # [todo] remove dependency on session
        return Connection(Session.current().local_db)


@contextmanager
def transaction():
    conn = Connection.current().conn
    with conn:
        yield conn


class SchemaMeta(type):
    def __getattr__(self, key):
        if key.startswith("__"):
            raise AttributeError()
        fields = self.__dataclass_fields__
        field = fields.get(key)
        return Column(field)


class Schema(metaclass=SchemaMeta):
    @classmethod
    def create_table(cls: Type[T], name: str, clobber=False) -> "Table[T]":
        # [todo] run a sql query here.
        # if clobber is true then if the table exists but the schema has changed we
        # just brutally wipe everything.

        with transaction() as conn:
            fields = ",\n  ".join(c.schema for c in columns(cls))
            q = f"CREATE TABLE IF NOT EXISTS {name} (\n  {fields}\n);"
            logger.debug(f"Running:\n{q}")
            conn.execute(q)

        return Table(name, schema=cls)

    @classmethod
    def pattern(cls: Type[T]) -> Pattern[T]:
        cs = list(columns(cls))
        qs = ", ".join(c.name for c in cs)

        def blam(xs):
            d = {c.name: x for c, x in zip(xs, cs)}
            return cls(**d)  # type: ignore

        return Pattern([Expr(c.name, []) for c in cs], blam)  # type: ignore


if __name__ == "__main__":

    @dataclass
    class Blob(Schema):
        digest: str = col()
        length: int = col()
        label: Optional[str] = col()
