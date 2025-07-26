from pydantic import BaseModel, create_model
from typing import Dict, Any, Type, List, Optional


def create_pydantic_models(schemas: Dict[str, Any]) -> Dict[str, Type[BaseModel]]:
    """
    Dynamically creates Pydantic models from a dictionary of OpenAPI schemas,
    correctly handling nested $ref dependencies.
    """
    model_cache: Dict[str, Type[BaseModel]] = {}
    type_mapping = {"string": str, "number": float, "integer": int, "boolean": bool}

    def resolve_ref(ref: str) -> Optional[Type[BaseModel]]:
        """Finds a previously created model from a $ref string."""
        model_name = ref.split('/')[-1]
        return model_cache.get(model_name)

    def get_field_type(prop_details: Dict) -> Any:
        """Determines the type for a Pydantic field, resolving refs and arrays."""
        if '$ref' in prop_details:
            return resolve_ref(prop_details['$ref'])
        if prop_details.get('type') == 'array':
            item_details = prop_details.get('items', {})
            item_type = get_field_type(item_details)
            return List[item_type] if item_type else List
        return type_mapping.get(prop_details.get('type'), Any)

    schemas_to_process = list(schemas.keys())
    # Add a safeguard for unresolvable circular dependencies
    max_passes = len(schemas_to_process) + 1
    passes = 0

    while schemas_to_process and passes < max_passes:
        processed_this_pass = []
        for name in schemas_to_process:
            schema = schemas[name]
            fields = {}
            dependencies_met = True

            for prop_name, prop_details in schema.get("properties", {}).items():
                field_type = get_field_type(prop_details)
                if field_type is None and '$ref' in prop_details:
                    # A $ref dependency is not yet created, so we skip this model for now
                    dependencies_met = False
                    break

                is_required = prop_name in schema.get("required", [])
                default_value = ... if is_required else prop_details.get('default')
                fields[prop_name] = (field_type, default_value)

            if dependencies_met:
                # All dependencies for this model are resolved, so we can create it
                model_cache[name] = create_model(name, **fields)
                processed_this_pass.append(name)

        if not processed_this_pass and schemas_to_process:
            # No progress was made in a full pass, indicating a circular dependency
            raise RuntimeError(f"Could not resolve dependencies for schemas: {schemas_to_process}.")

        # Remove the successfully processed schemas from the list for the next pass
        schemas_to_process = [s for s in schemas_to_process if s not in processed_this_pass]
        passes += 1

    return model_cache
