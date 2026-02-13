# Custom Tools API

Create your own tools to extend PatchPal's capabilities with automatic schema generation from Python functions.

## Tool Schema Generation

### function_to_tool_schema

::: patchpal.tool_schema.function_to_tool_schema
    options:
      show_root_heading: true
      heading_level: 4

### python_type_to_json_schema

::: patchpal.tool_schema.python_type_to_json_schema
    options:
      show_root_heading: true
      heading_level: 4

### parse_docstring_params

::: patchpal.tool_schema.parse_docstring_params
    options:
      show_root_heading: true
      heading_level: 4

## Tool Discovery

### discover_tools

::: patchpal.tool_schema.discover_tools
    options:
      show_root_heading: true
      heading_level: 4

### list_custom_tools

::: patchpal.tool_schema.list_custom_tools
    options:
      show_root_heading: true
      heading_level: 4

## Creating Custom Tools

### Basic Example

```python
from typing import Optional

def calculator(x: int, y: int, operation: str = "add") -> str:
    """Perform basic arithmetic operations.

    Args:
        x: First number
        y: Second number
        operation: Operation to perform (add, subtract, multiply, divide)

    Returns:
        Result as a string
    """
    if operation == "add":
        return f"{x} + {y} = {x + y}"
    elif operation == "subtract":
        return f"{x} - {y} = {x - y}"
    elif operation == "multiply":
        return f"{x} * {y} = {x * y}"
    elif operation == "divide":
        if y == 0:
            return "Error: Cannot divide by zero"
        return f"{x} / {y} = {x / y}"
    return "Unknown operation"
```

### Using Custom Tools

```python
from patchpal.agent import create_agent

# Pass custom tools when creating the agent
agent = create_agent(custom_tools=[calculator])

# The agent will automatically use your tool when appropriate
response = agent.run("What's 15 times 23?")
```

### Advanced Example with Optional Parameters

```python
from typing import Optional

def search_code(
    pattern: str,
    file_glob: Optional[str] = None,
    case_sensitive: bool = True
) -> str:
    """Search for patterns in code files.

    Args:
        pattern: Regular expression pattern to search for
        file_glob: Optional glob pattern to filter files (e.g., '*.py')
        case_sensitive: Whether search should be case-sensitive

    Returns:
        Search results as formatted string
    """
    # Your implementation here
    pass
```

## Tool Requirements

For a function to work as a custom tool:

1. **Type hints required**: All parameters and return type must have type hints
2. **Docstring required**: Must have a docstring with Args and Returns sections
3. **Returns string**: Must return a string (the agent sees tool output as text)
4. **Valid signature**: No `*args` or `**kwargs` allowed

## Automatic Schema Generation

PatchPal automatically converts your Python function into an LLM tool schema:

- Type hints → JSON schema types
- Docstring Args → parameter descriptions
- Default values → optional parameters
- Return type → validated as string

## Related

- [Custom Tools Guide](../features/custom-tools.md) - Complete guide to creating custom tools
- [Agent API](agent.md) - Using custom tools with the agent
- [Python API](../usage/python-api.md) - Comprehensive Python API guide
