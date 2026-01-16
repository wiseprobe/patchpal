"""Custom agent implementation using LiteLLM directly."""

import os
import json
from typing import Any, Dict, List, Optional
import litellm
from patchpal.tools import read_file, list_files, apply_patch, run_shell, grep_code


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
    "apply_patch": apply_patch,
    "grep_code": grep_code,
    "run_shell": run_shell,
}


SYSTEM_PROMPT = """You are an expert software engineer assistant helping with code tasks in a repository.

# Available Tools

- **read_file**: Read the contents of any file in the repository
- **list_files**: List all files in the repository
- **grep_code**: Search for patterns in code files (faster than run_shell with grep)
- **apply_patch**: Modify a file by providing the complete new content
- **run_shell**: Run safe shell commands (dangerous commands like rm, mv, sudo are blocked)

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

- Use list_files to explore the repository structure
- Use grep_code to search for patterns across files (preferred over run_shell with grep)
- Use read_file to examine specific files before modifying them
- When using apply_patch, provide the COMPLETE new file content (not just the changed parts)
- Use run_shell for safe commands only (testing, building, git operations, etc.)
- Never use run_shell for file operations - use read_file and apply_patch instead

## Code References
When referencing specific functions or code, include the pattern `file_path:line_number` to help users navigate.

Example: "The authentication logic is in src/auth.py:45"

# Important Notes

- Stop when the task is complete - don't continue working unless asked
- If you're unsure about requirements, ask for clarification
- Focus on what needs to be done, not when (don't suggest timelines)
- Maintain consistency with the existing codebase style and patterns"""


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

    def run(self, user_message: str, max_iterations: int = 10) -> str:
        """Run the agent on a user message.

        Args:
            user_message: The user's request
            max_iterations: Maximum number of agent iterations

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
                            elif tool_name == 'grep_code':
                                print(f"\033[2m🔍 Searching: {tool_args.get('pattern', '')}\033[0m", flush=True)
                            elif tool_name == 'apply_patch':
                                print(f"\033[2m✏️  Modifying: {tool_args.get('path', '')}\033[0m", flush=True)
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

                # Continue loop to let agent process tool results
                continue
            else:
                # No tool calls, agent is done
                return assistant_message.content or "Task completed"

        # Max iterations reached
        return "Maximum iterations reached. Task may be incomplete."


def create_agent(model_id: str = "anthropic/claude-sonnet-4-5") -> PatchPalAgent:
    """Create and return a PatchPal agent.

    Args:
        model_id: LiteLLM model identifier (default: anthropic/claude-sonnet-4-5)

    Returns:
        A configured PatchPalAgent instance
    """
    return PatchPalAgent(model_id=model_id)
