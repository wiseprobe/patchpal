# Intelligent Tool Output Pruning

## Overview

PatchPal now implements **intelligent summarization** when pruning old tool outputs from context. Instead of simply replacing pruned content with `[Tool output pruned - X chars]`, the system preserves useful information based on the tool type.

## Problem Solved

**Before**: Naive pruning removed all information from old tool calls, potentially causing:
- The agent to forget what files exist and re-read them (wasting tokens)
- Loss of important context needed for decision-making
- Repetitive tool calls to rediscover information

**After**: Smart summarization preserves key information while drastically reducing token usage.

## Summarization Strategies by Tool

### Heavy Summarization (Low Information Loss)

These tools produce outputs that can be regenerated or aren't needed for reasoning:

#### `list_files`
- **Before**: 500 lines of file paths
- **After**: `[Pruned list_files: 127 files, e.g., patchpal/agent.py, patchpal/cli.py, patchpal/context.py...]`
- **Savings**: ~95%
- **Preserved**: File count, sample files

#### `tree`
- **Before**: 200 lines of directory structure
- **After**: `[Pruned tree: ~45 directories, 200 lines of structure]`
- **Savings**: ~90%
- **Preserved**: Directory count, line count

#### `get_repo_map`
- **Before**: 5,000 chars of function signatures across all files
- **After**: `[Pruned repo_map: 36 files analyzed, ~5,000 chars of structure]`
- **Savings**: ~95%
- **Preserved**: File count, size indicator

#### `git_status`
- **Before**: Full git status output
- **After**: `[Pruned git_status: 2 modified, 1 untracked, 2 staged]`
- **Savings**: ~80%
- **Preserved**: Counts of changes

#### `run_shell`
- **Before**: 1,000 lines of command output
- **After**: `[Pruned run_shell: pytest tests/ → ✓ success, numbers: 45, 2, 0]`
- **Savings**: ~95%
- **Preserved**: Command, success/failure, key numbers

### Partial Preservation (High Information Value)

These tools produce information the agent needs to reason about code:

#### `read_file`
- **Short files (≤20 lines)**: Keep everything
- **Long files**: Keep first 10 and last 10 lines with ellipsis
- **Example**:
  ```python
  # First 10 lines...
  def main():
      parser = argparse.ArgumentParser()
      # ...

  ... [180 lines omitted] ...

  # Last 10 lines...
  if __name__ == "__main__":
      main()
  ```
- **Savings**: ~90% on large files, 0% on small files
- **Preserved**: File structure, beginning and end (often most important)

#### `code_structure`
- **Already compact**: Keeps first 500 chars
- **Savings**: ~70% on large outputs
- **Preserved**: Top-level structure

#### `git_diff` / `git_log`
- **Keeps**: First 300 chars
- **Savings**: ~70-90% on large diffs
- **Preserved**: Summary and first changes

#### `grep_code`
- **Keeps**: Match count + first 3 results
- **Example**:
  ```
  [Pruned grep_code: 15 matches, first 3:
  patchpal/agent.py:932: tool_name = tool_call.function.name
  patchpal/agent.py:943: tool_func = self.custom_tool_funcs.get(tool_name)
  patchpal/agent.py:947: tool_result = f"Error: Unknown tool {tool_name}"
  ... +12 more]
  ```
- **Savings**: ~80% with many matches
- **Preserved**: Where to find matches, sample results

## Real-World Example

Consider a long conversation where the agent:

1. Lists files (500 lines) → Summarized to 1 line
2. Reads agent.py (1,230 lines) → Summarized to ~20 lines (first/last 10)
3. Searches for "tool_name" (50 matches) → Summarized to 5 lines
4. Runs tests (200 lines output) → Summarized to 1 line

**Original tokens**: ~15,000
**After pruning**: ~1,500
**Savings**: 90%

**Key insight**: The agent can still remember:
- "I saw agent.py has a tool execution loop starting around line 930"
- "Tests passed with 45 tests"
- "There are ~50 places where tool_name is used"

But doesn't need to keep the full 15K tokens of raw output in context.

## Configuration

The pruning behavior is controlled by environment variables:

```bash
# Enable/disable intelligent summarization (default: true)
export PATCHPAL_INTELLIGENT_PRUNING=true

# How many recent tokens of tool outputs to protect (default: 40,000)
export PATCHPAL_PRUNE_PROTECT=20000

# Minimum tokens to save before pruning is worthwhile (default: 20,000)
export PATCHPAL_PRUNE_MINIMUM=10000

# When to trigger compaction (default: 0.75 = 75% of context)
export PATCHPAL_COMPACT_THRESHOLD=0.60
```

### Disabling Intelligent Summarization

If you prefer the old behavior (simple pruning without summarization):

```bash
export PATCHPAL_INTELLIGENT_PRUNING=false
```

This will replace pruned outputs with just `[Tool output pruned - X chars]` instead of
smart summaries. This may save slightly more tokens but loses all context from pruned outputs.

More aggressive settings for token savings:
```bash
export PATCHPAL_PRUNE_PROTECT=20000      # Prune more aggressively
export PATCHPAL_PRUNE_MINIMUM=10000      # Lower threshold
export PATCHPAL_COMPACT_THRESHOLD=0.60   # Compact earlier
```

## Expected Impact

Based on typical coding sessions:

- **Short sessions (3-5 tool calls)**: Little to no impact (nothing gets pruned)
- **Medium sessions (10-20 tool calls)**: 20-30% token reduction
- **Long sessions (30+ tool calls)**: 40-60% token reduction
- **Very long sessions**: Up to 90% reduction on pruned outputs

## Implementation Details

The summarization is implemented in `patchpal/context.py`:

```python
def _summarize_tool_output(self, tool_name: str, content: str) -> str:
    """Create an intelligent summary of a tool output."""
    # Different strategies for different tool types
    if tool_name == "list_files":
        # Heavy summarization
        return f"[Pruned: {file_count} files, samples: {samples}]"
    elif tool_name == "read_file":
        # Preserve first/last lines
        return f"{first_10_lines}\n\n... [omitted] ...\n\n{last_10_lines}"
    # ... etc
```

The pruning is triggered automatically when conversation history grows beyond `PRUNE_PROTECT` tokens (default 40K).

## Trade-offs

**Benefits**:
- ✅ Massive token savings (40-90% in long sessions)
- ✅ Reduced API costs
- ✅ Longer conversations before hitting context limits
- ✅ Agent retains key information

**Considerations**:
- ⚠️ Agent can't see full original output after pruning
- ⚠️ May need to re-run tools occasionally to get full output
- ⚠️ Summarization adds minor CPU overhead (negligible)

**Best practices**:
- The agent will naturally re-run tools when it needs fresh data
- Recent tool outputs (last 40K tokens) are never pruned
- Critical information like file contents preserves structure

## Future Enhancements

Potential improvements:
1. **Semantic summarization**: Use embeddings to extract most important parts
2. **User-configurable rules**: Let users define custom summarization per tool
3. **Adaptive thresholds**: Adjust pruning based on session cost
4. **Compression**: Use gzip or similar for rarely-accessed old outputs
