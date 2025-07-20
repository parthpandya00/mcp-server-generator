import os
import hvac
from functools import lru_cache


@lru_cache(maxsize=1)
def get_vault_client():
    """Initializes and returns a Vault client."""
    vault_addr = os.getenv("VAULT_ADDR")
    vault_token = os.getenv("VAULT_TOKEN")
    if not vault_addr or not vault_token:
        return None
    return hvac.Client(url=vault_addr, token=vault_token)


def fetch_secret_from_vault(path: str, key: str) -> str:
    """Fetches a specific key from a secret path in Vault."""
    client = get_vault_client()
    if not client:
        raise ValueError("Vault client is not configured. Check VAULT_ADDR and VAULT_TOKEN.")

    read_response = client.secrets.kv.v2.read_secret_version(path=path)
    secret_value = read_response['data']['data'].get(key)

    if not secret_value:
        raise ValueError(f"Key '{key}' not found in vault at path '{path}'.")

    return secret_value