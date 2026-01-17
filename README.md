# PatchPal - A Claude Code Clone

![PatchPal Screenshot](patchpal_screenshot.png)

> A lightweight clone of Claude Code in Python -- supports both local and cloud LLMs.

A key goal is to mimic Claude Code's core functionality while maintaining a lean, lightweight, accessible codebase, making it ideal for education and experimentation:

```bash
$ls ./patchpal
__init__.py agent.py  cli.py  permissions.py  skills.py  tools.py
```

## Installation

Install PatchPal from PyPI:

```bash
pip install patchpal
```

## Setup

1. **Get an API key** (or use local models):
   - For Anthropic models (default): Sign up at https://console.anthropic.com/
   - For OpenAI models: Get a key from https://platform.openai.com/
   - For vLLM (local): Install from https://docs.vllm.ai/ (no API key needed, faster than Ollama!)
   - For Ollama (local): Install from https://ollama.ai/ (no API key needed!)
   - For other providers: Check the [LiteLLM documentation](https://docs.litellm.ai/docs/providers)

2. **Set up your API key** (skip for local models like Ollama):
```bash
# For Anthropic (default)
export ANTHROPIC_API_KEY=your_api_key_here

# For OpenAI
export OPENAI_API_KEY=your_api_key_here

# For vLLM or Ollama (local) - no API key needed (unless configured)!

# For other providers, check LiteLLM docs
```

3. **Run PatchPal**:
```bash
# Use default model (anthropic/claude-sonnet-4-5)
patchpal

# Use a specific model via command-line argument
patchpal --model openai/gpt-4o

# Use vLLM (local)
# Note: vLLM server must be started with --tool-call-parser and --enable-auto-tool-choice
# See "Using Local Models (Ollama & vLLM)" section below for details
export OPENAI_API_BASE=http://localhost:8000/v1
export OPENAI_API_KEY=token-abc123
patchpal --model openai/Qwen2.5-Coder-32B-Instruct

# Use Ollama (local, no API key required - easier setup than vLLM)
patchpal --model ollama_chat/qwen2.5-coder:32b

# Or set the model via environment variable
export PATCHPAL_MODEL=openai/gpt-4o
patchpal
```

## Features

### Context Awareness

The agent is context-aware and knows:
- **Current date and time**: The agent always knows today's date and current time, useful for:
  - Searching for recent information (e.g., "latest React 2026 documentation")
  - Understanding file timestamps relative to "now"
  - Date-based queries (e.g., "what was released this month?")

### Tools

The agent has the following tools:

### File Operations
- **read_file**: Read contents of files in the repository
- **list_files**: List all files in the repository
- **get_file_info**: Get detailed metadata for file(s) - size, modification time, type
  - Supports single files: `get_file_info("file.txt")`
  - Supports directories: `get_file_info("src/")`
  - Supports glob patterns: `get_file_info("tests/*.py")`
- **find_files**: Find files by name pattern using glob-style wildcards
  - Example: `find_files("*.py")` - all Python files
  - Example: `find_files("test_*.py")` - all test files
  - Example: `find_files("**/*.md")` - all markdown files recursively
  - Supports case-insensitive matching
- **tree**: Show directory tree structure to understand folder organization
  - Example: `tree(".")` - show tree from current directory
  - Configurable max depth (default: 3, max: 10)
  - Option to show/hide hidden files
- **grep_code**: Search for patterns in code files (regex support, file filtering)
- **edit_file**: Edit a file by replacing an exact string (efficient for small changes)
  - Example: `edit_file("config.py", "port = 3000", "port = 8080")`
  - More efficient than apply_patch for targeted changes
  - Old string must appear exactly once in the file
- **apply_patch**: Modify files by providing complete new content
- **run_shell**: Execute shell commands (requires user permission; privilege escalation blocked)

### Git Operations (No Permission Required)
- **git_status**: Show modified, staged, and untracked files
- **git_diff**: Show changes in working directory or staged area
  - Optional parameters: `path` (specific file), `staged` (show staged changes)
- **git_log**: Show commit history
  - Optional parameters: `max_count` (number of commits, max 50), `path` (specific file history)

### Web Capabilities
- **web_search**: Search the web using DuckDuckGo (no API key required!)
  - Look up error messages and solutions
  - Find current documentation and best practices
  - Research library versions and compatibility
- **web_fetch**: Fetch and read content from URLs
  - Read documentation pages
  - Access API references
  - Extract readable text from HTML pages

### Skills System

Skills are reusable workflows and custom commands that can be invoked by name or discovered automatically by the agent.

**Creating Your Own Skills:**

1. **Choose a location:**
   - Personal skills (all projects): `~/.patchpal/skills/<skill-name>/SKILL.md`
   - Project-specific skills: `<repo>/.patchpal/skills/<skill-name>/SKILL.md`

2. **Create the skill file:**
```bash
# Create a personal skill
mkdir -p ~/.patchpal/skills/my-skill
cat > ~/.patchpal/skills/my-skill/SKILL.md <<'EOF'
---
name: my-skill
description: Brief description of what this skill does
---
# Instructions
Your detailed instructions here...
EOF
```

3. **Skill File Format:**
```markdown
---
name: skill-name
description: One-line description
---
# Detailed Instructions
- Step 1: Do this
- Step 2: Do that
- Use specific PatchPal tools like git_status, read_file, etc.
```

**Example Skills:**

The PatchPal repository includes example skills you can use as templates:
- **commit**: Best practices for creating git commits
- **review**: Comprehensive code review checklist
- **add-tests**: Add comprehensive pytest tests (includes code block templates)
- **slack-gif-creator**: Create animated GIFs for Slack (from [Anthropic's official skills repo](https://github.com/anthropics/skills), demonstrates Claude Code compatibility)
- **skill-creator**: Guide for creating effective skills with bundled scripts and references (from [Anthropic's official skills repo](https://github.com/anthropics/skills/tree/main/skills/skill-creator), demonstrates full bundled resources support)

**After `pip install patchpal`, get examples:**

```bash
# Quick way: Download examples directly from GitHub
curl -L https://github.com/amaiya/patchpal/archive/main.tar.gz | tar xz --strip=1 patchpal-main/examples

# Or clone the repository
git clone https://github.com/amaiya/patchpal.git
cd patchpal

# Copy examples to your personal skills directory
cp -r examples/skills/commit ~/.patchpal/skills/
cp -r examples/skills/review ~/.patchpal/skills/
cp -r examples/skills/add-tests ~/.patchpal/skills/
```

**View examples online:**
Browse the [examples/skills/](https://github.com/amaiya/patchpal/tree/main/examples/skills) directory on GitHub to see the skill format and create your own.

**Using Skills:**

There are two ways to invoke skills:

1. **Direct invocation** - Type `/skillname` at the prompt:
```bash
$ patchpal
You: /commit Fix authentication bug
```

2. **Natural language** - Just ask, and the agent discovers the right skill:
```bash
You: Help me commit these changes following best practices
# Agent automatically discovers and uses the commit skill
```

**Finding Available Skills:**

Ask the agent to list them:
```bash
You: list skills
```

**Skill Priority:**

Project skills (`.patchpal/skills/`) override personal skills (`~/.patchpal/skills/`) with the same name.

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

**Important:** vLLM >= 0.10.2 is required for proper tool calling support.

**Using Local vLLM Server:**

```bash
# 1. Install vLLM (>= 0.10.2)
pip install vllm

# 2. Start vLLM server with tool calling enabled
vllm serve Qwen/Qwen2.5-Coder-32B-Instruct \
  --dtype auto \
  --api-key token-abc123 \
  --tool-call-parser qwen3_xml \
  --enable-auto-tool-choice

# 3. Use with PatchPal (in another terminal)
# Option A: Using openai/ prefix (recommended)
export OPENAI_API_BASE=http://localhost:8000/v1
export OPENAI_API_KEY=token-abc123
patchpal --model openai/Qwen2.5-Coder-32B-Instruct

# Option B: Using hosted_vllm/ prefix
export HOSTED_VLLM_API_BASE=http://localhost:8000
export HOSTED_VLLM_API_KEY=token-abc123
patchpal --model hosted_vllm/Qwen2.5-Coder-32B-Instruct
```

**Using Remote/Hosted vLLM Server:**

```bash
# For remote vLLM servers (e.g., hosted by your organization)
# Option A: Using openai/ prefix (recommended)
export OPENAI_API_BASE=https://your-vllm-server.com/v1
export OPENAI_API_KEY=your_api_key_here
patchpal --model openai/your-model-name

# Option B: Using hosted_vllm/ prefix
export HOSTED_VLLM_API_BASE=https://your-vllm-server.com
export HOSTED_VLLM_API_KEY=your_api_key_here
patchpal --model hosted_vllm/your-model-name
```

**Environment Variables:**
- For `openai/` prefix: Use `OPENAI_API_BASE` and `OPENAI_API_KEY`
- For `hosted_vllm/` prefix: Use `HOSTED_VLLM_API_BASE` and `HOSTED_VLLM_API_KEY`
- **Note:** The `openai/` prefix is recommended as it's more widely compatible

**Using YAML Configuration (Alternative):**

Create a `config.yaml`:
```yaml
host: "0.0.0.0"
port: 8000
api-key: "token-abc123"
tool-call-parser: "openai"  # Use appropriate parser for your model
enable-auto-tool-choice: true
dtype: "auto"
```

Then start vLLM:
```bash
vllm serve openai/gpt-oss-20b --config config.yaml

# Use with PatchPal
export OPENAI_API_BASE=http://localhost:8000/v1
export OPENAI_API_KEY=token-abc123
patchpal --model openai/gpt-oss-20b
```

**Recommended models for vLLM:**
- `Qwen/Qwen2.5-Coder-32B-Instruct` - Excellent tool calling and coding (use parser: `qwen3_xml`) (RECOMMENDED)
- `openai/gpt-oss-20b` - OpenAI's open-source model (use parser: `openai`)
- `deepseek-ai/deepseek-coder-33b-instruct` - Strong coding and tool support (use parser: `deepseek_v3`)
- `meta-llama/Meta-Llama-3.1-70B-Instruct` - Good performance, needs 64GB+ RAM (use parser: `llama3_json`)

**Tool Call Parser Reference:**
Different models require different parsers. Common parsers include: `qwen3_xml`, `openai`, `deepseek_v3`, `llama3_json`, `mistral`, `hermes`, `pythonic`, `xlam`. See [vLLM Tool Calling docs](https://docs.vllm.ai/en/latest/features/tool_calling/) for the complete list.

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


### Air-Gapped and Offline Environments

For environments without internet access (air-gapped, offline, or restricted networks), you can disable web search and fetch tools:

```bash
# Disable web tools for air-gapped environment
export PATCHPAL_ENABLE_WEB=false
patchpal

# Or combine with local models for complete offline operation
export PATCHPAL_ENABLE_WEB=false
patchpal --model ollama_chat/qwen2.5-coder:32b
```

When web tools are disabled:
- `web_search` and `web_fetch` are removed from available tools
- The agent won't attempt any network requests
- Perfect for secure, isolated, or offline development environments

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

Using model: anthropic/claude-sonnet-4-5

Type 'exit' or 'quit' to exit the program.
Ask 'list skills' to see available skills, or use /skillname to invoke one
Press Ctrl-C during agent execution to interrupt the agent.

You: Add type hints and basic logging to my_module.py
```

The agent will process your request and show you the results. You can continue with follow-up tasks or type `exit` to quit.

**Interactive Features:**
- **Path Autocompletion**: Press `Tab` while typing file paths to see suggestions (e.g., `./src/mo` + Tab → `./src/models.py`)
- **Skill Autocompletion**: Type `/` followed by Tab to see available skills (e.g., `/comm` + Tab → `/commit`)
- **Command History**: Use ↑ (up arrow) and ↓ (down arrow) to navigate through previous commands within the current session
- **Interrupt Agent**: Press `Ctrl-C` during agent execution to stop the current task without exiting PatchPal
- **Exit**: Type `exit`, `quit`, or press `Ctrl-C` at the prompt to exit PatchPal

## Example Tasks

```
Add type hints and basic logging to app.py
Fix the divide by zero error in calculator.py
Create unit tests for the utils module
Refactor the authentication code for better security
Add error handling to all API calls
Search for solutions to this error message: "ModuleNotFoundError: requests"
Find and implement best practices for async/await in Python
Look up the latest FastAPI documentation and add dependency injection
```

## Safety

The agent operates with a security model inspired by Claude Code:

- **Permission system**: User approval required for all shell commands and file modifications (can be customized)
- **Write boundary enforcement**: Write operations restricted to repository (matches Claude Code)
  - Read operations allowed anywhere (system files, libraries, debugging, automation)
  - Write operations outside repository require explicit permission
- **Privilege escalation blocking**: Platform-aware blocking of privilege escalation commands
  - Unix/Linux/macOS: `sudo`, `su`
  - Windows: `runas`, `psexec`
- **Dangerous pattern detection**: Blocks patterns like `> /dev/`, `rm -rf /`, `| dd`, `--force`
- **Timeout protection**: Shell commands timeout after 30 seconds

### Enhanced Security Guardrails ✅ FULLY ENABLED

PatchPal includes comprehensive security protections enabled by default:

**Critical Security:**
- **Permission prompts**: Agent asks for permission before executing commands or modifying files (like Claude Code)
- **Sensitive file protection**: Blocks access to `.env`, credentials, API keys
- **File size limits**: Prevents OOM with configurable size limits (10MB default)
- **Binary file detection**: Blocks reading non-text files
- **Critical file warnings**: Warns when modifying infrastructure files (package.json, Dockerfile, etc.)
- **Read-only mode**: Optional mode that prevents all modifications
- **Command timeout**: 30-second timeout on shell commands
- **Pattern-based blocking**: Blocks dangerous command patterns (`> /dev/`, `--force`, etc.)
- **Write boundary protection**: Restricts write operations to repository (reads allowed system-wide for automation/debugging)

**Operational Safety:**
- **Operation audit logging**: All file operations and commands logged to `~/.patchpal/<repo-name>/audit.log` (enabled by default)
- **Automatic backups**: Optional auto-backup of files to `~/.patchpal/<repo-name>/backups/` before modification
- **Resource limits**: Configurable operation counter prevents infinite loops (1000 operations default)
- **Git state awareness**: Warns when modifying files with uncommitted changes

**Configuration via environment variables:**
```bash
# Critical Security Controls
export PATCHPAL_REQUIRE_PERMISSION=true  # Prompt for permission before executing commands/modifying files (default: true)
                                          # Set to false to disable prompts (not recommended for production use)
export PATCHPAL_MAX_FILE_SIZE=5242880     # Maximum file size in bytes for read/write operations (default: 10485760 = 10MB)
export PATCHPAL_READ_ONLY=true            # Prevent all file modifications, analysis-only mode (default: false)
                                           # Useful for: code review, exploration, security audits, CI/CD analysis, or trying PatchPal risk-free
export PATCHPAL_ALLOW_SENSITIVE=true      # Allow access to .env, credentials, API keys (default: false - blocked for safety)
                                           # Only enable when working with test/dummy credentials or intentionally managing config files

# Operational Safety Controls
export PATCHPAL_AUDIT_LOG=false           # Log all operations to ~/.patchpal/<repo-name>/audit.log (default: true)
export PATCHPAL_ENABLE_BACKUPS=true       # Auto-backup files to ~/.patchpal/<repo-name>/backups/ before modification (default: false)
export PATCHPAL_MAX_OPERATIONS=5000       # Maximum operations per session to prevent infinite loops (default: 1000)
export PATCHPAL_MAX_ITERATIONS=150        # Maximum agent iterations per task (default: 100)
                                          # Increase for very complex multi-file tasks, decrease for testing

# Web Tool Controls
export PATCHPAL_ENABLE_WEB=false          # Enable/disable web search and fetch tools (default: true)
                                          # Set to false for air-gapped or offline environments
export PATCHPAL_WEB_TIMEOUT=60            # Timeout for web requests in seconds (default: 30)
export PATCHPAL_MAX_WEB_SIZE=10485760     # Maximum web content size in bytes (default: 5242880 = 5MB)
export PATCHPAL_MAX_WEB_CHARS=500000      # Maximum characters from web content to prevent context overflow (default: 500000 ≈ 125k tokens)
```

**Permission System:**

When the agent wants to execute a command or modify a file, you'll see a prompt like:

```
================================================================================
Run Shell
--------------------------------------------------------------------------------
   pytest tests/test_cli.py -v
--------------------------------------------------------------------------------

Do you want to proceed?
  1. Yes
  2. Yes, and don't ask again for 'pytest' in this repository
  3. No

Choice [1-3]:
```

- Option 1: Allow this one operation
- Option 2: Allow and remember (saves permission to `~/.patchpal/<repo-name>/permissions.json`)
- Option 3: Cancel the operation

Permissions are stored per-repository and persist across sessions. You can edit `~/.patchpal/<repo-name>/permissions.json` to manage saved permissions.

<!--**Test coverage:** 131 tests including 38 dedicated security tests and 11 skills tests-->

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
├── __init__.py       - Package exports
├── tools.py          - Tool implementations (file ops, grep, web, shell)
├── agent.py          - Agent configuration and tool orchestration
├── permissions.py    - Permission management system
└── cli.py            - CLI entry point

tests/
├── __init__.py                   - Test package
├── test_tools.py                 - Tests for tools module (42 tests)
├── test_agent.py                 - Tests for agent module (15 tests)
├── test_cli.py                   - Tests for CLI module (14 tests)
├── test_guardrails.py            - Security guardrail tests (20 tests)
└── test_operational_safety.py    - Operational safety tests (18 tests)
```

## Troubleshooting

**Error: "maximum iterations reached"**
- The default number of iterations is 100.
- You can increase by setting the environment variable, `export PATCHPAL_MAX_ITERATIONS`
