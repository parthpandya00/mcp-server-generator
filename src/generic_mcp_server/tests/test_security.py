import pytest
import httpx
from unittest.mock import MagicMock
from fastapi import Request # <-- Import the real Request class
from app.services.security import apply_auth

# --- Fixtures for reusable test objects ---

@pytest.fixture
def outgoing_request():
    """A clean httpx.Request object for each test."""
    return httpx.Request("GET", "http://downstream-api.com/data")

@pytest.fixture
def mock_fastapi_request():
    """
    A mock FastAPI Request object that correctly identifies as an
    instance of Request.
    """
    # Using spec=Request makes this mock pass `isinstance(mock, Request)` checks.
    request = MagicMock(spec=Request)
    return request

# --- Test Cases ---

def test_apply_auth_api_key_in_header(outgoing_request, mock_fastapi_request):
    # Setup
    mock_fastapi_request.headers = {'x-api-key': 'my-secret-key'}
    auth_scheme = {'type': 'apiKey', 'in': 'header', 'name': 'X-API-Key'}

    # Execute
    final_request = apply_auth(outgoing_request, auth_scheme, mock_fastapi_request)

    # Assert
    assert final_request.headers['X-API-Key'] == 'my-secret-key'

def test_apply_auth_api_key_in_query(outgoing_request, mock_fastapi_request):
    # Setup
    mock_fastapi_request.headers = {'x-api-key': 'my-query-key'}
    auth_scheme = {'type': 'apiKey', 'in': 'query', 'name': 'x-api-key'}

    # Execute
    final_request = apply_auth(outgoing_request, auth_scheme, mock_fastapi_request)

    # Assert
    assert final_request.url.params['x-api-key'] == 'my-query-key'

def test_apply_auth_bearer_token(outgoing_request, mock_fastapi_request):
    # Setup
    mock_fastapi_request.headers = {'authorization': 'Bearer my-jwt-token'}
    auth_scheme = {'type': 'http', 'scheme': 'bearer'}

    # Execute
    final_request = apply_auth(outgoing_request, auth_scheme, mock_fastapi_request)

    # Assert
    assert final_request.headers['Authorization'] == 'Bearer my-jwt-token'

def test_apply_auth_basic_auth(outgoing_request, mock_fastapi_request):
    # Setup
    mock_fastapi_request.headers = {'authorization': 'Basic dXNlcjpwYXNz'} # user:pass
    auth_scheme = {'type': 'http', 'scheme': 'basic'}

    # Execute
    final_request = apply_auth(outgoing_request, auth_scheme, mock_fastapi_request)

    # Assert
    assert final_request.headers['Authorization'] == 'Basic dXNlcjpwYXNz'

def test_apply_auth_stdio_provider(outgoing_request):
    """Tests that auth works with a dict provider for stdio mode."""
    # Setup
    auth_provider = {
        '__auth_headers__': {'x-internal-key': 'stdio-key'}
    }
    auth_scheme = {'type': 'apiKey', 'in': 'header', 'name': 'X-Internal-Key'}

    # Execute
    final_request = apply_auth( outgoing_request, auth_scheme, auth_provider)

    # Assert
    assert final_request.headers['X-Internal-Key'] == 'stdio-key'

def test_apply_auth_missing_header_raises_error(outgoing_request, mock_fastapi_request):
    # Setup
    mock_fastapi_request.headers = {} # No auth header
    auth_scheme = {'type': 'http', 'scheme': 'bearer'}

    # Execute & Assert
    with pytest.raises(ValueError, match="Required 'Authorization' header not found"):
        apply_auth(outgoing_request, auth_scheme, mock_fastapi_request)