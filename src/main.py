from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from .generator.models import GeneratorRequest
from .generator.logic import generate_dockerfile, generate_mcp_files
import zipfile
import io
import json

app = FastAPI(
    title="MCP Dockerfile Generator",
    description="Generates a Dockerfile for a generic MCP server from an OpenAPI spec.",
    version="2.0.0"
)


@app.post("/generate-dockerfile", response_class=Response)
async def create_mcp_dockerfile(request: GeneratorRequest):
    """
    Generates a Dockerfile based on an OpenAPI spec and configuration.
    This endpoint maintains backward compatibility.

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


@app.post("/generate-mcp-package")
async def create_mcp_package(request: GeneratorRequest):
    """
    Generates both a Dockerfile and mcp_config.json based on an OpenAPI spec.
    Returns a ZIP file containing both files.

    - **openapi_spec**: The OpenAPI 3.x spec as a JSON object.
    - **direct_credentials**: A dictionary of secret values to be embedded as ENV vars.
    - **auth_source_config**: Configuration for Vault, if used.

    Returns a ZIP file with Dockerfile and mcp_config.json.
    """
    try:
        print("DEBUG: Starting MCP package generation...")
        dockerfile_content, config_content = generate_mcp_files(request)

        print(f"DEBUG: Generated Dockerfile ({len(dockerfile_content)} bytes)")
        print(f"DEBUG: Generated config ({len(config_content)} bytes)")

        # Validate that config_content is valid JSON
        try:
            json.loads(config_content.decode('utf-8'))
            print("DEBUG: Config JSON is valid")
        except json.JSONDecodeError as e:
            print(f"DEBUG: Config JSON is invalid: {e}")
            raise HTTPException(status_code=500, detail=f"Generated config is not valid JSON: {e}")

        # Create a ZIP file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Write as strings to ensure proper encoding
            zip_file.writestr('Dockerfile', dockerfile_content.decode('utf-8'))
            zip_file.writestr('mcp_config.json', config_content.decode('utf-8'))

        zip_content = zip_buffer.getvalue()
        print(f"DEBUG: Created ZIP file ({len(zip_content)} bytes)")

        return Response(
            content=zip_content,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=mcp-server-package.zip"}
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Error generating MCP package: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate MCP package: {str(e)}")


@app.post("/generate-config")
async def create_mcp_config(request: GeneratorRequest):
    """
    Generates only the mcp_config.json file based on an OpenAPI spec.

    - **openapi_spec**: The OpenAPI 3.x spec as a JSON object.

    Returns the mcp_config.json file.
    """
    try:
        print("DEBUG: Starting config generation...")
        _, config_content = generate_mcp_files(request)

        print(f"DEBUG: Generated config ({len(config_content)} bytes)")

        # Validate JSON
        try:
            config_dict = json.loads(config_content.decode('utf-8'))
            print("DEBUG: Config JSON is valid")
            print(f"DEBUG: Config has {len(config_dict.get('operations', {}))} operations")
        except json.JSONDecodeError as e:
            print(f"DEBUG: Config JSON is invalid: {e}")
            raise HTTPException(status_code=500, detail=f"Generated config is not valid JSON: {e}")

        return Response(
            content=config_content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=mcp_config.json"}
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"DEBUG: Error generating config: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate config: {str(e)}")
