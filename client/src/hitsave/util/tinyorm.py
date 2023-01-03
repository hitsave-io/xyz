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
from enum import Enum
from functools import singledispatch
import json
import logging
from typing import Callable, List, Literal, Union
from dataclasses import MISSING, fields, field, Field
from contextlib import contextmanager
import datetime
import sqlite3
import uuid
from hitsave.util.current import Current
from hitsave.util.type_helpers import as_optional, is_optional
from hitsave.util.ofdict import TypedJsonDecoder, ofdict, MyJsonEncoder
from hitsave.session import Session
from typing import Any, Generic, Iterable, Iterator, Optional, Type, TypeVar, overload
from hitsave.util.dispatch import classdispatch

logger = logging.getLogger("tinyorm")

T = TypeVar("T", bound="Schema")
S = TypeVar("S")
R = TypeVar("R")


class AdaptationError(TypeError):
    pass


@singledispatch
def adapt(o):
    """Turn it into a SQLite-compatible type."""
    if isinstance(o, (str, int, bytes, float)):
        return o
    if isinstance(o, Enum):
        return o.value
    if o is None:
        return None
    raise AdaptationError(o)


@classdispatch
def restore(X, x):
    """Convert the SQLite type to the python type."""
    # [todo] abstract this out into an adapter pattern. adapt(x, protocol = X)
    if isinstance(x, X):
        return x
    Y = as_optional(X)
    if Y is not None:
        if x is None:
            return x
        else:
            return restore(Y, x)
    if issubclass(X, Enum):
        return X(x)
    if X is bool:
        return bool(x)
    raise NotImplementedError(f"Unsupported target type {X}")


adapt.register(datetime.datetime)(lambda o: o.isoformat())
restore.register(datetime.datetime)(lambda T, t: datetime.datetime.fromisoformat(t))
adapt.register(uuid.UUID)(lambda u: u.bytes)
restore.register(uuid.UUID)(lambda T, b: uuid.UUID(bytes=b))


class UpdateKind(Enum):
    Abort = "ABORT"
    Fail = "FAIL"
    Ignore = "IGNORE"
    Replace = "REPLACE"
    Rollback = "ROLLBACK"


class OrderKind(Enum):
    Ascending = "ASC"
    Descending = "DESC"


WhereClause = Union[bool, dict]


def where_to_expr(where: WhereClause):
    if where is True:
        return Expr.empty


class Table(Generic[T]):
    schema: Type[T]

    def __init__(self, name: str, schema: Type[T]):
        # [todo] properly validate name is not an injection attack.
        if any(x in name for x in "; "):
            raise ValueError(
                f"Name {repr(name)} should not contain spaces or semicolons."
            )
        self.name = name
        self.schema = schema

    def __len__(self):
        with transaction() as conn:
            c = conn.execute(f"SELECT COUNT(*) FROM {self.name}")
            return c.fetchone()[0]

    def drop(self):
        """Drops the table.

        Note that once this is called subsequent queries to the table will error."""
        with transaction() as conn:
            conn.execute(f"DROP TABLE {self.name};")

    def as_column(self, item: Union["Column", str]) -> "Column":
        if isinstance(item, Column):
            return item
        else:
            assert isinstance(item, str)
            return Column(self.schema.__dataclass_fields__.get(item))  # type: ignore

    @property
    def exists(self):
        """Returns true if the table exists on the given sqlite connection.

        This returns false when you have dropped the table."""

        with transaction() as conn:
            cur = conn.execute(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.name}';"
            )
            return bool(cur.fetchone())

    def _mk_where_clause(self, where: WhereClause) -> "Expr":
        if where is True:
            return Expr.empty()
        if isinstance(where, dict):
            e = [self.as_column(k) == v for k, v in where.items()]
            e = Expr.binary("AND", e)
        else:
            assert isinstance(where, Expr)
            e = where
        return Expr("WHERE ?", [e])

    @overload
    def select(
        self,
        *,
        where: WhereClause = True,
        order_by: Optional[Any] = None,
        descending=False,
        limit: Optional[int] = None,
    ) -> Iterator[T]:
        ...

    @overload
    def select(
        self,
        *,
        where: WhereClause = True,
        select: S,
        order_by: Optional[Any] = None,
        descending=False,
        limit: Optional[int] = None,
    ) -> Iterator[S]:
        ...

    def select(self, *, where=True, select=None, order_by: Optional[Any] = None, descending=False, limit: Optional[int] = None):  # type: ignore
        p = Pattern(select) if select is not None else self.schema.pattern()
        query = Expr(f"SELECT ?\nFROM {self.name} ", [p.to_expr()])
        if where is not True:
            query = Expr("?\n?", [query, self._mk_where_clause(where)])
        if order_by is not None:
            asc = "DESC" if descending else "ASC"
            query = Expr(f"?\nORDER BY ? {asc}", [query, order_by])
        if limit is not None:
            query = Expr(f"?\nLIMIT {limit}", [query])
        with transaction() as conn:
            xs = query.execute(conn)
            return map(p.outfn, xs)

    @overload
    def select_one(
        self,
        *,
        where: WhereClause = True,
        select: S,
        order_by: Optional[Any] = None,
        descending=False,
    ) -> Optional[S]:
        ...

    @overload
    def select_one(
        self,
        *,
        where: WhereClause = True,
        order_by: Optional[Any] = None,
        descending=False,
    ) -> Optional[T]:
        ...

    def select_one(
        self,
        *,
        where: WhereClause = True,
        select=None,
        order_by: Optional[Any] = None,
        descending=False,
    ):
        return next(
            self.select(
                where=where,
                select=select,
                limit=1,
                order_by=order_by,
                descending=descending,
            ),
            None,
        )

    @overload
    def update(
        self, update_dict, /, *, where: bool = True, returning: S
    ) -> Iterator[S]:
        ...

    @overload
    def update(self, update_dict, /, *, where: bool = True) -> int:
        """Run an UPDATE query on the object. Returns the number of records that were updated."""
        ...

    def update(self, update_dict, /, where=True, returning=None, kind: Optional[UpdateKind] = None):  # type: ignore
        def mk_setter(key, value) -> "Expr":
            assert isinstance(key, Column)  # [todo] strings for column names are ok too
            return Expr(f"{key.name} = ?", [value])

        setters = Expr.binary(", ", [mk_setter(k, v) for k, v in update_dict.items()])
        t = "UPDATE"
        if kind is not None:
            t += " " + kind.value
        query = Expr(f"{t} {self.name} SET ? ", [setters])
        if where is not True:
            assert isinstance(where, Expr)
            query = Expr("?\nWHERE ?", [query, where])
        if returning is not None:
            p = Pattern(returning)
            query = Expr("?\nRETURNING ?", [query, p.to_expr()])
            with transaction() as conn:
                xs = query.execute(conn)
                return map(p.outfn, xs)
        else:
            with transaction() as conn:
                cur = query.execute(conn)
                i = cur.execute("SELECT changes();").fetchone()[0]
                return i

    def delete(self, where: WhereClause):
        assert isinstance(where, Expr)
        q = Expr(f"DELETE FROM {self.name} \nWHERE ?", [where])
        with transaction() as conn:
            q.execute(conn)

    @overload
    def insert_one(self, item: T, *, exist_ok=False) -> None:
        ...

    @overload
    def insert_one(self, item: T, *, returning: S, exist_ok=False) -> S:
        ...

    def insert_one(self, item: T, *, returning=None, exist_ok=False):
        assert isinstance(item, self.schema)
        if returning is not None:
            r = self.insert_many([item], returning, exist_ok=exist_ok)
            return next(iter(r))
        else:
            self.insert_many(items=[item], returning=returning, exist_ok=exist_ok)

    @overload
    def insert_many(self, items: Iterable[T], exist_ok=False) -> None:
        ...

    @overload
    def insert_many(
        self, items: Iterable[T], returning: S, exist_ok=False
    ) -> Iterable[S]:
        ...

    def insert_many(self, items: Iterable[T], returning=None, exist_ok=False):  # type: ignore
        items = list(items)
        assert all(isinstance(x, self.schema) for x in items)
        cs = list(columns(self.schema))
        qfs = ", ".join(c.name for c in cs)
        qqs = ", ".join("?" for _ in cs)
        caveat = "OR IGNORE" if exist_ok else ""
        q = f"INSERT {caveat} INTO {self.name} ({qfs}) VALUES ({qqs}) "
        if returning is not None:

            p = Pattern(returning)
            rq = Expr("RETURNING ? ;", [p.to_expr()])
            vs = [
                tuple(
                    [c.adapt(getattr(item, c.name)) for c in cs]
                    + list(map(adapt, rq.values))
                )
                for item in items
            ]
            q = q + rq.template
            with transaction() as conn:
                # [note] RETURNING keyword is not supported for executemany()
                return [p.outfn(conn.execute(q, v).fetchone()) for v in vs]
        else:
            q += ";"
            with transaction() as conn:
                vs = [[adapt(getattr(item, c.name)) for c in cs] for item in items]
                logger.debug(f"Running {len(vs)}:\n{q}")
                conn.executemany(q, vs)
            return


class Pattern(Generic[S]):
    """A list of Exprs and a function sending these exprs to a python value."""

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

    @overload
    def __init__(self, obj: "Column"):
        ...

    def __init__(self, obj: S, outfn=None):  # type: ignore
        if isinstance(obj, list) and isinstance(outfn, Callable):
            assert all(isinstance(x, Expr) for x in obj)
            self.items = obj
            self.outfn = outfn
            return
        elif isinstance(obj, Pattern):
            self.items = obj.items
            self.outfn = obj.outfn
            return
        elif isinstance(obj, Column):
            self.items = [Expr(obj)]
            self.outfn = lambda x: obj.restore(x[0])  # type: ignore
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

    def map(self, fn: Callable[[S], R]) -> "Pattern[R]":
        def comp(x):
            return fn(self.outfn(x))

        return Pattern(self.items, comp)

    def to_expr(self) -> "Expr":
        return Expr.binary(", ", self.items)


class Expr:
    """A sqlite expression. That is, it's a template string full of '?'s and a value for each '?'.

    Any user-provided data should be represented as a '?' with an item in `values` to prevent injection attacks.
    However we don't add any checks for this.
    """

    template: str
    values: List[Any]

    @classmethod
    def const(cls, template: str):
        return Expr(template, [])

    @classmethod
    def empty(cls):
        return Expr("", [])

    @overload
    def __init__(self, obj: "Expr"):
        """Creates a new Expr with the same values as the given one."""
        ...

    @overload
    def __init__(self, obj: "Column"):
        """Create an expression from a column in a table."""
        ...

    @overload
    def __init__(self, obj: str, values: list):
        """Create an expression from the given '?'-bearing template string, where each '?' is replaced with the python value given in ``values``."""
        ...

    @overload
    def __init__(self, obj: Union[str, int, bytes]):
        """Create a new constant expression with the given value."""
        ...

    def __init__(self, obj, values: Optional[list] = None):
        if isinstance(obj, Expr):
            assert values is None
            self.template = obj.template
            self.values = obj.values
        elif isinstance(obj, Column):
            assert values is None
            self.template = obj.name
            self.values = []
        elif isinstance(obj, str) and values is not None:
            [head, *tail] = obj.split("?")
            assert len(tail) == len(values)
            self.template = head
            self.values = []
            for c, p in zip(map(Expr, values), tail):
                self.template += c.template
                self.values.extend(c.values)
                self.template += p
        elif values is None:
            self.template = " ? "
            self.values = [obj]
        else:
            raise ValueError(f"Don't know how to make expression from {repr(obj)}.")

    def __repr__(self):
        return f"Expr({repr(self.template)}, {repr(self.values)})"

    def __str__(self):
        [x, *xs] = self.template.split("?")
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

    # [todo] all the other operators.

    def execute(self, conn: sqlite3.Connection):
        logger.info(f"Running:\n{str(self)}")
        e = self.template
        if not e.rstrip().endswith(";"):
            e += ";"
        return conn.execute(e, tuple(map(adapt, self.values)))

    def append(self, *values) -> "Expr":
        return Expr.binary(" ", [self, *values])


class Column(Expr):
    field: Field

    @property
    def name(self) -> str:
        return self.field.name

    @property
    def type(self) -> Type:
        return self.field.type

    @property
    def primary(self) -> bool:
        """Is it a primary key?"""
        return self.field.metadata.get("primary", False)

    def __init__(self, f: Field):
        self.field = f

    @property
    def encoding(self) -> Optional["Encoding"]:
        return self.field.metadata.get("encoding")

    def adapt(self, value):
        """Adapt a python value to the sql equivalent."""
        # [todo] replace with adapter pattern
        enc = self.encoding
        if enc is None:
            return adapt(value)
        if enc == "json":
            return MyJsonEncoder().encode(value)
        if enc == "str":
            return str(value)
        if isinstance(enc, tuple):
            enc, _ = enc
            return enc(value)
        else:
            raise NotImplementedError(f"unknown encoder {repr(enc)}")

    def restore(self, sql_value):
        # [todo] replace with adapter pattern.
        enc = self.encoding
        if enc is None:
            return restore(self.type, sql_value)
        elif enc == "json":
            return TypedJsonDecoder(self.type).decode(sql_value)
        elif enc == "str":
            assert isinstance(sql_value, str)
            return self.type.of_str(sql_value)
        elif isinstance(enc, tuple):
            _, dec = enc
            return dec(self.type, sql_value)
        else:
            raise NotImplementedError(f"unknown decoder {repr(enc)}")

    @property
    def template(self) -> str:
        """Convert to an Expr template."""
        return self.name

    @property
    def values(self) -> List[Any]:
        """Convert to Expr values."""
        return []

    @property
    def schema(self):
        s = f"{self.name} {get_sqlite_storage_type(self.type)}"
        return s

    def __repr__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)

    def pattern(self):
        return Pattern([Expr(self.name, [])], lambda x: self.restore(x[0]))


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
        elif T == uuid.UUID:
            return "BLOB"
        else:
            return ""

    X = as_optional(T)
    if X is None:
        return core(T) + " NOT NULL"
    else:
        return core(T)


def columns(x) -> Iterator[Column]:
    if isinstance(x, Table):
        return columns(x.schema)
    return map(Column, fields(x))


Encoding = Union[
    Literal["json"], Literal["str"], tuple[Callable, Callable], Literal["flatten"]
]


def col(
    primary=False,
    metadata={},
    encoding: Optional[Encoding] = None,
    default: Any = MISSING,
    default_factory: Union[Callable[[], Any], Literal[MISSING]] = MISSING,
    **kwargs,
) -> Any:
    if default is not MISSING:
        if default_factory is not MISSING:
            raise ValueError("Cannot set both default and default_factory.")
        default_factory = lambda: default
    return field(
        metadata={**metadata, "primary": primary, "encoding": encoding},
        default_factory=default_factory,
        **kwargs,
    )


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
    def __getattr__(cls, key):
        # [todo] instead of this, we should ``setattr(field.name, Column(field))`` for each
        # field on the cls. The problem is you have to do this after the @dataclass function has run.
        # probably do this with dataclass_transform
        if key.startswith("__"):
            raise AttributeError()
        field = cls.__dataclass_fields__.get(key, None)
        if field is None:
            raise AttributeError()
        return Column(field)


class Schema(metaclass=SchemaMeta):
    @classmethod
    def create_table(cls: Type[T], name: str, clobber=False) -> "Table[T]":
        # [todo] run a sql query here.
        # if clobber is true then if the table exists but the schema has changed we
        # just brutally wipe everything.
        # [todo] validate column names and table name.

        with transaction() as conn:
            fields = [c.schema for c in columns(cls)]
            if not any(c.primary for c in columns(cls)):
                raise TypeError(
                    f"At least one of the fields in {cls.__name__} should be labelled as primary: `= col(primary = True)`"
                )
            ks = ", ".join([c.name for c in columns(cls) if c.primary])
            fields.append(f"PRIMARY KEY ({ks})")
            fields = ",\n  ".join(fields)
            q = f"CREATE TABLE IF NOT EXISTS {name} (\n  {fields}\n);"
            logger.info(f"Running:\n{q}")
            conn.execute(q)

        return Table(name, schema=cls)

    @classmethod
    def pattern(cls: Type[T]) -> Pattern[T]:
        cs = list(columns(cls))

        def blam(d) -> T:
            return cls(**d)

        return Pattern({c.name: c.pattern() for c in cs}).map(blam)
