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
# Use default model (anthropic/claude-sonnet-4-5)
patchpal

# Use a specific model via command-line argument
patchpal --model openai/gpt-4o

# Use Ollama (local, no API key required - use larger models for better results)
patchpal --model ollama_chat/qwen2.5-coder:32b

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
patchpal --model ollama_chat/qwen2.5-coder:32b
```

### 2. Environment Variable
```bash
export PATCHPAL_MODEL=openai/gpt-4o
patchpal
```

### 3. Default Model
If no model is specified, PatchPal uses `anthropic/claude-sonnet-4-5` (Claude Sonnet 4.5).

### Supported Models

PatchPal works with any model supported by LiteLLM, including:

- **Anthropic**: `anthropic/claude-sonnet-4-5`, `anthropic/claude-opus-4-5`, `anthropic/claude-3-7-sonnet-latest`
- **OpenAI**: `openai/gpt-4o`, `openai/gpt-4-turbo`, `openai/gpt-3.5-turbo`
- **Ollama (Local)**: `ollama_chat/llama3.1`, `ollama_chat/llama3.2`, `ollama_chat/codellama`, `ollama_chat/mistral` - Run models locally without API keys!
- **Google**: `gemini/gemini-pro`, `vertex_ai/gemini-pro`
- **Others**: Cohere, Azure OpenAI, Bedrock, and many more

See the [LiteLLM providers documentation](https://docs.litellm.ai/docs/providers) for the complete list.

### Using Local Models (Ollama & vLLM)

Run models locally on your machine without needing API keys or internet access.

**⚠️ Important: For local models, use vLLM instead of Ollama for much better performance!**

#### vLLM (Recommended for Local Models)

vLLM is significantly faster than Ollama due to optimized inference with continuous batching and PagedAttention.

```bash
# 1. Install vLLM
pip install vllm

# 2. Start vLLM server with a model (example: Qwen 2.5 Coder)
vllm serve Qwen/Qwen2.5-Coder-32B-Instruct --dtype auto --api-key token-abc123

# 3. Use with PatchPal (in another terminal)
export OPENAI_API_KEY=token-abc123
patchpal --model openai/Qwen/Qwen2.5-Coder-32B-Instruct --api_base http://localhost:8000/v1
```

**Recommended models for vLLM:**
- `Qwen/Qwen2.5-Coder-32B-Instruct` - Excellent tool calling and coding (RECOMMENDED)
- `deepseek-ai/deepseek-coder-33b-instruct` - Strong coding and tool support
- `meta-llama/Meta-Llama-3.1-70B-Instruct` - Good performance, needs 64GB+ RAM

#### Ollama (Easier Setup, Slower Performance)

Ollama is easier to install but 3-10x slower than vLLM for the same models.

```bash
# 1. Install Ollama: Download from https://ollama.ai/
# 2. Pull a model
ollama pull qwen2.5-coder:32b

# 3. Run PatchPal
patchpal --model ollama_chat/qwen2.5-coder:32b
```

**Recommended Ollama models:**
- `ollama_chat/qwen2.5-coder:32b` - Best tool calling for Ollama
- `ollama_chat/deepseek-coder:33b` - Good coding support

**Not recommended** (poor tool calling):
- Smaller models (<32B parameters) struggle with tool calling
- `llama3.1:8b` often fails to properly format tool arguments

#### Performance Comparison

| Setup | Speed | Setup Difficulty | Best For |
|-------|-------|------------------|----------|
| **Cloud APIs** (Claude, GPT-4) | 1-3s per step | Easy | Production, best results |
| **vLLM** (local) | 3-10s per step | Medium | Privacy, local deployment |
| **Ollama** (local) | 30-90s per step | Easy | Quick testing, learning |

**Hardware requirements:**
- 32B models: ~20GB RAM/VRAM
- 70B models: ~40GB+ RAM/VRAM
- GPU highly recommended for acceptable performance

No API keys required for local models - everything runs on your machine!

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

### Running Tests

PatchPal includes a test suite that runs fairly quickly:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_tools.py

# Run with coverage report
pytest --cov=patchpal --cov-report=term-missing
```

```
patchpal/
├── __init__.py  - Package exports
├── tools.py     - Tool implementations (read, write, shell)
├── agent.py     - Agent configuration
└── cli.py       - CLI entry point

tests/
├── __init__.py       - Test package
├── test_tools.py     - Tests for tools module (15 tests)
├── test_agent.py     - Tests for agent module (5 tests)
└── test_cli.py       - Tests for CLI module (12 tests)
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
