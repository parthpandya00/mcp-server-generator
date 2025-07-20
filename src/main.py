from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from .generator.models import GeneratorRequest
from .generator.logic import generate_dockerfile

app = FastAPI(
    title="MCP Dockerfile Generator",
    description="Generates a Dockerfile for a generic MCP server from an OpenAPI spec.",
    version="2.0.0"
)


@app.post("/generate-dockerfile", response_class=Response)
async def create_mcp_dockerfile(request: GeneratorRequest):
    """
    Generates a Dockerfile based on an OpenAPI spec and configuration.

    - **openapi_spec**: The OpenAPI 3.x spec as a JSON object.
    - **direct_credentials**: A dictionary of secret values to be embedded as ENV vars.
    - **auth_source_config**: Configuration for Vault, if used.

    Returns a Dockerfile.
    """
    try:
        dockerfile_bytes = generate_dockerfile(request)
        return Response(
            content=dockerfile_bytes,
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=Dockerfile"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate Dockerfile: {str(e)}")