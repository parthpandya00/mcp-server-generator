import os
import json
from functools import lru_cache

@lru_cache()
def get_mcp_config():
    """Loads the master configuration from the environment variable."""
    config_str = os.getenv("MCP_CONFIG")
    if not config_str:
        raise ValueError("MCP_CONFIG environment variable not set or empty.")
    return json.loads(config_str)
