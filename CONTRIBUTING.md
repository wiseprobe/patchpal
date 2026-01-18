# Contributing to PatchPal

Thank you for your interest in contributing to PatchPal! This document provides guidelines and instructions for contributing.

## Development Setup

### Quick Setup (Recommended)

We provide a setup script that installs everything you need:

```bash
git clone https://github.com/yourusername/patchpal.git
cd patchpal
bash scripts/setup-dev.sh
```

### Manual Setup

1. **Fork and clone the repository:**
```bash
git clone https://github.com/yourusername/patchpal.git
cd patchpal
```

2. **Install in development mode:**
```bash
pip install -e ".[dev]"
```

3. **Set up pre-commit hooks (recommended):**
```bash
pip install pre-commit
pre-commit install
```

This will automatically run linting and formatting checks before each commit.

## Code Quality Standards

PatchPal uses automated linting and formatting to maintain code quality:

### Ruff (Formatting and Linting)

We use [Ruff](https://docs.astral.sh/ruff/) for both code formatting and linting.

**Auto-format your code:**
```bash
ruff format patchpal tests
```

**Check formatting without making changes:**
```bash
ruff format --check patchpal tests
```

**Auto-fix linting issues:**
```bash
ruff check --fix patchpal tests
```

**Check for linting issues:**
```bash
ruff check patchpal tests
```

### Pre-commit Hooks

If you installed pre-commit hooks, these checks run automatically before each commit:
- Code formatting (ruff format)
- Linting with auto-fix (ruff check)
- Trailing whitespace removal
- End-of-file fixing
- YAML validation
- Merge conflict detection

**Run pre-commit manually on all files:**
```bash
pre-commit run --all-files
```

**Skip pre-commit hooks (not recommended):**
```bash
git commit --no-verify
```

## Running Tests

**Run all tests:**
```bash
pytest
```

**Run with verbose output:**
```bash
pytest -v
```

**Run specific test file:**
```bash
pytest tests/test_tools.py
```

**Run with coverage:**
```bash
pytest --cov=patchpal --cov-report=term-missing
```

**Run tests for a specific function:**
```bash
pytest tests/test_tools.py::test_read_file
```

## CI/CD Pipeline

When you submit a pull request, GitHub Actions will automatically:

1. **Lint your code** - Ruff format and lint checks must pass
2. **Run tests** - All tests must pass on Python 3.10, 3.11, 3.12 (Linux, macOS, Windows)
3. **Build the package** - Ensure distribution builds correctly

**If CI fails:**

### Linting Failures

If ruff format or ruff check fail in CI:

```bash
# Fix formatting
ruff format patchpal tests

# Fix linting issues
ruff check --fix patchpal tests

# Check what still needs manual fixing
ruff check patchpal tests

# Commit the fixes
git add .
git commit -m "Fix linting issues"
git push
```

### Test Failures

If tests fail:

```bash
# Run tests locally to reproduce
pytest -v

# Run specific failing test
pytest tests/test_tools.py::test_specific_function -v

# Fix the issue, then commit
git add .
git commit -m "Fix test failures"
git push
```

## Making Changes

### Before You Start

1. **Create a new branch:**
```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

2. **Ensure your environment is set up:**
```bash
pip install -e ".[dev]"
pre-commit install
```

### Development Workflow

1. **Make your changes**
2. **Run formatting and linting:**
```bash
ruff format patchpal tests
ruff check --fix patchpal tests
```

3. **Run tests:**
```bash
pytest -v
```

4. **Commit your changes:**
```bash
git add .
git commit -m "Brief description of changes"
```

If pre-commit hooks are installed, they'll run automatically and may fix some issues. If they make changes, review them and commit again:
```bash
git add .
git commit -m "Brief description of changes"
```

5. **Push to your fork:**
```bash
git push origin feature/your-feature-name
```

6. **Create a pull request** on GitHub

### Commit Message Guidelines

- Use clear, descriptive commit messages
- Start with a verb in the imperative mood (e.g., "Add", "Fix", "Update", "Remove")
- Keep the first line under 72 characters
- Add more details in the commit body if needed

**Examples:**
```
Add web search timeout configuration

Fix divide by zero error in calculator.py

Update documentation for pre-commit setup
```

## Code Style Guidelines

- Follow PEP 8 (enforced by black and ruff)
- Line length: 100 characters (configured in pyproject.toml)
- Use type hints where appropriate
- Write descriptive variable and function names
- Add docstrings for public functions and classes
- Keep functions focused and concise

## Adding New Features

When adding new features:

1. **Add tests** - New features should include test coverage
2. **Update documentation** - Update README.md and docstrings
3. **Follow existing patterns** - Look at similar code in the project
4. **Keep it simple** - Avoid over-engineering

## Security

- Never commit sensitive information (API keys, credentials, etc.)
- Follow the security model outlined in README.md
- Report security vulnerabilities privately via GitHub Security Advisories

## Getting Help

- **Questions?** Open a GitHub issue with the "question" label
- **Bug reports?** Open a GitHub issue with the "bug" label
- **Feature requests?** Open a GitHub issue with the "enhancement" label

## Code of Conduct

- Be respectful and constructive
- Focus on the code, not the person
- Welcome newcomers and help them get started
- Assume good intentions

## License

By contributing to PatchPal, you agree that your contributions will be licensed under the Apache 2.0 License.
