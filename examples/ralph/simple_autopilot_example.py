#!/usr/bin/env python3
"""
Simple autopilot example - Use autopilot_loop() as a library function

This example shows how to use autopilot_loop() directly in Python code
rather than via the CLI.
"""

import sys

try:
    from patchpal.autopilot import autopilot_loop
except ImportError:
    # Fallback for running from examples directory before installation
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from patchpal.autopilot import autopilot_loop


def main():
    """Run a simple autopilot task programmatically."""

    prompt = """
Build a simple Python calculator module.

Requirements:
- Create calculator.py with add, subtract, multiply, divide functions
- Handle division by zero with appropriate error
- Create test_calculator.py with pytest tests
- All tests must pass

Process:
1. Create calculator.py with functions
2. Create test_calculator.py with tests for each function
3. Run tests: run_shell("pytest test_calculator.py -v")
4. Fix any failures
5. Repeat until all tests pass

When all tests pass, output: <promise>CALCULATOR_COMPLETE</promise>
"""

    print("=" * 80)
    print("Simple Autopilot Example: Build a Calculator")
    print("=" * 80)
    print()

    result = autopilot_loop(
        prompt=prompt,
        completion_promise="CALCULATOR_COMPLETE",
        max_iterations=10,
        model=None,  # Use default model
    )

    if result:
        print("\n🎉 Calculator completed successfully!")
        print("Check the generated files: calculator.py and test_calculator.py")
        return True
    else:
        print("\n⚠️  Task did not complete within max iterations")
        return False


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
