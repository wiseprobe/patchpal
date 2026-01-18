#!/bin/bash
# Development setup script for PatchPal
# This script sets up the development environment with all necessary dependencies

set -e  # Exit on error

echo "======================================"
echo "PatchPal Development Setup"
echo "======================================"
echo ""

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Check if Python 3.10+ is available
if ! python3 -c 'import sys; exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    echo "ERROR: Python 3.10 or higher is required"
    exit 1
fi

echo ""
echo "Installing PatchPal in development mode..."
pip install -e ".[dev]"

echo ""
echo "Installing pre-commit..."
pip install pre-commit

echo ""
echo "Setting up pre-commit hooks..."
pre-commit install

echo ""
echo "======================================"
echo "Setup complete! 🎉"
echo "======================================"
echo ""
echo "Next steps:"
echo "  1. Set your API key:"
echo "     export ANTHROPIC_API_KEY=your_api_key_here"
echo ""
echo "  2. Run PatchPal:"
echo "     patchpal"
echo ""
echo "  3. Run tests:"
echo "     pytest -v"
echo ""
echo "  4. Format code:"
echo "     ruff format patchpal tests"
echo ""
echo "  5. Lint code:"
echo "     ruff check --fix patchpal tests"
echo ""
echo "  6. Run pre-commit on all files:"
echo "     pre-commit run --all-files"
echo ""
echo "For more information, see CONTRIBUTING.md"
echo ""
