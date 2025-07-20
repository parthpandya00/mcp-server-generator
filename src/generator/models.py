from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class AuthSourceConfig(BaseModel):
    vault_address: Optional[str] = Field(None, description="Address of the HashiCorp Vault instance.")
    vault_token: Optional[str] = Field(None, description="Token for authenticating with Vault.")


class GeneratorRequest(BaseModel):
    openapi_spec: Dict[str, Any] = Field(
        ...,
        description="A valid OpenAPI 3.x specification as a JSON object."
    )
    direct_credentials: Dict[str, str] = Field(
        {},
        description="A dictionary of credentials provided directly, referenced by 'value_ref' in the spec."
    )
    auth_source_config: Optional[AuthSourceConfig] = Field(
        None,
        description="Configuration for external authentication sources like Vault."
    )