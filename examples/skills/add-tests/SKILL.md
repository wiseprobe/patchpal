---
name: add-tests
description: Add comprehensive tests for Python code with pytest
---

# Add Tests Workflow

Follow this workflow to add well-structured tests to Python code.

## 1. Understand the Code

- Use `read_file` to examine the code that needs testing
- Identify functions, classes, and methods to test
- Note edge cases, error conditions, and expected behavior

## 2. Create Test File Structure

Tests should follow this structure:

```python
"""Tests for module_name."""

import pytest
from module_name import function_to_test, ClassName


@pytest.fixture
def sample_data():
    """Fixture providing sample test data."""
    return {
        'key': 'value',
        'number': 42
    }


def test_function_basic_case():
    """Test function_to_test with basic input."""
    result = function_to_test('input')
    assert result == 'expected_output'


def test_function_edge_case():
    """Test function_to_test with edge case."""
    result = function_to_test('')
    assert result is None


def test_function_raises_error():
    """Test function_to_test raises appropriate error."""
    with pytest.raises(ValueError, match="invalid input"):
        function_to_test(None)


class TestClassName:
    """Tests for ClassName."""

    def test_init(self):
        """Test ClassName initialization."""
        obj = ClassName('param')
        assert obj.attribute == 'param'

    def test_method(self, sample_data):
        """Test ClassName.method with fixture data."""
        obj = ClassName('test')
        result = obj.method(sample_data)
        assert result == 'expected'
```

## 3. Test Coverage Guidelines

For each function/method, write tests for:

**Normal Cases:**
- Typical valid inputs
- Boundary values

**Edge Cases:**
- Empty inputs
- None values
- Zero/negative numbers
- Empty collections

**Error Cases:**
- Invalid input types
- Out-of-range values
- Missing required data

**Example test structure:**

```python
def test_calculate_discount_normal():
    """Test discount calculation with normal values."""
    assert calculate_discount(100, 0.1) == 90.0


def test_calculate_discount_zero():
    """Test discount with zero percent."""
    assert calculate_discount(100, 0) == 100.0


def test_calculate_discount_invalid():
    """Test discount rejects invalid percentage."""
    with pytest.raises(ValueError):
        calculate_discount(100, 1.5)  # >100% discount
```

## 4. Mock External Dependencies

Use pytest fixtures and mocks for external dependencies:

```python
from unittest.mock import Mock, patch


@pytest.fixture
def mock_api_client():
    """Mock API client for testing."""
    client = Mock()
    client.fetch_data.return_value = {'data': 'test'}
    return client


def test_function_with_api(mock_api_client):
    """Test function that calls external API."""
    result = process_api_data(mock_api_client)
    assert result == 'processed test'
    mock_api_client.fetch_data.assert_called_once()


@patch('module.requests.get')
def test_http_request(mock_get):
    """Test function making HTTP request."""
    mock_get.return_value.json.return_value = {'status': 'ok'}
    result = fetch_remote_data()
    assert result['status'] == 'ok'
```

## 5. Parametrize for Multiple Cases

Use `@pytest.mark.parametrize` for testing multiple inputs:

```python
@pytest.mark.parametrize("input_val,expected", [
    ("hello", "HELLO"),
    ("World", "WORLD"),
    ("", ""),
    ("123", "123"),
])
def test_uppercase_conversion(input_val, expected):
    """Test string conversion with various inputs."""
    assert to_uppercase(input_val) == expected
```

## 6. Create the Test File

- Place in `tests/` directory
- Name as `test_<module_name>.py`
- Use `apply_patch` to create the test file with content

## 7. Run and Verify

Use `run_shell` to:
1. Run the tests: `pytest tests/test_<module>.py -v`
2. Check coverage: `pytest --cov=<module> tests/test_<module>.py`
3. Fix any failures and iterate

## Best Practices

- **One assertion per test** when possible
- **Descriptive test names** that explain what's being tested
- **Docstrings** for complex tests
- **Arrange-Act-Assert** pattern:
  ```python
  def test_example():
      # Arrange: Set up test data
      input_data = {'key': 'value'}

      # Act: Call the function
      result = function(input_data)

      # Assert: Check the result
      assert result == expected
  ```
- **Test isolation** - each test should be independent
- **Fast tests** - avoid slow operations, use mocks

## Common Pytest Patterns

```python
# Testing exceptions
with pytest.raises(TypeError):
    invalid_function_call()

# Testing warnings
with pytest.warns(UserWarning):
    deprecated_function()

# Skipping tests conditionally
@pytest.mark.skipif(sys.version_info < (3, 9), reason="requires python3.9")
def test_new_feature():
    pass

# Marking tests
@pytest.mark.slow
def test_slow_operation():
    pass

# Testing async code
@pytest.mark.asyncio
async def test_async_function():
    result = await async_operation()
    assert result == 'expected'
```
