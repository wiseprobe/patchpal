"""Tests for patchpal.cli module."""

import pytest
from unittest.mock import patch, MagicMock
import sys
from io import StringIO


def test_main_uses_default_model(monkeypatch):
    """Test that main() uses the default model when no args provided."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    with patch("patchpal.cli.create_agent") as mock_create, \
         patch("builtins.input", side_effect=["exit"]):

        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        # Verify create_agent was called with default model
        mock_create.assert_called_once_with(model_id="anthropic/claude-sonnet-4-5")


def test_main_uses_cli_model_arg(monkeypatch):
    """Test that main() uses model from CLI argument."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["patchpal", "--model", "openai/gpt-4o"])

    with patch("patchpal.cli.create_agent") as mock_create, \
         patch("builtins.input", side_effect=["exit"]):

        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        # Verify create_agent was called with CLI model
        mock_create.assert_called_once_with(model_id="openai/gpt-4o")


def test_main_uses_env_var_model(monkeypatch):
    """Test that main() uses model from environment variable."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("PATCHPAL_MODEL", "ollama/llama3.1")
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    with patch("patchpal.cli.create_agent") as mock_create, \
         patch("builtins.input", side_effect=["exit"]):

        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        # Verify create_agent was called with env var model
        mock_create.assert_called_once_with(model_id="ollama/llama3.1")


def test_main_cli_arg_overrides_env_var(monkeypatch):
    """Test that CLI argument takes precedence over environment variable."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("PATCHPAL_MODEL", "ollama/llama3.1")
    monkeypatch.setattr(sys, "argv", ["patchpal", "--model", "openai/gpt-4o"])

    with patch("patchpal.cli.create_agent") as mock_create, \
         patch("builtins.input", side_effect=["exit"]):

        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        # Verify CLI arg takes precedence
        mock_create.assert_called_once_with(model_id="openai/gpt-4o")


def test_main_exits_without_api_key(monkeypatch, capsys):
    """Test that main() exits if ANTHROPIC_API_KEY is not set."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    from patchpal.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1

    captured = capsys.readouterr()
    assert "ANTHROPIC_API_KEY" in captured.out
    assert "environment variable not set" in captured.out


def test_main_handles_quit_command(monkeypatch, capsys):
    """Test that main() exits on 'quit' command."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    with patch("patchpal.cli.create_agent") as mock_create, \
         patch("builtins.input", side_effect=["quit"]):

        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        captured = capsys.readouterr()
        assert "Goodbye" in captured.out


def test_main_handles_exit_command(monkeypatch, capsys):
    """Test that main() exits on 'exit' command."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    with patch("patchpal.cli.create_agent") as mock_create, \
         patch("builtins.input", side_effect=["exit"]):

        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        captured = capsys.readouterr()
        assert "Goodbye" in captured.out


def test_main_handles_keyboard_interrupt(monkeypatch, capsys):
    """Test that main() handles KeyboardInterrupt gracefully."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    with patch("patchpal.cli.create_agent") as mock_create, \
         patch("builtins.input", side_effect=KeyboardInterrupt):

        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        captured = capsys.readouterr()
        assert "Interrupted" in captured.out or "Goodbye" in captured.out


def test_main_handles_agent_error(monkeypatch, capsys):
    """Test that main() handles agent errors gracefully."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    with patch("patchpal.cli.create_agent") as mock_create, \
         patch("builtins.input", side_effect=["test query", "exit"]):

        mock_agent = MagicMock()
        mock_agent.run.side_effect = Exception("Test error")
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        captured = capsys.readouterr()
        assert "Error:" in captured.out
        assert "Test error" in captured.out


def test_main_runs_agent_with_user_input(monkeypatch):
    """Test that main() runs agent with user input."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    with patch("patchpal.cli.create_agent") as mock_create, \
         patch("builtins.input", side_effect=["What files are here?", "exit"]):

        mock_agent = MagicMock()
        mock_agent.run.return_value = "Here are the files..."
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        # Verify agent.run was called with user input
        mock_agent.run.assert_called_once_with("What files are here?")


def test_main_skips_empty_input(monkeypatch):
    """Test that main() skips empty input."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    with patch("patchpal.cli.create_agent") as mock_create, \
         patch("builtins.input", side_effect=["", "   ", "exit"]):

        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        # Verify agent.run was never called (empty inputs were skipped)
        mock_agent.run.assert_not_called()


def test_main_displays_model_name(monkeypatch, capsys):
    """Test that main() displays which model is being used."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["patchpal", "--model", "openai/gpt-4o"])

    with patch("patchpal.cli.create_agent") as mock_create, \
         patch("builtins.input", side_effect=["exit"]):

        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        captured = capsys.readouterr()
        assert "Using model: openai/gpt-4o" in captured.out
