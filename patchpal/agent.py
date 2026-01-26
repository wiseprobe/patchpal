"""Custom agent implementation using LiteLLM directly."""

import inspect
import json
import os
import platform
from datetime import datetime
from typing import Any, Dict, List

import litellm
from rich.console import Console
from rich.markdown import Markdown

from patchpal.context import ContextManager
from patchpal.tools import (
    apply_patch,
    edit_file,
    find_files,
    get_file_info,
    git_diff,
    git_log,
    git_status,
    grep_code,
    list_files,
    list_skills,
    read_file,
    read_lines,
    run_shell,
    tree,
    use_skill,
    web_fetch,
    web_search,
)


def _is_bedrock_arn(model_id: str) -> bool:
    """Check if a model ID is a Bedrock ARN."""
    return (
        model_id.startswith("arn:aws")
        and ":bedrock:" in model_id
        and ":inference-profile/" in model_id
    )


def _normalize_bedrock_model_id(model_id: str) -> str:
    """Normalize Bedrock model ID to ensure it has the bedrock/ prefix.

    Args:
        model_id: Model identifier, may or may not have bedrock/ prefix

    Returns:
        Model ID with bedrock/ prefix if it's a Bedrock model
    """
    # If it already has bedrock/ prefix, return as-is
    if model_id.startswith("bedrock/"):
        return model_id

    # If it looks like a Bedrock ARN, add the prefix
    if _is_bedrock_arn(model_id):
        return f"bedrock/{model_id}"

    # If it's a standard Bedrock model ID (e.g., anthropic.claude-v2)
    # Check if it looks like a Bedrock model format
    if "." in model_id and any(
        provider in model_id for provider in ["anthropic", "amazon", "meta", "cohere", "ai21"]
    ):
        return f"bedrock/{model_id}"

    return model_id


def _setup_bedrock_env():
    """Set up Bedrock-specific environment variables for LiteLLM.

    Configures custom region and endpoint URL for AWS Bedrock (including GovCloud and VPC endpoints).
    Maps PatchPal's environment variables to LiteLLM's expected format.
    """
    # Set custom region (e.g., us-gov-east-1 for GovCloud)
    bedrock_region = os.getenv("AWS_BEDROCK_REGION")
    if bedrock_region and not os.getenv("AWS_REGION_NAME"):
        os.environ["AWS_REGION_NAME"] = bedrock_region

    # Set custom endpoint URL (e.g., VPC endpoint or GovCloud endpoint)
    bedrock_endpoint = os.getenv("AWS_BEDROCK_ENDPOINT")
    if bedrock_endpoint and not os.getenv("AWS_BEDROCK_RUNTIME_ENDPOINT"):
        os.environ["AWS_BEDROCK_RUNTIME_ENDPOINT"] = bedrock_endpoint


# Define tools in LiteLLM format
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. Can read files anywhere on the system (repository files, system configs like /etc/fstab, logs, etc.) for automation and debugging. Sensitive files (.env, credentials) are blocked for safety.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file - can be relative to repository root or an absolute path (e.g., /etc/fstab, /var/log/app.log)",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_lines",
            "description": "Read specific lines from a file without loading the entire file. Useful for viewing code sections, error context, or specific regions of large files. More efficient than read_file when you only need a few lines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file - can be relative to repository root or an absolute path",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number (1-indexed)",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Ending line number (inclusive, 1-indexed). If omitted, reads only start_line",
                    },
                },
                "required": ["path", "start_line"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List ALL files in the ENTIRE repository - no filtering by directory. This tool shows every file across all folders. To list files in a specific directory, use the 'tree' tool with a path parameter instead.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_info",
            "description": "Get detailed metadata for file(s) - size, modification time, type. Works with any file on the system. Supports single files, directories, or glob patterns (e.g., 'tests/*.py', '/etc/*.conf').",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to file, directory, or glob pattern - can be relative or absolute (e.g., 'tests/*.txt', '/var/log/', '/etc/fstab')",
                    }
                },
                "required": ["path"],
            },
        },
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
                        "description": "Glob pattern to match file names (e.g., '*.py' for Python files, 'test_*.py' for test files)",
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether to match case-sensitively (default: true)",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tree",
            "description": "Show directory tree structure for a specific directory path. Use this to list files in a particular folder (e.g., './tests', 'src/components'). Works with any directory on the system - repository folders, /etc, /var/log, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Starting directory path - can be relative or absolute (default: current directory '.', examples: '/etc', '/var/log', 'src')",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth to traverse (default: 3, max: 10)",
                    },
                    "show_hidden": {
                        "type": "boolean",
                        "description": "Include hidden files/directories (default: false)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit a file by replacing an exact string. More efficient than apply_patch for small changes. Primarily for repository files. Writing outside repository requires explicit user permission. The old_string must match exactly and appear only once.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file - relative to repository root or absolute path (note: writes outside repository require permission)",
                    },
                    "old_string": {
                        "type": "string",
                        "description": "The exact string to find and replace (must appear exactly once)",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The string to replace it with",
                    },
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": "Modify a file by replacing its contents. Primarily for repository files. Writing outside repository requires explicit user permission. Returns a unified diff of changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file - relative to repository root or absolute path (note: writes outside repository require permission)",
                    },
                    "new_content": {
                        "type": "string",
                        "description": "The complete new content for the file",
                    },
                },
                "required": ["path", "new_content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Get git repository status showing modified, staged, and untracked files. No permission required - read-only operation.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
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
                        "description": "Optional: specific file path to show diff for",
                    },
                    "staged": {
                        "type": "boolean",
                        "description": "If true, show staged changes (--cached), else show unstaged changes",
                    },
                },
                "required": [],
            },
        },
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
                        "description": "Maximum number of commits to show (default: 10, max: 50)",
                    },
                    "path": {
                        "type": "string",
                        "description": "Optional: specific file path to show history for",
                    },
                },
                "required": [],
            },
        },
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
                        "description": "Regular expression pattern to search for",
                    },
                    "file_glob": {
                        "type": "string",
                        "description": "Optional glob pattern to filter files (e.g., '*.py', 'src/**/*.js')",
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether the search should be case-sensitive (default: true)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 100)",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information. Requires permission to prevent information leakage about your codebase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5, max: 10)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch and read content from a URL. Requires permission to prevent information leakage about your codebase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch (must start with http:// or https://)",
                    },
                    "extract_text": {
                        "type": "boolean",
                        "description": "If true, extract readable text from HTML (default: true)",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_skills",
            "description": "List all available skills. When telling users about skills, instruct them to use /skillname syntax (e.g., /commit).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "use_skill",
            "description": "Invoke a skill programmatically when it's relevant to the user's request. Note: Users invoke skills via /skillname at the CLI, not by calling tools.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Name of the skill to invoke (without / prefix)",
                    },
                    "args": {
                        "type": "string",
                        "description": "Optional arguments to pass to the skill",
                    },
                },
                "required": ["skill_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a safe shell command in the repository. Privilege escalation (sudo, su) blocked by default unless PATCHPAL_ALLOW_SUDO=true.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {"type": "string", "description": "The shell command to execute"}
                },
                "required": ["cmd"],
            },
        },
    },
]

# Map tool names to functions
TOOL_FUNCTIONS = {
    "read_file": read_file,
    "read_lines": read_lines,
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
    "list_skills": list_skills,
    "use_skill": use_skill,
    "run_shell": run_shell,
}

# Check if web tools should be disabled (for air-gapped environments)
WEB_TOOLS_ENABLED = os.getenv("PATCHPAL_ENABLE_WEB", "true").lower() in ("true", "1", "yes")

if not WEB_TOOLS_ENABLED:
    # Remove web tools from available tools
    TOOLS = [tool for tool in TOOLS if tool["function"]["name"] not in ("web_search", "web_fetch")]
    TOOL_FUNCTIONS = {
        k: v for k, v in TOOL_FUNCTIONS.items() if k not in ("web_search", "web_fetch")
    }


# Detect platform and generate platform-specific guidance
os_name = platform.system()  # 'Linux', 'Darwin', 'Windows'

if os_name == "Windows":
    PLATFORM_INFO = """## Platform: Windows
When using run_shell, use Windows commands:
- File operations: `dir`, `type`, `copy`, `move`, `del`, `mkdir`, `rmdir`
- Search: `where`, `findstr`
- Path format: Use backslashes `C:\\path\\to\\file.txt`
  - For relative paths: Use `.\\Documents` NOT `./Documents`
  - For current directory: Use `.` or omit the path prefix
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


def _load_system_prompt() -> str:
    """Load system prompt from markdown file and substitute dynamic values.

    Checks PATCHPAL_SYSTEM_PROMPT environment variable for a custom prompt file path.
    If not set, uses the default system_prompt.md in the patchpal package directory.

    Returns:
        The formatted system prompt string
    """
    # Check for custom system prompt path from environment variable
    custom_prompt_path = os.getenv("PATCHPAL_SYSTEM_PROMPT")

    if custom_prompt_path:
        # Use custom prompt file
        prompt_path = os.path.expanduser(custom_prompt_path)
        if not os.path.isfile(prompt_path):
            print(
                f"\033[1;33m⚠️  Warning: Custom system prompt file not found: {prompt_path}\033[0m"
            )
            print("\033[1;33m   Falling back to default system prompt.\033[0m\n")
            # Fall back to default
            prompt_path = os.path.join(os.path.dirname(__file__), "system_prompt.md")
    else:
        # Use default prompt from package directory
        prompt_path = os.path.join(os.path.dirname(__file__), "system_prompt.md")

    # Read the prompt template
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    # Get current date and time
    now = datetime.now()
    current_date = now.strftime("%A, %B %d, %Y")  # e.g., "Wednesday, January 15, 2026"
    current_time = now.strftime("%I:%M %p %Z").strip()  # e.g., "03:45 PM EST"
    if not current_time.endswith(("EST", "CST", "MST", "PST", "UTC")):
        # If no timezone abbreviation, just show time without timezone
        current_time = now.strftime("%I:%M %p").strip()

    # Prepare template variables
    template_vars = {
        "platform_info": PLATFORM_INFO,
        "current_date": current_date,
        "current_time": current_time,
        "web_tools": WEB_TOOLS_DESC,
        "web_usage": WEB_USAGE_DESC,
        "web_tools_scope_desc": WEB_TOOLS_SCOPE,
    }

    # Substitute variables - gracefully handle missing variables
    # This allows custom prompts to omit variables they don't need
    try:
        return prompt_template.format(**template_vars)
    except KeyError as e:
        # Missing variable in template - warn but continue with partial substitution
        print(f"\033[1;33m⚠️  Warning: System prompt references undefined variable: {e}\033[0m")
        print(f"\033[1;33m   Available variables: {', '.join(template_vars.keys())}\033[0m")
        print("\033[1;33m   Attempting partial substitution...\033[0m\n")

        # Try to substitute what we can by replacing unmatched placeholders with empty strings
        result = prompt_template
        for key, value in template_vars.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result
    except Exception as e:
        print(f"\033[1;33m⚠️  Warning: Error processing system prompt template: {e}\033[0m")
        print("\033[1;33m   Using prompt as-is without variable substitution.\033[0m\n")
        return prompt_template


# Load the system prompt at module initialization
SYSTEM_PROMPT = _load_system_prompt()


class PatchPalAgent:
    """Simple agent that uses LiteLLM for tool calling."""

    def __init__(self, model_id: str = "anthropic/claude-sonnet-4-5"):
        """Initialize the agent.

        Args:
            model_id: LiteLLM model identifier
        """
        # Convert ollama/ to ollama_chat/ for LiteLLM compatibility
        if model_id.startswith("ollama/"):
            model_id = model_id.replace("ollama/", "ollama_chat/", 1)

        self.model_id = _normalize_bedrock_model_id(model_id)

        # Register Ollama models as supporting native function calling
        # LiteLLM defaults to JSON mode if not explicitly registered
        if self.model_id.startswith("ollama_chat/"):
            # Suppress verbose output from register_model
            import sys
            from io import StringIO

            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                litellm.register_model(
                    {"model_cost": {self.model_id: {"supports_function_calling": True}}}
                )
            finally:
                sys.stdout = old_stdout

        # Set up Bedrock environment if needed
        if self.model_id.startswith("bedrock/"):
            _setup_bedrock_env()

        # Conversation history (list of message dicts)
        self.messages: List[Dict[str, Any]] = []

        # Initialize context manager
        self.context_manager = ContextManager(self.model_id, SYSTEM_PROMPT)

        # Check if auto-compaction is enabled (default: True)
        self.enable_auto_compact = (
            os.getenv("PATCHPAL_DISABLE_AUTOCOMPACT", "false").lower() != "true"
        )

        # Track last compaction to prevent compaction loops
        self._last_compaction_message_count = 0

        # LiteLLM settings for models that need parameter dropping
        self.litellm_kwargs = {}
        if self.model_id.startswith("bedrock/"):
            self.litellm_kwargs["drop_params"] = True
            # Configure LiteLLM to handle Bedrock's strict message alternation requirement
            # This must be set globally, not as a completion parameter
            litellm.modify_params = True
        elif self.model_id.startswith("openai/") and os.getenv("OPENAI_API_BASE"):
            # Custom OpenAI-compatible servers (vLLM, etc.) often don't support all parameters
            self.litellm_kwargs["drop_params"] = True

    def _perform_auto_compaction(self):
        """Perform automatic context window compaction.

        This method is called when the context window reaches 85% capacity.
        It attempts pruning first, then full compaction if needed.
        """
        # Don't compact if we have very few messages - compaction summary
        # could be longer than the messages being removed
        if len(self.messages) < 5:
            print(
                f"\033[2m   Skipping compaction - only {len(self.messages)} messages (need at least 5 for effective compaction)\033[0m"
            )
            return

        # Prevent compaction loops - don't compact again if we just did
        # and haven't added significant new messages
        messages_since_last_compact = len(self.messages) - self._last_compaction_message_count
        if self._last_compaction_message_count > 0 and messages_since_last_compact < 3:
            # Just compacted recently and haven't added enough new context
            print(
                f"\033[2m   Skipping compaction - only {messages_since_last_compact} messages since last compact\033[0m"
            )
            return

        stats_before = self.context_manager.get_usage_stats(self.messages)

        print(
            f"\n\033[1;33m⚠️  Context window at {stats_before['usage_percent']}% capacity. Compacting...\033[0m"
        )
        print(
            f"\033[2m   Current: {stats_before['total_tokens']:,} / {stats_before['context_limit']:,} tokens "
            f"(system: {stats_before['system_tokens']:,}, messages: {stats_before['message_tokens']:,}, "
            f"output reserve: {stats_before['output_reserve']:,})\033[0m"
        )
        print(
            f"\033[2m   Messages: {len(self.messages)} total, last compaction at message {self._last_compaction_message_count}\033[0m"
        )

        # Phase 1: Try pruning old tool outputs first
        pruned_messages, tokens_saved = self.context_manager.prune_tool_outputs(self.messages)

        if tokens_saved > 0:
            self.messages = pruned_messages
            print(
                f"\033[2m   Pruned old tool outputs (saved ~{tokens_saved:,} tokens)\033[0m",
                flush=True,
            )

            # Check if pruning was enough
            if not self.context_manager.needs_compaction(self.messages):
                stats_after = self.context_manager.get_usage_stats(self.messages)
                print(
                    f"\033[1;32m✓ Context reduced to {stats_after['usage_percent']}% through pruning "
                    f"({stats_after['total_tokens']:,} tokens)\033[0m\n"
                )
                return

        # Phase 2: Full compaction needed
        print("\033[2m   Generating conversation summary...\033[0m", flush=True)

        try:
            # Create compaction using the LLM
            summary_msg, summary_text = self.context_manager.create_compaction(
                self.messages,
                lambda msgs: litellm.completion(
                    model=self.model_id,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}] + msgs,
                    **self.litellm_kwargs,
                ),
            )

            # Replace message history with compacted version
            # Strategy: Keep summary + recent complete turns (preserve tool call/result pairs)
            # This ensures Bedrock's strict message structure requirements are met

            # Find complete assistant turns (assistant message + all its tool results)
            # Walk backwards and keep complete turns
            preserved_messages = []
            i = len(self.messages) - 1
            turns_kept = 0
            max_turns_to_keep = 2  # Keep last 2 complete turns

            while i >= 0 and turns_kept < max_turns_to_keep:
                msg = self.messages[i]

                if msg.get("role") == "user":
                    # Found start of a turn, keep it and everything after
                    preserved_messages = self.messages[i:]
                    turns_kept += 1
                    i -= 1
                elif msg.get("role") == "assistant":
                    # Keep going back to find all tool results for this assistant message
                    i -= 1
                elif msg.get("role") == "tool":
                    # Part of current turn, keep going back
                    i -= 1
                else:
                    i -= 1

            if preserved_messages:
                self.messages = [summary_msg] + preserved_messages
            else:
                # Fallback: keep all messages plus summary
                self.messages = [summary_msg] + self.messages

            # Show results
            stats_after = self.context_manager.get_usage_stats(self.messages)
            print(
                f"\033[1;32m✓ Compaction complete. Saved {stats_before['total_tokens'] - stats_after['total_tokens']:,} tokens ({stats_before['usage_percent']}% → {stats_after['usage_percent']}%)\033[0m\n"
            )

            # Update last compaction tracker
            self._last_compaction_message_count = len(self.messages)

        except Exception as e:
            # Compaction failed - warn but continue
            print(f"\033[1;31m✗ Compaction failed: {e}\033[0m")
            print(
                "\033[1;33m   Continuing without compaction. Consider starting a new session.\033[0m\n"
            )

    def run(self, user_message: str, max_iterations: int = 100) -> str:
        """Run the agent on a user message.

        Args:
            user_message: The user's request
            max_iterations: Maximum number of agent iterations (default: 100)

        Returns:
            The agent's final response
        """
        # Add user message to history
        self.messages.append({"role": "user", "content": user_message})

        # Check for compaction BEFORE starting work
        # This ensures we never compact mid-execution and lose tool results
        if self.enable_auto_compact and self.context_manager.needs_compaction(self.messages):
            self._perform_auto_compaction()

        # Agent loop
        for iteration in range(max_iterations):
            # Show thinking message
            print("\033[2m🤔 Thinking...\033[0m", flush=True)

            # Use LiteLLM for all providers
            try:
                response = litellm.completion(
                    model=self.model_id,
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self.messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    **self.litellm_kwargs,
                )
            except Exception as e:
                return f"Error calling model: {e}"

            # Get the assistant's response
            assistant_message = response.choices[0].message

            # Add assistant message to history
            self.messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content or "",
                    "tool_calls": assistant_message.tool_calls
                    if hasattr(assistant_message, "tool_calls") and assistant_message.tool_calls
                    else None,
                }
            )

            # Check if there are tool calls
            if hasattr(assistant_message, "tool_calls") and assistant_message.tool_calls:
                # Print explanation text before executing tools (render as markdown)
                if assistant_message.content and assistant_message.content.strip():
                    console = Console()
                    print()  # Blank line before markdown
                    console.print(Markdown(assistant_message.content))
                    print()  # Blank line after markdown

                # Track if any operation was cancelled
                operation_cancelled = False

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
                            tool_display = tool_name.replace("_", " ").title()
                            if tool_name == "read_file":
                                print(
                                    f"\033[2m📖 Reading: {tool_args.get('path', '')}\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "read_lines":
                                start = tool_args.get("start_line", "")
                                end = tool_args.get("end_line", start)
                                print(
                                    f"\033[2m📖 Reading lines {start}-{end}: {tool_args.get('path', '')}\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "list_files":
                                print("\033[2m📁 Listing files...\033[0m", flush=True)
                            elif tool_name == "get_file_info":
                                print(
                                    f"\033[2m📊 Getting info: {tool_args.get('path', '')}\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "edit_file":
                                print(
                                    f"\033[2m✏️  Editing: {tool_args.get('path', '')}\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "apply_patch":
                                print(
                                    f"\033[2m📝 Patching: {tool_args.get('path', '')}\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "git_status":
                                print("\033[2m🔀 Git status...\033[0m", flush=True)
                            elif tool_name == "git_diff":
                                print(
                                    f"\033[2m🔀 Git diff{': ' + tool_args.get('path', '') if tool_args.get('path') else '...'}\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "git_log":
                                print("\033[2m🔀 Git log...\033[0m", flush=True)
                            elif tool_name == "grep_code":
                                print(
                                    f"\033[2m🔍 Searching: {tool_args.get('pattern', '')}\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "find_files":
                                print(
                                    f"\033[2m🔍 Finding: {tool_args.get('pattern', '')}\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "tree":
                                print(
                                    f"\033[2m🌳 Tree: {tool_args.get('path', '.')}\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "list_skills":
                                print("\033[2m📋 Listing skills...\033[0m", flush=True)
                            elif tool_name == "use_skill":
                                print(
                                    f"\033[2m⚡ Using skill: {tool_args.get('skill_name', '')}\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "web_search":
                                print(
                                    f"\033[2m🌐 Searching web: {tool_args.get('query', '')}\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "web_fetch":
                                print(
                                    f"\033[2m🌐 Fetching: {tool_args.get('url', '')}\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "run_shell":
                                print(
                                    f"\033[2m⚡ Running: {tool_args.get('cmd', '')}\033[0m",
                                    flush=True,
                                )

                            # Execute the tool (permission checks happen inside the tool)
                            try:
                                # Filter tool_args to only include parameters the function accepts
                                sig = inspect.signature(tool_func)
                                valid_params = set(sig.parameters.keys())
                                filtered_args = {
                                    k: v for k, v in tool_args.items() if k in valid_params
                                }

                                # Coerce types for parameters (Ollama sometimes passes strings)
                                for param_name, param in sig.parameters.items():
                                    if param_name in filtered_args:
                                        expected_type = param.annotation
                                        actual_value = filtered_args[param_name]

                                        # Convert strings to expected types
                                        if expected_type is int and isinstance(actual_value, str):
                                            filtered_args[param_name] = int(actual_value)
                                        elif expected_type is bool and isinstance(
                                            actual_value, str
                                        ):
                                            filtered_args[param_name] = actual_value.lower() in (
                                                "true",
                                                "1",
                                                "yes",
                                            )

                                # Silently filter out invalid args (models sometimes hallucinate parameters)

                                tool_result = tool_func(**filtered_args)
                            except Exception as e:
                                tool_result = f"Error executing {tool_name}: {e}"
                                print(f"\033[1;31m✗ {tool_display}: {e}\033[0m")

                    # Add tool result to messages
                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_name,
                            "content": str(tool_result),
                        }
                    )

                    # Check if operation was cancelled by user
                    # Use exact match to avoid false positives from file contents
                    if str(tool_result).strip() == "Operation cancelled by user.":
                        operation_cancelled = True

                # If any operation was cancelled, return now (after all tool results are added)
                # This ensures Bedrock gets all expected tool results before we exit
                if operation_cancelled:
                    return "Operation cancelled by user."

                # Check if context window needs compaction after tool results are added
                # This prevents context from ballooning within a single turn (e.g., reading large files)
                if self.enable_auto_compact and self.context_manager.needs_compaction(
                    self.messages
                ):
                    self._perform_auto_compaction()

                # Continue loop to let agent process tool results
                continue
            else:
                # No tool calls, agent is done
                # Check if we need compaction before returning (final response might be large)
                if self.enable_auto_compact and self.context_manager.needs_compaction(
                    self.messages
                ):
                    self._perform_auto_compaction()

                return assistant_message.content or "Task completed"

        # Max iterations reached
        return (
            f"Maximum iterations ({max_iterations}) reached. Task may be incomplete.\n\n"
            "💡 Tip: Type 'continue' or 'please continue' to resume where I left off, "
            "or set PATCHPAL_MAX_ITERATIONS=<large #> as environment variable."
        )


def create_agent(model_id: str = "anthropic/claude-sonnet-4-5") -> PatchPalAgent:
    """Create and return a PatchPal agent.

    Args:
        model_id: LiteLLM model identifier (default: anthropic/claude-sonnet-4-5)

    Returns:
        A configured PatchPalAgent instance
    """
    return PatchPalAgent(model_id=model_id)
