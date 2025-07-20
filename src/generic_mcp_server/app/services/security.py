import httpx
from fastapi import Request
from typing import Dict, Any, Union

def apply_auth(
    outgoing_request: httpx.Request,
    auth_scheme: Dict,
    auth_provider: Union[Request, Dict[str, Any]]
) -> httpx.Request:
    """
    Applies auth by taking a credential from the auth_provider and adding
    it to the outgoing_request to the downstream service.
    """
    if not auth_scheme:
        return outgoing_request

    headers = {}
    if isinstance(auth_provider, Request):
        headers = auth_provider.headers
    elif isinstance(auth_provider, dict):
        # For stdio mode, auth headers are passed in a special key
        headers = auth_provider.get('__auth_headers__', {})

    scheme_type = auth_scheme.get('type')

    # Handle API Key in header or query
    if scheme_type == 'apiKey':
        key_name = auth_scheme.get('name')
        if not key_name:
            raise ValueError("Auth scheme of type 'apiKey' is missing a 'name'.")

        key_value = headers.get(key_name.lower())
        if not key_value:
            raise ValueError(f"Required auth header/key '{key_name}' not found.")

        if auth_scheme.get('in') == 'header':
            outgoing_request.headers[key_name] = key_value
        elif auth_scheme.get('in') == 'query':
            outgoing_request.url = outgoing_request.url.copy_with(
                params={**outgoing_request.url.params, key_name: key_value}
            )

    # Handle Bearer and Basic auth schemes
    elif scheme_type == 'http' and auth_scheme.get('scheme') in ['bearer', 'basic']:
        auth_header_value = headers.get('authorization')
        if not auth_header_value:
            raise ValueError("Required 'Authorization' header not found for http auth scheme.")
        outgoing_request.headers['Authorization'] = auth_header_value

    else:
        # You could add support for other schemes here
        pass

    return outgoing_request