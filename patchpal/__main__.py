"""Entry point for python -m patchpal"""

import sys

if __name__ == "__main__":
    # Check if subcommand specified
    if len(sys.argv) > 1 and sys.argv[1] in ("autopilot", "ralph"):
        # Run autopilot mode (ralph is an alias)
        from patchpal.autopilot import main

        sys.argv.pop(1)  # Remove subcommand from argv
        main()
    else:
        # Default to main interactive CLI
        from patchpal.cli import main

        main()
