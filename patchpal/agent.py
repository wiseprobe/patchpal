"""Custom agent implementation using LiteLLM directly."""

import inspect
import json
import os
import platform
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import litellm
from rich.console import Console
from rich.markdown import Markdown

from patchpal.context import ContextManager
from patchpal.tools.definitions import get_tools

# LLM API timeout in seconds (default: 300 seconds = 5 minutes)
# Can be overridden with PATCHPAL_LLM_TIMEOUT environment variable
LLM_TIMEOUT = int(os.getenv("PATCHPAL_LLM_TIMEOUT", "300"))


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


def _is_govcloud_bedrock(model_id: str) -> bool:
    """Check if the model is using AWS GovCloud Bedrock.

    Args:
        model_id: Model identifier

    Returns:
        True if using GovCloud Bedrock
    """
    # Check if model ID contains us-gov region
    if "us-gov" in model_id.lower():
        return True

    # Check if AWS_BEDROCK_REGION environment variable indicates GovCloud
    bedrock_region = os.getenv("AWS_BEDROCK_REGION", "")
    if bedrock_region.startswith("us-gov"):
        return True

    # Check AWS_REGION_NAME as fallback (set by _setup_bedrock_env)
    region_name = os.getenv("AWS_REGION_NAME", "")
    if region_name.startswith("us-gov"):
        return True

    return False


# Get tool definitions (with web tools optionally disabled for air-gapped environments)
WEB_TOOLS_ENABLED = os.getenv("PATCHPAL_ENABLE_WEB", "true").lower() in ("true", "1", "yes")
TOOLS, TOOL_FUNCTIONS = get_tools(web_tools_enabled=WEB_TOOLS_ENABLED)


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
WEB_USAGE_DESC = ""
if WEB_TOOLS_ENABLED:
    WEB_USAGE_DESC = """
- Use web_search when you encounter unfamiliar errors, need documentation, or want to research solutions
- Use web_fetch to read documentation pages, download examples, or fetch office documents"""


def _get_current_datetime_message() -> str:
    """Generate current date/time system message.

    Called dynamically on each LLM API call to ensure date/time is always current.

    Returns:
        Formatted date/time string for injection into system messages
    """
    now = datetime.now()
    current_date = now.strftime("%A, %B %d, %Y")  # e.g., "Wednesday, January 15, 2026"
    current_time = now.strftime("%I:%M %p %Z").strip()  # e.g., "03:45 PM EST"
    if not current_time.endswith(("EST", "CST", "MST", "PST", "UTC")):
        # If no timezone abbreviation, just show time without timezone
        current_time = now.strftime("%I:%M %p").strip()

    return f"## Current Date and Time\nToday is {current_date}. Current time is {current_time}."


def _load_system_prompt() -> str:
    """Load system prompt from markdown file and substitute dynamic values.

    Checks PATCHPAL_USE_SIMPLE_PROMPT and PATCHPAL_SYSTEM_PROMPT environment variables.
    Priority: PATCHPAL_SYSTEM_PROMPT > PATCHPAL_USE_SIMPLE_PROMPT > default

    Note: Date/time is NOT included here - it's dynamically injected on each API call
    via _get_current_datetime_message() to prevent staleness in long sessions.

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
            prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "system_prompt.md")
    elif os.getenv("PATCHPAL_USE_SIMPLE_PROMPT", "").lower() in ("true", "1", "yes"):
        # Use simplified prompt
        prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "system_prompt_simple.md")
    else:
        # Use default prompt from package directory
        prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "system_prompt.md")

    # Read the prompt template
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    # Prepare template variables
    template_vars = {
        "platform_info": PLATFORM_INFO,
        "web_usage": WEB_USAGE_DESC,
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


def _supports_prompt_caching(model_id: str) -> bool:
    """Check if the model supports prompt caching.

    Args:
        model_id: LiteLLM model identifier

    Returns:
        True if the model supports prompt caching
    """
    # Anthropic models support caching (direct API or via Bedrock)
    if "anthropic" in model_id.lower() or "claude" in model_id.lower():
        return True
    # Bedrock Nova models support caching
    if model_id.startswith("bedrock/") and "amazon.nova" in model_id.lower():
        return True
    return False


def _apply_prompt_caching(messages: List[Dict[str, Any]], model_id: str) -> List[Dict[str, Any]]:
    """Apply prompt caching markers to messages following OpenCode's strategy.

    Caches:
    - System messages (first 1-2 messages with role="system")
    - Last 2 non-system messages (recent context, any role except system)

    Args:
        messages: List of message dictionaries
        model_id: LiteLLM model identifier

    Returns:
        Modified messages with cache markers
    """
    if not _supports_prompt_caching(model_id):
        return messages

    # Determine cache marker format based on provider
    # Anthropic models (direct or via Bedrock) use cache_control
    # Other Bedrock models (Nova, etc.) use cachePoint
    if model_id.startswith("bedrock/") and "anthropic" not in model_id.lower():
        # Non-Anthropic Bedrock models (Nova, etc.) use cachePoint
        cache_marker = {"cachePoint": {"type": "default"}}
    else:
        # Anthropic models (direct or via Bedrock) use cache_control
        cache_marker = {"cache_control": {"type": "ephemeral"}}

    # Find system messages (usually at the start)
    system_messages = [i for i, msg in enumerate(messages) if msg.get("role") == "system"]

    # Find last 2 non-system messages (recent context)
    non_system_messages = [i for i, msg in enumerate(messages) if msg.get("role") != "system"]
    last_two_indices = (
        non_system_messages[-2:] if len(non_system_messages) >= 2 else non_system_messages
    )

    # Apply caching to system messages (first 2)
    for idx in system_messages[:2]:
        msg = messages[idx]
        # Skip if already has cache marker at content block level
        if isinstance(msg.get("content"), list):
            # Already structured - check if any block has cache_control/cachePoint
            has_cache = any(
                "cache_control" in block or "cachePoint" in block
                for block in msg["content"]
                if isinstance(block, dict)
            )
            if not has_cache and msg["content"]:
                # Add cache marker to the last content block
                last_block = msg["content"][-1]
                if isinstance(last_block, dict):
                    last_block.update(cache_marker)
        else:
            # Convert simple string content to structured format with cache marker
            content_text = msg.get("content", "")
            messages[idx] = {
                **msg,
                "content": [{"type": "text", "text": content_text, **cache_marker}],
            }

    # Apply caching to last 2 messages
    for idx in last_two_indices:
        msg = messages[idx]
        # Skip if already has cache marker at content block level
        if isinstance(msg.get("content"), list):
            # Already structured - check if any block has cache_control/cachePoint
            has_cache = any(
                "cache_control" in block or "cachePoint" in block
                for block in msg["content"]
                if isinstance(block, dict)
            )
            if not has_cache and msg["content"]:
                # Add cache marker to the last content block
                last_block = msg["content"][-1]
                if isinstance(last_block, dict):
                    last_block.update(cache_marker)
        else:
            # Convert simple string content to structured format with cache marker
            content_text = msg.get("content", "")
            if content_text:  # Only convert non-empty content
                messages[idx] = {
                    **msg,
                    "content": [{"type": "text", "text": content_text, **cache_marker}],
                }

    return messages


class PatchPalAgent:
    """Simple agent that uses LiteLLM for tool calling."""

    def __init__(
        self,
        model_id: str = "anthropic/claude-sonnet-4-5",
        custom_tools: Optional[List[Callable]] = None,
        litellm_kwargs: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the agent.

        Args:
            model_id: LiteLLM model identifier
            custom_tools: Optional list of Python functions to add as tools
            litellm_kwargs: Optional dict of extra parameters to pass to litellm.completion()
                          (e.g., {"reasoning_effort": "high"} for reasoning models)
        """
        # Store custom tools
        self.custom_tools = custom_tools or []
        self.custom_tool_funcs = {func.__name__: func for func in self.custom_tools}

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

        # Track cumulative token usage across all LLM calls
        self.total_llm_calls = 0
        self.cumulative_input_tokens = 0
        self.cumulative_output_tokens = 0

        # Track cache-related tokens (for Anthropic/Bedrock models with prompt caching)
        self.cumulative_cache_creation_tokens = 0
        self.cumulative_cache_read_tokens = 0

        # Track OpenAI cache tokens (prompt_tokens_details.cached_tokens)
        self.cumulative_openai_cached_tokens = 0

        # Track cumulative costs across all LLM calls
        self.cumulative_cost = 0.0
        self.last_message_cost = 0.0

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

        # Merge in any user-provided litellm_kwargs
        if litellm_kwargs:
            self.litellm_kwargs.update(litellm_kwargs)

        # Load MEMORY.md if it exists and has non-template content
        self._load_project_memory()

    def _load_project_memory(self):
        """Load MEMORY.md file at session start if it has non-template content."""
        try:
            from patchpal.tools.common import MEMORY_FILE

            # Always tell the agent where MEMORY.md is located
            if not MEMORY_FILE.exists():
                return

            memory_content = MEMORY_FILE.read_text(encoding="utf-8")

            # Check if user has added content after the "---" separator
            has_user_content = False
            if "---" in memory_content:
                parts = memory_content.split("---", 1)
                if len(parts) > 1:
                    user_content = parts[1].strip()
                    if user_content and len(user_content) > 10:
                        has_user_content = True

            # Build the message - include full content if user added info, otherwise just location
            if has_user_content:
                memory_msg = f"""# Project Memory (from MEMORY.md)

{memory_content}

The information above is from {MEMORY_FILE} and persists across sessions.
To update it, use edit_file("{MEMORY_FILE}", ...) or apply_patch("{MEMORY_FILE}", ...)."""
            else:
                # Empty template - just inform agent
                memory_msg = f"""# Project Memory (MEMORY.md)

Your project memory file is located at: {MEMORY_FILE}

It's currently empty (just the template). The file is automatically loaded at session start."""

            # Add as a system message at the start
            self.messages.insert(
                0,
                {
                    "role": "system",
                    "content": memory_msg,
                    "metadata": {"is_memory": True},
                },
            )
        except Exception:
            # If loading fails, silently continue (don't break agent initialization)
            pass

    def _prune_tool_outputs_inline(self, max_chars: int, truncation_message: str) -> int:
        """Unified pruning function for tool outputs.

        Args:
            max_chars: Maximum characters to keep per tool output
            truncation_message: Message to append after truncation

        Returns:
            Number of characters pruned
        """
        pruned_chars = 0
        for msg in self.messages:
            if msg.get("role") == "tool" and msg.get("content"):
                content_size = len(str(msg["content"]))
                if content_size > max_chars:
                    original_size = content_size
                    msg["content"] = str(msg["content"])[:max_chars] + truncation_message
                    pruned_chars += original_size - len(msg["content"])
        return pruned_chars

    def _is_openai_model(self) -> bool:
        """Check if the current model is an OpenAI model.

        Returns:
            True if the model is OpenAI, False otherwise
        """
        model_lower = self.model_id.lower()
        return (
            "openai" in model_lower or "gpt" in model_lower or self.model_id.startswith("openai/")
        )

    def _perform_auto_compaction(self):
        """Perform automatic context window compaction.

        This method is called when the context window reaches 75% capacity.
        It attempts pruning first, then full compaction if needed.
        """
        # Don't compact if we have very few messages - compaction summary
        # could be longer than the messages being removed
        # Instead, use aggressive pruning since high capacity with few messages
        # indicates large tool outputs rather than conversation depth
        if len(self.messages) < 10:
            print(
                f"\033[2m   Only {len(self.messages)} messages - using aggressive pruning instead of summarization\033[0m"
            )

            # Aggressively truncate all large tool outputs (5K chars)
            pruned_chars = self._prune_tool_outputs_inline(
                max_chars=5_000,
                truncation_message="\n\n[... content truncated during compaction. Use read_lines or grep for targeted access ...]",
            )

            stats_after = self.context_manager.get_usage_stats(self.messages)
            if pruned_chars > 0:
                print(
                    f"\033[1;32m✓ Context reduced to {stats_after['usage_percent']}% through aggressive pruning (removed ~{pruned_chars:,} chars)\033[0m\n"
                )
            else:
                print(
                    f"\033[1;33m⚠️  No large tool outputs to prune. Context at {stats_after['usage_percent']}%.\033[0m"
                )
                print("\033[1;33m   Consider using '/clear' to start fresh.\033[0m\n")

            # Update tracker to prevent immediate re-compaction
            self._last_compaction_message_count = len(self.messages)
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

        # Phase 1: Try pruning old tool outputs first (simple pruning, no summarization)
        pruned_messages, tokens_saved = self.context_manager.prune_tool_outputs(
            self.messages, intelligent=False
        )

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
        # EMERGENCY: If context is at or over capacity (≥100%), do aggressive pruning first
        # Otherwise the summarization request itself will exceed context limits
        stats_after_prune = self.context_manager.get_usage_stats(self.messages)
        if stats_after_prune["usage_ratio"] >= 1.0:
            print(
                f"\033[1;31m   ⚠️  Context at or over capacity ({stats_after_prune['usage_percent']}%)!\033[0m"
            )
            print(
                "\033[2m   Emergency: Aggressively pruning recent large tool outputs...\033[0m",
                flush=True,
            )

            # Truncate large tool outputs (10K chars - less aggressive than 5K for few-messages case)
            emergency_pruned = self._prune_tool_outputs_inline(
                max_chars=10_000,
                truncation_message="\n\n[... content truncated due to context window limits ...]",
            )

            if emergency_pruned > 0:
                print(
                    f"\033[2m   Emergency pruned ~{emergency_pruned:,} chars from large tool outputs\033[0m",
                    flush=True,
                )
                stats_after_emergency = self.context_manager.get_usage_stats(self.messages)
                print(
                    f"\033[2m   Context now at {stats_after_emergency['usage_percent']}% capacity\033[0m",
                    flush=True,
                )

                # If still over 150%, give up and recommend /clear
                if stats_after_emergency["usage_ratio"] > 1.5:
                    print(
                        f"\033[1;31m✗ Context still too large for compaction ({stats_after_emergency['usage_percent']}%)\033[0m"
                    )
                    print("\033[1;33m   Please use '/clear' to start a fresh session.\033[0m\n")
                    return

        print("\033[2m   Generating conversation summary...\033[0m", flush=True)

        try:
            # Create compaction using the LLM
            def compaction_completion(msgs):
                # Prepare messages with system prompt
                messages = [{"role": "system", "content": SYSTEM_PROMPT}] + msgs
                # Apply prompt caching for supported models
                messages = _apply_prompt_caching(messages, self.model_id)
                response = litellm.completion(
                    model=self.model_id,
                    messages=messages,
                    timeout=LLM_TIMEOUT,
                    **self.litellm_kwargs,
                )

                # Track token usage from compaction call
                self.total_llm_calls += 1
                if hasattr(response, "usage") and response.usage:
                    if hasattr(response.usage, "prompt_tokens"):
                        self.cumulative_input_tokens += response.usage.prompt_tokens
                    if hasattr(response.usage, "completion_tokens"):
                        self.cumulative_output_tokens += response.usage.completion_tokens
                    # Track cache statistics (Anthropic/Bedrock prompt caching)
                    if (
                        hasattr(response.usage, "cache_creation_input_tokens")
                        and response.usage.cache_creation_input_tokens
                    ):
                        self.cumulative_cache_creation_tokens += (
                            response.usage.cache_creation_input_tokens
                        )
                    if (
                        hasattr(response.usage, "cache_read_input_tokens")
                        and response.usage.cache_read_input_tokens
                    ):
                        self.cumulative_cache_read_tokens += response.usage.cache_read_input_tokens

                    # Track OpenAI cache tokens (prompt_tokens_details.cached_tokens)
                    # Only track for OpenAI models to avoid LiteLLM cross-contamination
                    if self._is_openai_model() and hasattr(response.usage, "prompt_tokens_details"):
                        prompt_details = response.usage.prompt_tokens_details
                        if (
                            hasattr(prompt_details, "cached_tokens")
                            and prompt_details.cached_tokens
                        ):
                            self.cumulative_openai_cached_tokens += prompt_details.cached_tokens

                # Track cost from compaction call
                self._calculate_cost(response)

                return response

            summary_msg, summary_text = self.context_manager.create_compaction(
                self.messages,
                compaction_completion,
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

    def _compute_cost_from_tokens(self, usage):
        """Manually calculate cost from token usage using model pricing.

        Args:
            usage: The usage object from the LLM response

        Returns:
            float: The calculated cost in dollars
        """
        try:
            model_info = litellm.get_model_info(self.model_id)
            input_cost_per_token = model_info.get("input_cost_per_token", 0)
            output_cost_per_token = model_info.get("output_cost_per_token", 0)

            # Get cached input cost (OpenAI models have cache_read_input_token_cost in LiteLLM)
            cached_input_cost_per_token = model_info.get("cached_input_cost_per_token", 0)
            if not cached_input_cost_per_token:
                # Try LiteLLM's actual field name for OpenAI cached tokens
                cached_input_cost_per_token = model_info.get("cache_read_input_token_cost", 0)

            # Apply GovCloud pricing adjustment (20% higher than commercial regions)
            # GovCloud Bedrock pricing is approximately 1.2x commercial pricing
            if self.model_id.startswith("bedrock/") and _is_govcloud_bedrock(self.model_id):
                govcloud_multiplier = 1.2
                input_cost_per_token *= govcloud_multiplier
                output_cost_per_token *= govcloud_multiplier
                cached_input_cost_per_token *= govcloud_multiplier

            cost = 0.0

            # Handle Anthropic/Bedrock cache pricing
            # Cache writes cost 1.25x, cache reads cost 0.1x of base price
            cache_creation_tokens = 0
            cache_read_tokens = 0

            if hasattr(usage, "cache_creation_input_tokens") and usage.cache_creation_input_tokens:
                cache_creation_tokens = usage.cache_creation_input_tokens
                cost += cache_creation_tokens * input_cost_per_token * 1.25

            if hasattr(usage, "cache_read_input_tokens") and usage.cache_read_input_tokens:
                cache_read_tokens = usage.cache_read_input_tokens
                cost += cache_read_tokens * input_cost_per_token * 0.1

            # Handle OpenAI cache pricing (prompt_tokens_details.cached_tokens)
            openai_cached_tokens = 0
            if hasattr(usage, "prompt_tokens_details") and usage.prompt_tokens_details is not None:
                prompt_details = usage.prompt_tokens_details
                if hasattr(prompt_details, "cached_tokens") and prompt_details.cached_tokens:
                    # Ensure cached_tokens is a number, not a mock or None
                    if isinstance(prompt_details.cached_tokens, (int, float)):
                        openai_cached_tokens = prompt_details.cached_tokens
                        # Use cached_input_cost_per_token if available, otherwise fallback to 0.5x multiplier
                        if cached_input_cost_per_token > 0:
                            cost += openai_cached_tokens * cached_input_cost_per_token
                        else:
                            # Fallback: OpenAI cached tokens typically cost 50% of regular input
                            cost += openai_cached_tokens * input_cost_per_token * 0.5

            # Regular input tokens (excluding all cache tokens)
            regular_input = (
                usage.prompt_tokens
                - cache_creation_tokens
                - cache_read_tokens
                - openai_cached_tokens
            )
            cost += regular_input * input_cost_per_token

            # Output tokens
            cost += usage.completion_tokens * output_cost_per_token

            return cost
        except Exception:
            # If pricing data is unavailable, return 0
            return 0.0

    def _calculate_cost(self, response):
        """Calculate cost from LLM response and update cumulative tracking.

        Args:
            response: The LLM response object

        Returns:
            float: The calculated cost in dollars
        """
        try:
            # Try litellm's built-in cost calculator first
            cost = litellm.completion_cost(completion_response=response)
        except Exception:
            cost = 0.0

        if not cost and hasattr(response, "usage") and response.usage:
            # Fallback: manual calculation using model pricing
            cost = self._compute_cost_from_tokens(response.usage)

        if isinstance(cost, (int, float)) and cost > 0:
            self.cumulative_cost += cost
            self.last_message_cost = cost

        return cost

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

        # Agent loop with interrupt handling
        try:
            return self._run_agent_loop(max_iterations)
        except KeyboardInterrupt:
            # Clean up conversation state if interrupted mid-execution
            self._cleanup_interrupted_state()
            raise  # Re-raise so CLI can handle it

    def _cleanup_interrupted_state(self):
        """Clean up conversation state after KeyboardInterrupt.

        If the last message is an assistant message with tool_calls but no
        corresponding tool responses, we need to either remove the message
        or add error responses to maintain valid conversation structure.
        """
        if not self.messages:
            return

        last_msg = self.messages[-1]

        # Check if last message is assistant with tool_calls
        if last_msg.get("role") == "assistant" and last_msg.get("tool_calls"):
            tool_calls = last_msg["tool_calls"]

            # Check if we have tool responses for all tool_calls
            tool_call_ids = {tc.id for tc in tool_calls}

            # Look for tool responses after this assistant message
            # (should be immediately following, but scan to be safe)
            response_ids = set()
            for msg in self.messages[self.messages.index(last_msg) + 1 :]:
                if msg.get("role") == "tool":
                    response_ids.add(msg.get("tool_call_id"))

            # If we're missing responses, add error responses for all tool calls
            if tool_call_ids != response_ids:
                missing_ids = tool_call_ids - response_ids

                # Add error tool responses for the missing tool calls
                for tool_call in tool_calls:
                    if tool_call.id in missing_ids:
                        self.messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_call.function.name,
                                "content": "Error: Operation interrupted by user (Ctrl-C)",
                            }
                        )

    def _run_agent_loop(self, max_iterations: int) -> str:
        """Internal method that runs the agent loop.

        Separated from run() to enable proper interrupt handling.

        Args:
            max_iterations: Maximum number of agent iterations

        Returns:
            The agent's final response
        """
        # Agent loop
        for iteration in range(max_iterations):
            # Show thinking message
            print("\033[2m🤔 Thinking...\033[0m", flush=True)

            # Prepare messages with system prompt and dynamic date/time
            # Date/time is regenerated on each call to prevent staleness in long sessions
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "system", "content": _get_current_datetime_message()},
            ] + self.messages

            # Apply prompt caching for supported models (Anthropic/Claude)
            messages = _apply_prompt_caching(messages, self.model_id)

            # Use LiteLLM for all providers
            try:
                # Build tool list (built-in + custom)
                tools = list(TOOLS)
                if self.custom_tools:
                    from patchpal.tool_schema import function_to_tool_schema

                    for func in self.custom_tools:
                        tools.append(function_to_tool_schema(func))

                response = litellm.completion(
                    model=self.model_id,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    timeout=LLM_TIMEOUT,
                    **self.litellm_kwargs,
                )

                # Track token usage from this LLM call
                self.total_llm_calls += 1
                if hasattr(response, "usage") and response.usage:
                    if hasattr(response.usage, "prompt_tokens"):
                        self.cumulative_input_tokens += response.usage.prompt_tokens
                    if hasattr(response.usage, "completion_tokens"):
                        self.cumulative_output_tokens += response.usage.completion_tokens
                    # Track cache statistics (Anthropic/Bedrock prompt caching)
                    if (
                        hasattr(response.usage, "cache_creation_input_tokens")
                        and response.usage.cache_creation_input_tokens
                    ):
                        self.cumulative_cache_creation_tokens += (
                            response.usage.cache_creation_input_tokens
                        )
                    if (
                        hasattr(response.usage, "cache_read_input_tokens")
                        and response.usage.cache_read_input_tokens
                    ):
                        self.cumulative_cache_read_tokens += response.usage.cache_read_input_tokens

                    # Track OpenAI cache tokens (prompt_tokens_details.cached_tokens)
                    # Only track for OpenAI models to avoid LiteLLM cross-contamination
                    if self._is_openai_model() and hasattr(response.usage, "prompt_tokens_details"):
                        prompt_details = response.usage.prompt_tokens_details
                        if (
                            hasattr(prompt_details, "cached_tokens")
                            and prompt_details.cached_tokens
                        ):
                            self.cumulative_openai_cached_tokens += prompt_details.cached_tokens

                # Track cost from this LLM call
                self._calculate_cost(response)

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
                        # Get the tool function (check custom tools first, then built-in)
                        tool_func = self.custom_tool_funcs.get(tool_name) or TOOL_FUNCTIONS.get(
                            tool_name
                        )
                        if tool_func is None:
                            tool_result = f"Error: Unknown tool {tool_name}"
                            print(f"\033[1;31m✗ Unknown tool: {tool_name}\033[0m")
                        else:
                            # Show tool call message
                            if tool_name in self.custom_tool_funcs:
                                # Custom tool - show generic message with args
                                args_preview = str(tool_args)[:60]
                                if len(str(tool_args)) > 60:
                                    args_preview += "..."
                                print(
                                    f"\033[2m🔧 {tool_name}({args_preview})\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "read_file":
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
                            elif tool_name == "count_lines":
                                print(
                                    f"\033[2m🔢 Counting lines: {tool_args.get('path', '')}\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "code_structure":
                                print(
                                    f"\033[2m🔍 Analyzing structure: {tool_args.get('path', '')}\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "get_repo_map":
                                max_files = tool_args.get("max_files", 100)
                                patterns = ""
                                if tool_args.get("include_patterns"):
                                    patterns = (
                                        f" (include: {', '.join(tool_args['include_patterns'])})"
                                    )
                                elif tool_args.get("exclude_patterns"):
                                    patterns = (
                                        f" (exclude: {', '.join(tool_args['exclude_patterns'])})"
                                    )
                                print(
                                    f"\033[2m🗺️  Generating repository map (max {max_files} files{patterns})...\033[0m",
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
                            elif tool_name == "grep":
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
                            elif tool_name == "todo_add":
                                print(
                                    f"\033[2m✅ Adding TODO: {tool_args.get('description', '')[:50]}\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "todo_list":
                                print("\033[2m📋 Listing TODO tasks...\033[0m", flush=True)
                            elif tool_name == "todo_complete":
                                print(
                                    f"\033[2m✓ Completed task #{tool_args.get('task_id', '')}\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "todo_update":
                                print(
                                    f"\033[2m📝 Updating task #{tool_args.get('task_id', '')}\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "todo_remove":
                                print(
                                    f"\033[2m🗑️  Removing task #{tool_args.get('task_id', '')}\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "todo_clear":
                                clear_type = (
                                    "completed" if tool_args.get("completed_only", True) else "all"
                                )
                                print(
                                    f"\033[2m🧹 Clearing {clear_type} TODO tasks...\033[0m",
                                    flush=True,
                                )
                            elif tool_name == "ask_user":
                                print(
                                    "\033[2m❓ Asking user a question...\033[0m",
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
                                print(f"\033[1;31m✗ {tool_name}: {e}\033[0m")

                    # Add tool result to messages
                    # Apply universal output limits to prevent context explosions
                    result_str = str(tool_result)
                    result_size = len(result_str)
                    lines = result_str.split("\n")
                    total_lines = len(lines)

                    # Check if output exceeds universal limits
                    from patchpal.tools import MAX_TOOL_OUTPUT_CHARS, MAX_TOOL_OUTPUT_LINES

                    if total_lines > MAX_TOOL_OUTPUT_LINES or result_size > MAX_TOOL_OUTPUT_CHARS:
                        truncated_by_lines = total_lines > MAX_TOOL_OUTPUT_LINES
                        truncated_by_chars = result_size > MAX_TOOL_OUTPUT_CHARS

                        # Truncate to limits
                        truncated_lines = lines[:MAX_TOOL_OUTPUT_LINES]
                        truncated_str = "\n".join(truncated_lines)

                        # Also enforce character limit
                        if len(truncated_str) > MAX_TOOL_OUTPUT_CHARS:
                            truncated_str = truncated_str[:MAX_TOOL_OUTPUT_CHARS]

                        removed_lines = total_lines - len(truncated_str.split("\n"))

                        if truncated_by_lines:
                            truncation_note = f"\n\n... {removed_lines:,} lines truncated ({total_lines:,} total lines) ...\n\n"
                        else:
                            truncation_note = f"\n\n... output truncated to {MAX_TOOL_OUTPUT_CHARS:,} characters (was {result_size:,}) ...\n\n"

                        # Add helpful hint message
                        hint = (
                            f"{truncation_note}"
                            f"Output exceeded limits ({MAX_TOOL_OUTPUT_LINES:,} lines or {MAX_TOOL_OUTPUT_CHARS:,} characters).\n"
                            f"Consider:\n"
                            f"- Using grep() to search files directly\n"
                            f"- Using read_lines() to read files in chunks\n"
                            f"- Refining the command to filter output (e.g., | grep, | head)"
                        )

                        result_str = truncated_str + hint
                        if truncated_by_lines:
                            print(
                                f"\033[1;33m⚠️  Tool output truncated: {total_lines:,} lines → {MAX_TOOL_OUTPUT_LINES:,} lines\033[0m"
                            )
                        elif truncated_by_chars:
                            print(
                                f"\033[1;33m⚠️  Tool output truncated: {result_size:,} chars → {MAX_TOOL_OUTPUT_CHARS:,} chars\033[0m"
                            )

                    self.messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_name,
                            "content": result_str,
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

                # Proactive pruning: If enabled and tool outputs exceed PRUNE_PROTECT threshold,
                # summarize old outputs now (before hitting 75% compaction threshold)
                # This keeps context lean and reduces tokens in subsequent API calls
                if self.context_manager.ENABLE_PROACTIVE_PRUNING:
                    tool_output_tokens = sum(
                        self.context_manager.estimator.estimate_message_tokens(msg)
                        for msg in self.messages
                        if msg.get("role") == "tool"
                    )

                    if tool_output_tokens > self.context_manager.PRUNE_PROTECT:
                        # Use intelligent summarization for proactive pruning
                        pruned_messages, tokens_saved = self.context_manager.prune_tool_outputs(
                            self.messages, intelligent=True
                        )
                        if tokens_saved > 0:
                            self.messages = pruned_messages
                            print(
                                f"\033[2m   💡 Proactively summarized old tool outputs (saved ~{tokens_saved:,} tokens)\033[0m"
                            )

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


def create_agent(
    model_id: str = "anthropic/claude-sonnet-4-5",
    custom_tools: Optional[List[Callable]] = None,
    litellm_kwargs: Optional[Dict[str, Any]] = None,
) -> PatchPalAgent:
    """Create and return a PatchPal agent.

    Args:
        model_id: LiteLLM model identifier (default: anthropic/claude-sonnet-4-5)
        custom_tools: Optional list of Python functions to use as custom tools.
                     Each function should have type hints and a docstring.
        litellm_kwargs: Optional dict of extra parameters to pass to litellm.completion()
                       (e.g., {"reasoning_effort": "high"} for reasoning models)

    Returns:
        A configured PatchPalAgent instance

    Example:
        def calculator(x: int, y: int) -> str:
            '''Add two numbers.

            Args:
                x: First number
                y: Second number
            '''
            return str(x + y)

        agent = create_agent(custom_tools=[calculator])
        response = agent.run("What's 5 + 3?")

        # With reasoning model
        agent = create_agent(
            model_id="ollama_chat/gpt-oss:20b",
            litellm_kwargs={"reasoning_effort": "high"}
        )
    """
    # Reset session todos for new session
    from patchpal.tools import reset_session_todos

    reset_session_todos()

    return PatchPalAgent(
        model_id=model_id, custom_tools=custom_tools, litellm_kwargs=litellm_kwargs
    )
