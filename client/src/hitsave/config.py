import tempfile
import os
import os.path

""" This module is responsible for loading all of the environment based config options.

[todo]: you want to get these args from
- environment variables
- cli arguments
- `.config/hitsave.toml` or similar
"""

# [todo] should be XDG_CACHE_DIR
tmp_dir = os.environ.get("HITSAVE_DIR", tempfile.gettempdir())

# The path to the file with the local cache.
local_store_path = os.path.join(tmp_dir, "hitsave.diskcache")

# URL of the hitsave API endpoint.
cloud_url = os.environ.get("HITSAVE_URL", "https://api.hitsave.io")
cloud_api_key = os.environ.get("HITSAVE_API_KEY", None)
