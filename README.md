# PatchPal - A Claude Code Clone

An educational implementation of a Claude Code-like agent using smolagents.

## Installation

Install PatchPal from PyPI:

```bash
pip install patchpal
```

Or install from source:

```bash
git clone https://github.com/amaiya/patchpal.git
cd patchpal
pip install -e .
```

## Setup

1. **Get an API key** (or use local models):
   - For Anthropic models (default): Sign up at https://console.anthropic.com/
   - For OpenAI models: Get a key from https://platform.openai.com/
   - For Ollama (local): Install from https://ollama.ai/ (no API key needed!)
   - For other providers: Check the [LiteLLM documentation](https://docs.litellm.ai/docs/providers)

2. **Set up your API key** (skip for local models like Ollama):
```bash
# For Anthropic (default)
export ANTHROPIC_API_KEY=your_api_key_here

# For OpenAI
export OPENAI_API_KEY=your_api_key_here

# For Ollama (local) - no API key needed!

# For other providers, check LiteLLM docs
```

3. **Run PatchPal**:
```bash
# Use default model (claude-3-7-sonnet-latest)
patchpal

# Use a specific model via command-line argument
patchpal --model openai/gpt-4o

# Use Ollama (local, no API key required)
patchpal --model ollama/llama3.1

# Or set the model via environment variable
export PATCHPAL_MODEL=openai/gpt-4o
patchpal
```

## Features

The agent has the following tools:

- **read_file**: Read contents of files in the repository
- **list_files**: List all files in the repository
- **apply_patch**: Modify files by providing new content
- **run_shell**: Execute safe shell commands (forbidden: rm, mv, sudo, etc.)

## Model Configuration

PatchPal supports any LiteLLM-compatible model. You can configure the model in three ways (in order of priority):

### 1. Command-line Argument
```bash
patchpal --model openai/gpt-4o
patchpal --model anthropic/claude-opus-4
patchpal --model ollama/llama3.1
```

### 2. Environment Variable
```bash
export PATCHPAL_MODEL=openai/gpt-4o
patchpal
```

### 3. Default Model
If no model is specified, PatchPal uses `anthropic/claude-3-7-sonnet-latest`.

### Supported Models

PatchPal works with any model supported by LiteLLM, including:

- **Anthropic**: `anthropic/claude-opus-4`, `anthropic/claude-3-7-sonnet-latest`, `anthropic/claude-3-5-sonnet-latest`
- **OpenAI**: `openai/gpt-4o`, `openai/gpt-4-turbo`, `openai/gpt-3.5-turbo`
- **Ollama (Local)**: `ollama/llama3.1`, `ollama/llama3.2`, `ollama/codellama`, `ollama/mistral` - Run models locally without API keys!
- **Google**: `gemini/gemini-pro`, `vertex_ai/gemini-pro`
- **Others**: Cohere, Azure OpenAI, Bedrock, and many more

See the [LiteLLM providers documentation](https://docs.litellm.ai/docs/providers) for the complete list.

### Using Ollama (Local Models)

Ollama lets you run models locally on your machine without needing API keys or internet access:

1. **Install Ollama**: Download from https://ollama.ai/
2. **Pull a model**: `ollama pull llama3.1` (or any other model)
3. **Run PatchPal**: `patchpal --model ollama/llama3.1`

Popular Ollama models for coding:
- `ollama/llama3.1` - Meta's latest Llama model
- `ollama/codellama` - Code-specialized Llama model
- `ollama/deepseek-coder` - Excellent for programming tasks
- `ollama/qwen2.5-coder` - Strong coding model

No API keys required - everything runs on your local machine!

### Viewing Help
```bash
patchpal --help
```

## Usage

Simply run the `patchpal` command and type your requests interactively:

```bash
$ patchpal
================================================================================
PatchPal - Claude Code Clone
================================================================================

Type 'exit' or 'quit' to exit the program.

You: Add type hints and basic logging to my_module.py
```

The agent will process your request and show you the results. You can continue with follow-up tasks or type `exit` to quit.

## Example Tasks

```
Add type hints and basic logging to app.py
Fix the divide by zero error in calculator.py
Create unit tests for the utils module
Refactor the authentication code for better security
Add error handling to all API calls
```

## Safety

The agent operates within a sandboxed environment with several restrictions:

- All file operations are restricted to the repository root
- Dangerous shell commands are blocked (rm, mv, sudo, etc.)
- All changes require passing through the apply_patch function
- Shell commands run with limited permissions

## Development

Install in development mode with dev dependencies:

```bash
pip install -e ".[dev]"
```

## Package Structure

```
patchpal/
├── __init__.py  - Package exports
├── tools.py     - Tool implementations (read, write, shell)
├── agent.py     - Agent configuration
└── cli.py       - CLI entry point
```

## Troubleshooting

**Error: "model: claude-3-5-sonnet-20240620"**
- Make sure your ANTHROPIC_API_KEY is set correctly
- Check that your API key has sufficient credits

**Error: "Invalid path"**
- The agent can only access files within the repository
- Use relative paths from the repository root

**Error: "Blocked command"**
- Some dangerous commands are forbidden for safety
- Check the FORBIDDEN list in tools.py
