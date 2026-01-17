import os
import sys
import argparse
import warnings
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import Completer, Completion, PathCompleter, merge_completers
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import InMemoryHistory
from patchpal.agent import create_agent


class SkillCompleter(Completer):
    """Completer for skill names when input starts with /"""

    def __init__(self):
        self.repo_root = Path(".").resolve()

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # Only complete if line starts with /
        if not text.startswith('/'):
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
                        display_meta=skills[skill_name].description[:60] + "..." if len(skills[skill_name].description) > 60 else skills[skill_name].description
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
        path_pattern = r'(?:^|[\s])([.~/][\S]*?)$'
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
                    display_meta=completion.display_meta
                )


def _get_patchpal_dir() -> Path:
    """Get the patchpal directory for this repository.

    Returns the directory ~/.patchpal/<repo-name>/ where repo-specific
    data like history and logs are stored.
    """
    repo_root = Path(".").resolve()
    home = Path.home()
    patchpal_root = home / '.patchpal'

    # Use repo name (last part of path) to create unique directory
    repo_name = repo_root.name
    repo_dir = patchpal_root / repo_name

    # Create directory if it doesn't exist
    repo_dir.mkdir(parents=True, exist_ok=True)

    return repo_dir


# Enable command history with up/down arrows
try:
    import readline
    import atexit

    # Use repo-specific history file
    history_file = _get_patchpal_dir() / 'history.txt'

    try:
        readline.read_history_file(str(history_file))
    except FileNotFoundError:
        pass

    # Save history on exit
    atexit.register(readline.write_history_file, str(history_file))

    # Set history length
    readline.set_history_length(1000)
except ImportError:
    # readline not available (e.g., on Windows without pyreadline3)
    pass


def main():
    """Main CLI entry point for PatchPal."""
    # Suppress warnings to keep CLI clean (e.g., Pydantic, deprecation warnings from dependencies)
    warnings.simplefilter('ignore')

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
        """
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LiteLLM model identifier (e.g., openai/gpt-4o, anthropic/claude-opus-4, ollama_chat/llama3.1). "
             "Can also be set via PATCHPAL_MODEL environment variable."
    )
    args = parser.parse_args()

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

    print("=" * 80)
    print("PatchPal - a lightweight, flexible Claude Code clone")
    print("=" * 80)
    print(f"\nUsing model: {model_id}")
    print("\nType 'exit' or 'quit' to exit the program.")
    print("Ask 'list skills' to see available skills, or use /skillname to invoke one.")
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
            prompt_text = FormattedText([
                ('ansibrightcyan bold', 'You:'),
                ('', ' ')
            ])
            user_input = pt_prompt(
                prompt_text,
                completer=completer,
                complete_while_typing=False,  # Only show completions on Tab
                history=history  # In-memory history for this session only
            ).strip()

            # Replace newlines with spaces to prevent history file corruption
            # This can happen if user pastes multi-line text
            user_input = user_input.replace('\n', ' ').replace('\r', ' ')

            # Check for exit commands
            if user_input.lower() in ['exit', 'quit', 'q']:
                print("\nGoodbye!")
                break

            # Skip empty input
            if not user_input:
                continue

            # Handle skill invocations (/skillname args...)
            if user_input.startswith('/'):
                parts = user_input[1:].split(maxsplit=1)
                skill_name = parts[0]
                skill_args = parts[1] if len(parts) > 1 else ""

                from patchpal.skills import get_skill
                from pathlib import Path

                skill = get_skill(skill_name, repo_root=Path(".").resolve())

                if skill:
                    print(f"\n\033[1;35m⚡ Invoking skill: {skill.name}\033[0m")
                    print("=" * 80)

                    # Pass skill instructions to agent with context
                    prompt = f"Execute this skill:\n\n{skill.instructions}"
                    if skill_args:
                        prompt += f"\n\nArguments: {skill_args}"

                    result = agent.run(prompt, max_iterations=max_iterations)

                    print("\n" + "=" * 80)
                    print("\033[1;32mAgent:\033[0m")
                    print("=" * 80)
                    console.print(Markdown(result))
                    print("=" * 80)
                else:
                    print(f"\n\033[1;31mSkill not found: {skill_name}\033[0m")
                    print("Ask 'list skills' to see available skills.")
                    print("See example skills at: https://github.com/amaiya/patchpal/tree/main/examples/skills")

                continue

            # Run the agent (Ctrl-C here will interrupt agent, not exit)
            try:
                print()  # Add blank line before agent output
                result = agent.run(user_input, max_iterations=max_iterations)

                print("\n" + "=" * 80)
                print("\033[1;32mAgent:\033[0m")
                print("=" * 80)
                # Render markdown output
                console.print(Markdown(result))
                print("=" * 80)

            except KeyboardInterrupt:
                print("\n\n\033[1;33mAgent interrupted.\033[0m Type your next command or 'exit' to quit.")
                continue

        except KeyboardInterrupt:
            # Ctrl-C during input prompt - exit the program
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n\033[1;31mError:\033[0m {e}")
            print("Please try again or type 'exit' to quit.")


if __name__ == "__main__":
    main()
