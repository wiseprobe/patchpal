"""Tests for simplified system prompt."""

import os

from patchpal.agent import _load_system_prompt


def test_simplified_prompt_exists():
    """Test that simplified system prompt file exists."""
    import patchpal

    simple_prompt_path = os.path.join(
        os.path.dirname(patchpal.__file__), "prompts", "system_prompt_simple.md"
    )
    assert os.path.exists(simple_prompt_path), "Simplified prompt file not found"


def test_load_simplified_prompt(monkeypatch):
    """Test that simplified prompt can be loaded via PATCHPAL_USE_SIMPLE_PROMPT."""
    # Clear any existing custom prompt setting
    monkeypatch.delenv("PATCHPAL_SYSTEM_PROMPT", raising=False)
    # Set environment variable to use simplified prompt
    monkeypatch.setenv("PATCHPAL_USE_SIMPLE_PROMPT", "true")

    # Reload the system prompt
    prompt = _load_system_prompt()

    # Verify it loaded the simplified version
    assert "software engineer assistant" in prompt.lower()
    assert len(prompt) < 3000  # Simplified prompt should be shorter than default


def test_load_simplified_prompt_with_path(monkeypatch):
    """Test that PATCHPAL_SYSTEM_PROMPT takes priority over PATCHPAL_USE_SIMPLE_PROMPT."""
    import patchpal

    simple_prompt_path = os.path.join(
        os.path.dirname(patchpal.__file__), "prompts", "system_prompt_simple.md"
    )

    # Set both environment variables
    monkeypatch.setenv("PATCHPAL_USE_SIMPLE_PROMPT", "true")
    monkeypatch.setenv("PATCHPAL_SYSTEM_PROMPT", simple_prompt_path)

    # Reload the system prompt
    prompt = _load_system_prompt()

    # Should still load simplified (path matches)
    assert "software engineer assistant" in prompt.lower()


def test_simplified_prompt_has_required_sections():
    """Test that simplified prompt has all required sections."""
    import patchpal

    simple_prompt_path = os.path.join(
        os.path.dirname(patchpal.__file__), "prompts", "system_prompt_simple.md"
    )

    with open(simple_prompt_path) as f:
        content = f.read()

    # Check for key sections (tools are provided via API, not listed in prompt)
    assert "Overview" in content or "Rules" in content
    assert "Rules" in content

    # Check that strategic guidance is present
    assert "read_file" in content.lower() or "read files" in content.lower()
    assert "edit_file" in content.lower() or "edit files" in content.lower()

    # Check for key behavioral rules
    assert "concise" in content.lower() or "brevity" in content.lower()
    assert "security" in content.lower()


def test_simplified_prompt_template_variables():
    """Test that simplified prompt uses template variables correctly."""
    import patchpal

    simple_prompt_path = os.path.join(
        os.path.dirname(patchpal.__file__), "prompts", "system_prompt_simple.md"
    )

    with open(simple_prompt_path) as f:
        content = f.read()

    # Check that it uses template variables
    assert "{platform_info}" in content
    # May or may not have web_tools depending on design
    # Just check it's properly formatted


def test_token_count_comparison():
    """Compare token counts between default and simplified prompts."""
    import patchpal

    default_prompt_path = os.path.join(
        os.path.dirname(patchpal.__file__), "prompts", "system_prompt.md"
    )
    simple_prompt_path = os.path.join(
        os.path.dirname(patchpal.__file__), "prompts", "system_prompt_simple.md"
    )

    with open(default_prompt_path) as f:
        default_content = f.read()

    with open(simple_prompt_path) as f:
        simple_content = f.read()

    # Simplified should be significantly shorter
    # Even with template variables, simplified should be < 50% of default
    assert len(simple_content) < len(default_content) * 0.5, (
        f"Simplified prompt ({len(simple_content)} chars) should be < 50% "
        f"of default ({len(default_content)} chars)"
    )
