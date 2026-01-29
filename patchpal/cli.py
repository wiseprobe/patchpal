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


def _save_to_history_file(command: str, history_file: Path, max_entries: int = 1000):
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

    # Create the agent with the specified model
    # LiteLLM will handle API key validation and provide appropriate error messages
    agent = create_agent(model_id=model_id)

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

    print("=" * 80)
    print("PatchPal - Claude Code–inspired coding and automation assistant")
    print("=" * 80)
    print(f"\nUsing model: {model_id}")

    # Show require-permission-for-all indicator if active
    if args.require_permission_for_all:
        print("\033[1;33m🔒 Permission required for ALL operations (including reads)\033[0m")

    # Show custom prompt indicator if set
    custom_prompt_path = os.getenv("PATCHPAL_SYSTEM_PROMPT")
    if custom_prompt_path:
        print(f"\033[1;36m🔧 Using custom system prompt: {custom_prompt_path}\033[0m")

    print("\nType 'exit' to quit.")
    print(
        "Use '/status' to check context window usage, '/compact' to manually compact, '/clear' to start fresh."
    )
    print("Use 'list skills' to see available skills or /skillname to invoke skills.")
    print("Press Ctrl-C during agent execution to interrupt the agent.\n")

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
                print("\nGoodbye!")
                break

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
