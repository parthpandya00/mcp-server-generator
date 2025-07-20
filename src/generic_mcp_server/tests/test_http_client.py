import pytest
import respx
import httpx
import json  # <-- Import json
from httpx import Response
from unittest.mock import MagicMock
from fastapi import Request
from app.services.http_client import execute_http_steps

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_auth_provider():
    provider = MagicMock(spec=Request)
    provider.headers = {
        'x-api-key': 'test-key',
        'authorization': 'Bearer test-token'
    }
    return provider


@respx.mock
async def test_execute_single_step(mock_auth_provider):
    respx.get("http://test.com/step1").mock(return_value=Response(200, json={"data": "success"}))
    steps = [{"step_id": "s1", "method": "get", "url": "http://test.com/step1"}]
    auth_scheme = {'type': 'apiKey', 'in': 'header', 'name': 'x-api-key'}
    result = await execute_http_steps(steps, auth_scheme, {}, mock_auth_provider)
    assert result == {"data": "success"}


@respx.mock
async def test_execute_multi_step_with_templating(mock_auth_provider):
    respx.get("http://test.com/orders").mock(return_value=Response(200, json={"order_id": 123}))
    respx.get("http://test.com/orders/123/details").mock(return_value=Response(200, json={"details": "item is new"}))
    steps = [
        {"step_id": "fetch_order", "method": "get", "url": "http://test.com/orders"},
        {"step_id": "fetch_details", "method": "get", "url": "http://test.com/orders/${fetch_order.order_id}/details"}
    ]
    auth_scheme = {'type': 'http', 'scheme': 'bearer'}
    result = await execute_http_steps(steps, auth_scheme, {}, mock_auth_provider)
    assert result == {"details": "item is new"}


@respx.mock
async def test_execute_http_error_propagates(mock_auth_provider):
    respx.get("http://test.com/broken").mock(return_value=Response(500))
    steps = [{"step_id": "s1", "method": "get", "url": "http://test.com/broken"}]
    auth_scheme = {}
    with pytest.raises(httpx.HTTPStatusError):
        await execute_http_steps(steps, auth_scheme, {}, mock_auth_provider)


@respx.mock
async def test_execute_step_with_body_templating(mock_auth_provider):
    respx.get("http://test.com/user").mock(return_value=Response(200, json={"name": "Alice"}))
    post_mock = respx.post("http://test.com/notify").mock(return_value=Response(200, json={"status": "ok"}))
    steps = [
        {"step_id": "get_user", "method": "get", "url": "http://test.com/user"},
        {
            "step_id": "send_notification", "method": "post",
            "url": "http://test.com/notify", "body": {"message": "Hello, ${get_user.name}"}
        }
    ]
    auth_scheme = {}
    result = await execute_http_steps(steps, auth_scheme, {}, mock_auth_provider)

    # Assert
    assert result == {"status": "ok"}

    # CORRECTED ASSERTION: Parse the JSON and compare dictionaries.
    actual_body = json.loads(post_mock.calls.last.request.content)
    expected_body = {"message": "Hello, Alice"}
    assert actual_body == expected_body
