import json
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from typing import Dict, Any, Union

from .core.config import get_mcp_config
from .services.http_client import execute_http_steps


# --- Models ---
class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Dict[str, Any] = {}
    id: Union[int, str]


# --- Core Dispatch Logic (Unchanged) ---
async def dispatch_mcp_operation(
        operation_id: str,
        params: Dict[str, Any],
        auth_provider: Union[Request, Dict[str, Any]]
):
    mcp_config = get_mcp_config()
    op_config = mcp_config.get("operations", {}).get(operation_id)
    if not op_config:
        raise HTTPException(status_code=404, detail=f"Operation '{operation_id}' not found.")

    security_schemes = mcp_config.get("security_schemes", {})
    auth_scheme_name = op_config.get('auth_scheme_name')
    auth_scheme = security_schemes.get(auth_scheme_name)

    source_config = op_config['source_config']
    source_type = source_config.get('type')

    if source_type == 'http':
        path_params = {p['name']: params.get(p['name']) for p in op_config.get('parameters', []) if p['in'] == 'path'}
        return await execute_http_steps(
            steps=source_config['steps'],
            auth_scheme=auth_scheme,
            path_params=path_params,
            auth_provider=auth_provider
        )
    else:
        raise HTTPException(501, f"Source type '{source_type}' not implemented.")


# --- App Creation (Corrected for Python 3.11) ---
def create_app():
    app = FastAPI(title="Generic Multi-Transport MCP Server")
    mcp_config = get_mcp_config()

    # Dynamically add REST endpoints
    for op_id, op_config in mcp_config.get("operations", {}).items():
        if 'path' in op_config and 'method' in op_config:
            # --- PYTHON 3.11 COMPATIBLE DYNAMIC ENDPOINT CREATION ---
            path_params = [p['name'] for p in op_config.get('parameters', []) if p['in'] == 'path']

            # 1. Build signature string
            signature_params = ["request: Request"] + [f"{p}: str" for p in path_params]
            signature = "async def generated_endpoint({}):".format(', '.join(signature_params))

            # 2. Build params dictionary string
            param_pairs = ['"{p}": {p}'.format(p=p) for p in path_params]
            params_dict_str = "{" + ", ".join(param_pairs) + "}"

            # 3. Build function body string
            body = """
    return await dispatch_mcp_operation(
        operation_id='{op_id}',
        params={params_dict_str},
        auth_provider=request
    )""".format(op_id=op_id, params_dict_str=params_dict_str)

            # 4. Create the function object dynamically
            function_str = signature + "\n    " + body
            local_scope = {}
            exec(function_str, {"dispatch_mcp_operation": dispatch_mcp_operation, "Request": Request}, local_scope)
            endpoint_func = local_scope['generated_endpoint']
            # --- END OF PYTHON 3.11 COMPATIBLE LOGIC ---

            # Register the newly created function
            app.add_api_route(
                path=op_config['path'],
                endpoint=endpoint_func,
                methods=[op_config['method'].upper()],
                tags=["REST Endpoints"],
                operation_id=op_id,
            )

    # Add other transport endpoints
    @app.post("/rpc", tags=["Transports"])
    async def rpc_endpoint(rpc_request: JsonRpcRequest, request: Request):
        # ... (rest of the function is unchanged)
        try:
            result = await dispatch_mcp_operation(
                operation_id=rpc_request.method, params=rpc_request.params, auth_provider=request
            )
            return {"jsonrpc": "2.0", "id": rpc_request.id, "result": result}
        except Exception as e:
            detail = getattr(e, 'detail', str(e))
            return JSONResponse(status_code=500, content={
                "jsonrpc": "2.0", "id": rpc_request.id, "error": {"code": -32603, "data": detail}
            })

    return app


app = create_app()
