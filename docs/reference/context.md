# Context Management API

PatchPal's context management system handles token estimation, context window limits, and automatic compaction.

## TokenEstimator

::: patchpal.context.TokenEstimator
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - __init__
        - estimate_tokens
        - estimate_message_tokens
        - estimate_messages_tokens

## ContextManager

::: patchpal.context.ContextManager
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - __init__
        - needs_compaction
        - get_usage_stats
        - compact_messages

## Usage Example

```python
from patchpal.agent import create_agent

agent = create_agent()

# Check context usage
stats = agent.context_manager.get_usage_stats(agent.messages)
print(f"Token usage: {stats['total_tokens']:,} / {stats['context_limit']:,}")
print(f"Usage: {stats['usage_percent']}%")
print(f"Output budget remaining: {stats['output_budget_remaining']:,} tokens")

# Check if compaction is needed
if agent.context_manager.needs_compaction(agent.messages):
    print("Context window getting full - compaction will trigger soon")

# Manually trigger compaction (usually automatic)
agent._perform_auto_compaction()
```

## How Context Management Works

1. **Token Estimation**: Uses tiktoken (or fallback character estimation) to estimate message tokens
2. **Context Limits**: Tracks model-specific context window sizes (e.g., 200K for Claude Sonnet)
3. **Automatic Compaction**: When context reaches 70% full, summarizes old messages to free space
4. **Output Budget**: Reserves tokens for model output based on context window size

## Context Limits by Model Family

The context manager automatically detects limits for common models:

- **Claude 3.5 Sonnet**: 200,000 tokens
- **Claude 3 Opus**: 200,000 tokens
- **GPT-4 Turbo**: 128,000 tokens
- **GPT-4**: 8,192 tokens
- **GPT-3.5**: 16,385 tokens

For unknown models, falls back to 128,000 tokens.

## Related

- [Context Management Guide](../context-management.md) - Overview of context management
- [Agent API](agent.md) - Using the agent with automatic context management
