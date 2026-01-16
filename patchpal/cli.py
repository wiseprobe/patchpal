import os
import sys
import argparse
import warnings
from pathlib import Path
from patchpal.agent import create_agent


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

    # Check for API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set.")
        print("\nTo fix this:")
        print("1. Get your API key from https://console.anthropic.com/")
        print("2. Set it in your environment:")
        print("   export ANTHROPIC_API_KEY=your_api_key_here")
        print("\nOr create a .env file with:")
        print("   ANTHROPIC_API_KEY=your_api_key_here")
        sys.exit(1)

    # Create the agent with the specified model
    agent = create_agent(model_id=model_id)

    print("=" * 80)
    print("PatchPal - Claude Code Clone")
    print("=" * 80)
    print(f"\nUsing model: {model_id}")
    print("\nType 'exit' or 'quit' to exit the program.")
    print("Press Ctrl-C during agent execution to interrupt the agent.\n")

    while True:
        try:
            # Flush any pending output to ensure clean prompt
            sys.stdout.flush()
            sys.stderr.flush()

            # Print separator and prompt on fresh line to ensure visibility
            # even if warnings/logs appear above
            print()  # Blank line for separation
            # Use \001 and \002 to mark non-printing characters (ANSI codes) for readline
            user_input = input("\001\033[1;36m\002You:\001\033[0m\002 ").strip()

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

            # Run the agent (Ctrl-C here will interrupt agent, not exit)
            try:
                print()  # Add blank line before agent output
                result = agent.run(user_input)

                print("\n" + "=" * 80)
                print("\033[1;32mAgent:\033[0m", result)
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
