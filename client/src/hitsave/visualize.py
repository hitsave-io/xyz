from dataclasses import fields, is_dataclass
from enum import Enum
from functools import partial, singledispatch
from itertools import islice
from json import JSONEncoder
from hitsave.console import logger


""" This file contains the 'visualisation encoding' of python values.
These are used to make visualisations that our experiment explorer can show.
The encoding is lossy, and should only be used for showing pretty things to the user.

As well as the basic primitive types, we support the following
- images
- plotly plots [todo]
- matplotlib [todo]
- SVG [todo]


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


def html(tag: str, attrs: dict, children: list):
    """Makes a thing that will be visualised as an html element.

    You can use this to make simple custom visualisations for your data.
    `visualize` will be called recursively on the 'children' objects.
    """
    return {
        "__kind__": Kind.html.name,
        "tag": tag,
        "attrs": attrs,
        "children": children,
    }


@singledispatch
def visualize(item):
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
            o[field.name] = getattr(item, field.name)
        return o
    # [todo] named tuples
    logger.debug(f"Don't know how to visualise {type(item)}")
    return opaque(item)


def visualize_rec(item, max_depth=None):
    if max_depth == 0:
        return opaque(item)
    r = partial(visualize_rec, max_depth=max_depth and max_depth - 1)
    x = visualize(item)
    if isinstance(x, dict):
        return {k: r(v) for k, v in x.items()}
    elif isinstance(x, (list, tuple)):
        return list(map(r, x))
    else:
        return x


class VisualizeEncoder(JSONEncoder):
    def default(self, x):
        v = visualize(x)
        return super().default(v)


def ident(x):
    return x


def init(x):
    return {"__class__": type(x).__name__}


def opaque(x):
    t = type(x)
    s = repr(x)
    return {"__class__": t.__name__, "__kind__": Kind.opaque.name, "repr": s}


visualize.register(int)(ident)
visualize.register(float)(ident)
visualize.register(bool)(ident)
visualize.register(list)(ident)
visualize.register(tuple)(ident)
visualize.register(dict)(ident)
# [todo] maybe if it's too long then truncate?
visualize.register(str)(ident)
visualize.register(bytes)(init)
visualize.register(type(None))(ident)


@visualize.register(type(...))
def _vis_ellipsis(x):
    return "..."


@visualize.register(complex)
def _viz_complex(x: complex):
    return {**init(x), "real": x.real, "imag": x.imag}


@visualize.register(Enum)
def _viz_enum(x: Enum):
    o = init(x)
    o["name"] = x.name
    o["value"] = x.value
    return o


MAX_VISUALIZE_SIZE = 100


@visualize.register(list)
def _viz_list(x: list):
    if len(x) > MAX_VISUALIZE_SIZE:
        t = x[:MAX_VISUALIZE_SIZE]
        """ [todo] need a better way to do this. eg we want to report the number of elements and the type of each element.
        It's all about asking what the user would expect to see and what they would be reasonably ok with not seeing.
        The user also needs to be able to override visualisation behaviour. Eg maybe they want to see the list of elements as a cool graph.

        By default the visualisation should be quite compact.
        """
        t.append({"__truncated__": len(x) - MAX_VISUALIZE_SIZE})
        return t
    else:
        return x


@visualize.register(dict)
def _viz_dict(x: dict):
    if len(x) > MAX_VISUALIZE_SIZE:
        o = {k: x[k] for k in islice(list(x.keys()), 0, MAX_VISUALIZE_SIZE)}
        o["__truncated__"] = len(x) - MAX_VISUALIZE_SIZE
        return o
    else:
        return x


"""
sketch for images:

when the type is PIL.Image or a hitsave.Image:
- save the file as a jpeg or png or whatever as a blob.
- save as {"__kind__" : "image", "__class__" : "PIL.Image", digest: "aaaaa", mimetype : "jpeg" or whatever}
- api.hitsave.io has a `/images` endpoint

 """


try:
    import plotly.io
    import plotly.graph_objects as go

    @visualize.register(go.Figure)
    def _viz_plotly(fig: go.Figure):
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
    def _viz_nparray(x: np.ndarray):
        # [todo] make fancy
        return repr(x)

except ModuleNotFoundError:
    pass
