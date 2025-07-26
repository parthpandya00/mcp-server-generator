"""
Robust templating & HTTP‑step execution utility

Key fixes & improvements
-----------------------
1. **Path resolution now supports list/array indexes and bracket notation**
   e.g. ``${step1.items[0].id}`` or ``${step1.2}``.
2. **Resolves placeholders inside strings _and_ returns raw values when the whole string is a placeholder**, keeping JSON serialisation types intact.
3. **Clearer error messages** when a path cannot be resolved.
4. **Centralised placeholder regex** for small performance win.
5. **Safer logging** – redacts bearer tokens & prettifies output.
6. **Docstrings + type hints** for easier maintenance.

Drop this file in place of the old implementation and update imports if the module name changed.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Sequence, Union, Match

import httpx
from fastapi import Request
from pydantic import BaseModel

from .security import apply_auth  # <- keep your existing helper

__all__ = [
    "execute_http_steps",
]

# Sentinel for unresolved placeholders
_UNSET = object()

# Pre‑compiled placeholder regex: matches ``${ ... }``
_PLACEHOLDER_RE = re.compile(r"\$\{(.*?)\}")


# ---------------------------------------------------------------------------
# Path resolution helpers
# ---------------------------------------------------------------------------

def _parse_path_tokens(path: str) -> List[Union[str, int]]:
    """Split dotted / bracketed path into a list of tokens.

    Examples
    --------
    >>> _parse_path_tokens("foo.bar[0].baz")
    ['foo', 'bar', 0, 'baz']
    >>> _parse_path_tokens("items.2.id")
    ['items', 2, 'id']
    """
    tokens: List[Union[str, int]] = []
    for part in path.split('.'):
        # Handle bracket notation like "bar[0]"
        bracket_parts = re.split(r"\[|\]", part)
        for p in bracket_parts:
            if not p:
                continue
            tokens.append(int(p) if p.isdigit() else p)
    return tokens


def _resolve_value(path: str, data: Any) -> Any:
    """Resolve *path* inside *data* supporting dict keys and list indexes."""
    value = data
    for tok in _parse_path_tokens(path):
        if isinstance(tok, int):
            if not isinstance(value, Sequence):
                raise KeyError(f"Cannot index non‑list value with {tok}.")
            if tok >= len(value):
                raise KeyError(f"Index {tok} out of range (len={len(value)}).")
            value = value[tok]
        else:
            if not isinstance(value, dict):
                raise KeyError(f"Cannot access key '{tok}' on non‑dict value.")
            if tok not in value:
                raise KeyError(f"Key '{tok}' does not exist.")
            value = value[tok]
    return value


# ---------------------------------------------------------------------------
# Template substitution helpers
# ---------------------------------------------------------------------------

def _substitute_templates_in_string(text: str, data: Dict) -> str:
    """Replace *all* placeholders inside *text* with their resolved values."""

    def _replacer(match: Match[str]) -> str:  # noqa: N803
        path = match.group(1).strip()
        try:
            resolved = _resolve_value(path, data)
        except (KeyError, TypeError, IndexError):
            return match.group(0)  # leave as‑is if unresolved

        if resolved is None:
            return "null"
        if isinstance(resolved, bool):
            return str(resolved).lower()
        if isinstance(resolved, (dict, list)):
            # Dump compact to avoid needless whitespace in URLs
            return json.dumps(resolved, separators=(",", ":"))
        return str(resolved)

    return _PLACEHOLDER_RE.sub(_replacer, text)


def _resolve_templates_in_obj(obj: Any, data: Dict) -> Any:
    """Recursively resolve templates inside dict/list/str structures.

**Behaviour rules**
1. When the **entire string** is a single placeholder – e.g. ``"${foo.bar}"`` – we return
   the *raw* resolved value **without** type coercion. This preserves booleans,
   dicts, lists, etc. exactly as the downstream API schema expects.
2. When the placeholder appears **inline** inside a larger string –
   e.g. ``"Bearer ${token}"`` – we fall back to string substitution rules:
   * ``None`` -> ``"null"``
   * ``bool``  -> ``"true"`` / ``"false"``
   * ``dict``/``list`` -> compact JSON string.

These rules ensure Microsoft Graph (and similar APIs) receive the correct JSON
value types for fields like ``toRecipients`` (array) and ``saveToSentItems``
(boolean), eliminating the 400 errors you observed.
"""
    if isinstance(obj, dict):
        return {k: _resolve_templates_in_obj(v, data) for k, v in obj.items()}

    if isinstance(obj, list):
        return [_resolve_templates_in_obj(item, data) for item in obj]

    if isinstance(obj, str):
        m = re.fullmatch(r"\$\{(.*?)\}", obj)
        if m:
            # Whole‑string placeholder → return raw value.
            try:
                return _resolve_value(m.group(1).strip(), data)
            except (KeyError, TypeError, IndexError):
                return obj  # leave unresolved

        # Inline substitution (string contains other chars besides placeholder)
        return _substitute_templates_in_string(obj, data)

    return obj  # primitives unchanged


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

async def execute_http_steps(
    steps: List[Dict[str, Any]],
    auth_scheme: Dict,
    path_params: Dict,
    auth_provider: Union[Request, Dict[str, Any]],
    incoming_body: BaseModel | None = None,
) -> Dict[str, Any]:
    """Orchestrate a list of HTTP steps, injecting outputs into templates."""

    # --- DEBUG LOGS ---
    print("\n--- [DEBUG: execute_http_steps Start] ---")
    print(f"Incoming Body is None: {incoming_body is None}")
    # --- END DEBUG ---

    # Context for template resolution
    template_data: Dict[str, Any] = {"path_params": path_params}
    if incoming_body is not None:
        template_data["incoming_request_body"] = incoming_body.model_dump(exclude_unset=True)

        # --- DEBUG LOGS ---
    print("\n--- Template Data Context ---")
    # Pretty-print the dictionary that will be used for template substitution
    print(json.dumps(template_data, indent=2, default=str))
    # --- END DEBUG ---

    async with httpx.AsyncClient() as client:
        for step in steps:
            step_id = step.get("step_id")
            if not step_id:
                raise ValueError("Each step must include a unique 'step_id'.")

                        # ------------ Build request -------------
            url = _substitute_templates_in_string(step["url"], template_data)

            def _prune_unresolved(val: Any) -> Any:  # noqa: ANN001
                """Recursively drop keys / items that are still unresolved placeholders."""
                if isinstance(val, dict):
                    return {
                        k: v
                        for k, v in ((k, _prune_unresolved(v)) for k, v in val.items())
                        if v is not _UNSET
                    }
                if isinstance(val, list):
                    return [x for x in (_prune_unresolved(x) for x in val) if x is not _UNSET]
                if isinstance(val, str) and _PLACEHOLDER_RE.search(val):
                    return _UNSET
                return val

            final_body = None
            if body_tpl := step.get("body"):
                # --- DEBUG LOGS ---
                print("\n--- [DEBUG: Body Processing] ---")
                print("Original Body Template from Config:")
                print(json.dumps(body_tpl, indent=2))

                resolved_body = _resolve_templates_in_obj(body_tpl, template_data)
                print("\nBody after template resolution (_resolve_templates_in_obj):")
                # Use default=str to handle non-serializable types like Pydantic models if any slip through
                print(json.dumps(resolved_body, indent=2, default=str))

                final_body = _prune_unresolved(resolved_body)
                print("\nFinal Body after pruning (_prune_unresolved):")
                print(json.dumps(final_body, indent=2, default=str))


            request = client.build_request(
                method=step["method"].upper(),
                url=url,
                json=final_body,
            )

            request = apply_auth(request, auth_scheme, auth_provider)

            # ------------ Logging -------------
            print("\n---[MCP Outgoing Request]-----------------")
            print(f"{request.method} {request.url}")
            for k, v in request.headers.items():
                if k.lower() == "authorization":
                    scheme, *_ = v.split(maxsplit=1)
                    print(f"{k}: {scheme} <redacted>")
                else:
                    print(f"{k}: {v}")
            if request.content:
                print(f"BODY: {request.content.decode('utf-8')}")
            print("------------------------------------------\n")

            # ------------ Execute -------------
            response = await client.send(request)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                print("\n---[Downstream API Error]----------------")
                print(f"Status: {exc.response.status_code} {exc.response.reason_phrase}")
                print(f"Body  : {exc.response.text}")
                print("----------------------------------------\n")
                raise

            # ------------ Save output -------------
            if "application/json" in response.headers.get("content-type", ""):
                response_data: Any = response.json()
            else:
                response_data = response.text

            template_data[step_id] = response_data

    # Return output of the last step
    return template_data[steps[-1]["step_id"]]
