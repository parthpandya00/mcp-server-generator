import os
import json
from functools import lru_cache


@lru_cache()
def get_mcp_config():
    """
    Loads the master configuration from either:
    1. MCP_CONFIG_FILE environment variable (path to JSON file)
    2. MCP_CONFIG environment variable (inline JSON string) - for backward compatibility
    """
    # Try to load from file first (preferred method)
    config_file_path = os.getenv("MCP_CONFIG_FILE")
    if config_file_path and os.path.exists(config_file_path):
        try:
            with open(config_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to load MCP config from file '{config_file_path}': {e}")

    # Fall back to inline JSON for backward compatibility
    config_str = os.getenv("MCP_CONFIG")
    if config_str:
        try:
            return json.loads(config_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse MCP_CONFIG environment variable: {e}")

    # Neither method worked
    if config_file_path:
        raise ValueError(f"MCP_CONFIG_FILE specified ('{config_file_path}') but file does not exist.")
    else:
        raise ValueError("Neither MCP_CONFIG_FILE nor MCP_CONFIG environment variable is set.")