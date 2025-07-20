import pytest
import json
import respx
from httpx import Response
from fastapi.testclient import TestClient

@pytest.fixture
def client_factory():
    """
    Returns a factory function that can create a new TestClient instance.
    """
    def _create_client():
        # Import the app here, inside the factory, to ensure it's loaded fresh.
        from app.main import app
        return TestClient(app)
    return _create_client

@respx.mock
def test_rpc_endpoint_success(client_factory, monkeypatch):
    """
    Tests a successful call to the /rpc endpoint.
    """
    # 1. Setup: Define the SPECIFIC MCP logic for this test.
    mcp_config = {
        "operations": {
            "get_user": {
                "auth_scheme_name": "api_key_auth",
                "source_config": {
                    "type": "http",
                    "steps": [{"step_id": "s1", "method": "get", "url": "http://downstream.com/api/user"}]
                }
            }
        },
        "security_schemes": {
            "api_key_auth": {"type": "apiKey", "in": "header", "name": "X-API-Key"}
        }
    }
    # Set the environment variable BEFORE creating the client.
    monkeypatch.setenv("MCP_CONFIG", json.dumps(mcp_config))

    # Mock the downstream API call
    downstream_route = respx.get("http://downstream.com/api/user").mock(
        return_value=Response(200, json={"id": 1, "name": "Alice"})
    )

    # 2. Execute: Create the client AFTER setting the config, then make the request.
    client = client_factory()
    response = client.post(
        "/rpc",
        headers={"X-API-Key": "my-secret-key"},
        json={"jsonrpc": "2.0", "method": "get_user", "params": {}, "id": 1}
    )

    # 3. Assert
    assert response.status_code == 200
    assert response.json()["result"] == {"id": 1, "name": "Alice"}
    assert downstream_route.called