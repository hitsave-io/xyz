from collections import defaultdict
import configparser
from pathlib import Path
from typing import Any, Iterable, Dict, Type, TypeVar, Union, overload
import logging
from hitsave.util.ofdict import validate
from hitsave.util.type_helpers import as_optional

""" Code for reading keys from a config file """

T = TypeVar("T")

logger = logging.getLogger("hitsave.util")


def interpret_var_str(t: Type[T], value: str) -> T:
    """Given a string attained from an environment variable, make a best-effort attempt to parse it to an instance of the given type."""
    # [todo] this must be in argparse or something
    if t == str:
        return value  # type: ignore
    if t == int:
        return int(value)  # type: ignore
    if t == bool:
        return value not in ["False", "false", "0", "no"]  # type: ignore
    if t == Path:
        return Path(value)  # type: ignore
    X = as_optional(t)
    if X is not None:
        if value in ["None", "null", "undefined"]:
            return None  # type: ignore
        else:
            return interpret_var_str(X, value)

    raise NotImplementedError(f"Don't know how to interpret {t}")


@overload
def get_config(path: Path, key: str) -> Any:
    ...


@overload
def get_config(path: Path, key: str, type: Type[T]) -> T:
    ...


@overload
def get_config(path: Path, keys: Iterable[str]) -> Dict[str, Any]:
    ...


@overload
def get_config(path: Path, keys_and_types: Dict[str, Type]) -> Dict[str, Any]:
    ...


def get_config(path: Path, keys, type=Any) -> Any:  # type: ignore
    if isinstance(keys, dict):
        return read_keys_from_config_file(path, keys)
    elif isinstance(keys, list):
        return read_keys_from_config_file(path, keys)
    else:
        if not isinstance(keys, str):
            raise ValueError(f"Expected {keys} to be a string.")
        d = read_keys_from_config_file(path, {keys: type})
        return d.get(keys, None)


def read_keys_from_config_file(
    path: Path, keys: Union[Dict[str, Type], Iterable[str]]
) -> Dict[str, Any]:
    if not path.exists():
        return {}
    cfg = configparser.ConfigParser()
    cfg.read(path)
    o = {}
    if isinstance(keys, dict):
        types = keys
        keys = list(keys.keys())
    else:
        types = {}
        keys = list(keys)
    for key in keys:
        v = cfg.get(cfg.default_section, key, fallback=None)
        if v is None:
            continue
        type = types.get(key, Any)
        if not validate(type, v):
            logger.error(
                f"Invalid config value {key}, expected {type} but was {type(v)}"
            )
            continue
        o[key] = v
    return o


def set_config(path: Path, **kvs):
    cfg = configparser.ConfigParser()
    cfg.read(path)
    for k, v in kvs.items():
        if v is None:
            cfg.remove_option(cfg.default_section, k)
        else:
            cfg.set(cfg.default_section, k, v)
    logger.debug(f"Writing to {path}:", kvs)
    with open(path, "w") as fd:
        cfg.write(fd)
