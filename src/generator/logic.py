import json
import os
from jinja2 import Environment, FileSystemLoader
from typing import Dict, Any, Tuple

from .models import GeneratorRequest

# --- CORRECTED TEMPLATE PATH ---
# This makes the path absolute to this file's location, which is more robust.
TEMPLATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


def generate_mcp_files(request: GeneratorRequest) -> Tuple[bytes, bytes]:
    """
    Generates both a Dockerfile and mcp_config.json for the generic MCP server.

    Returns:
        Tuple[bytes, bytes]: (dockerfile_content, config_content)
    """
    spec = request.openapi_spec

    mcp_config = {
        "operations": {},
        "security_schemes": {},
        "components": {}
    }

    paths = spec.get('paths', {})

    # Extract security schemes
    mcp_config["security_schemes"] = spec.get('components', {}).get('securitySchemes', {})

    # Extract all component schemas (crucial for request body validation)
    mcp_config["components"] = {
        "schemas": spec.get('components', {}).get('schemas', {})
    }

    for path, path_item in paths.items():
        for method, operation_obj in path_item.items():
            if 'x-mcp-source' in operation_obj and 'operationId' in operation_obj:
                op_id = operation_obj['operationId']
                auth_conf = operation_obj.get('security', [])
                auth_scheme_name = list(auth_conf[0].keys())[0] if auth_conf else None

                # Build the operation configuration
                operation_config = {
                    "path": path,  # Use the actual path from the paths object
                    "method": method,  # Use the actual method
                    "source_config": operation_obj['x-mcp-source'],
                    "auth_scheme_name": auth_scheme_name,
                    "parameters": operation_obj.get('parameters', [])
                }

                # CRITICAL: Include requestBody information if present
                if 'requestBody' in operation_obj:
                    operation_config["requestBody"] = operation_obj['requestBody']

                mcp_config["operations"][op_id] = operation_config

    # Generate the config file content (ensure proper formatting)
    config_content = json.dumps(mcp_config, indent=2, ensure_ascii=False).encode('utf-8')

    # Generate the Dockerfile
    template_context = {
        "direct_secrets": request.direct_credentials,
        "auth_source_config": request.auth_source_config
    }

    dockerfile_template = env.get_template('Dockerfile.j2')
    dockerfile_content = dockerfile_template.render(template_context).encode('utf-8')

    return dockerfile_content, config_content


# Backward compatibility function
def generate_dockerfile(request: GeneratorRequest) -> bytes:
    """
    Generates a Dockerfile for the generic MCP server.
    This function is kept for backward compatibility.
    """
    dockerfile_content, _ = generate_mcp_files(request)
    return dockerfile_content
