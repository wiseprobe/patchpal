"""Test custom tools functionality."""

from patchpal.tool_schema import function_to_tool_schema


def test_function_to_tool_schema_basic():
    """Test basic schema generation."""

    def calculator(x: int, y: int) -> str:
        """Add two numbers.

        Args:
            x: First number
            y: Second number
        """
        return str(x + y)

    schema = function_to_tool_schema(calculator)

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "calculator"
    assert "Add two numbers" in schema["function"]["description"]

    params = schema["function"]["parameters"]
    assert params["type"] == "object"
    assert "x" in params["properties"]
    assert "y" in params["properties"]
    assert params["properties"]["x"]["type"] == "integer"
    assert params["properties"]["y"]["type"] == "integer"
    assert params["required"] == ["x", "y"]


def test_function_to_tool_schema_with_defaults():
    """Test schema generation with default parameters."""

    def greet(name: str, greeting: str = "Hello") -> str:
        """Greet someone.

        Args:
            name: Person's name
            greeting: Greeting message
        """
        return f"{greeting}, {name}!"

    schema = function_to_tool_schema(greet)

    # Only 'name' should be required (greeting has default)
    assert schema["function"]["parameters"]["required"] == ["name"]
    assert "name" in schema["function"]["parameters"]["properties"]
    assert "greeting" in schema["function"]["parameters"]["properties"]


def test_function_to_tool_schema_optional():
    """Test schema generation with Optional types."""
    from typing import Optional

    def search(query: str, limit: Optional[int] = None) -> str:
        """Search for something.

        Args:
            query: Search query
            limit: Maximum results
        """
        return f"Searching for: {query}"

    schema = function_to_tool_schema(search)

    assert schema["function"]["parameters"]["required"] == ["query"]
    assert schema["function"]["parameters"]["properties"]["limit"]["type"] == "integer"


if __name__ == "__main__":
    test_function_to_tool_schema_basic()
    test_function_to_tool_schema_with_defaults()
    test_function_to_tool_schema_optional()
    print("✓ All tests passed!")
