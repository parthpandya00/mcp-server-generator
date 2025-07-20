import json
import os
from jinja2 import Environment, FileSystemLoader
from typing import Dict, Any

from .models import GeneratorRequest

# --- CORRECTED TEMPLATE PATH ---
# This makes the path absolute to this file's location, which is more robust.
TEMPLATE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


# --- END CORRECTION ---

def generate_dockerfile(request: GeneratorRequest) -> bytes:
    """
    Generates a Dockerfile for the generic MCP server.
    """
    spec = request.openapi_spec

    mcp_config = {"operations": {}, "security_schemes": {}}
    paths = spec.get('paths', {})
    mcp_config["security_schemes"] = spec.get('components', {}).get('securitySchemes', {})

    for path, path_item in paths.items():
        for method, operation_obj in path_item.items():
            if 'x-mcp-source' in operation_obj and 'operationId' in operation_obj:
                op_id = operation_obj['operationId']
                auth_conf = operation_obj.get('security', [])
                auth_scheme_name = list(auth_conf[0].keys())[0] if auth_conf else None

                mcp_config["operations"][op_id] = {
                    "path": operation_obj.get('path', path),
                    "method": operation_obj.get('method', method),
                    "source_config": operation_obj['x-mcp-source'],
                    "auth_scheme_name": auth_scheme_name,
                    "parameters": operation_obj.get('parameters', [])
                }

    template_context = {
        "mcp_config_json": json.dumps(mcp_config),
        "direct_secrets": request.direct_credentials,
        "auth_source_config": request.auth_source_config
    }

    dockerfile_template = env.get_template('Dockerfile.j2')
    dockerfile_content = dockerfile_template.render(template_context)

    return dockerfile_content.encode('utf-8')