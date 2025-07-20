import httpx
import json
import re
from fastapi import Request
from typing import Dict, Any, List, Union

from .security import apply_auth


def _substitute_templates(text: str, data: Dict) -> str:
    """
    Finds all `${...}` placeholders and replaces them with values
    from the data dictionary, supporting nested access like 'step_1.body.id'.
    """

    def _replacer(match):
        path = match.group(1)  # The part inside ${...}
        keys = path.split('.')
        value = data
        try:
            for key in keys:
                value = value[key]
            return str(value)
        except (KeyError, TypeError):
            # If the key is not found, return the original placeholder
            return match.group(0)

    return re.sub(r'\$\{(.*?)\}', _replacer, text)


async def execute_http_steps(
        steps: List[Dict[str, Any]],
        auth_scheme: Dict,
        path_params: Dict,
        auth_provider: Union[Request, Dict[str, Any]]
) -> Dict[str, Any]:
    """Executes a series of HTTP requests described by the config."""
    template_data = {"path_params": path_params}

    async with httpx.AsyncClient() as client:
        for step in steps:
            step_id = step.get('step_id')
            if not step_id:
                raise ValueError("All steps in x-mcp-source must have a 'step_id'.")

            # Substitute URL templates
            url = _substitute_templates(step['url'], template_data)

            # Substitute body templates if a body exists
            final_body = None
            if body := step.get('body'):
                body_str = json.dumps(body)
                rendered_body_str = _substitute_templates(body_str, template_data)
                final_body = json.loads(rendered_body_str)

            request = client.build_request(
                method=step['method'].upper(), url=url, json=final_body
            )

            request = apply_auth(request, auth_scheme, auth_provider)

            response = await client.send(request)
            response.raise_for_status()

            response_data = response.json() if 'application/json' in response.headers.get('content-type',
                                                                                          '') else response.text
            template_data[step_id] = response_data

    last_step_id = steps[-1].get('step_id')
    return template_data.get(last_step_id, {})
