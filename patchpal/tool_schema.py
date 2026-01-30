"""Utility to automatically convert Python functions to LiteLLM tool schemas."""

import inspect
from typing import Any, Callable, Dict, Union, get_args, get_origin, get_type_hints


def python_type_to_json_schema(py_type: Any) -> Dict[str, Any]:
    """Convert Python type hint to JSON schema type.

    Args:
        py_type: Python type hint

    Returns:
        JSON schema type dict
    """
    if py_type is type(None):
        return {"type": "null"}

    origin = get_origin(py_type)

    # Handle Optional/Union types
    if origin is Union:
        args = get_args(py_type)
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return python_type_to_json_schema(non_none[0])

    # Handle List
    if origin is list:
        args = get_args(py_type)
        if args:
            return {"type": "array", "items": python_type_to_json_schema(args[0])}
        return {"type": "array"}

    # Handle Dict
    if origin is dict:
        return {"type": "object"}

    # Basic types
    type_map = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
        list: {"type": "array"},
        dict: {"type": "object"},
    }

    return type_map.get(py_type, {"type": "string"})


def parse_docstring_params(docstring: str) -> Dict[str, str]:
    """Parse parameter descriptions from Google-style docstring.

    Args:
        docstring: Function docstring

    Returns:
        Dict mapping parameter names to descriptions
    """
    if not docstring:
        return {}

    params = {}
    lines = docstring.split("\n")
    in_args = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped.lower() in ("args:", "arguments:", "parameters:"):
            in_args = True
            continue

        if in_args:
            # Check if we left the Args section
            if stripped and not line.startswith((" ", "\t")) and ":" in stripped:
                break

            # Parse "param_name: description"
            if ":" in stripped:
                parts = stripped.split(":", 1)
                param_name = parts[0].strip()
                description = parts[1].strip()

                # Collect continuation lines
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if not next_line or ":" in next_line:
                        break
                    description += " " + next_line

                params[param_name] = description

    return params


def function_to_tool_schema(func: Callable) -> Dict[str, Any]:
    """Convert a Python function to LiteLLM tool schema.

    Extracts schema from function signature and docstring.

    Args:
        func: Python function with type hints and docstring

    Returns:
        LiteLLM tool schema dict
    """
    sig = inspect.signature(func)
    docstring = inspect.getdoc(func) or ""

    # Extract description (first paragraph)
    description = (
        docstring.split("\n\n")[0].replace("\n", " ").strip() or f"Execute {func.__name__}"
    )

    # Parse parameter descriptions
    param_descriptions = parse_docstring_params(docstring)

    # Get type hints
    try:
        type_hints = get_type_hints(func)
    except Exception:
        type_hints = {}

    # Build parameters
    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        param_type = type_hints.get(param_name, str)
        param_schema = python_type_to_json_schema(param_type)
        param_schema["description"] = param_descriptions.get(param_name, f"Parameter {param_name}")

        properties[param_name] = param_schema

        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }
