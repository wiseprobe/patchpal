"""Tests for patchpal.cli module."""

import sys
from unittest.mock import ANY, MagicMock, patch


def test_main_uses_default_model(monkeypatch):
    """Test that main() uses the default model when no args provided."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    with (
        patch("patchpal.cli.create_agent") as mock_create,
        patch("patchpal.cli.pt_prompt", side_effect=["exit"]),
    ):
        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        # Verify create_agent was called with default model (custom_tools can be anything)
        mock_create.assert_called_once_with(
            model_id="anthropic/claude-sonnet-4-5", custom_tools=ANY, litellm_kwargs=None
        )


def test_main_uses_cli_model_arg(monkeypatch):
    """Test that main() uses model from CLI argument."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["patchpal", "--model", "openai/gpt-4o"])

    with (
        patch("patchpal.cli.create_agent") as mock_create,
        patch("patchpal.cli.pt_prompt", side_effect=["exit"]),
    ):
        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        # Verify create_agent was called with CLI model (custom_tools can be anything)
        mock_create.assert_called_once_with(
            model_id="openai/gpt-4o", custom_tools=ANY, litellm_kwargs=None
        )


def test_main_uses_env_var_model(monkeypatch):
    """Test that main() uses model from environment variable."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("PATCHPAL_MODEL", "ollama_chat/llama3.1")
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    with (
        patch("patchpal.cli.create_agent") as mock_create,
        patch("patchpal.cli.pt_prompt", side_effect=["exit"]),
    ):
        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        # Verify create_agent was called with env var model (custom_tools can be anything)
        mock_create.assert_called_once_with(
            model_id="ollama_chat/llama3.1", custom_tools=ANY, litellm_kwargs=None
        )


def test_main_cli_arg_overrides_env_var(monkeypatch):
    """Test that CLI argument takes precedence over environment variable."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("PATCHPAL_MODEL", "ollama_chat/llama3.1")
    monkeypatch.setattr(sys, "argv", ["patchpal", "--model", "openai/gpt-4o"])

    with (
        patch("patchpal.cli.create_agent") as mock_create,
        patch("patchpal.cli.pt_prompt", side_effect=["exit"]),
    ):
        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        # Verify CLI arg takes precedence (custom_tools can be anything)
        mock_create.assert_called_once_with(
            model_id="openai/gpt-4o", custom_tools=ANY, litellm_kwargs=None
        )


def test_main_handles_quit_command(monkeypatch, capsys):
    """Test that main() exits on 'quit' command."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    with (
        patch("patchpal.cli.create_agent") as mock_create,
        patch("patchpal.cli.pt_prompt", side_effect=["quit"]),
    ):
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

    with (
        patch("patchpal.cli.create_agent") as mock_create,
        patch("patchpal.cli.pt_prompt", side_effect=["exit"]),
    ):
        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        captured = capsys.readouterr()
        assert "Goodbye" in captured.out


def test_main_handles_keyboard_interrupt(monkeypatch, capsys):
    """Test that main() handles KeyboardInterrupt during input by showing message and continuing."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    with (
        patch("patchpal.cli.create_agent") as mock_create,
        patch("patchpal.cli.pt_prompt", side_effect=[KeyboardInterrupt, "exit"]),
    ):
        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        captured = capsys.readouterr()
        # Should show message about using 'exit' instead of exiting immediately
        assert "Use 'exit' to quit" in captured.out
        assert "Ctrl-C is reserved for interrupting the agent" in captured.out
        # Eventually exits with "exit" command
        assert "Goodbye" in captured.out


def test_main_handles_keyboard_interrupt_during_agent_run(monkeypatch, capsys):
    """Test that main() handles KeyboardInterrupt during agent execution without exiting."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    with (
        patch("patchpal.cli.create_agent") as mock_create,
        patch("patchpal.cli.pt_prompt", side_effect=["test query", "exit"]),
    ):
        mock_agent = MagicMock()
        # Agent raises KeyboardInterrupt during execution
        mock_agent.run.side_effect = KeyboardInterrupt
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        captured = capsys.readouterr()
        # Should show "interrupted" message and continue, not exit immediately
        assert "Agent interrupted" in captured.out
        assert "Goodbye" in captured.out  # Eventually exits with "exit" command


def test_main_handles_agent_error(monkeypatch, capsys):
    """Test that main() handles agent errors gracefully."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    with (
        patch("patchpal.cli.create_agent") as mock_create,
        patch("patchpal.cli.pt_prompt", side_effect=["test query", "exit"]),
    ):
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

    with (
        patch("patchpal.cli.create_agent") as mock_create,
        patch("patchpal.cli.pt_prompt", side_effect=["What files are here?", "exit"]),
    ):
        mock_agent = MagicMock()
        mock_agent.run.return_value = "Here are the files..."
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        # Verify agent.run was called with user input and max_iterations
        mock_agent.run.assert_called_once_with("What files are here?", max_iterations=100)


def test_main_skips_empty_input(monkeypatch):
    """Test that main() skips empty input."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    with (
        patch("patchpal.cli.create_agent") as mock_create,
        patch("patchpal.cli.pt_prompt", side_effect=["", "   ", "exit"]),
    ):
        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        # Verify agent.run was never called (empty inputs were skipped)
        mock_agent.run.assert_not_called()


def test_main_respects_max_iterations_env_var(monkeypatch):
    """Test that main() respects PATCHPAL_MAX_ITERATIONS environment variable."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("PATCHPAL_MAX_ITERATIONS", "150")
    monkeypatch.setattr(sys, "argv", ["patchpal"])

    with (
        patch("patchpal.cli.create_agent") as mock_create,
        patch("patchpal.cli.pt_prompt", side_effect=["Test task", "exit"]),
    ):
        mock_agent = MagicMock()
        mock_agent.run.return_value = "Done"
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        # Verify agent.run was called with custom max_iterations from env var
        mock_agent.run.assert_called_once_with("Test task", max_iterations=150)


def test_main_displays_model_name(monkeypatch, capsys):
    """Test that main() displays which model is being used."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["patchpal", "--model", "openai/gpt-4o"])

    with (
        patch("patchpal.cli.create_agent") as mock_create,
        patch("patchpal.cli.pt_prompt", side_effect=["exit"]),
    ):
        mock_agent = MagicMock()
        mock_create.return_value = mock_agent

        from patchpal.cli import main

        main()

        captured = capsys.readouterr()
        assert "Using model: openai/gpt-4o" in captured.out
