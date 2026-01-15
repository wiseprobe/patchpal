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
- **AWS Bedrock**: `bedrock/anthropic.claude-sonnet-4-5-v1:0`, or full ARNs for GovCloud/VPC endpoints
- **Ollama (Local)**: `ollama_chat/llama3.1`, `ollama_chat/llama3.2`, `ollama_chat/codellama`, `ollama_chat/mistral` - Run models locally without API keys!
- **Google**: `gemini/gemini-pro`, `vertex_ai/gemini-pro`
- **Others**: Cohere, Azure OpenAI, and many more

See the [LiteLLM providers documentation](https://docs.litellm.ai/docs/providers) for the complete list.

### Using AWS Bedrock (Including GovCloud and VPC Endpoints)

PatchPal supports AWS Bedrock with custom regions and VPC endpoints for secure enterprise deployments.

**Basic AWS Bedrock Setup:**
```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key

# Use Bedrock model
patchpal --model bedrock/anthropic.claude-sonnet-4-5-20250929-v1:0
```

**AWS GovCloud or VPC Endpoint Setup:**
```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key

# Set custom region (e.g., GovCloud)
export AWS_BEDROCK_REGION=us-gov-east-1

# Set VPC endpoint URL (optional, for VPC endpoints)
export AWS_BEDROCK_ENDPOINT=https://vpce-xxxxx.bedrock-runtime.us-gov-east-1.vpce.amazonaws.com

# Use Bedrock with full ARN (bedrock/ prefix is optional - auto-detected)
patchpal --model "arn:aws-us-gov:bedrock:us-gov-east-1:012345678901:inference-profile/us-gov.anthropic.claude-sonnet-4-5-20250929-v1:0"
```

**Environment Variables for Bedrock:**
- `AWS_ACCESS_KEY_ID`: AWS access key ID (required)
- `AWS_SECRET_ACCESS_KEY`: AWS secret access key (required)
- `AWS_BEDROCK_REGION`: Custom AWS region (e.g., `us-gov-east-1` for GovCloud)
- `AWS_BEDROCK_ENDPOINT`: Custom endpoint URL for VPC endpoints or GovCloud

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

### Enhanced Security Guardrails ✅ FULLY ENABLED

PatchPal includes comprehensive security protections enabled by default:

**Critical Security:**
- **Sensitive file protection**: Blocks access to `.env`, credentials, API keys
- **File size limits**: Prevents OOM with configurable size limits (10MB default)
- **Binary file detection**: Blocks reading non-text files
- **Critical file warnings**: Warns when modifying infrastructure files (package.json, Dockerfile, etc.)
- **Read-only mode**: Optional mode that prevents all modifications
- **Command timeout**: 30-second timeout on shell commands
- **Pattern-based blocking**: Blocks dangerous command patterns (`> /dev/`, `--force`, etc.)
- **Path traversal protection**: Prevents access outside repository root

**Operational Safety:**
- **Operation audit logging**: All file operations and commands logged to `~/.patchpal/<repo-name>/audit.log` (enabled by default)
- **Automatic backups**: Optional auto-backup of files to `~/.patchpal/<repo-name>/backups/` before modification
- **Resource limits**: Configurable operation counter prevents infinite loops (1000 operations default)
- **Git state awareness**: Warns when modifying files with uncommitted changes

**Configuration via environment variables:**
```bash
# Critical Security Controls
export PATCHPAL_MAX_FILE_SIZE=5242880     # Maximum file size in bytes for read/write operations (default: 10485760 = 10MB)
export PATCHPAL_READ_ONLY=true            # Prevent all file modifications, analysis-only mode (default: false)
                                           # Useful for: code review, exploration, security audits, CI/CD analysis, or trying PatchPal risk-free
export PATCHPAL_ALLOW_SENSITIVE=true      # Allow access to .env, credentials, API keys (default: false - blocked for safety)
                                           # Only enable when working with test/dummy credentials or intentionally managing config files

# Operational Safety Controls
export PATCHPAL_AUDIT_LOG=false           # Log all operations to ~/.patchpal/<repo-name>/audit.log (default: true)
export PATCHPAL_ENABLE_BACKUPS=true       # Auto-backup files to ~/.patchpal/<repo-name>/backups/ before modification (default: false)
export PATCHPAL_MAX_OPERATIONS=5000       # Maximum operations per session to prevent infinite loops (default: 1000)
```

**Test coverage:** 70 tests including 38 dedicated security tests

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
