"""Custom agent implementation using LiteLLM directly."""

import os
import json
import platform
from datetime import datetime
from typing import Any, Dict, List, Optional
import litellm
from patchpal.tools import (
    read_file, list_files, apply_patch, run_shell, grep_code,
    web_fetch, web_search, get_file_info, edit_file,
    git_status, git_diff, git_log, find_files, tree
)


def _is_bedrock_arn(model_id: str) -> bool:
    """Check if a model ID is a Bedrock ARN."""
    return (
        model_id.startswith('arn:aws') and
        ':bedrock:' in model_id and
        ':inference-profile/' in model_id
    )


def _normalize_bedrock_model_id(model_id: str) -> str:
    """Normalize Bedrock model ID to ensure it has the bedrock/ prefix.

    Args:
        model_id: Model identifier, may or may not have bedrock/ prefix

    Returns:
        Model ID with bedrock/ prefix if it's a Bedrock model
    """
    # If it already has bedrock/ prefix, return as-is
    if model_id.startswith('bedrock/'):
        return model_id

    # If it looks like a Bedrock ARN, add the prefix
    if _is_bedrock_arn(model_id):
        return f'bedrock/{model_id}'

    # If it's a standard Bedrock model ID (e.g., anthropic.claude-v2)
    # Check if it looks like a Bedrock model format
    if '.' in model_id and any(provider in model_id for provider in ['anthropic', 'amazon', 'meta', 'cohere', 'ai21']):
        return f'bedrock/{model_id}'

    return model_id


def _setup_bedrock_env():
    """Set up Bedrock-specific environment variables for LiteLLM.

    Configures custom region and endpoint URL for AWS Bedrock (including GovCloud and VPC endpoints).
    Maps PatchPal's environment variables to LiteLLM's expected format.
    """
    # Set custom region (e.g., us-gov-east-1 for GovCloud)
    bedrock_region = os.getenv('AWS_BEDROCK_REGION')
    if bedrock_region and not os.getenv('AWS_REGION_NAME'):
        os.environ['AWS_REGION_NAME'] = bedrock_region

    # Set custom endpoint URL (e.g., VPC endpoint or GovCloud endpoint)
    bedrock_endpoint = os.getenv('AWS_BEDROCK_ENDPOINT')
    if bedrock_endpoint and not os.getenv('AWS_BEDROCK_RUNTIME_ENDPOINT'):
        os.environ['AWS_BEDROCK_RUNTIME_ENDPOINT'] = bedrock_endpoint


# Define tools in LiteLLM format
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file in the repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file from the repository root"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List all files in the repository (excludes hidden and binary files).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_info",
            "description": "Get detailed metadata for file(s) - size, modification time, type. Supports single files, directories, or glob patterns (e.g., 'tests/*.py').",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to file, directory, or glob pattern (e.g., 'tests/*.txt', 'src/', 'file.py')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_files",
            "description": "Find files by name pattern using glob-style wildcards (e.g., '*.py', 'test_*.txt', '**/*.md'). Faster than list_files when searching for specific file names.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match file names (e.g., '*.py' for Python files, 'test_*.py' for test files)"
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether to match case-sensitively (default: true)"
                    }
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "tree",
            "description": "Show directory tree structure to understand folder organization. Useful for getting an overview of the codebase structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Starting directory path (default: current directory '.')"
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth to traverse (default: 3, max: 10)"
                    },
                    "show_hidden": {
                        "type": "boolean",
                        "description": "Include hidden files/directories (default: false)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit a file by replacing an exact string. More efficient than apply_patch for small changes. The old_string must match exactly and appear only once.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file from the repository root"
                    },
                    "old_string": {
                        "type": "string",
                        "description": "The exact string to find and replace (must appear exactly once)"
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The string to replace it with"
                    }
                },
                "required": ["path", "old_string", "new_string"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": "Modify a file by replacing its contents. Returns a unified diff of changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path to the file from the repository root"
                    },
                    "new_content": {
                        "type": "string",
                        "description": "The complete new content for the file"
                    }
                },
                "required": ["path", "new_content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Get git repository status showing modified, staged, and untracked files. No permission required - read-only operation.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Get git diff to see changes. No permission required - read-only operation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Optional: specific file path to show diff for"
                    },
                    "staged": {
                        "type": "boolean",
                        "description": "If true, show staged changes (--cached), else show unstaged changes"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "Get git commit history. No permission required - read-only operation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_count": {
                        "type": "integer",
                        "description": "Maximum number of commits to show (default: 10, max: 50)"
                    },
                    "path": {
                        "type": "string",
                        "description": "Optional: specific file path to show history for"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "grep_code",
            "description": "Search for a pattern in repository files. Much faster than run_shell with grep. Returns results in 'file:line:content' format.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regular expression pattern to search for"
                    },
                    "file_glob": {
                        "type": "string",
                        "description": "Optional glob pattern to filter files (e.g., '*.py', 'src/**/*.js')"
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether the search should be case-sensitive (default: true)"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 100)"
                    }
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information. Useful for looking up error messages, documentation, best practices, or current information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5, max: 10)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch and read content from a URL. Useful for reading documentation, error references, or code examples.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch (must start with http:// or https://)"
                    },
                    "extract_text": {
                        "type": "boolean",
                        "description": "If true, extract readable text from HTML (default: true)"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a safe shell command in the repository. Dangerous commands (rm, mv, sudo, etc.) are blocked.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {
                        "type": "string",
                        "description": "The shell command to execute"
                    }
                },
                "required": ["cmd"]
            }
        }
    }
]

# Map tool names to functions
TOOL_FUNCTIONS = {
    "read_file": read_file,
    "list_files": list_files,
    "get_file_info": get_file_info,
    "find_files": find_files,
    "tree": tree,
    "edit_file": edit_file,
    "apply_patch": apply_patch,
    "git_status": git_status,
    "git_diff": git_diff,
    "git_log": git_log,
    "grep_code": grep_code,
    "web_search": web_search,
    "web_fetch": web_fetch,
    "run_shell": run_shell,
}

# Check if web tools should be disabled (for air-gapped environments)
WEB_TOOLS_ENABLED = os.getenv('PATCHPAL_ENABLE_WEB', 'true').lower() in ('true', '1', 'yes')

if not WEB_TOOLS_ENABLED:
    # Remove web tools from available tools
    TOOLS = [tool for tool in TOOLS if tool['function']['name'] not in ('web_search', 'web_fetch')]
    TOOL_FUNCTIONS = {k: v for k, v in TOOL_FUNCTIONS.items() if k not in ('web_search', 'web_fetch')}


# Detect platform and generate platform-specific guidance
os_name = platform.system()  # 'Linux', 'Darwin', 'Windows'

if os_name == 'Windows':
    PLATFORM_INFO = """## Platform: Windows
When using run_shell, use Windows commands:
- File operations: `dir`, `type`, `copy`, `move`, `del`, `mkdir`, `rmdir`
- Search: `where`, `findstr`
- Path format: Use backslashes `C:\\path\\file.txt` or forward slashes (both work)
- Chain commands with `&&`
"""
else:  # Linux or macOS
    PLATFORM_INFO = f"""## Platform: {os_name} (Unix-like)
When using run_shell, use Unix commands:
- File operations: `ls`, `cat`, `cp`, `mv`, `rm`, `mkdir`, `rmdir`
- Search: `grep`, `find`, `which`
- Path format: Forward slashes `/path/to/file.txt`
- Chain commands with `&&` or `;`
"""

# Build web tools description
WEB_TOOLS_DESC = ""
WEB_USAGE_DESC = ""
WEB_TOOLS_SCOPE = ""
if WEB_TOOLS_ENABLED:
    WEB_TOOLS_DESC = """- **web_search**: Search the web for information (error messages, documentation, best practices)
- **web_fetch**: Fetch and read content from a URL (documentation, examples, references)
"""
    WEB_USAGE_DESC = """
- Use web_search when you encounter unfamiliar errors, need documentation, or want to research solutions
- Use web_fetch to read specific documentation pages or references you find"""
    WEB_TOOLS_SCOPE = """- **Web access**: web_search, web_fetch
"""

SYSTEM_PROMPT = """You are an expert software engineer assistant helping with code tasks in a repository.

## Current Date and Time
Today is {current_date}. Current time is {current_time}.

{platform_info}

# Available Tools

- **read_file**: Read the contents of any file in the repository
- **list_files**: List all files in the repository
- **get_file_info**: Get metadata for file(s) - size, type, modified time (supports globs like '*.py')
- **find_files**: Find files by name pattern using glob wildcards (e.g., '*.py', 'test_*.txt')
- **tree**: Show directory tree structure to understand folder organization
- **edit_file**: Edit a file by replacing an exact string (more efficient than apply_patch for small changes)
- **apply_patch**: Modify a file by providing the complete new content
- **git_status**: Get git status (modified, staged, untracked files) - no permission required
- **git_diff**: Get git diff to see changes - no permission required
- **git_log**: Get git commit history - no permission required
- **grep_code**: Search for patterns in code files (faster than run_shell with grep)
{web_tools}- **run_shell**: Run shell commands (requires permission; privilege escalation blocked)

## Tool Overview and Scope

You are a LOCAL CODE ASSISTANT focused on file navigation and code understanding. Your tools are organized into:

- **File navigation/reading**: read_file, list_files, find_files, tree, get_file_info
- **Code search**: grep_code
- **File modification**: edit_file, apply_patch
- **Git operations**: git_status, git_diff, git_log (read-only, no permission needed)
{web_tools_scope_desc}- **Shell execution**: run_shell (safety-restricted, requires permission)

When suggesting improvements or new tools, focus on gaps in LOCAL file operations and code navigation. This is NOT an enterprise DevOps platform - avoid suggesting CI/CD integrations, project management tools, dependency scanners, or cloud service integrations.

# Core Principles

## Professional Objectivity
Prioritize technical accuracy and truthfulness over validating the user's beliefs. Focus on facts and problem-solving. Provide direct, objective technical information without unnecessary superlatives or excessive praise. Apply rigorous standards to all ideas and disagree when necessary, even if it may not be what the user wants to hear.

## Read Before Modifying
NEVER propose changes to code you haven't read. If a user asks about or wants you to modify a file, read it first. Always understand existing code before suggesting modifications.

## Avoid Over-Engineering
Only make changes that are directly requested or clearly necessary. Keep solutions simple and focused.

- Don't add features, refactor code, or make "improvements" beyond what was asked
- A bug fix doesn't need surrounding code cleaned up
- A simple feature doesn't need extra configurability
- Don't add docstrings, comments, or type annotations to code you didn't change
- Only add comments where the logic isn't self-evident
- Don't add error handling, fallbacks, or validation for scenarios that can't happen
- Trust internal code and framework guarantees
- Only validate at system boundaries (user input, external APIs)
- Don't create helpers, utilities, or abstractions for one-time operations
- Don't design for hypothetical future requirements
- Three similar lines of code is better than a premature abstraction

## Avoid Backwards-Compatibility Hacks
Avoid backwards-compatibility hacks like renaming unused variables with `_`, re-exporting types, adding `// removed` comments for removed code, etc. If something is unused, delete it completely.

## Security Awareness
Be careful not to introduce security vulnerabilities such as command injection, XSS, SQL injection, and other OWASP top 10 vulnerabilities. If you notice insecure code, immediately fix it.

# How to Approach Tasks

## For Software Engineering Tasks
The user will primarily request software engineering tasks like solving bugs, adding functionality, refactoring code, or explaining code.

1. **Understand First**: Use read_file and list_files to understand the codebase before making changes
2. **Plan Carefully**: Think through the minimal changes needed
3. **Make Focused Changes**: Use apply_patch to update files with complete new content
4. **Test When Appropriate**: Use run_shell to test changes (run tests, check builds, etc.)
5. **Explain Your Actions**: Describe what you're doing and why

## Tool Usage Guidelines

- Use tree to get a quick overview of directory structure
- Use list_files to explore all files in the repository
- Use find_files to locate specific files by name pattern (e.g., '*.py', 'test_*.txt')
- Use get_file_info to check file metadata (size, type, timestamps) - supports globs
- Use grep_code to search for patterns in file contents (preferred over run_shell with grep)
- Use read_file to examine specific files before modifying them
- For modifications:
  - Use edit_file for small, targeted changes (replacing a specific string)
  - Use apply_patch for larger changes or when rewriting significant portions
- Use git_status, git_diff, git_log to understand repository state (no permission needed){web_usage}
- Use run_shell only when no dedicated tool exists (requires permission)
- Never use run_shell for file operations or git commands - dedicated tools are available

## Code References
When referencing specific functions or code, include the pattern `file_path:line_number` to help users navigate.

Example: "The authentication logic is in src/auth.py:45"

## Response Quality Examples

**Good tool suggestions** (specific, actionable, within scope):
- "Consider find_files for glob-based file search"
- "A code_outline tool showing function/class signatures would help navigate large files"
- "A git_blame tool would help understand code history"

**Bad tool suggestions** (generic, out of scope, enterprise features):
- "Add CI/CD pipeline integration"
- "Integrate with Jira for project management"
- "Add automated security scanning"

**Good responses to user questions**:
- Use tools to gather information, then synthesize a clear answer
- Be specific and cite file locations with line numbers
- Provide actionable next steps

**Bad responses**:
- Return raw tool output without interpretation
- Give generic advice without checking the codebase
- Suggest hypothetical features without grounding in actual code

# Important Notes

- Stop when the task is complete - don't continue working unless asked
- If you're unsure about requirements, ask for clarification
- Focus on what needs to be done, not when (don't suggest timelines)
- Maintain consistency with the existing codebase style and patterns"""

# Get current date and time
now = datetime.now()
current_date = now.strftime("%A, %B %d, %Y")  # e.g., "Wednesday, January 15, 2026"
current_time = now.strftime("%I:%M %p %Z").strip()  # e.g., "03:45 PM EST"
if not current_time.endswith(('EST', 'CST', 'MST', 'PST', 'UTC')):
    # If no timezone abbreviation, just show time without timezone
    current_time = now.strftime("%I:%M %p").strip()

# Substitute platform information, date/time, and web tools into the system prompt
SYSTEM_PROMPT = SYSTEM_PROMPT.format(
    platform_info=PLATFORM_INFO,
    current_date=current_date,
    current_time=current_time,
    web_tools=WEB_TOOLS_DESC,
    web_usage=WEB_USAGE_DESC,
    web_tools_scope_desc=WEB_TOOLS_SCOPE
)


class PatchPalAgent:
    """Simple agent that uses LiteLLM for tool calling."""

    def __init__(self, model_id: str = "anthropic/claude-sonnet-4-5"):
        """Initialize the agent.

        Args:
            model_id: LiteLLM model identifier
        """
        self.model_id = _normalize_bedrock_model_id(model_id)

        # Set up Bedrock environment if needed
        if self.model_id.startswith('bedrock/'):
            _setup_bedrock_env()

        # Conversation history (list of message dicts)
        self.messages: List[Dict[str, Any]] = []

        # LiteLLM settings for Bedrock
        self.litellm_kwargs = {}
        if self.model_id.startswith('bedrock/'):
            self.litellm_kwargs['drop_params'] = True

    def run(self, user_message: str, max_iterations: int = 100) -> str:
        """Run the agent on a user message.

        Args:
            user_message: The user's request
            max_iterations: Maximum number of agent iterations (default: 100)

        Returns:
            The agent's final response
        """
        # Add user message to history
        self.messages.append({
            "role": "user",
            "content": user_message
        })

        # Agent loop
        for iteration in range(max_iterations):
            # Show thinking message
            print("\033[2m🤔 Thinking...\033[0m", flush=True)

            # Call LiteLLM with tools
            try:
                response = litellm.completion(
                    model=self.model_id,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self.messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    **self.litellm_kwargs
                )
            except Exception as e:
                return f"Error calling model: {e}"

            # Get the assistant's response
            assistant_message = response.choices[0].message

            # Add assistant message to history
            self.messages.append({
                "role": "assistant",
                "content": assistant_message.content or "",
                "tool_calls": assistant_message.tool_calls if hasattr(assistant_message, 'tool_calls') and assistant_message.tool_calls else None
            })

            # Check if there are tool calls
            if hasattr(assistant_message, 'tool_calls') and assistant_message.tool_calls:
                # Execute each tool call
                for tool_call in assistant_message.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args_str = tool_call.function.arguments

                    # Parse arguments
                    try:
                        tool_args = json.loads(tool_args_str)
                    except json.JSONDecodeError:
                        tool_result = f"Error: Invalid JSON arguments for {tool_name}"
                        print(f"\033[1;31m✗ {tool_name}: Invalid arguments\033[0m")
                    else:
                        # Get the tool function
                        tool_func = TOOL_FUNCTIONS.get(tool_name)
                        if tool_func is None:
                            tool_result = f"Error: Unknown tool {tool_name}"
                            print(f"\033[1;31m✗ Unknown tool: {tool_name}\033[0m")
                        else:
                            # Show tool call message
                            tool_display = tool_name.replace('_', ' ').title()
                            if tool_name == 'read_file':
                                print(f"\033[2m📖 Reading: {tool_args.get('path', '')}\033[0m", flush=True)
                            elif tool_name == 'list_files':
                                print(f"\033[2m📁 Listing files...\033[0m", flush=True)
                            elif tool_name == 'get_file_info':
                                print(f"\033[2m📊 Getting info: {tool_args.get('path', '')}\033[0m", flush=True)
                            elif tool_name == 'edit_file':
                                print(f"\033[2m✏️  Editing: {tool_args.get('path', '')}\033[0m", flush=True)
                            elif tool_name == 'apply_patch':
                                print(f"\033[2m📝 Patching: {tool_args.get('path', '')}\033[0m", flush=True)
                            elif tool_name == 'git_status':
                                print(f"\033[2m🔀 Git status...\033[0m", flush=True)
                            elif tool_name == 'git_diff':
                                print(f"\033[2m🔀 Git diff{': ' + tool_args.get('path', '') if tool_args.get('path') else '...'}\033[0m", flush=True)
                            elif tool_name == 'git_log':
                                print(f"\033[2m🔀 Git log...\033[0m", flush=True)
                            elif tool_name == 'grep_code':
                                print(f"\033[2m🔍 Searching: {tool_args.get('pattern', '')}\033[0m", flush=True)
                            elif tool_name == 'find_files':
                                print(f"\033[2m🔍 Finding: {tool_args.get('pattern', '')}\033[0m", flush=True)
                            elif tool_name == 'tree':
                                print(f"\033[2m🌳 Tree: {tool_args.get('path', '.')}\033[0m", flush=True)
                            elif tool_name == 'web_search':
                                print(f"\033[2m🌐 Searching web: {tool_args.get('query', '')}\033[0m", flush=True)
                            elif tool_name == 'web_fetch':
                                print(f"\033[2m🌐 Fetching: {tool_args.get('url', '')}\033[0m", flush=True)
                            elif tool_name == 'run_shell':
                                print(f"\033[2m⚡ Running: {tool_args.get('cmd', '')}\033[0m", flush=True)

                            # Execute the tool (permission checks happen inside the tool)
                            try:
                                tool_result = tool_func(**tool_args)
                            except Exception as e:
                                tool_result = f"Error executing {tool_name}: {e}"
                                print(f"\033[1;31m✗ {tool_display}: {e}\033[0m")

                    # Add tool result to messages
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": str(tool_result)
                    })

                    # Check if operation was cancelled by user
                    # Use exact match to avoid false positives from file contents
                    if str(tool_result).strip() == "Operation cancelled by user.":
                        # Return immediately - don't continue agent loop
                        return str(tool_result)

                # Continue loop to let agent process tool results
                continue
            else:
                # No tool calls, agent is done
                return assistant_message.content or "Task completed"

        # Max iterations reached
        return (
            f"Maximum iterations ({max_iterations}) reached. Task may be incomplete.\n\n"
            "💡 Tip: Type 'continue' or 'please continue' to resume where I left off, "
            "or provide more specific instructions."
        )


def create_agent(model_id: str = "anthropic/claude-sonnet-4-5") -> PatchPalAgent:
    """Create and return a PatchPal agent.

    Args:
        model_id: LiteLLM model identifier (default: anthropic/claude-sonnet-4-5)

    Returns:
        A configured PatchPalAgent instance
    """
    return PatchPalAgent(model_id=model_id)
