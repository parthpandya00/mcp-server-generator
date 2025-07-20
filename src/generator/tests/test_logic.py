import pytest
import json
import re

from ..logic import generate_dockerfile
from ..models import GeneratorRequest, AuthSourceConfig

def _parse_dockerfile_env(dockerfile_content: str) -> dict:
    envs = {}
    for match in re.finditer(r"^\s*ENV\s+([^\s=]+)\s*(.*)", dockerfile_content, re.MULTILINE):
        key, value = match.groups()
        if value.startswith('='):
            value = value[1:]
        value = value.strip().strip("'\"")
        envs[key] = value
    return envs

def test_generates_basic_dockerfile():
    request = GeneratorRequest(openapi_spec={})
    dockerfile_bytes = generate_dockerfile(request)
    dockerfile_content = dockerfile_bytes.decode('utf-8')
    assert "FROM python:3.11-slim" in dockerfile_content
    assert 'WORKDIR /usr/src/app' in dockerfile_content

def test_generates_correct_mcp_config():
    spec = {
        "paths": {
            "/my-data": {
                "get": {
                    "operationId": "get_my_data",
                    "x-mcp-source": {"type": "http", "steps": []}
                }
            }
        }
    }
    request = GeneratorRequest(openapi_spec=spec)
    dockerfile_bytes = generate_dockerfile(request)
    dockerfile_content = dockerfile_bytes.decode('utf-8')
    envs = _parse_dockerfile_env(dockerfile_content)
    mcp_config = json.loads(envs["MCP_CONFIG"])
    assert "get_my_data" in mcp_config["operations"]

def test_generates_direct_credentials():
    creds = {"MY_API_KEY": "secret123", "DB_PASS": "password"}
    request = GeneratorRequest(openapi_spec={}, direct_credentials=creds)
    dockerfile_bytes = generate_dockerfile(request)
    dockerfile_content = dockerfile_bytes.decode('utf-8')
    envs = _parse_dockerfile_env(dockerfile_content)
    assert envs["MY_API_KEY"] == "secret123"
    assert envs["DB_PASS"] == "password"

def test_generates_vault_config():
    # The stray 's' was here. It has been removed.
    auth_config = AuthSourceConfig(
        vault_address="http://vault:8200",
        vault_token="my-root-token"
    )
    request = GeneratorRequest(openapi_spec={}, auth_source_config=auth_config)
    dockerfile_bytes = generate_dockerfile(request)
    dockerfile_content = dockerfile_bytes.decode('utf-8')
    envs = _parse_dockerfile_env(dockerfile_content)
    assert envs["VAULT_ADDR"] == "http://vault:8200"
    assert envs["VAULT_TOKEN"] == "my-root-token"