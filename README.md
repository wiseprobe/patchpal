# PatchPal - A Lean Claude Code Clone in Python

<!--![PatchPal Screenshot](patchpal_screenshot.png)-->
<img src="patchpal_screenshot.png" alt="PatchPal Screenshot" width="650"/>

> A lightweight clone of Claude Code in Python -- supports both local and cloud LLMs.

A key goal of this project is to approximate Claude Code's core functionality while remaining lightweight, accessible, and configurable, enabling learning, experimentation, and broad applicability across use cases.


```bash
$ls ./patchpal
__init__.py agent.py  cli.py  permissions.py  skills.py system_prompt.md tools.py
```

## Installation

Install PatchPal from PyPI:

```bash
pip install patchpal
```

**Recommended Operating Systems:** Linux, Windows Subsystem for Linux ([WSL](https://learn.microsoft.com/en-us/windows/wsl/install)), and MacOS are the recommended OS environments. Running PatchPal direcly on a Windows 11 OS should also work but is not thoroughly tested.


## Setup


1. **Get an API key or a Local LLM Engine**:
   - **[Cloud]** For Anthropic models (default): Sign up at https://console.anthropic.com/
   - **[Cloud]** For OpenAI models: Get a key from https://platform.openai.com/
   - **[Local]** For vLLM: Install from https://docs.vllm.ai/ (free - no API charges) **Recommended for Local Use**
   - **[Local]** For Ollama: Install from https://ollama.com/ (⚠️ not well-suited for agents - use vLLM)
   - For other providers: Check the [LiteLLM documentation](https://docs.litellm.ai/docs/providers)

2. **Set up your API key as environment variable**:
```bash

# For Anthropic (default)
export ANTHROPIC_API_KEY=your_api_key_here

# For OpenAI
export OPENAI_API_KEY=your_api_key_here

# For vLLM - API key required only if configured
export HOSTED_VLLM_API_BASE=http://localhost:8000 # depends on your vLLM setup
export HOSTED_VLLM_API_KEY=token-abc123           # optional depending on your vLLM setup

# For other providers, check LiteLLM docs
```

3. **Run PatchPal**:
```bash
# Use default model (anthropic/claude-sonnet-4-5)
patchpal

# Use a specific model via command-line argument
patchpal --model openai/gpt-5  # or openai/gpt-4o, anthropic/claude-opus-4-5 etc.

# Use vLLM (local)
# Note: vLLM server must be started with --tool-call-parser and --enable-auto-tool-choice
# See "Using Local Models (vLLM & Ollama)" section below for details
export HOSTED_VLLM_API_BASE=http://localhost:8000
export HOSTED_VLLM_API_KEY=token-abc123
patchpal --model hosted_vllm/openai/gpt-oss-20b

# Use Ollama (local, ⚠️ not recommended - use vLLM)
patchpal --model ollama_chat/qwen3:32b # vLLM is better for agents

# Or set the model via environment variable
export PATCHPAL_MODEL=openai/gpt-5
patchpal
```

## Features

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

The PatchPal repository includes [example skills](https://github.com/amaiya/patchpal/tree/main/examples) you can use as templates:
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

You can also try out the example skills at [anthropic/skills](https://github.com/anthropics/skills).


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
patchpal --model openai/gpt-5
patchpal --model anthropic/claude-sonnet-4-5
patchpal --model hosted_vllm/openai/gpt-oss-20b # local model - no API charges
```

### 2. Environment Variable
```bash
export PATCHPAL_MODEL=openai/gpt-5
patchpal
```

### 3. Default Model
If no model is specified, PatchPal uses `anthropic/claude-sonnet-4-5` (Claude Sonnet 4.5).

### Supported Models

PatchPal works with any model supported by LiteLLM, including:

- **Anthropic** (Recommended): `anthropic/claude-sonnet-4-5`, `anthropic/claude-opus-4-5`, `anthropic/claude-3-7-sonnet-latest`
- **OpenAI**: `openai/gpt-5`, `openai/gpt-4o`
- **AWS Bedrock**: `bedrock/anthropic.claude-sonnet-4-5-v1:0`, or full ARNs for GovCloud/VPC endpoints
- **vLLM (Local)** (Recommended for local): See vLLM section below for setup
- **Ollama (Local)**:  See Ollama section below for setup
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

### Using Local Models (vLLM & Ollama)

Run models locally on your machine without needing API keys or internet access.

**⚠️ IMPORTANT: For local models, we recommend vLLM.**

vLLM provides:
- ✅ Robust multi-turn tool calling
- ✅ 3-10x faster inference than Ollama
- ✅ Production-ready reliability

#### vLLM (Recommended for Local Models)

vLLM is significantly faster than Ollama due to optimized inference with continuous batching and PagedAttention.

**Important:** vLLM >= 0.10.2 is required for proper tool calling support.

**Using Local vLLM Server:**

```bash
# 1. Install vLLM (>= 0.10.2)
pip install vllm

# 2. Start vLLM server with tool calling enabled
vllm serve openai/gpt-oss-20b \
  --dtype auto \
  --api-key token-abc123 \
  --tool-call-parser openai \
  --enable-auto-tool-choice

# 3. Use with PatchPal (in another terminal)
export HOSTED_VLLM_API_BASE=http://localhost:8000
export HOSTED_VLLM_API_KEY=token-abc123
patchpal --model hosted_vllm/openai/gpt-oss-20b
```

**Using Remote/Hosted vLLM Server:**

```bash
# For remote vLLM servers (e.g., hosted by your organization)
export HOSTED_VLLM_API_BASE=https://your-vllm-server.com
export HOSTED_VLLM_API_KEY=your_api_key_here
patchpal --model hosted_vllm/openai/gpt-oss-20b
```

**Environment Variables:**
- Use `HOSTED_VLLM_API_BASE` and `HOSTED_VLLM_API_KEY`

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
export HOSTED_VLLM_API_BASE=http://localhost:8000
export HOSTED_VLLM_API_KEY=token-abc123
patchpal --model hosted_vllm/openai/gpt-oss-20b
```

**Recommended models for vLLM:**
- `openai/gpt-oss-20b` - OpenAI's open-source model (use parser: `openai`)

**Tool Call Parser Reference:**
Different models require different parsers. Common parsers include: `qwen3_xml`, `openai`, `deepseek_v3`, `llama3_json`, `mistral`, `hermes`, `pythonic`, `xlam`. See [vLLM Tool Calling docs](https://docs.vllm.ai/en/latest/features/tool_calling/) for the complete list.

#### Ollama

We find that Ollama models do not work well in agentic settings. For instance, while [gpt-oss-20b](https://huggingface.co/openai/gpt-oss-20b) works well in vLLM, the [Ollama versison](https://ollama.com/library/gpt-oss) of the same model performs poorly. vLLM is recommended for local deployments.

**Examples:**

```bash
patchpal --model ollama_chat/qwen3:32b          # local model: performs poorly
patchpal --model ollama_chat/gpt-oss:20b        # local model: performs poorly
patchpal --model hosted_vllm/openai/gpt-oss-20b # local model: performs well
```

### Air-Gapped and Offline Environments

For environments without internet access (air-gapped, offline, or restricted networks), you can disable web search and fetch tools:

```bash
# Disable web tools for air-gapped environment
export PATCHPAL_ENABLE_WEB=false
patchpal

# Or combine with local vLLM for complete offline operation (recommended)
export PATCHPAL_ENABLE_WEB=false
export HOSTED_VLLM_API_BASE=http://localhost:8000
export HOSTED_VLLM_API_KEY=token-abc123
patchpal --model hosted_vllm/openai/gpt-oss-20b
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

Type 'exit' or press Ctrl-C to quit.
Use 'list skills' or /skillname to invoke skills.
Press Ctrl-C during execution to interrupt the agent.

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
- **Write boundary protection**: Requires permission for write operations

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

# Customization
export PATCHPAL_SYSTEM_PROMPT=~/.patchpal/my_prompt.md  # Use custom system prompt file (default: built-in prompt)
                                                         # The file can use template variables like {current_date}, {platform_info}, etc.
                                                         # Useful for: custom agent behavior, team standards, domain-specific instructions

# Web Tool Controls
export PATCHPAL_ENABLE_WEB=false          # Enable/disable web search and fetch tools (default: true)
                                          # Set to false for air-gapped or offline environments
export PATCHPAL_WEB_TIMEOUT=60            # Timeout for web requests in seconds (default: 30)
export PATCHPAL_MAX_WEB_SIZE=10485760     # Maximum web content size in bytes (default: 5242880 = 5MB)
export PATCHPAL_MAX_WEB_CHARS=500000      # Maximum characters from web content to prevent context overflow (default: 500000 ≈ 125k tokens)

# Shell Command Controls
export PATCHPAL_SHELL_TIMEOUT=60          # Timeout for shell commands in seconds (default: 30)
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
  2. Yes, and don't ask again this session for 'pytest'
  3. No

Choice [1-3]:
```

- Option 1: Allow this one operation
- Option 2: Allow for the rest of this session (like Claude Code - resets when you restart PatchPal)
- Option 3: Cancel the operation

**Advanced:** You can manually edit `~/.patchpal/<repo-name>/permissions.json` to grant persistent permissions across sessions.

**Example permissions.json:**

```json
{
  "run_shell": ["pytest", "npm", "git"],
  "apply_patch": true,
  "edit_file": ["config.py", "settings.json"]
}
```

Format:
- `"tool_name": true` - Grant all operations for this tool (no more prompts)
- `"tool_name": ["pattern1", "pattern2"]` - Grant only specific patterns (e.g., specific commands or file names)

<!--**Test coverage:** 131 tests including 38 dedicated security tests and 11 skills tests-->

## Development

### Quick Start

Install in development mode with dev dependencies:

```bash
# Clone the repository
git clone https://github.com/amaiya/patchpal.git
cd patchpal

# Install in development mode
pip install -e ".[dev]"

# Set up pre-commit hooks (recommended)
pip install pre-commit
pre-commit install
```

### Pre-commit Hooks

Pre-commit hooks automatically check your code before each commit:

- **Black** - Auto-formats code to maintain consistent style
- **Ruff** - Lints and auto-fixes common issues
- **Trailing whitespace** - Removes trailing whitespace
- **End of file fixer** - Ensures files end with a newline
- **YAML validation** - Checks YAML syntax
- **Merge conflict detection** - Prevents committing merge conflicts

**Run pre-commit manually:**
```bash
# Run on all files
pre-commit run --all-files

# Run on staged files only
pre-commit run
```

**Skip pre-commit (not recommended):**
```bash
git commit --no-verify
```

### Code Quality Tools

**Format code with Black:**
```bash
# Auto-format
black patchpal tests

# Check without modifying
black --check patchpal tests
```

**Lint with Ruff:**
```bash
# Auto-fix issues
ruff check --fix patchpal tests

# Check without fixing
ruff check patchpal tests
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
