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

        agent = create_agent(model_id="ollama_chat/llama3.1")

        # Verify LiteLLMModel was called with Ollama model
        mock_model.assert_called_once_with(model_id="ollama_chat/llama3.1")


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


def test_create_agent_bedrock_env_setup(monkeypatch):
    """Test that Bedrock environment variables are set up correctly."""
    import os

    # Clear any existing AWS env vars
    for key in ['AWS_REGION_NAME', 'AWS_BEDROCK_RUNTIME_ENDPOINT']:
        monkeypatch.delenv(key, raising=False)

    # Set Bedrock-specific env vars
    monkeypatch.setenv('AWS_BEDROCK_REGION', 'us-gov-east-1')
    monkeypatch.setenv('AWS_BEDROCK_ENDPOINT', 'https://vpce-test.bedrock-runtime.us-gov-east-1.vpce.amazonaws.com')

    with patch("patchpal.agent.LiteLLMModel") as mock_model, \
         patch("patchpal.agent.ToolCallingAgent") as mock_agent:

        from patchpal.agent import create_agent

        # Create agent with Bedrock model
        agent = create_agent(model_id="bedrock/anthropic.claude-sonnet-4-5-v1:0")

        # Verify environment variables were mapped
        assert os.getenv('AWS_REGION_NAME') == 'us-gov-east-1'
        assert os.getenv('AWS_BEDROCK_RUNTIME_ENDPOINT') == 'https://vpce-test.bedrock-runtime.us-gov-east-1.vpce.amazonaws.com'

        # Verify LiteLLMModel was called with Bedrock model and drop_params
        mock_model.assert_called_once_with(model_id="bedrock/anthropic.claude-sonnet-4-5-v1:0", drop_params=True)


def test_create_agent_bedrock_arn_auto_detection(monkeypatch):
    """Test that Bedrock ARNs are automatically detected and prefixed."""
    import os

    # Clear any existing AWS env vars
    for key in ['AWS_REGION_NAME', 'AWS_BEDROCK_RUNTIME_ENDPOINT']:
        monkeypatch.delenv(key, raising=False)

    with patch("patchpal.agent.LiteLLMModel") as mock_model, \
         patch("patchpal.agent.ToolCallingAgent") as mock_agent:

        from patchpal.agent import create_agent

        # Create agent with bare ARN (without bedrock/ prefix)
        arn = "arn:aws-us-gov:bedrock:us-gov-east-1:012345678901:inference-profile/us-gov.anthropic.claude-sonnet-4-5-20250929-v1:0"
        agent = create_agent(model_id=arn)

        # Verify bedrock/ prefix was automatically added and drop_params set
        mock_model.assert_called_once_with(model_id=f"bedrock/{arn}", drop_params=True)


def test_create_agent_bedrock_model_id_auto_detection():
    """Test that standard Bedrock model IDs are automatically detected."""
    with patch("patchpal.agent.LiteLLMModel") as mock_model, \
         patch("patchpal.agent.ToolCallingAgent") as mock_agent:

        from patchpal.agent import create_agent

        # Create agent with bare Bedrock model ID
        agent = create_agent(model_id="anthropic.claude-v2")

        # Verify bedrock/ prefix was automatically added and drop_params set
        mock_model.assert_called_once_with(model_id="bedrock/anthropic.claude-v2", drop_params=True)
