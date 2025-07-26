import json
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from typing import Dict, Any, Union

from .core.config import get_mcp_config
from .core.dynamic_models import create_pydantic_models
from .services.http_client import execute_http_steps


# --- Models ---
class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: Dict[str, Any] = {}
    id: Union[int, str]


async def dispatch_mcp_operation(
        operation_id: str,
        params: Dict[str, Any],
        auth_provider: Union[Request, Dict[str, Any]],
        body: BaseModel | None = None
):
    # --- DEBUG LOGS ---
    print("\n--- [DEBUG: Dispatch Start] ---")
    print(f"Operation ID: '{operation_id}'")
    print(f"Initial params: {params}")
    print(f"Initial body is None: {body is None}")
    if body:
        # Use model_dump_json for clean, indented output of the Pydantic model
        print(f"Initial body content:\n{body.model_dump_json(indent=2)}")
    # --- END DEBUG ---

    mcp_config = get_mcp_config()
    op_config = mcp_config.get("operations", {}).get(operation_id)
    if not op_config:
        raise HTTPException(status_code=404, detail=f"Operation '{operation_id}' not found.")

    # Only try to build body from params if body is None AND this is likely an RPC call
    # (i.e., when we have meaningful params to work with)
    if body is None and params and op_config.get('requestBody'):
        # --- DEBUG LOGS ---
        print("--> Body is None and operation expects one. Attempting to build from params (RPC case).")
        # --- END DEBUG ---
        request_body_schema_ref = op_config.get('requestBody', {}).get('content', {}).get('application/json', {}).get(
            'schema', {}).get('$ref')
        if request_body_schema_ref:
            schemas = mcp_config.get("components", {}).get("schemas", {})
            pydantic_models = create_pydantic_models(schemas)
            schema_name = request_body_schema_ref.split('/')[-1]
            if body_model := pydantic_models.get(schema_name):
                try:
                    body = body_model(**params)
                    # --- DEBUG LOGS ---
                    print(f"--> Successfully created body model from params:\n{body.model_dump_json(indent=2)}")
                    # --- END DEBUG ---
                except Exception as e:
                    # --- DEBUG LOGS ---
                    print(f"[ERROR] Failed to create body model from params: {e}")
                    # --- END DEBUG ---
                    raise HTTPException(status_code=400, detail=f"Invalid RPC parameters for body: {e}")
    elif body is None and op_config.get('requestBody'):
        # This is a REST call that expects a body but didn't receive one
        raise HTTPException(status_code=400, detail="Request body is required for this operation.")

    # --- DEBUG LOGS ---
    print("--- [DEBUG: Dispatch End] ---")
    print(f"Final body is None: {body is None}")
    if body:
        print(f"Final body content:\n{body.model_dump_json(indent=2)}")
    # --- END DEBUG ---

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
            auth_provider=auth_provider,
            incoming_body=body  # 'body' will now be correctly populated for both REST and RPC
        )
    else:
        raise HTTPException(501, f"Source type '{source_type}' not implemented.")

# --- App Creation ---
def create_app():
    app = FastAPI(title="Generic Multi-Transport MCP Server")
    mcp_config = get_mcp_config()

    # Create all Pydantic models from the spec at startup
    schemas = mcp_config.get("components", {}).get("schemas", {})
    pydantic_models = create_pydantic_models(schemas)

    # Dynamically add REST endpoints
    for op_id, op_config in mcp_config.get("operations", {}).items():
        if 'path' in op_config and 'method' in op_config:

            # Check if this endpoint expects a request body
            request_body_schema_ref = op_config.get('requestBody', {}).get('content', {}).get('application/json',
                                                                                              {}).get('schema', {}).get(
                '$ref')
            body_model = None
            if request_body_schema_ref:
                schema_name = request_body_schema_ref.split('/')[-1]
                body_model = pydantic_models.get(schema_name)

            # Build the function signature with or without the body model
            signature_params = ["request: Request"]
            path_params = [p['name'] for p in op_config.get('parameters', []) if p['in'] == 'path']
            signature_params.extend([f"{p}: str" for p in path_params])
            if body_model:
                signature_params.append(f"body: {body_model.__name__}")

            signature = "async def generated_endpoint({}):".format(', '.join(signature_params))

            # Build the function body
            params_dict_str = "{" + ", ".join([f'"{p}": {p}' for p in path_params]) + "}"
            body_arg = "body=body" if body_model else "body=None"
            body = """
    return await dispatch_mcp_operation(
        operation_id='{op_id}',
        params={params_dict_str},
        auth_provider=request,
        {body_arg}
    )""".format(op_id=op_id, params_dict_str=params_dict_str, body_arg=body_arg)

            # Create the function object dynamically
            function_str = signature + "\n    " + body
            local_scope = {}
            exec_globals = {"dispatch_mcp_operation": dispatch_mcp_operation, "Request": Request}
            if body_model:
                exec_globals[body_model.__name__] = body_model

            exec(function_str, exec_globals, local_scope)
            endpoint_func = local_scope['generated_endpoint']

            # Register the endpoint
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

    @app.get("/events", tags=["Transports"])
    async def sse_endpoint(request: Request):
        async def event_generator():
            op_id = request.query_params.get('op')
            if op_id:
                try:
                    params = dict(request.query_params)
                    result = await dispatch_mcp_operation(op_id, params, request)
                    yield json.dumps({"event": "message", "id": op_id, "data": result})
                except Exception as e:
                    detail = getattr(e, 'detail', str(e))
                    yield json.dumps({"event": "error", "id": op_id, "data": detail})

        return EventSourceResponse(event_generator())

    return app


app = create_app()
