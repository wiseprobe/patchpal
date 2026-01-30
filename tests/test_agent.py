"""Tests for patchpal.agent module."""

from unittest.mock import MagicMock, patch


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
    from patchpal.agent import TOOL_FUNCTIONS, TOOLS

    # Verify we have 24 tools (original 17 + 6 TODO tools + 1 ask_user)
    assert len(TOOLS) == 24
    assert len(TOOL_FUNCTIONS) == 24

    # Verify tool names
    tool_names = [tool["function"]["name"] for tool in TOOLS]
    assert "read_file" in tool_names
    assert "read_lines" in tool_names
    assert "list_files" in tool_names
    assert "get_file_info" in tool_names
    assert "find_files" in tool_names
    assert "tree" in tool_names
    assert "edit_file" in tool_names
    assert "apply_patch" in tool_names
    assert "git_status" in tool_names
    assert "git_diff" in tool_names
    assert "git_log" in tool_names
    assert "grep_code" in tool_names
    assert "list_skills" in tool_names
    assert "use_skill" in tool_names
    assert "web_search" in tool_names
    assert "web_fetch" in tool_names
    assert "run_shell" in tool_names
    # New TODO tools
    assert "todo_add" in tool_names
    assert "todo_list" in tool_names
    assert "todo_complete" in tool_names
    assert "todo_update" in tool_names
    assert "todo_remove" in tool_names
    assert "todo_clear" in tool_names
    # New ask_user tool
    assert "ask_user" in tool_names


def test_agent_system_prompt():
    """Test that the agent has proper system prompt."""
    from patchpal.agent import SYSTEM_PROMPT

    # Verify system prompt mentions the tools
    assert "read_file" in SYSTEM_PROMPT
    assert "list_files" in SYSTEM_PROMPT
    assert "get_file_info" in SYSTEM_PROMPT
    assert "edit_file" in SYSTEM_PROMPT
    assert "apply_patch" in SYSTEM_PROMPT
    assert "git_status" in SYSTEM_PROMPT
    assert "git_diff" in SYSTEM_PROMPT
    assert "git_log" in SYSTEM_PROMPT
    assert "grep_code" in SYSTEM_PROMPT
    assert "web_search" in SYSTEM_PROMPT
    assert "web_fetch" in SYSTEM_PROMPT
    assert "run_shell" in SYSTEM_PROMPT

    # Verify system prompt has key principles
    assert "expert software engineer" in SYSTEM_PROMPT.lower()
    assert "avoid over-engineering" in SYSTEM_PROMPT.lower()
    assert "read before modifying" in SYSTEM_PROMPT.lower()

    # Verify system prompt includes current date/time
    assert "Current Date and Time" in SYSTEM_PROMPT
    assert "Today is" in SYSTEM_PROMPT


def test_create_agent_bedrock_env_setup(monkeypatch):
    """Test that Bedrock environment variables are set up correctly."""
    import os

    # Clear any existing AWS env vars
    for key in ["AWS_REGION_NAME", "AWS_BEDROCK_RUNTIME_ENDPOINT"]:
        monkeypatch.delenv(key, raising=False)

    # Set Bedrock-specific env vars
    monkeypatch.setenv("AWS_BEDROCK_REGION", "us-gov-east-1")
    monkeypatch.setenv(
        "AWS_BEDROCK_ENDPOINT", "https://vpce-test.bedrock-runtime.us-gov-east-1.vpce.amazonaws.com"
    )

    from patchpal.agent import create_agent

    # Create agent with Bedrock model
    agent = create_agent(model_id="bedrock/anthropic.claude-sonnet-4-5-v1:0")

    # Verify environment variables were mapped
    assert os.getenv("AWS_REGION_NAME") == "us-gov-east-1"
    assert (
        os.getenv("AWS_BEDROCK_RUNTIME_ENDPOINT")
        == "https://vpce-test.bedrock-runtime.us-gov-east-1.vpce.amazonaws.com"
    )

    # Verify agent has drop_params set for Bedrock
    assert agent.litellm_kwargs.get("drop_params")


def test_create_agent_bedrock_arn_auto_detection(monkeypatch):
    """Test that Bedrock ARNs are automatically detected and prefixed."""

    # Clear any existing AWS env vars
    for key in ["AWS_REGION_NAME", "AWS_BEDROCK_RUNTIME_ENDPOINT"]:
        monkeypatch.delenv(key, raising=False)

    from patchpal.agent import create_agent

    # Create agent with bare ARN (without bedrock/ prefix)
    arn = "arn:aws-us-gov:bedrock:us-gov-east-1:012345678901:inference-profile/us-gov.anthropic.claude-sonnet-4-5-20250929-v1:0"
    agent = create_agent(model_id=arn)

    # Verify bedrock/ prefix was automatically added and drop_params set
    assert agent.model_id == f"bedrock/{arn}"
    assert agent.litellm_kwargs.get("drop_params")


def test_create_agent_bedrock_model_id_auto_detection():
    """Test that standard Bedrock model IDs are automatically detected."""
    from patchpal.agent import create_agent

    # Create agent with bare Bedrock model ID
    agent = create_agent(model_id="anthropic.claude-v2")

    # Verify bedrock/ prefix was automatically added and drop_params set
    assert agent.model_id == "bedrock/anthropic.claude-v2"
    assert agent.litellm_kwargs.get("drop_params")


def test_agent_run_simple_response(monkeypatch):
    """Test agent.run() with a simple text response (no tool calls)."""
    from patchpal.agent import create_agent

    # Mock litellm.completion to return a simple text response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = "Hello! I can help you."
    mock_response.choices[0].message.tool_calls = None

    with patch("patchpal.agent.litellm.completion", return_value=mock_response):
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

    with patch("patchpal.agent.litellm.completion", side_effect=[mock_response1, mock_response2]):
        with patch("patchpal.agent.list_files", return_value=["file1.py", "file2.py", "file3.py"]):
            agent = create_agent()
            # Disable permissions for test
            monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

            result = agent.run("List files")

            assert result == "Found 3 files"
            # Should have: user message, assistant with tool call, tool result, assistant response
            assert len(agent.messages) == 4


def test_web_tools_enabled_by_default():
    """Test that web tools are enabled by default."""
    # Need to reload module to pick up default env var
    import sys

    # Remove patchpal.agent from cache if present
    if "patchpal.agent" in sys.modules:
        del sys.modules["patchpal.agent"]

    # Import fresh module
    from patchpal.agent import TOOL_FUNCTIONS, TOOLS

    # Verify web tools are present
    tool_names = [tool["function"]["name"] for tool in TOOLS]
    assert "web_search" in tool_names
    assert "web_fetch" in tool_names
    assert "web_search" in TOOL_FUNCTIONS
    assert "web_fetch" in TOOL_FUNCTIONS


def test_web_tools_can_be_disabled(monkeypatch):
    """Test that web tools can be disabled via environment variable."""
    import sys

    # Set environment variable before importing
    monkeypatch.setenv("PATCHPAL_ENABLE_WEB", "false")

    # Remove patchpal.agent from cache to force reload
    if "patchpal.agent" in sys.modules:
        del sys.modules["patchpal.agent"]

    # Import module with web tools disabled
    from patchpal.agent import SYSTEM_PROMPT, TOOL_FUNCTIONS, TOOLS

    # Verify web tools are not present
    tool_names = [tool["function"]["name"] for tool in TOOLS]
    assert "web_search" not in tool_names
    assert "web_fetch" not in tool_names
    assert "web_search" not in TOOL_FUNCTIONS
    assert "web_fetch" not in TOOL_FUNCTIONS

    # Verify system prompt doesn't mention web tools
    assert "web_search" not in SYSTEM_PROMPT
    assert "web_fetch" not in SYSTEM_PROMPT

    # Clean up - remove from cache so other tests get default behavior
    del sys.modules["patchpal.agent"]


def test_web_tools_disabled_with_various_values(monkeypatch):
    """Test that PATCHPAL_ENABLE_WEB accepts various false values."""
    import sys

    for false_value in ["false", "False", "FALSE", "0", "no", "No", "NO"]:
        # Set environment variable
        monkeypatch.setenv("PATCHPAL_ENABLE_WEB", false_value)

        # Remove patchpal.agent from cache
        if "patchpal.agent" in sys.modules:
            del sys.modules["patchpal.agent"]

        # Import module
        from patchpal.agent import TOOLS

        # Verify web tools are not present
        tool_names = [tool["function"]["name"] for tool in TOOLS]
        assert "web_search" not in tool_names, (
            f"web_search should be disabled with value '{false_value}'"
        )
        assert "web_fetch" not in tool_names, (
            f"web_fetch should be disabled with value '{false_value}'"
        )

        # Clean up
        del sys.modules["patchpal.agent"]


def test_agent_returns_immediately_on_cancellation(monkeypatch):
    """Test that agent returns immediately when user cancels operation (no extra API calls)."""
    from patchpal.agent import create_agent

    # Disable permissions for this test
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

    # Track how many times litellm.completion is called
    call_count = [0]

    def mock_completion(*args, **kwargs):
        call_count[0] += 1

        # First call: agent wants to call run_shell
        tool_call = MagicMock()
        tool_call.id = "call_123"
        tool_call.function.name = "run_shell"
        tool_call.function.arguments = '{"cmd": "echo test"}'

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = MagicMock()
        mock_response.choices[0].message.content = ""
        mock_response.choices[0].message.tool_calls = [tool_call]

        return mock_response

    # Mock run_shell to return exact cancellation message (simulating user pressing "3")
    def mock_run_shell(cmd):
        return "Operation cancelled by user."  # Exact message from permissions.py

    # Patch the TOOL_FUNCTIONS dict directly since it's populated at import time
    from patchpal.agent import TOOL_FUNCTIONS

    original_run_shell = TOOL_FUNCTIONS["run_shell"]
    TOOL_FUNCTIONS["run_shell"] = mock_run_shell

    try:
        with patch("patchpal.agent.litellm.completion", side_effect=mock_completion):
            agent = create_agent()

            result = agent.run("Run echo test")

            # Verify agent made only ONE API call (not two)
            # Without the fix, it would make a second call to process the cancellation
            assert call_count[0] == 1, f"Expected 1 API call, got {call_count[0]}"

            # Verify the result is the cancellation message
            assert "Operation cancelled by user" in result
    finally:
        # Restore original function
        TOOL_FUNCTIONS["run_shell"] = original_run_shell


def test_agent_doesnt_trigger_on_file_containing_cancellation_text(monkeypatch):
    """Test that reading a file containing 'Operation cancelled by user' doesn't trigger early exit."""
    from patchpal.agent import TOOL_FUNCTIONS, create_agent

    # Disable permissions for this test
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

    call_count = [0]

    def mock_completion(*args, **kwargs):
        call_count[0] += 1

        if call_count[0] == 1:
            # First call: agent wants to call read_file
            tool_call = MagicMock()
            tool_call.id = "call_123"
            tool_call.function.name = "read_file"
            tool_call.function.arguments = '{"path": "test.txt"}'

            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[0].message.content = ""
            mock_response.choices[0].message.tool_calls = [tool_call]

            return mock_response
        else:
            # Second call: agent responds after reading the file
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message = MagicMock()
            mock_response.choices[
                0
            ].message.content = "The file contains documentation about cancellation."
            mock_response.choices[0].message.tool_calls = None

            return mock_response

    # Mock read_file to return content that includes the cancellation phrase
    def mock_read_file(path):
        return "Documentation: When user presses 3, the system shows 'Operation cancelled by user.' message."

    # Patch TOOL_FUNCTIONS dict
    original_read_file = TOOL_FUNCTIONS["read_file"]
    TOOL_FUNCTIONS["read_file"] = mock_read_file

    try:
        with patch("patchpal.agent.litellm.completion", side_effect=mock_completion):
            agent = create_agent()

            result = agent.run("Read the test file")

            # Verify agent made TWO API calls (not one)
            # If the cancellation check was too broad, it would exit after first call
            assert call_count[0] == 2, f"Expected 2 API calls, got {call_count[0]}"

            # Verify the result is the agent's synthesized response, not raw file contents
            assert result == "The file contains documentation about cancellation."
            assert "Documentation:" not in result  # Should not be raw file contents
    finally:
        # Restore original function
        TOOL_FUNCTIONS["read_file"] = original_read_file


def test_prompt_caching_detection():
    """Test that prompt caching is correctly detected for supported models."""
    from patchpal.agent import _supports_prompt_caching

    # Anthropic models should support caching
    assert _supports_prompt_caching("anthropic/claude-sonnet-4-5")
    assert _supports_prompt_caching("anthropic/claude-opus-4")

    # Bedrock Anthropic models should support caching
    assert _supports_prompt_caching("bedrock/anthropic.claude-sonnet-4-5-v1:0")
    assert _supports_prompt_caching("bedrock/anthropic.claude-v2")

    # Bedrock Nova models should support caching
    assert _supports_prompt_caching("bedrock/amazon.nova-pro-v1:0")
    assert _supports_prompt_caching("bedrock/amazon.nova-lite-v1:0")

    # Non-Anthropic/Nova models should not support caching
    assert not _supports_prompt_caching("openai/gpt-4o")
    assert not _supports_prompt_caching("ollama_chat/llama3.1")


def test_prompt_caching_application_anthropic():
    """Test that prompt caching markers are correctly applied for Anthropic models."""
    from patchpal.agent import _apply_prompt_caching

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "How are you?"},
    ]

    # Test with direct Anthropic API
    cached_messages = _apply_prompt_caching(messages.copy(), "anthropic/claude-sonnet-4-5")

    # System message should have cache_control inside content block
    assert isinstance(cached_messages[0]["content"], list)
    assert cached_messages[0]["content"][0]["type"] == "text"
    assert "cache_control" in cached_messages[0]["content"][0]
    assert cached_messages[0]["content"][0]["cache_control"] == {"type": "ephemeral"}

    # Last 2 messages should have cache_control inside content blocks
    assert isinstance(cached_messages[-1]["content"], list)  # Last user message
    assert "cache_control" in cached_messages[-1]["content"][0]
    assert isinstance(cached_messages[-2]["content"], list)  # Last assistant message
    assert "cache_control" in cached_messages[-2]["content"][0]


def test_prompt_caching_application_bedrock_anthropic():
    """Test that prompt caching markers use cache_control for Bedrock Anthropic models."""
    from patchpal.agent import _apply_prompt_caching

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "How are you?"},
    ]

    # Test with Bedrock Anthropic model - should use cache_control (same as direct Anthropic)
    cached_messages = _apply_prompt_caching(
        messages.copy(), "bedrock/anthropic.claude-sonnet-4-5-v1:0"
    )

    # System message should have cache_control inside content block (NOT cachePoint)
    assert isinstance(cached_messages[0]["content"], list)
    assert cached_messages[0]["content"][0]["type"] == "text"
    assert "cache_control" in cached_messages[0]["content"][0]
    assert cached_messages[0]["content"][0]["cache_control"] == {"type": "ephemeral"}

    # Last 2 messages should have cache_control inside content blocks
    assert isinstance(cached_messages[-1]["content"], list)
    assert "cache_control" in cached_messages[-1]["content"][0]
    assert isinstance(cached_messages[-2]["content"], list)
    assert "cache_control" in cached_messages[-2]["content"][0]


def test_prompt_caching_application_bedrock_nova():
    """Test that prompt caching markers use cachePoint for Bedrock Nova models."""
    from patchpal.agent import _apply_prompt_caching

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "user", "content": "How are you?"},
    ]

    # Test with Bedrock Nova model - should use cachePoint
    cached_messages = _apply_prompt_caching(messages.copy(), "bedrock/amazon.nova-pro-v1:0")

    # System message should have cachePoint inside content block
    assert isinstance(cached_messages[0]["content"], list)
    assert cached_messages[0]["content"][0]["type"] == "text"
    assert "cachePoint" in cached_messages[0]["content"][0]
    assert cached_messages[0]["content"][0]["cachePoint"] == {"type": "default"}

    # Last 2 messages should have cachePoint inside content blocks
    assert isinstance(cached_messages[-1]["content"], list)
    assert "cachePoint" in cached_messages[-1]["content"][0]
    assert isinstance(cached_messages[-2]["content"], list)
    assert "cachePoint" in cached_messages[-2]["content"][0]


def test_prompt_caching_no_modification_for_unsupported():
    """Test that prompt caching doesn't modify messages for unsupported models."""
    from patchpal.agent import _apply_prompt_caching

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
    ]

    # Test with non-Anthropic model
    cached_messages = _apply_prompt_caching(messages.copy(), "openai/gpt-4o")

    # Messages should be unchanged
    assert "cache_control" not in cached_messages[0]
    assert "cachePoint" not in cached_messages[0]
    assert cached_messages == messages


def test_prompt_caching_idempotent():
    """Test that applying caching multiple times doesn't add duplicate markers."""
    from patchpal.agent import _apply_prompt_caching

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello"},
    ]

    # Apply caching twice
    cached_once = _apply_prompt_caching(messages.copy(), "anthropic/claude-sonnet-4-5")
    cached_twice = _apply_prompt_caching(cached_once.copy(), "anthropic/claude-sonnet-4-5")

    # Should have the same structure after second application
    assert cached_once[0]["content"][0] == cached_twice[0]["content"][0]
    assert cached_once[1]["content"][0] == cached_twice[1]["content"][0]

    # Should only have one cache_control marker per message
    assert len([k for k in cached_twice[0]["content"][0].keys() if "cache" in k]) == 1
    assert len([k for k in cached_twice[1]["content"][0].keys() if "cache" in k]) == 1


def test_agent_handles_keyboard_interrupt_during_tool_execution(monkeypatch):
    """Test that agent properly cleans up conversation state when interrupted during tool execution."""
    from patchpal.agent import create_agent

    # Disable permissions for this test
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

    # Mock litellm.completion to return a tool call
    tool_call = MagicMock()
    tool_call.id = "call_abc123"
    tool_call.function.name = "read_file"
    tool_call.function.arguments = '{"path": "test.txt"}'

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = "Let me read that file."
    mock_response.choices[0].message.tool_calls = [tool_call]

    # Mock read_file to raise KeyboardInterrupt (simulating user pressing CTRL-C)
    from patchpal.agent import TOOL_FUNCTIONS

    original_read_file = TOOL_FUNCTIONS["read_file"]

    def mock_read_file_interrupt(path):
        raise KeyboardInterrupt()

    TOOL_FUNCTIONS["read_file"] = mock_read_file_interrupt

    try:
        with patch("patchpal.agent.litellm.completion", return_value=mock_response):
            agent = create_agent()

            # Run should raise KeyboardInterrupt
            try:
                agent.run("Read test.txt")
                assert False, "Expected KeyboardInterrupt to be raised"
            except KeyboardInterrupt:
                pass

            # Verify conversation state is valid
            # Should have: user message, assistant with tool_calls, tool error response
            assert len(agent.messages) == 3

            # Check user message
            assert agent.messages[0]["role"] == "user"

            # Check assistant message with tool_calls
            assert agent.messages[1]["role"] == "assistant"
            assert agent.messages[1]["tool_calls"] is not None
            assert len(agent.messages[1]["tool_calls"]) == 1

            # Check error tool response was added
            assert agent.messages[2]["role"] == "tool"
            assert agent.messages[2]["tool_call_id"] == "call_abc123"
            assert agent.messages[2]["name"] == "read_file"
            assert "interrupted" in agent.messages[2]["content"].lower()

    finally:
        TOOL_FUNCTIONS["read_file"] = original_read_file


def test_agent_handles_keyboard_interrupt_with_multiple_tool_calls(monkeypatch):
    """Test that agent adds error responses for ALL pending tool calls when interrupted."""
    from patchpal.agent import create_agent

    # Disable permissions for this test
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

    # Mock litellm.completion to return multiple tool calls
    tool_call_1 = MagicMock()
    tool_call_1.id = "call_1"
    tool_call_1.function.name = "read_file"
    tool_call_1.function.arguments = '{"path": "file1.txt"}'

    tool_call_2 = MagicMock()
    tool_call_2.id = "call_2"
    tool_call_2.function.name = "read_file"
    tool_call_2.function.arguments = '{"path": "file2.txt"}'

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = ""
    mock_response.choices[0].message.tool_calls = [tool_call_1, tool_call_2]

    # Mock read_file to raise KeyboardInterrupt on first call
    from patchpal.agent import TOOL_FUNCTIONS

    original_read_file = TOOL_FUNCTIONS["read_file"]

    call_count = [0]

    def mock_read_file_interrupt(path):
        call_count[0] += 1
        if call_count[0] == 1:
            raise KeyboardInterrupt()
        return "This shouldn't be reached"

    TOOL_FUNCTIONS["read_file"] = mock_read_file_interrupt

    try:
        with patch("patchpal.agent.litellm.completion", return_value=mock_response):
            agent = create_agent()

            # Run should raise KeyboardInterrupt
            try:
                agent.run("Read both files")
                assert False, "Expected KeyboardInterrupt to be raised"
            except KeyboardInterrupt:
                pass

            # Verify conversation state has error responses for ALL tool calls
            # Should have: user message, assistant with 2 tool_calls, 2 tool error responses
            assert len(agent.messages) == 4

            # Check assistant message
            assert agent.messages[1]["role"] == "assistant"
            assert len(agent.messages[1]["tool_calls"]) == 2

            # Check both error responses were added
            tool_responses = [msg for msg in agent.messages if msg.get("role") == "tool"]
            assert len(tool_responses) == 2

            # Verify both tool_call_ids are present
            response_ids = {msg["tool_call_id"] for msg in tool_responses}
            assert response_ids == {"call_1", "call_2"}

            # Both should have error messages
            for response in tool_responses:
                assert "interrupted" in response["content"].lower()

    finally:
        TOOL_FUNCTIONS["read_file"] = original_read_file


def test_agent_keyboard_interrupt_after_successful_retry(monkeypatch):
    """Test that after cleaning up from interrupt, agent can be used again successfully."""
    from patchpal.agent import create_agent

    # Disable permissions for this test
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

    # First call: return a tool call
    tool_call = MagicMock()
    tool_call.id = "call_xyz"
    tool_call.function.name = "list_files"
    tool_call.function.arguments = "{}"

    mock_response_1 = MagicMock()
    mock_response_1.choices = [MagicMock()]
    mock_response_1.choices[0].message = MagicMock()
    mock_response_1.choices[0].message.content = ""
    mock_response_1.choices[0].message.tool_calls = [tool_call]

    # Second call: return success response (after interrupt and retry)
    mock_response_2 = MagicMock()
    mock_response_2.choices = [MagicMock()]
    mock_response_2.choices[0].message = MagicMock()
    mock_response_2.choices[0].message.content = "I found 3 files."
    mock_response_2.choices[0].message.tool_calls = None

    # Mock list_files to raise interrupt first, then succeed
    from patchpal.agent import TOOL_FUNCTIONS

    original_list_files = TOOL_FUNCTIONS["list_files"]

    call_count = [0]

    def mock_list_files_conditional():
        call_count[0] += 1
        if call_count[0] == 1:
            raise KeyboardInterrupt()
        return ["file1.py", "file2.py", "file3.py"]

    TOOL_FUNCTIONS["list_files"] = mock_list_files_conditional

    try:
        with patch(
            "patchpal.agent.litellm.completion", side_effect=[mock_response_1, mock_response_2]
        ):
            agent = create_agent()

            # First run: should be interrupted
            try:
                agent.run("List files")
                assert False, "Expected KeyboardInterrupt"
            except KeyboardInterrupt:
                pass

            # Verify state after interrupt - should have error response
            assert len(agent.messages) == 3
            assert agent.messages[2]["role"] == "tool"
            assert "interrupted" in agent.messages[2]["content"].lower()

            # Second run: should succeed (using the error responses from cleanup)
            # The agent should be able to continue from the cleaned-up state
            result = agent.run("Try again")

            # Should complete successfully
            assert result == "I found 3 files."

    finally:
        TOOL_FUNCTIONS["list_files"] = original_list_files
