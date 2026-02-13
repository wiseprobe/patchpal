# Custom Tools

Custom tools extend PatchPal's capabilities by adding new Python functions that the agent can call. Unlike skills (which are prompt-based workflows), custom tools are executable Python code that the agent invokes automatically when needed.

**Key Differences:**
- **Skills**: Markdown files with instructions for the agent to follow
- **Custom Tools**: Python functions that execute code and return results

## Installation

1. **Create the tools directory:**
```bash
mkdir -p ~/.patchpal/tools
```

2. **Copy the example tools (or create your own):**
```bash
# After pip install patchpal, get the example tools
curl -L https://github.com/wiseprobe/patchpal/archive/main.tar.gz | tar xz --strip=1 patchpal-main/examples

# Copy to your tools directory
cp examples/tools/calculator.py ~/.patchpal/tools/
```

3. **Start PatchPal - tools are loaded automatically:**
```bash
$ patchpal
================================================================================
PatchPal - AI coding and automation assistant
================================================================================

Using model: anthropic/claude-sonnet-4-5
🔧 Loaded 7 custom tool(s): add, subtract, multiply, divide, calculate_percentage, fahrenheit_to_celsius, celsius_to_fahrenheit
```

## Creating Custom Tools

Custom tools are Python functions with specific requirements:

**Requirements:**
1. **Type hints** for all parameters
2. **Docstring** with description and Args section (Google-style)
3. **Module-level** functions (not nested inside classes)
4. **Return type** should typically be `str` (for LLM consumption)
5. Function names **cannot start with underscore** (private functions ignored)

**Example:**

```python
# ~/.patchpal/tools/my_tools.py

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


def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert between currencies.

    Args:
        amount: Amount to convert
        from_currency: Source currency code (e.g., USD)
        to_currency: Target currency code (e.g., EUR)

    Returns:
        Converted amount as a string
    """
    # Your implementation here (API call, etc.)
    # This is just a simple example
    rates = {"USD": 1.0, "EUR": 0.85, "GBP": 0.73}
    usd_amount = amount / rates.get(from_currency, 1.0)
    result = usd_amount * rates.get(to_currency, 1.0)
    return f"{amount} {from_currency} = {result:.2f} {to_currency}"
```

## Using Custom Tools

Once loaded, the agent calls your custom tools automatically:

```bash
You: What's 15 + 27?
Agent: [Calls calculator(15, 27, "add")]
        15 + 27 = 42

You: What's 100 divided by 4?
Agent: [Calls calculator(100, 4, "divide")]
        100 / 4 = 25

You: Convert 100 USD to EUR
Agent: [Calls convert_currency(100, "USD", "EUR")]
        100 USD = 85.00 EUR
```

## Tool Discovery

PatchPal discovers tools from `~/.patchpal/tools/*.py` at startup. All `.py` files are scanned for valid tool functions.

**What Gets Loaded:**
- ✅ Functions with type hints and docstrings
- ✅ Multiple functions per file
- ✅ Files can import standard libraries
- ❌ Functions without type hints
- ❌ Functions without docstrings
- ❌ Private functions (starting with `_`)
- ❌ Imported functions (must be defined in the file)

## Example Tools

The repository includes [example tools](https://github.com/wiseprobe/patchpal/tree/main/examples/tools):
- **calculator.py**: Basic arithmetic (add, subtract, multiply, divide), temperature conversion, percentage calculations
  - Demonstrates different numeric types (int, float)
  - Shows proper formatting of results for LLM consumption
  - Examples: `add`, `subtract`, `multiply`, `divide`, `calculate_percentage`, `fahrenheit_to_celsius`

View the [examples/tools/](https://github.com/wiseprobe/patchpal/tree/main/examples/tools) directory for complete examples and a detailed README.

## Security Note

⚠️ Custom tools execute arbitrary Python code on your system. Only install tools from sources you trust.

- Tools are only loaded from `~/.patchpal/tools/` (your home directory)
- Project-local tools (`.patchpal/tools/`) are **not supported** for security
- This prevents accidental execution of untrusted code from repositories

## Advanced Features

**Optional Parameters:**
```python
from typing import Optional

def greet(name: str, greeting: Optional[str] = "Hello") -> str:
    """Greet someone.

    Args:
        name: Person's name
        greeting: Optional greeting message (default: "Hello")
    """
    return f"{greeting}, {name}!"
```

**Complex Types:**
```python
from typing import List

def sum_numbers(numbers: List[int]) -> str:
    """Sum a list of numbers.

    Args:
        numbers: List of integers to sum
    """
    total = sum(numbers)
    return f"Sum of {numbers} = {total}"
```

**Python API:**

Custom tools can also be used programmatically:

```python
from patchpal.agent import create_agent

def calculator(x: int, y: int) -> str:
    """Add two numbers.

    Args:
        x: First number
        y: Second number
    """
    return str(x + y)

# Create agent with custom tools
agent = create_agent(custom_tools=[calculator])
response = agent.run("What's 5 + 3?")
```

See the Python API section for more details.

## Troubleshooting

If tools aren't loading:
1. Check the file has a `.py` extension
2. Ensure functions have type hints for all parameters
3. Verify docstrings follow Google style (with Args: section)
4. Look for warning messages when starting PatchPal
5. Test the function directly in Python to check for syntax errors
