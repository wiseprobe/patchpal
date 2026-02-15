import argparse
import os
import sys
import warnings
from pathlib import Path

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import Completer, Completion, PathCompleter, merge_completers
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console
from rich.markdown import Markdown

from patchpal.agent import create_agent
from patchpal.tools import audit_logger


def _format_cost(value: float) -> str:
    """Format cost with smart precision.

    Args:
        value: Cost in dollars

    Returns:
        Formatted cost string (e.g., "0.0234" or "0.00145")
    """
    if value == 0:
        return "0.00"
    magnitude = abs(value)
    if magnitude >= 0.01:
        return f"{value:.2f}"
    else:
        # For very small costs, show more decimal places
        import math

        return f"{value:.{max(2, 2 - int(math.log10(magnitude)))}f}"


def _print_cost_statistics(
    agent, total_tokens: int, show_header: bool = False, show_disclaimer: bool = False
):
    """Print cost statistics section.

    Args:
        agent: PatchPalAgent instance
        total_tokens: Total token count for calculating averages
        show_header: If True, print a section header
        show_disclaimer: If True, show disclaimer about checking provider bills
    """
    if agent.cumulative_cost > 0:
        if show_header:
            print("\n  \033[1;36mCost Statistics\033[0m")
        print(f"  Session cost: ${_format_cost(agent.cumulative_cost)} (estimated)")

        # Check if using GovCloud pricing
        from patchpal.agent import _is_govcloud_bedrock

        if agent.model_id.startswith("bedrock/") and _is_govcloud_bedrock(agent.model_id):
            print("  \033[2m(Using AWS GovCloud pricing: ~1.2x commercial rates)\033[0m")

        if show_disclaimer:
            print(
                "  \033[2m(Calculated from token counts - check provider bill for exact cost)\033[0m"
            )

        # Show cost breakdown if we have token data
        if total_tokens > 0:
            cost_per_1k = (agent.cumulative_cost / total_tokens) * 1000
            print(f"  Average: ${_format_cost(cost_per_1k)} per 1K tokens")
    elif agent.total_llm_calls > 0:
        # Model might not have pricing data (e.g., local Ollama)
        if show_header:
            print()
        print("  \033[2mCost tracking unavailable (no pricing data for this model)\033[0m")


def _print_session_summary(agent, show_detailed: bool = False):
    """Print session statistics summary.

    Args:
        agent: PatchPalAgent instance
        show_detailed: If True, show detailed breakdown; if False, show compact summary
    """
    # Guard against missing attributes (e.g., in tests with mock agents)
    if (
        not hasattr(agent, "total_llm_calls")
        or not isinstance(agent.total_llm_calls, int)
        or agent.total_llm_calls == 0
    ):
        return

    print("\n" + "=" * 70)
    print("\033[1;36mSession Summary\033[0m")
    print("=" * 70)
    print(f"  LLM calls: {agent.total_llm_calls}")

    # Show token usage if available
    has_usage_info = (
        hasattr(agent, "cumulative_input_tokens")
        and hasattr(agent, "cumulative_output_tokens")
        and (agent.cumulative_input_tokens > 0 or agent.cumulative_output_tokens > 0)
    )
    if has_usage_info:
        total_tokens = agent.cumulative_input_tokens + agent.cumulative_output_tokens
        print(f"  Total tokens: {total_tokens:,}")

        # Show cache hit rate if caching was used (Anthropic/Bedrock)
        if (
            hasattr(agent, "cumulative_cache_read_tokens")
            and hasattr(agent, "cumulative_input_tokens")
            and agent.cumulative_cache_read_tokens > 0
        ):
            cache_hit_rate = (
                agent.cumulative_cache_read_tokens / agent.cumulative_input_tokens
            ) * 100
            print(f"  Cache hit rate (Anthropic): {cache_hit_rate:.1f}%")

        # Show OpenAI cache hit rate if caching was used
        if (
            hasattr(agent, "cumulative_openai_cached_tokens")
            and hasattr(agent, "cumulative_input_tokens")
            and agent.cumulative_openai_cached_tokens > 0
        ):
            cache_hit_rate = (
                agent.cumulative_openai_cached_tokens / agent.cumulative_input_tokens
            ) * 100
            print(f"  Cache hit rate (OpenAI): {cache_hit_rate:.1f}%")

    # Show cost statistics
    if has_usage_info:
        total_tokens = agent.cumulative_input_tokens + agent.cumulative_output_tokens
    else:
        total_tokens = 0

    if show_detailed:
        _print_cost_statistics(agent, total_tokens, show_header=False, show_disclaimer=False)
    else:
        # Show cost if available (compact version)
        if hasattr(agent, "cumulative_cost") and agent.cumulative_cost > 0:
            print(f"  Session cost: ${_format_cost(agent.cumulative_cost)} (estimated)")

    print("=" * 70)


class SkillCompleter(Completer):
    """Completer for skill names when input starts with /"""

    def __init__(self):
        self.repo_root = Path(".").resolve()

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # Only complete if line starts with /
        if not text.startswith("/"):
            return

        # Get the text after the /
        word = text[1:]

        # Import here to avoid circular imports
        from patchpal.skills import discover_skills

        try:
            # Get all available skills
            skills = discover_skills(repo_root=self.repo_root)

            # Filter skills that match the current word
            for skill_name in sorted(skills.keys()):
                if skill_name.startswith(word):
                    # Calculate how much we need to complete
                    yield Completion(
                        skill_name,
                        start_position=-len(word),
                        display=skill_name,
                        display_meta=skills[skill_name].description[:60] + "..."
                        if len(skills[skill_name].description) > 60
                        else skills[skill_name].description,
                    )
        except Exception:
            # Silently fail if skills discovery fails
            pass


class SmartPathCompleter(Completer):
    """Path completer that works anywhere in the text, not just at the start."""

    def __init__(self):
        self.path_completer = PathCompleter(expanduser=True)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # Find the start of the current path-like token
        # Look for common path prefixes: ./ ../ / ~/
        import re

        # Find all potential path starts
        path_pattern = r"(?:^|[\s])([.~/][\S]*?)$"
        match = re.search(path_pattern, text)

        if match:
            # Extract the path portion
            path_start = match.group(1)

            # Create a fake document with just the path for PathCompleter
            fake_doc = Document(path_start, len(path_start))

            # Get completions from PathCompleter
            for completion in self.path_completer.get_completions(fake_doc, complete_event):
                # Use the PathCompleter's start_position directly
                # It's already calculated correctly relative to the cursor
                yield Completion(
                    completion.text,
                    start_position=completion.start_position,
                    display=completion.display,
                    display_meta=completion.display_meta,
                )


def _get_version() -> str:
    """Get the PatchPal version string."""
    from patchpal import __version__

    return __version__


def _get_patchpal_dir() -> Path:
    """Get the patchpal directory for this repository.

    Returns the directory ~/.patchpal/<repo-name>/ where repo-specific
    data like history and logs are stored.
    """
    repo_root = Path(".").resolve()
    home = Path.home()
    patchpal_root = home / ".patchpal"

    # Use repo name (last part of path) to create unique directory
    repo_name = repo_root.name
    repo_dir = patchpal_root / repo_name

    # Create directory if it doesn't exist
    repo_dir.mkdir(parents=True, exist_ok=True)

    return repo_dir


def _save_to_history_file(command: str, history_file: Path, max_entries: int = 8000):
    """Append a command to the persistent history file.

    This allows users to manually review their command history,
    while keeping InMemoryHistory for session-only terminal scrolling.

    Keeps only the last max_entries commands to prevent unbounded growth.
    """
    try:
        from datetime import datetime

        # Read existing entries
        entries = []
        if history_file.exists():
            with open(history_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                # Each entry is 2 lines (timestamp + command)
                for i in range(0, len(lines), 2):
                    if i + 1 < len(lines):
                        entries.append((lines[i], lines[i + 1]))

        # Add new entry
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entries.append((f"# {timestamp}\n", f"+{command}\n"))

        # Keep only last N entries
        entries = entries[-max_entries:]

        # Write back
        with open(history_file, "w", encoding="utf-8") as f:
            for ts, cmd in entries:
                f.write(ts)
                f.write(cmd)
    except Exception:
        # Silently fail if history can't be written
        pass


def main():
    """Main CLI entry point for PatchPal."""
    # Suppress warnings to keep CLI clean (e.g., Pydantic, deprecation warnings from dependencies)
    warnings.simplefilter("ignore")

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="PatchPal - Claude Code Clone",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  patchpal                                    # Use default model
  patchpal --model openai/gpt-4o              # Use GPT-4o
  patchpal --model anthropic/claude-opus-4    # Use Claude Opus
  patchpal --model ollama_chat/llama3.1            # Use Ollama (local, no API key!)
  PATCHPAL_MODEL=openai/gpt-4o patchpal       # Use environment variable

Supported models: Any LiteLLM-supported model
  - Anthropic: anthropic/claude-sonnet-4-5 (default), anthropic/claude-opus-4-5, etc.
  - OpenAI: openai/gpt-4o, openai/gpt-3.5-turbo, etc.
  - Ollama (local): ollama_chat/llama3.1, ollama_chat/codellama, ollama_chat/deepseek-coder, etc.
  - Others: See https://docs.litellm.ai/docs/providers
        """,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
        help="Show program's version number and exit",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LiteLLM model identifier (e.g., openai/gpt-4o, anthropic/claude-opus-4, ollama_chat/llama3.1). "
        "Can also be set via PATCHPAL_MODEL environment variable.",
    )
    parser.add_argument(
        "--require-permission-for-all",
        action="store_true",
        help="Require permission for ALL operations including read operations (read_file, list_files, etc.). "
        "Use this for maximum security when you want to review every operation the agent performs.",
    )
    args = parser.parse_args()

    # Set the require-permission-for-all flag if specified
    if args.require_permission_for_all:
        from patchpal.tools import set_require_permission_for_all

        set_require_permission_for_all(True)

    # Determine model to use (priority: CLI arg > env var > default)
    model_id = args.model or os.getenv("PATCHPAL_MODEL") or "anthropic/claude-sonnet-4-5"

    # Parse litellm_kwargs from environment variable if set
    # Format: PATCHPAL_LITELLM_KWARGS='{"reasoning_effort": "high", "temperature": 0.7}'
    litellm_kwargs = None
    litellm_kwargs_env = os.getenv("PATCHPAL_LITELLM_KWARGS")
    if litellm_kwargs_env:
        try:
            import json

            litellm_kwargs = json.loads(litellm_kwargs_env)
        except json.JSONDecodeError as e:
            print(f"\033[1;31m⚠️  Warning: Invalid PATCHPAL_LITELLM_KWARGS JSON: {e}\033[0m")
            litellm_kwargs = None

    # Discover custom tools from ~/.patchpal/tools/
    from patchpal.tool_schema import discover_tools, list_custom_tools

    custom_tools = discover_tools()

    # Show custom tools info if any were loaded
    custom_tool_info = list_custom_tools()
    if custom_tool_info:
        tool_names = [name for name, _, _ in custom_tool_info]
        tools_str = ", ".join(tool_names)
        # Store for later display (after model info)
        custom_tools_message = (
            f"\033[1;36m🔧 Loaded {len(custom_tool_info)} custom tool(s): {tools_str}\033[0m"
        )
    else:
        custom_tools_message = None

    # Create the agent with the specified model and custom tools
    # LiteLLM will handle API key validation and provide appropriate error messages
    agent = create_agent(
        model_id=model_id, custom_tools=custom_tools, litellm_kwargs=litellm_kwargs
    )

    # Get max iterations from environment variable or use default
    max_iterations = int(os.getenv("PATCHPAL_MAX_ITERATIONS", "100"))

    # Create Rich console for markdown rendering
    console = Console()

    # Create completers for paths and skills
    path_completer = SmartPathCompleter()
    skill_completer = SkillCompleter()
    # Merge completers - skill completer takes precedence for / commands
    completer = merge_completers([skill_completer, path_completer])

    # Create in-memory history (within session only, no persistence)
    history = InMemoryHistory()

    # Get history file path for manual logging
    history_file = _get_patchpal_dir() / "history.txt"

    print(" ╔═══════════════════════════════════════════════════════════╗")
    print(" ║  PatchPal - AI Coding and Automation Assistant  🤖        ║")
    print(" ╚═══════════════════════════════════════════════════════════╝")
    print(f"\nUsing model: {model_id}")

    # Show custom tools info if any were loaded
    if custom_tools_message:
        print(custom_tools_message)

    # Show litellm_kwargs info if set
    if litellm_kwargs:
        kwargs_str = ", ".join(f"{k}={v}" for k, v in litellm_kwargs.items())
        print(f"\033[1;36m⚙️  LiteLLM parameters: {kwargs_str}\033[0m")

    # Show require-permission-for-all indicator if active
    if args.require_permission_for_all:
        print("\033[1;33m🔒 Permission required for ALL operations (including reads)\033[0m")

    # Show custom prompt indicator if set
    custom_prompt_path = os.getenv("PATCHPAL_SYSTEM_PROMPT")
    use_simple = os.getenv("PATCHPAL_USE_SIMPLE_PROMPT", "").lower() in ("true", "1", "yes")

    if custom_prompt_path:
        print(f"\033[1;36m🔧 Using custom system prompt: {custom_prompt_path}\033[0m")
    elif use_simple:
        print("\033[1;36m🔧 Using simplified system prompt\033[0m")

    print(
        "\nType \033[1;33m'exit'\033[0m to quit or \033[1;33m'/help'\033[0m to see available commands.\n"
    )

    while True:
        try:
            # Flush any pending output to ensure clean prompt
            sys.stdout.flush()
            sys.stderr.flush()

            # Print separator and prompt on fresh line to ensure visibility
            # even if warnings/logs appear above
            print()  # Blank line for separation

            # Use prompt_toolkit for input with autocompletion
            # FormattedText: (style, text) tuples
            prompt_text = FormattedText([("ansibrightcyan bold", "You:"), ("", " ")])
            user_input = pt_prompt(
                prompt_text,
                completer=completer,
                complete_while_typing=False,  # Only show completions on Tab
                history=history,  # In-memory history for this session only
            ).strip()

            # Replace newlines with spaces to prevent history file corruption
            # This can happen if user pastes multi-line text
            user_input = user_input.replace("\n", " ").replace("\r", " ")

            # Save command to history file for manual review
            _save_to_history_file(user_input, history_file)

            # Check for exit commands
            if user_input.lower() in ["exit", "quit", "q"]:
                # Show session statistics before exiting
                _print_session_summary(agent, show_detailed=False)

                # Log session statistics to audit log
                # Guard against missing/invalid attributes (e.g., in tests with mock agents)
                if (
                    hasattr(agent, "total_llm_calls")
                    and isinstance(agent.total_llm_calls, int)
                    and agent.total_llm_calls > 0
                ):
                    log_parts = [f"SESSION_END: {agent.total_llm_calls} LLM calls"]

                    if hasattr(agent, "cumulative_input_tokens") and hasattr(
                        agent, "cumulative_output_tokens"
                    ):
                        log_parts.append(
                            f"{agent.cumulative_input_tokens} input tokens, "
                            f"{agent.cumulative_output_tokens} output tokens"
                        )

                    if (
                        hasattr(agent, "cumulative_cache_read_tokens")
                        and agent.cumulative_cache_read_tokens > 0
                    ):
                        cache_hit_rate = (
                            (
                                agent.cumulative_cache_read_tokens
                                / agent.cumulative_input_tokens
                                * 100
                            )
                            if agent.cumulative_input_tokens > 0
                            else 0
                        )
                        log_parts.append(f"cache hit rate: {cache_hit_rate:.1f}%")

                    if hasattr(agent, "cumulative_cost") and agent.cumulative_cost > 0:
                        log_parts.append(f"cost: ${agent.cumulative_cost:.4f}")

                    audit_logger.info(", ".join(log_parts))

                print("\nGoodbye!")
                break

            # Handle /help command - show available commands
            if user_input.lower() in ["help", "/help"]:
                print("\n" + "=" * 70)
                print("\033[1;36mAvailable Commands\033[0m")
                print("=" * 70)
                print()
                print("  \033[1;33mBasic Commands:\033[0m")
                print("    exit, quit, q        Exit the session")
                print("    /help                Show this help message")
                print()
                print("  \033[1;33mContext Management:\033[0m")
                print("    /status              Show context window usage and token statistics")
                print("    /context             View all messages in conversation history")
                print(
                    "    /context <number>    View specific message by number (0=base system prompt)"
                )
                print("    /clear               Clear conversation history (start fresh)")
                print("    /compact             Manually trigger context compaction")
                print("    /prune               Prune old tool outputs (keeps last 2 turns)")
                print()
                print("  \033[1;33mSkills:\033[0m")
                print("    /skillname [args]    Invoke a skill (e.g., /commit)")
                print("    list skills          Ask agent to list available skills")
                print()
                print("  \033[1;33mTips:\033[0m")
                print("    • Use UP/DOWN arrows to navigate command history")
                print("    • Press TAB for path and skill name completion")
                print("    • Type your questions or requests naturally to the AI agent")
                print("    • Use Ctrl+C to cancel current input (not the entire session)")
                print()
                print("=" * 70 + "\n")
                continue

            # Handle /status command - show context window usage
            if user_input.lower() in ["status", "/status"]:
                stats = agent.context_manager.get_usage_stats(agent.messages)

                print("\n" + "=" * 70)
                print("\033[1;36mContext Window Status\033[0m")
                print("=" * 70)
                print(f"  Model: {model_id}")

                # Show context limit info
                override = os.getenv("PATCHPAL_CONTEXT_LIMIT")
                if override:
                    print(
                        f"  \033[1;33m⚠️  Context limit overridden: {stats['context_limit']:,} tokens (PATCHPAL_CONTEXT_LIMIT={override})\033[0m"
                    )
                else:
                    print(f"  Context limit: {stats['context_limit']:,} tokens (model default)")

                print(f"  Messages in history: {len(agent.messages)}")
                print(f"  System prompt: {stats['system_tokens']:,} tokens")
                print(f"  Conversation: {stats['message_tokens']:,} tokens")
                print(f"  Output reserve: {stats['output_reserve']:,} tokens")
                print(f"  Total: {stats['total_tokens']:,} tokens")
                print(f"  Usage: {stats['usage_percent']}%")

                # Visual progress bar (cap at 100% for display)
                bar_width = 50
                display_ratio = min(stats["usage_ratio"], 1.0)  # Cap at 100% for visual
                filled = int(bar_width * display_ratio)
                empty = bar_width - filled
                bar = "█" * filled + "░" * empty

                # Color based on usage
                if stats["usage_ratio"] < 0.7:
                    color = "\033[32m"  # Green
                elif stats["usage_ratio"] < 0.85:
                    color = "\033[33m"  # Yellow
                else:
                    color = "\033[31m"  # Red

                print(f"  {color}[{bar}]\033[0m")

                # Show warning if over capacity
                if stats["usage_ratio"] > 1.0:
                    print(
                        f"\n  \033[1;31m⚠️  Context is {stats['usage_percent']}% over capacity!\033[0m"
                    )
                    if not agent.enable_auto_compact:
                        print(
                            "  \033[1;33m   Enable auto-compaction or start a new session.\033[0m"
                        )
                    else:
                        print(
                            "  \033[1;33m   Compaction may have failed. Consider starting a new session.\033[0m"
                        )

                    # Also check if context limit is artificially low
                    if override and int(override) < 50000:
                        print(
                            f"  \033[1;33m   Note: Context limit is overridden to a very low value ({override})\033[0m"
                        )
                        print(
                            "  \033[1;33m   Run 'unset PATCHPAL_CONTEXT_LIMIT' to use model's actual capacity.\033[0m"
                        )

                # Show auto-compaction status
                if agent.enable_auto_compact:
                    threshold_pct = int(agent.context_manager.COMPACT_THRESHOLD * 100)
                    print(
                        f"\n  Auto-compaction: \033[32mEnabled\033[0m (triggers at {threshold_pct}%)"
                    )
                else:
                    print(
                        "\n  Auto-compaction: \033[33mDisabled\033[0m (set PATCHPAL_DISABLE_AUTOCOMPACT=false to enable)"
                    )

                # Show cumulative token usage
                print("\n\033[1;36mSession Statistics\033[0m")
                print(f"  LLM calls: {agent.total_llm_calls}")

                # Check if usage info is available (if we have LLM calls but no token counts)
                has_usage_info = (
                    agent.cumulative_input_tokens > 0 or agent.cumulative_output_tokens > 0
                )
                if agent.total_llm_calls > 0 and not has_usage_info:
                    print(
                        "  \033[2mToken usage unavailable (model doesn't report usage info)\033[0m"
                    )
                else:
                    print(f"  Cumulative input tokens: {agent.cumulative_input_tokens:,}")
                    print(f"  Cumulative output tokens: {agent.cumulative_output_tokens:,}")
                    total_tokens = agent.cumulative_input_tokens + agent.cumulative_output_tokens
                    print(f"  Total tokens: {total_tokens:,}")

                    # Show cache statistics if available (Anthropic/Bedrock/OpenAI prompt caching)
                    has_anthropic_cache = (
                        agent.cumulative_cache_creation_tokens > 0
                        or agent.cumulative_cache_read_tokens > 0
                    )
                    has_openai_cache = agent.cumulative_openai_cached_tokens > 0

                    if has_anthropic_cache:
                        print("\n  \033[1;36mPrompt Caching Statistics (Anthropic/Bedrock)\033[0m")
                        print(f"  Cache write tokens: {agent.cumulative_cache_creation_tokens:,}")
                        print(f"  Cache read tokens: {agent.cumulative_cache_read_tokens:,}")

                        # Calculate cache hit rate
                        if agent.cumulative_input_tokens > 0:
                            cache_hit_rate = (
                                agent.cumulative_cache_read_tokens / agent.cumulative_input_tokens
                            ) * 100
                            print(f"  Cache hit rate: {cache_hit_rate:.1f}%")

                        # Show cost-adjusted input tokens (cache reads cost less)
                        # For Anthropic: cache writes = 1.25x, cache reads = 0.1x, regular = 1x
                        if "anthropic" in model_id.lower() or "claude" in model_id.lower():
                            # Break down: cumulative_input = non_cached + cache_read + cache_write
                            non_cached_tokens = (
                                agent.cumulative_input_tokens
                                - agent.cumulative_cache_read_tokens
                                - agent.cumulative_cache_creation_tokens
                            )
                            # Approximate cost-equivalent tokens (cache reads cost 10%, cache writes cost 125%)
                            cost_adjusted = (
                                non_cached_tokens
                                + (agent.cumulative_cache_read_tokens * 0.1)
                                + (agent.cumulative_cache_creation_tokens * 1.25)
                            )
                            savings_pct = (
                                (
                                    (agent.cumulative_input_tokens - cost_adjusted)
                                    / agent.cumulative_input_tokens
                                    * 100
                                )
                                if agent.cumulative_input_tokens > 0
                                else 0
                            )
                            print(
                                f"  Cost-adjusted input tokens: {cost_adjusted:,.0f} (~{savings_pct:.0f}% savings)"
                            )
                            print(
                                "  \033[2m(Cache reads cost 10% of base price, writes cost 125% of base price)\033[0m"
                            )

                    if has_openai_cache:
                        print("\n  \033[1;36mPrompt Caching Statistics (OpenAI)\033[0m")
                        print(f"  Cached tokens: {agent.cumulative_openai_cached_tokens:,}")

                        # Calculate cache hit rate
                        if agent.cumulative_input_tokens > 0:
                            cache_hit_rate = (
                                agent.cumulative_openai_cached_tokens
                                / agent.cumulative_input_tokens
                            ) * 100
                            print(f"  Cache hit rate: {cache_hit_rate:.1f}%")

                        # Show cost-adjusted input tokens
                        # For OpenAI: cached tokens have model-specific discounts (from LiteLLM database)
                        if (
                            "openai" in model_id.lower()
                            or "gpt" in model_id.lower()
                            or model_id.startswith("openai/")
                        ):
                            non_cached_tokens = (
                                agent.cumulative_input_tokens
                                - agent.cumulative_openai_cached_tokens
                            )
                            # Calculate actual discount based on model pricing
                            # We use the same pricing data that _compute_cost_from_tokens uses
                            try:
                                import litellm

                                model_info = litellm.get_model_info(agent.model_id)
                                input_cost = model_info.get("input_cost_per_token", 0)
                                cached_cost = model_info.get("cache_read_input_token_cost", 0)

                                if cached_cost > 0 and input_cost > 0:
                                    # Use actual pricing ratio
                                    cache_multiplier = cached_cost / input_cost
                                    discount_pct = (1 - cache_multiplier) * 100
                                else:
                                    # Fallback to 0.5x if no pricing data
                                    cache_multiplier = 0.5
                                    discount_pct = 50
                            except Exception:
                                # Fallback on error
                                cache_multiplier = 0.5
                                discount_pct = 50

                            cost_adjusted = non_cached_tokens + (
                                agent.cumulative_openai_cached_tokens * cache_multiplier
                            )
                            savings_pct = (
                                (
                                    (agent.cumulative_input_tokens - cost_adjusted)
                                    / agent.cumulative_input_tokens
                                    * 100
                                )
                                if agent.cumulative_input_tokens > 0
                                else 0
                            )
                            print(
                                f"  Cost-adjusted input tokens: {cost_adjusted:,.0f} (~{savings_pct:.0f}% savings)"
                            )
                            print(
                                f"  \033[2m(Cached tokens cost {cache_multiplier * 100:.0f}% of base input price = {discount_pct:.0f}% discount)\033[0m"
                            )

                    # Show cost statistics if available
                    _print_cost_statistics(
                        agent, total_tokens, show_header=True, show_disclaimer=True
                    )

                print("=" * 70 + "\n")
                continue

            # Handle /clear command - clear conversation history
            if user_input.lower() in ["clear", "/clear"]:
                print("\n" + "=" * 70)
                print("\033[1;36mClear Context\033[0m")
                print("=" * 70)

                if not agent.messages:
                    print("\033[1;33m  Context is already empty.\033[0m")
                    print("=" * 70 + "\n")
                    continue

                # Show current status
                stats = agent.context_manager.get_usage_stats(agent.messages)
                print(
                    f"  Current: {len(agent.messages)} messages, {stats['total_tokens']:,} tokens"
                )

                # Confirm before clearing
                try:
                    confirm = pt_prompt(
                        FormattedText(
                            [
                                ("ansiyellow", "  Clear all context and start fresh? (y/n): "),
                                ("", ""),
                            ]
                        )
                    ).strip()
                    if confirm.lower() not in ["y", "yes"]:
                        print("  Cancelled.")
                        print("=" * 70 + "\n")
                        continue
                except KeyboardInterrupt:
                    print("\n  Cancelled.")
                    print("=" * 70 + "\n")
                    continue

                # Clear conversation history
                agent.messages = []
                agent._last_compaction_message_count = 0

                print("\n\033[1;32m✓ Context cleared successfully!\033[0m")
                print("  Starting fresh with empty conversation history.")
                print("  All previous context has been removed - ready for a new task.")
                print("=" * 70 + "\n")
                continue

            # Handle /context command - view current context
            if (
                user_input.lower() == "context"
                or user_input.lower().startswith("context ")
                or user_input.lower().startswith("/context")
            ):
                # Parse optional message number
                parts = user_input.split()
                specific_msg_num = None
                if len(parts) > 1:
                    try:
                        specific_msg_num = int(parts[1])
                    except ValueError:
                        print(f"\033[1;31m  Error: Invalid message number '{parts[1]}'\033[0m")
                        print("  Usage: /context [message_number]")
                        print("=" * 70 + "\n")
                        continue

                print("\n" + "=" * 70)
                print("\033[1;36mCurrent Context\033[0m")
                print("=" * 70)

                # Import SYSTEM_PROMPT to prepend as message 0
                from patchpal.agent import SYSTEM_PROMPT

                # If specific message requested, show only that message
                if specific_msg_num is not None:
                    # Message 0 is the base system prompt
                    if specific_msg_num == 0:
                        base_system_msg = {"role": "system", "content": SYSTEM_PROMPT}
                        msg_tokens = agent.context_manager.estimator.estimate_messages_tokens(
                            [base_system_msg]
                        )

                        role_display = "\033[1;33mSystem (Base Prompt)\033[0m"
                        print(f"  Message [0] {role_display} ({msg_tokens:,} tokens):")
                        print()
                        print(f"  {SYSTEM_PROMPT}")
                        print("=" * 70 + "\n")
                        continue

                    # Messages 1+ are from agent.messages
                    if specific_msg_num < 0 or specific_msg_num > len(agent.messages):
                        print(
                            f"\033[1;31m  Error: Message {specific_msg_num} not found. Valid range: 0-{len(agent.messages)}\033[0m"
                        )
                        print("=" * 70 + "\n")
                        continue

                    msg = agent.messages[specific_msg_num - 1]
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")

                    # Format role with color
                    if role == "user":
                        role_display = "\033[1;36mUser\033[0m"
                    elif role == "assistant":
                        role_display = "\033[1;32mAssistant\033[0m"
                    elif role == "tool":
                        # Show tool name if available
                        tool_name = msg.get("name", "unknown")
                        role_display = f"\033[1;33mTool ({tool_name})\033[0m"
                    else:
                        role_display = f"\033[1;33m{role.capitalize()}\033[0m"

                    # Calculate token count for this message
                    msg_tokens = agent.context_manager.estimator.estimate_messages_tokens([msg])

                    print(f"  Message [{specific_msg_num}] {role_display} ({msg_tokens:,} tokens):")
                    print()

                    # Handle different content types - show full content
                    if isinstance(content, str):
                        print(f"  {content}")
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict):
                                block_type = block.get("type", "unknown")
                                if block_type == "text":
                                    text = block.get("text", "")
                                    print("  [text]")
                                    print(f"  {text}")
                                    print()
                                elif block_type == "tool_use":
                                    tool_name = block.get("name", "unknown")
                                    tool_id = block.get("id", "")
                                    tool_input = block.get("input", {})
                                    print(f"  [tool_use] {tool_name}")
                                    print(f"    id: {tool_id}")
                                    print(f"    input: {tool_input}")
                                    print()
                                elif block_type == "tool_result":
                                    tool_id = block.get("tool_use_id", "")
                                    is_error = block.get("is_error", False)
                                    result_content = block.get("content", "")
                                    status = "error" if is_error else "success"
                                    print(f"  [tool_result] ({status})")
                                    print(f"    tool_use_id: {tool_id}")
                                    print(f"    content: {result_content}")
                                    print()
                                else:
                                    print(f"  [{block_type}]")
                                    print(f"  {block}")
                                    print()
                            else:
                                print(f"  {block}")
                                print()
                    else:
                        print(f"  {content}")

                    print("=" * 70 + "\n")
                    continue

                # Show all messages with summary view
                stats = agent.context_manager.get_usage_stats(agent.messages)
                print(f"  Messages: {len(agent.messages) + 1} (including base system prompt)")
                print(
                    f"  Token usage: {stats['total_tokens']:,} / {stats['context_limit']:,} ({stats['usage_percent']}%)"
                )
                print()

                # Display message 0 - base system prompt
                from patchpal.agent import SYSTEM_PROMPT

                base_system_msg = {"role": "system", "content": SYSTEM_PROMPT}
                base_tokens = agent.context_manager.estimator.estimate_messages_tokens(
                    [base_system_msg]
                )
                print(f"  [0] \033[1;33mSystem (Base Prompt)\033[0m ({base_tokens:,} tokens):")
                preview = SYSTEM_PROMPT[:200]
                if len(SYSTEM_PROMPT) > 200:
                    preview += "..."
                print(f"      {preview}")
                print()

                # Display each message from agent.messages
                for i, msg in enumerate(agent.messages, 1):
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")

                    # Calculate token count for this message
                    msg_tokens = agent.context_manager.estimator.estimate_messages_tokens([msg])

                    # Format role with color
                    if role == "user":
                        role_display = "\033[1;36mUser\033[0m"
                    elif role == "assistant":
                        role_display = "\033[1;32mAssistant\033[0m"
                    elif role == "tool":
                        # Show tool name if available
                        tool_name = msg.get("name", "unknown")
                        role_display = f"\033[1;33mTool ({tool_name})\033[0m"
                    else:
                        role_display = f"\033[1;33m{role.capitalize()}\033[0m"

                    print(f"  [{i}] {role_display} ({msg_tokens:,} tokens):")

                    # Handle different content types
                    if isinstance(content, str):
                        # Simple text content
                        preview = content[:200]
                        if len(content) > 200:
                            preview += "..."
                        print(f"      {preview}")
                    elif isinstance(content, list):
                        # Complex content (e.g., with tool use blocks)
                        for block in content:
                            if isinstance(block, dict):
                                block_type = block.get("type", "unknown")
                                if block_type == "text":
                                    text = block.get("text", "")
                                    preview = text[:200]
                                    if len(text) > 200:
                                        preview += "..."
                                    print(f"      [text] {preview}")
                                elif block_type == "tool_use":
                                    tool_name = block.get("name", "unknown")
                                    tool_id = block.get("id", "")[:8]
                                    print(f"      [tool_use] {tool_name} (id: {tool_id}...)")
                                elif block_type == "tool_result":
                                    tool_id = block.get("tool_use_id", "")[:8]
                                    is_error = block.get("is_error", False)
                                    status = "error" if is_error else "success"
                                    print(f"      [tool_result] id: {tool_id}... ({status})")
                                else:
                                    print(f"      [{block_type}]")
                            else:
                                print(f"      {str(block)[:100]}")
                    else:
                        print(f"      {str(content)[:200]}")

                    print()

                print("=" * 70 + "\n")
                continue

            # Handle /compact command - manually trigger compaction
            if user_input.lower() in ["compact", "/compact"]:
                print("\n" + "=" * 70)
                print("\033[1;36mManual Compaction\033[0m")
                print("=" * 70)

                # Check if auto-compaction is disabled
                if not agent.enable_auto_compact:
                    print(
                        "\033[1;33m⚠️  Auto-compaction is disabled (PATCHPAL_DISABLE_AUTOCOMPACT=true)\033[0m"
                    )
                    print("\033[1;33m   Manual compaction will still work.\033[0m\n")

                # Check current status
                stats_before = agent.context_manager.get_usage_stats(agent.messages)
                print(
                    f"  Current usage: {stats_before['usage_percent']}% "
                    f"({stats_before['total_tokens']:,} / {stats_before['context_limit']:,} tokens)"
                )
                print(f"  Messages: {len(agent.messages)} in history")

                # Check if compaction is needed
                if len(agent.messages) < 5:
                    print("\n\033[1;33m⚠️  Not enough messages to compact (need at least 5)\033[0m")
                    print("=" * 70 + "\n")
                    continue

                if stats_before["usage_ratio"] < 0.5:
                    print(
                        "\n\033[1;33m⚠️  Context usage is below 50% - compaction not recommended\033[0m"
                    )
                    print("\033[2m   Compaction works best when context is >50% full.\033[0m")
                    # Ask for confirmation
                    try:
                        confirm = pt_prompt(
                            FormattedText([("ansiyellow", "   Compact anyway? (y/n): "), ("", "")])
                        ).strip()
                        if confirm.lower() not in ["y", "yes"]:
                            print("=" * 70 + "\n")
                            continue
                    except KeyboardInterrupt:
                        print("\n  Cancelled.")
                        print("=" * 70 + "\n")
                        continue

                print("\n  Compacting conversation history...")
                agent._perform_auto_compaction()

                # Show results
                stats_after = agent.context_manager.get_usage_stats(agent.messages)
                if stats_after["total_tokens"] < stats_before["total_tokens"]:
                    saved = stats_before["total_tokens"] - stats_after["total_tokens"]
                    print("\n\033[1;32m✓ Compaction successful!\033[0m")
                    print(
                        f"  Saved {saved:,} tokens "
                        f"({stats_before['usage_percent']}% → {stats_after['usage_percent']}%)"
                    )
                    print(f"  Messages: {len(agent.messages)} in history")
                else:
                    print(
                        "\n\033[1;33m⚠️  No tokens saved - compaction may not have been effective\033[0m"
                    )

                print("=" * 70 + "\n")
                continue

            # Handle /prune command - manually prune old tool outputs
            if user_input.lower() in ["prune", "/prune"]:
                print("\n" + "=" * 70)
                print("\033[1;36mManual Pruning\033[0m")
                print("=" * 70)

                # Check current status
                stats_before = agent.context_manager.get_usage_stats(agent.messages)

                # Count tool outputs
                tool_messages = [msg for msg in agent.messages if msg.get("role") == "tool"]
                tool_output_tokens = sum(
                    agent.context_manager.estimator.estimate_message_tokens(msg)
                    for msg in tool_messages
                )

                print(
                    f"  Current usage: {stats_before['usage_percent']}% "
                    f"({stats_before['total_tokens']:,} / {stats_before['context_limit']:,} tokens)"
                )
                print(f"  Messages: {len(agent.messages)} total, {len(tool_messages)} tool outputs")
                print(f"  Tool output tokens: {tool_output_tokens:,}")

                # Count protected tool outputs (last 2 conversational turns)
                # A conversational turn = 1 user message + 1 assistant response (which may include tool calls)
                protected_count = 0
                turn_count = 0
                for msg in reversed(agent.messages):
                    if msg.get("role") == "user":
                        turn_count += 1
                    if turn_count >= 2:
                        break
                    if msg.get("role") == "tool":
                        protected_count += 1

                prunable_count = len(tool_messages) - protected_count
                print(f"  Protected (last 2 turns): {protected_count} tool outputs")
                print(f"  Eligible for pruning: {prunable_count} tool outputs")

                # Check if pruning is possible
                if prunable_count == 0:
                    print("\n\033[1;33m⚠️  No old tool outputs to prune\033[0m")
                    print(
                        "\033[2m   Tool outputs from the last 2 conversational turns are protected.\033[0m"
                    )
                    print("=" * 70 + "\n")
                    continue

                # Perform intelligent pruning
                print("\n  Pruning old tool outputs with intelligent summarization...")
                pruned_messages, tokens_saved = agent.context_manager.prune_tool_outputs(
                    agent.messages, intelligent=True, force=True
                )

                if tokens_saved > 0:
                    agent.messages = pruned_messages
                    stats_after = agent.context_manager.get_usage_stats(agent.messages)

                    print("\n\033[1;32m✓ Pruning successful!\033[0m")
                    print(
                        f"  Saved {tokens_saved:,} tokens "
                        f"({stats_before['usage_percent']}% → {stats_after['usage_percent']}%)"
                    )
                    print(f"  Messages: {len(agent.messages)} in history")
                else:
                    print("\n\033[1;33m⚠️  No tokens saved\033[0m")
                    print("\033[2m   Eligible tool outputs may already be optimally sized.\033[0m")

                print("=" * 70 + "\n")
                continue

            # Skip empty input
            if not user_input:
                continue

            # Handle skill invocations (/skillname args...)
            if user_input.startswith("/"):
                parts = user_input[1:].split(maxsplit=1)
                skill_name = parts[0]
                skill_args = parts[1] if len(parts) > 1 else ""

                from pathlib import Path

                from patchpal.skills import get_skill

                skill = get_skill(skill_name, repo_root=Path(".").resolve())

                if skill:
                    print(f"\n\033[1;35m⚡ Invoking skill: {skill.name}\033[0m")
                    print("=" * 80)

                    # Pass skill instructions to agent with context
                    prompt = f"Execute this skill:\n\n{skill.instructions}"
                    if skill_args:
                        prompt += f"\n\nArguments: {skill_args}"

                    # Log user prompt to audit log
                    audit_logger.info(f"USER_PROMPT: /{skill_name} {skill_args}")
                    result = agent.run(prompt, max_iterations=max_iterations)

                    print("\n" + "=" * 80)
                    print("\033[1;32mAgent:\033[0m")
                    print("=" * 80)
                    console.print(Markdown(result))
                    print("=" * 80)
                else:
                    print(f"\n\033[1;31mSkill not found: {skill_name}\033[0m")
                    print("Ask 'list skills' to see available skills.")
                    print(
                        "See example skills at: https://github.com/amaiya/patchpal/tree/main/examples/skills"
                    )

                continue

            # Run the agent (Ctrl-C here will interrupt agent, not exit)
            try:
                print()  # Add blank line before agent output
                # Log user prompt to audit log
                audit_logger.info(f"USER_PROMPT: {user_input}")
                result = agent.run(user_input, max_iterations=max_iterations)

                print("\n" + "=" * 80)
                print("\033[1;32mAgent:\033[0m")
                print("=" * 80)
                # Render markdown output
                console.print(Markdown(result))
                print("=" * 80)

            except KeyboardInterrupt:
                print(
                    "\n\n\033[1;33mAgent interrupted.\033[0m Type your next command or 'exit' to quit."
                )
                continue

        except KeyboardInterrupt:
            # Ctrl-C during input prompt - show message instead of exiting
            print("\n\n\033[1;33mUse 'exit' to quit PatchPal.\033[0m")
            print(
                "\033[2m(Ctrl-C is reserved for interrupting the agent during execution)\033[0m\n"
            )
            continue
        except Exception as e:
            print(f"\n\033[1;31mError:\033[0m {e}")
            print("Please try again or type 'exit' to quit.")


if __name__ == "__main__":
    main()
