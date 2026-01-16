"""Tests for patchpal.agent module."""

import pytest
from unittest.mock import patch, MagicMock


def test_create_agent_default_model():
    """Test creating an agent with default model."""
    from patchpal.agent import create_agent

    agent = create_agent()

    # Verify agent was created with default model
    assert agent.model_id == "anthropic/claude-sonnet-4-5"
    assert agent.messages == []


def test_create_agent_custom_model():
    """Test creating an agent with a custom model."""
    from patchpal.agent import create_agent

    agent = create_agent(model_id="openai/gpt-4o")

    # Verify agent was created with custom model
    assert agent.model_id == "openai/gpt-4o"


def test_create_agent_ollama_model():
    """Test creating an agent with an Ollama model."""
    from patchpal.agent import create_agent

    agent = create_agent(model_id="ollama_chat/llama3.1")

    # Verify agent was created with Ollama model
    assert agent.model_id == "ollama_chat/llama3.1"


def test_agent_has_correct_tools():
    """Test that the agent has the correct tools defined."""
    from patchpal.agent import TOOLS, TOOL_FUNCTIONS

    # Verify we have 5 tools
    assert len(TOOLS) == 5
    assert len(TOOL_FUNCTIONS) == 5

    # Verify tool names
    tool_names = [tool['function']['name'] for tool in TOOLS]
    assert 'read_file' in tool_names
    assert 'list_files' in tool_names
    assert 'grep_code' in tool_names
    assert 'apply_patch' in tool_names
    assert 'run_shell' in tool_names


def test_agent_system_prompt():
    """Test that the agent has proper system prompt."""
    from patchpal.agent import SYSTEM_PROMPT

    # Verify system prompt mentions the tools
    assert "read_file" in SYSTEM_PROMPT
    assert "list_files" in SYSTEM_PROMPT
    assert "grep_code" in SYSTEM_PROMPT
    assert "apply_patch" in SYSTEM_PROMPT
    assert "run_shell" in SYSTEM_PROMPT

    # Verify system prompt has key principles
    assert "expert software engineer" in SYSTEM_PROMPT.lower()
    assert "avoid over-engineering" in SYSTEM_PROMPT.lower()
    assert "read before modifying" in SYSTEM_PROMPT.lower()


def test_create_agent_bedrock_env_setup(monkeypatch):
    """Test that Bedrock environment variables are set up correctly."""
    import os

    # Clear any existing AWS env vars
    for key in ['AWS_REGION_NAME', 'AWS_BEDROCK_RUNTIME_ENDPOINT']:
        monkeypatch.delenv(key, raising=False)

    # Set Bedrock-specific env vars
    monkeypatch.setenv('AWS_BEDROCK_REGION', 'us-gov-east-1')
    monkeypatch.setenv('AWS_BEDROCK_ENDPOINT', 'https://vpce-test.bedrock-runtime.us-gov-east-1.vpce.amazonaws.com')

    from patchpal.agent import create_agent

    # Create agent with Bedrock model
    agent = create_agent(model_id="bedrock/anthropic.claude-sonnet-4-5-v1:0")

    # Verify environment variables were mapped
    assert os.getenv('AWS_REGION_NAME') == 'us-gov-east-1'
    assert os.getenv('AWS_BEDROCK_RUNTIME_ENDPOINT') == 'https://vpce-test.bedrock-runtime.us-gov-east-1.vpce.amazonaws.com'

    # Verify agent has drop_params set for Bedrock
    assert agent.litellm_kwargs.get('drop_params') == True


def test_create_agent_bedrock_arn_auto_detection(monkeypatch):
    """Test that Bedrock ARNs are automatically detected and prefixed."""
    import os

    # Clear any existing AWS env vars
    for key in ['AWS_REGION_NAME', 'AWS_BEDROCK_RUNTIME_ENDPOINT']:
        monkeypatch.delenv(key, raising=False)

    from patchpal.agent import create_agent

    # Create agent with bare ARN (without bedrock/ prefix)
    arn = "arn:aws-us-gov:bedrock:us-gov-east-1:012345678901:inference-profile/us-gov.anthropic.claude-sonnet-4-5-20250929-v1:0"
    agent = create_agent(model_id=arn)

    # Verify bedrock/ prefix was automatically added and drop_params set
    assert agent.model_id == f"bedrock/{arn}"
    assert agent.litellm_kwargs.get('drop_params') == True


def test_create_agent_bedrock_model_id_auto_detection():
    """Test that standard Bedrock model IDs are automatically detected."""
    from patchpal.agent import create_agent

    # Create agent with bare Bedrock model ID
    agent = create_agent(model_id="anthropic.claude-v2")

    # Verify bedrock/ prefix was automatically added and drop_params set
    assert agent.model_id == "bedrock/anthropic.claude-v2"
    assert agent.litellm_kwargs.get('drop_params') == True


def test_agent_run_simple_response(monkeypatch):
    """Test agent.run() with a simple text response (no tool calls)."""
    from patchpal.agent import create_agent

    # Mock litellm.completion to return a simple text response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = "Hello! I can help you."
    mock_response.choices[0].message.tool_calls = None

    with patch('patchpal.agent.litellm.completion', return_value=mock_response):
        agent = create_agent()
        result = agent.run("Hello")

        assert result == "Hello! I can help you."
        assert len(agent.messages) == 2  # User message + assistant response


def test_agent_run_with_tool_call(monkeypatch):
    """Test agent.run() with a tool call."""
    from patchpal.agent import create_agent

    # First response: agent wants to call list_files
    tool_call = MagicMock()
    tool_call.id = "call_123"
    tool_call.function.name = "list_files"
    tool_call.function.arguments = "{}"

    mock_response1 = MagicMock()
    mock_response1.choices = [MagicMock()]
    mock_response1.choices[0].message = MagicMock()
    mock_response1.choices[0].message.content = ""
    mock_response1.choices[0].message.tool_calls = [tool_call]

    # Second response: agent responds after tool execution
    mock_response2 = MagicMock()
    mock_response2.choices = [MagicMock()]
    mock_response2.choices[0].message = MagicMock()
    mock_response2.choices[0].message.content = "Found 3 files"
    mock_response2.choices[0].message.tool_calls = None

    with patch('patchpal.agent.litellm.completion', side_effect=[mock_response1, mock_response2]):
        with patch('patchpal.agent.list_files', return_value=['file1.py', 'file2.py', 'file3.py']):
            agent = create_agent()
            # Disable permissions for test
            monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

            result = agent.run("List files")

            assert result == "Found 3 files"
            # Should have: user message, assistant with tool call, tool result, assistant response
            assert len(agent.messages) == 4
