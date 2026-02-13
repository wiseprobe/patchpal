# Python API

PatchPal can be used programmatically from Python scripts or a REPL, giving you full agent capabilities with a simple API. **Unlike fully autonomous agent frameworks, PatchPal is designed for human-in-the-loop workflows** where users maintain control through interactive permission prompts, making it ideal for code assistance, debugging, and automation tasks that benefit from human oversight.

!!! info "Complete API Reference"
    For detailed API documentation with all parameters, return types, and method signatures, see the **[API Reference](../reference/agent.md)** section.

## Basic Usage

```python
from patchpal.agent import create_agent

# Create an agent (uses default model or PATCHPAL_MODEL env var)
agent = create_agent()

# Or specify a model explicitly
agent = create_agent(model_id="anthropic/claude-sonnet-4_5")

# Run the agent on a task
response = agent.run("List all Python files in this directory")
print(response)

# Continue the conversation (history is maintained)
response = agent.run("Now read the main agent file")
print(response)
```

## Adding Custom Tools

Custom tools can be used in two ways:

1. **CLI**: Place `.py` files in `~/.patchpal/tools/` (auto-discovered at startup)
2. **Python API**: Pass functions directly to `create_agent(custom_tools=[...])`

Both methods use the same tool schema auto-generation from Python functions with type hints and docstrings:

```python
from patchpal.agent import create_agent

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


def get_weather(city: str, units: str = "celsius") -> str:
    """Get weather information for a city.

    Args:
        city: Name of the city
        units: Temperature units (celsius or fahrenheit)

    Returns:
        Weather information string
    """
    # Your implementation here (API call, etc.)
    return f"Weather in {city}: 22°{units[0].upper()}, Sunny"


# Create agent with custom tools
agent = create_agent(
    model_id="anthropic/claude-sonnet-4-5",
    custom_tools=[calculator, get_weather]
)

# Use the agent - it will call your custom tools when appropriate
response = agent.run("What's 15 multiplied by 23?")
print(response)

response = agent.run("What's the weather in Paris?")
print(response)
```

**Key Points:**
- Custom tools are automatically converted to LLM tool schemas
- Functions should have type hints and Google-style docstrings
- The agent will call your functions when appropriate
- Tool execution follows the same permission system as built-in tools

## Advanced Usage

```python
from patchpal.agent import PatchPalAgent

# Create agent with custom configuration
agent = PatchPalAgent(model_id="anthropic/claude-sonnet-4-5")

# Set custom max iterations for complex tasks
response = agent.run("Refactor the entire codebase", max_iterations=200)

# Access conversation history
print(f"Messages in history: {len(agent.messages)}")

# Check context window usage
stats = agent.context_manager.get_usage_stats(agent.messages)
print(f"Token usage: {stats['total_tokens']:,} / {stats['context_limit']:,}")
print(f"Usage: {stats['usage_percent']}%")

# Manually trigger compaction if needed
if agent.context_manager.needs_compaction(agent.messages):
    agent._perform_auto_compaction()

# Track API costs (cumulative token counts across session)
print(f"Total LLM calls: {agent.total_llm_calls}")
print(f"Cumulative input tokens: {agent.cumulative_input_tokens:,}")
print(f"Cumulative output tokens: {agent.cumulative_output_tokens:,}")
print(f"Total tokens: {agent.cumulative_input_tokens + agent.cumulative_output_tokens:,}")
```

## Use Cases

- **Interactive debugging**: Use in Jupyter notebooks for hands-on debugging with agent assistance
- **Automation scripts**: Build scripts that use the agent for complex tasks with human oversight
- **Custom workflows**: Integrate PatchPal into your own tools and pipelines
- **Code review assistance**: Programmatic code analysis with permission controls
- **Batch processing**: Process multiple tasks programmatically while maintaining control
- **Testing and evaluation**: Test agent behavior with different prompts and configurations

## Key Features

- **Human-in-the-loop design**: Permission prompts ensure human oversight (unlike fully autonomous frameworks)
- **Stateful conversations**: Agent maintains full conversation history
- **Custom tools**: Add your own Python functions (via CLI auto-discovery or API parameter) with automatic schema generation
- **Automatic context management**: Auto-compaction works the same as CLI
- **All built-in tools available**: File operations, git, web search, skills, etc.
- **Model flexibility**: Works with any LiteLLM-compatible model
- **Token tracking**: Monitor API usage and costs in real-time
- **Environment variables respected**: All `PATCHPAL_*` settings apply

## PatchPal vs. Other Agent Frameworks

Unlike fully autonomous agent frameworks (e.g., smolagents, autogen), PatchPal is explicitly designed for **human-in-the-loop workflows**:

| Feature | PatchPal | Autonomous Frameworks |
|---------|----------|----------------------|
| **Design Philosophy** | Human oversight & control | Autonomous execution |
| **Permission System** | Interactive prompts for sensitive operations | Typically no prompts |
| **Primary Use Case** | Code assistance, debugging, interactive tasks | Automated workflows, batch processing |
| **Safety Model** | Write boundary protection, command blocking | Varies by framework |
| **Custom Tools** | Yes, with automatic schema generation | Yes (varies by framework) |
| **Best For** | Developers who want AI assistance with control | Automation, research, agent benchmarks |

The Python API uses the same agent implementation as the CLI, so you get the complete feature set including permissions, safety guardrails, and context management.
