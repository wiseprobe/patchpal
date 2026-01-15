"""Tests for patchpal.agent module."""

import pytest
from unittest.mock import patch, MagicMock


def test_create_agent_default_model():
    """Test creating an agent with default model."""
    with patch("patchpal.agent.LiteLLMModel") as mock_model, \
         patch("patchpal.agent.ToolCallingAgent") as mock_agent:

        from patchpal.agent import create_agent

        agent = create_agent()

        # Verify LiteLLMModel was called with default model
        mock_model.assert_called_once_with(
            model_id="anthropic/claude-sonnet-4-5"
        )

        # Verify ToolCallingAgent was created
        mock_agent.assert_called_once()
        call_kwargs = mock_agent.call_args[1]
        assert "model" in call_kwargs
        assert "tools" in call_kwargs
        assert "instructions" in call_kwargs
        assert len(call_kwargs["tools"]) == 4  # read_file, list_files, apply_patch, run_shell


def test_create_agent_custom_model():
    """Test creating an agent with a custom model."""
    with patch("patchpal.agent.LiteLLMModel") as mock_model, \
         patch("patchpal.agent.ToolCallingAgent") as mock_agent:

        from patchpal.agent import create_agent

        agent = create_agent(model_id="openai/gpt-4o")

        # Verify LiteLLMModel was called with custom model
        mock_model.assert_called_once_with(model_id="openai/gpt-4o")


def test_create_agent_ollama_model():
    """Test creating an agent with an Ollama model."""
    with patch("patchpal.agent.LiteLLMModel") as mock_model, \
         patch("patchpal.agent.ToolCallingAgent") as mock_agent:

        from patchpal.agent import create_agent

        agent = create_agent(model_id="ollama/llama3.1")

        # Verify LiteLLMModel was called with Ollama model
        mock_model.assert_called_once_with(model_id="ollama/llama3.1")


def test_create_agent_has_correct_tools():
    """Test that the agent is created with the correct tools."""
    with patch("patchpal.agent.LiteLLMModel"), \
         patch("patchpal.agent.ToolCallingAgent") as mock_agent, \
         patch("patchpal.agent.tool") as mock_tool:

        from patchpal.agent import create_agent

        # Make tool() return a recognizable mock for each tool
        mock_tool.side_effect = lambda func: MagicMock(name=func.__name__)

        agent = create_agent()

        # Verify tool() was called 4 times (once for each tool function)
        assert mock_tool.call_count == 4


def test_create_agent_instructions():
    """Test that the agent has proper instructions."""
    with patch("patchpal.agent.LiteLLMModel"), \
         patch("patchpal.agent.ToolCallingAgent") as mock_agent:

        from patchpal.agent import create_agent

        agent = create_agent()

        call_kwargs = mock_agent.call_args[1]
        instructions = call_kwargs["instructions"]

        # Verify instructions mention the tools
        assert "read_file" in instructions
        assert "list_files" in instructions
        assert "apply_patch" in instructions
        assert "run_shell" in instructions

        # Verify instructions have guidance
        assert "senior software engineer" in instructions.lower()
