# Agent API

The core agent implementation for PatchPal, providing the main interface for interacting with LLMs and executing tools.

## Creating an Agent

::: patchpal.agent.create_agent
    options:
      show_root_heading: true
      heading_level: 3

## Agent Class

::: patchpal.agent.PatchPalAgent
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - __init__
        - run
        - compaction_completion

## Helper Functions

::: patchpal.agent._is_bedrock_arn
    options:
      show_root_heading: true
      heading_level: 3

## Usage Example

```python
from patchpal.agent import create_agent

# Create agent with default model
agent = create_agent()

# Or specify a model
agent = create_agent(model_id="anthropic/claude-sonnet-4-5")

# Run a task
response = agent.run("List all Python files")
print(response)

# Check token usage
print(f"Total tokens: {agent.cumulative_input_tokens + agent.cumulative_output_tokens:,}")
```

## Related

- [Python API Guide](../usage/python-api.md) - Comprehensive guide to using the Python API
- [Context Management](context.md) - How context windows are managed
- [Custom Tools](custom-tools.md) - Adding your own tools to the agent
