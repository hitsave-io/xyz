from pathlib import Path
from hitsave.config import Config


def test_config_workspace_dir():
    d = Config.current().workspace_dir
    assert isinstance(d, Path)
    assert d.exists()


def test_config_local_cache_path():
    d = Config.current().local_cache_dir
    assert isinstance(d, Path)
    assert d.exists()
