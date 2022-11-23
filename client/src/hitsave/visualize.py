from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from functools import partial, singledispatch
from itertools import islice
from hitsave.console import logger
from typing import List, Dict, Any
from dataclasses import dataclass
from typing import Optional
from hitsave.blobstore import BlobStore


""" This file contains the 'visualisation encoding' of python values.
These are used to make visualisations that our experiment explorer can show.
The encoding is lossy, and should only be used for showing pretty things to the user.

As well as the basic primitive types, we support the following
- images
- plotly plots
- matplotlib [todo]
- SVG


If we don't know how to encode an object, we simply return a string.


Convention:
- each python class instance includes a `__class__` json field with a string telling you the class name.
- images are stored as blobs on the blob service.
- there is an optional `__kind__` field which gives the visualiser hints about how to view the data.
- visualize on list and dict is is _always_ identity [todo] unit tests for this.

Challenges
- We need a sensible policy when it comes to visualising very large objects

[todo] test on giant binaries, giant numpys etc, make sure it doesn't make an unboundedly large json.

"""


class Kind(Enum):
    object = 0
    """ Normal python object. """
    html = 1
    """ Render this as some html. """
    image = 2
    """ An image to render. """
    plotly = 3
    """ A plotly plot json object to render with the plotly library. """
    blob = 4
    """ A blob is a reference to a blob that contains json that should be visualised in the same way """
    opaque = 5
    # [todo] file


@dataclass
class Html:
    """Makes a thing that will be visualised as an html element.

    You can use this to make simple custom visualisations for your data.
    `visualize` will be called recursively on the 'children' objects.
    """

    tag: str
    attrs: Dict[str, Any]
    children: List[Any]

    def __visualize__(self):
        return {
            "__kind__": Kind.html.name,
            "tag": self.tag,
            "attrs": self.attrs,
            "children": self.children,
        }


@singledispatch
def visualize(item, rec):
    """Convert an item to a visualisable json-like object.

    You do not need to use this recursively
    The output should be a Dict[str, _], a List[_] or a json-compatible scalar value.
    In the case of a composite output, visualise will be run on the child objects.

    """

    if hasattr(item, "__visualize__"):
        # [todo] I'm not sure what the convention is with defining new dunders.
        return item.__visualize__()
    if is_dataclass(item):
        o = {"__class__": item.__class__.__qualname__}
        for field in fields(item):
            # another possibility is asdict, but that is recursive
            o[field.name] = rec(getattr(item, field.name))
        return o
    # [todo] named tuples
    logger.debug(f"Don't know how to visualise {type(item)}")
    return opaque(item)


def visualize_rec(item, max_depth=None):
    if max_depth == 0:
        return opaque(item)
    r = partial(visualize_rec, max_depth=max_depth and max_depth - 1)
    x = visualize(item, r)
    return x


def ident(x, rec):
    return x


def init(x, rec=None):
    return {"__class__": type(x).__name__}


def opaque(x, rec=None):
    t = type(x)
    s = repr(x)
    if len(s) > 256:
        s = s[:256] + "..."
    return {"__class__": t.__name__, "__kind__": Kind.opaque.name, "repr": s}


visualize.register(int)(ident)
visualize.register(float)(ident)
visualize.register(bool)(ident)
# [todo] maybe if it's too long then truncate?
visualize.register(str)(ident)
visualize.register(bytes)(init)
visualize.register(type(None))(ident)


@visualize.register(type(...))
def _vis_ellipsis(x, rec):
    return "..."


@visualize.register(complex)
def _viz_complex(x: complex, rec):
    return {**init(x), "real": x.real, "imag": x.imag}


@visualize.register(Enum)
def _viz_enum(x: Enum, rec):
    o = init(x)
    o["name"] = x.name
    o["value"] = rec(x.value)
    return o


@visualize.register(type)
def _viz_type(x: type, rec):
    return getattr(x, "__name__", repr(x))


MAX_VISUALIZE_SIZE = 10


@visualize.register(tuple)
@visualize.register(list)
def _viz_list(x: list, rec):
    if len(x) > MAX_VISUALIZE_SIZE:
        values = [rec(v) for v in x[:MAX_VISUALIZE_SIZE]]
        """ [todo] need a better way to do this. eg we want to report the number of elements and the type of each element.
        It's all about asking what the user would expect to see and what they would be reasonably ok with not seeing.
        The user also needs to be able to override visualisation behaviour. Eg maybe they want to see the list of elements as a cool graph.

        By default the visualisation should be quite compact.
        """
        return {**init(x), "truncated": len(x), "values": values}
    else:
        return {**init(x), "truncated": False, "values": list(map(rec, x))}


@visualize.register(dict)
def _viz_dict(x: dict, rec):
    if len(x) > MAX_VISUALIZE_SIZE:
        o = {k: rec(x[k]) for k in islice(list(x.keys()), 0, MAX_VISUALIZE_SIZE)}
        return {**init(x), "values": o, "truncated": len(x)}
    else:
        return {
            **init(x),
            "values": {k: rec(v) for k, v in x.items()},
            "truncated": False,
        }


@dataclass
class Svg:
    """Use this class to create svg images that can be visualised on the HitSave dashboard."""

    svg: str
    label: Optional[str] = field(default=None)

    def __visualize__(self):
        blobstore = BlobStore.current()

        s = self.svg
        if not s.startswith("<?xml"):
            s = '<?xml version="1.0" encoding="UTF-8" standalone="no"?>' + s
        info = blobstore.add_blob(
            s.encode("utf-8"), label=self.label or "visualisation svg"
        )
        blobstore.push_blob(info.digest)
        return {
            **init(self),
            "__kind__": Kind.image.value,
            "mime_type": "image/svg+xml",
            "digest": info.digest,
            "content_length": info.content_length,
        }


try:
    import plotly.io
    import plotly.graph_objects as go

    @visualize.register(go.Figure)
    def _viz_plotly(fig: go.Figure, rec):
        return {
            **init(fig),
            "__kind__": Kind.plotly.name,
            "value": plotly.io.to_json(fig),
        }

except ModuleNotFoundError:
    pass

try:
    import numpy as np

    @visualize.register(np.ndarray)
    def _viz_nparray(x: np.ndarray, rec):
        # [todo] make fancy
        return repr(x)[:256]

except ModuleNotFoundError:
    pass

try:
    # [todo] in these, we need to also assert that it is the PyPI module
    # and not a user-module with the same name.
    import chess.svg
    from chess import Board

    @visualize.register(Board)
    def _viz_board(board: Board):
        return Svg(chess.svg.board(board))

except ModuleNotFoundError:
    pass
