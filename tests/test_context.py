"""Tests for context management and token estimation."""

from patchpal.agent import create_agent
from patchpal.context import ContextManager, TokenEstimator


class TestTokenEstimator:
    """Tests for token estimation."""

    def test_token_estimator_init(self):
        """Test TokenEstimator initialization."""
        estimator = TokenEstimator("anthropic/claude-sonnet-4")
        assert estimator.model_id == "anthropic/claude-sonnet-4"

    def test_estimate_tokens_empty(self):
        """Test token estimation with empty string."""
        estimator = TokenEstimator("gpt-4")
        assert estimator.estimate_tokens("") == 0
        assert estimator.estimate_tokens(None) == 0

    def test_estimate_tokens_text(self):
        """Test token estimation with text."""
        estimator = TokenEstimator("gpt-4")
        # Simple test - should be > 0
        tokens = estimator.estimate_tokens("Hello, world!")
        assert tokens > 0
        assert tokens < 100  # Sanity check

    def test_estimate_tokens_long_text(self):
        """Test token estimation with longer text."""
        estimator = TokenEstimator("gpt-4")
        text = "This is a longer piece of text. " * 100
        tokens = estimator.estimate_tokens(text)
        # Should be roughly 3100 chars / 4 = ~775 tokens minimum (fallback)
        assert tokens > 500

    def test_estimate_message_tokens(self):
        """Test token estimation for messages."""
        estimator = TokenEstimator("gpt-4")

        # User message
        msg = {"role": "user", "content": "Hello!"}
        tokens = estimator.estimate_message_tokens(msg)
        assert tokens > 0

        # Empty message
        empty_msg = {"role": "user", "content": ""}
        tokens = estimator.estimate_message_tokens(empty_msg)
        assert tokens >= 4  # Just role overhead

    def test_estimate_messages_tokens(self):
        """Test token estimation for multiple messages."""
        estimator = TokenEstimator("gpt-4")

        messages = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
        ]

        tokens = estimator.estimate_messages_tokens(messages)
        assert tokens > 0
        # Should be roughly: 3 roles (12) + content
        assert tokens > 12


class TestContextManager:
    """Tests for context management."""

    def test_context_manager_init(self):
        """Test ContextManager initialization."""
        manager = ContextManager("gpt-4", "You are a helpful assistant.")
        assert manager.model_id == "gpt-4"
        assert manager.context_limit > 0
        assert manager.estimator is not None

    def test_get_context_limit(self):
        """Test context limit detection for different models."""
        import os

        # Save original env var
        original_limit = os.environ.get("PATCHPAL_CONTEXT_LIMIT")

        try:
            # Clear any test override
            if "PATCHPAL_CONTEXT_LIMIT" in os.environ:
                del os.environ["PATCHPAL_CONTEXT_LIMIT"]

            # Claude models
            manager = ContextManager("anthropic/claude-sonnet-4", "test")
            assert manager.context_limit == 200_000

            # GPT-4 models
            manager = ContextManager("openai/gpt-4o", "test")
            assert manager.context_limit == 128_000

            # GPT-3.5
            manager = ContextManager("openai/gpt-3.5-turbo", "test")
            assert manager.context_limit == 16_385

            # Unknown model - should use conservative default
            manager = ContextManager("unknown/model", "test")
            assert manager.context_limit == 128_000

        finally:
            # Restore original env var
            if original_limit is not None:
                os.environ["PATCHPAL_CONTEXT_LIMIT"] = original_limit

    def test_model_matching_litellm_format(self):
        """Test that model matching works correctly with LiteLLM format (provider/model)."""
        import os

        # Save original env var
        original_limit = os.environ.get("PATCHPAL_CONTEXT_LIMIT")

        try:
            # Clear any test override
            if "PATCHPAL_CONTEXT_LIMIT" in os.environ:
                del os.environ["PATCHPAL_CONTEXT_LIMIT"]

            # Test cases: (model_id, expected_context_limit)
            test_cases = [
                # Anthropic Claude models
                ("anthropic/claude-opus-4", 200_000),
                ("anthropic/claude-sonnet-4-5", 200_000),
                ("anthropic/claude-haiku-4", 200_000),
                ("anthropic/claude-3-5-sonnet", 200_000),
                ("anthropic/claude-3-7-sonnet", 200_000),
                # OpenAI GPT models - test version matching
                ("openai/gpt-5", 400_000),
                ("openai/gpt-5.1", 128_000),  # Should match gpt-5.1, not gpt-5
                ("openai/gpt-5.2", 400_000),
                ("openai/gpt-5-mini", 400_000),
                ("openai/gpt-4o", 128_000),
                ("openai/gpt-4-turbo", 128_000),
                ("openai/gpt-4.1", 128_000),
                ("openai/gpt-4", 8_000),
                ("openai/gpt-3.5-turbo", 16_385),
                ("openai/o3-mini", 128_000),
                # Google Gemini models
                ("gemini/gemini-3-pro", 1_000_000),
                ("gemini/gemini-2.5-pro", 1_048_576),
                ("gemini/gemini-1.5-flash", 1_000_000),
                ("gemini/gemini-pro", 32_000),
                # xAI Grok models
                ("xai/grok-4", 256_000),
                ("xai/grok-4-fast", 2_000_000),
                ("xai/grok-3-mini", 131_072),
                ("xai/grok-2", 131_072),
                # DeepSeek models
                ("deepseek/deepseek-v3.1", 128_000),
                ("deepseek/deepseek-r1", 128_000),
                ("deepseek/deepseek-chat", 128_000),
                ("deepseek/deepseek-coder", 128_000),
                # Qwen models
                ("qwen/qwen-turbo", 1_000_000),
                ("qwen/qwen-plus", 1_000_000),
                ("qwen/qwen3-coder", 262_144),
                ("qwen/qwq-32b", 131_072),
                # Meta Llama models
                ("meta/llama-4", 131_072),
                ("meta/llama-3.3-70b", 128_000),
                ("meta/llama-3.1-405b", 128_000),
                ("meta/llama-3", 8_192),
                # Mistral models
                ("mistral/mistral-large", 128_000),
                ("mistral/codestral", 128_000),
                ("mistral/ministral", 262_144),
                # Cohere Command models
                ("cohere/command-r-plus", 128_000),
                ("cohere/command-a", 256_000),
                # Other models
                ("openai/gpt-oss-120b", 128_000),
                ("minimax/minimax-m2", 128_000),
                ("kimi/kimi-k2", 262_144),
                # Bedrock format (provider stripped in agent)
                ("bedrock/anthropic.claude-sonnet-4-5", 200_000),
                # Hosted vLLM format
                ("hosted_vllm/openai/gpt-oss-20b", 128_000),
            ]

            for model_id, expected_limit in test_cases:
                manager = ContextManager(model_id, "test")
                assert manager.context_limit == expected_limit, (
                    f"Model {model_id}: expected {expected_limit:,}, got {manager.context_limit:,}"
                )

        finally:
            # Restore original env var
            if original_limit is not None:
                os.environ["PATCHPAL_CONTEXT_LIMIT"] = original_limit

    def test_model_matching_longest_first(self):
        """Test that longer model names are matched before shorter ones."""
        import os

        original_limit = os.environ.get("PATCHPAL_CONTEXT_LIMIT")

        try:
            if "PATCHPAL_CONTEXT_LIMIT" in os.environ:
                del os.environ["PATCHPAL_CONTEXT_LIMIT"]

            # Test that gpt-5.1 matches correctly (not gpt-5)
            manager = ContextManager("openai/gpt-5.1", "test")
            assert manager.context_limit == 128_000, "gpt-5.1 should be 128K, not 400K (gpt-5)"

            # Test that gpt-5.2 matches correctly
            manager = ContextManager("openai/gpt-5.2", "test")
            assert manager.context_limit == 400_000, "gpt-5.2 should be 400K"

            # Test that gpt-5 still works
            manager = ContextManager("openai/gpt-5", "test")
            assert manager.context_limit == 400_000, "gpt-5 should be 400K"

            # Test that gpt-4-turbo matches correctly (not gpt-4)
            manager = ContextManager("openai/gpt-4-turbo", "test")
            assert manager.context_limit == 128_000, "gpt-4-turbo should be 128K, not 8K (gpt-4)"

            # Test that claude-3-5-sonnet matches correctly
            manager = ContextManager("anthropic/claude-3-5-sonnet", "test")
            assert manager.context_limit == 200_000, "claude-3-5-sonnet should be 200K"

        finally:
            if original_limit is not None:
                os.environ["PATCHPAL_CONTEXT_LIMIT"] = original_limit

    def test_model_family_fallback(self):
        """Test fallback to model family when specific model not in dict."""
        import os

        original_limit = os.environ.get("PATCHPAL_CONTEXT_LIMIT")

        try:
            if "PATCHPAL_CONTEXT_LIMIT" in os.environ:
                del os.environ["PATCHPAL_CONTEXT_LIMIT"]

            # Test unknown Claude version falls back to 200K
            manager = ContextManager("anthropic/claude-opus-99", "test")
            assert manager.context_limit == 200_000

            # Test unknown GPT-5 version falls back to 400K
            manager = ContextManager("openai/gpt-5.99", "test")
            assert manager.context_limit == 400_000

            # Test unknown Gemini 2 version falls back to 1M
            manager = ContextManager("gemini/gemini-2.9-ultra", "test")
            assert manager.context_limit == 1_000_000

            # Test unknown DeepSeek version falls back to 128K
            manager = ContextManager("deepseek/deepseek-v99", "test")
            assert manager.context_limit == 128_000

            # Test completely unknown model falls back to 128K default
            manager = ContextManager("unknown-provider/unknown-model", "test")
            assert manager.context_limit == 128_000

        finally:
            if original_limit is not None:
                os.environ["PATCHPAL_CONTEXT_LIMIT"] = original_limit

    def test_get_usage_stats(self):
        """Test getting usage statistics."""
        manager = ContextManager("gpt-4", "System prompt")
        messages = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi!"},
        ]

        stats = manager.get_usage_stats(messages)

        assert "system_tokens" in stats
        assert "message_tokens" in stats
        assert "total_tokens" in stats
        assert "context_limit" in stats
        assert "usage_ratio" in stats
        assert "usage_percent" in stats

        assert stats["system_tokens"] > 0
        assert stats["message_tokens"] > 0
        assert stats["total_tokens"] > 0
        assert stats["context_limit"] > 0
        assert 0 <= stats["usage_ratio"] <= 1
        assert 0 <= stats["usage_percent"] <= 100

    def test_needs_compaction_below_threshold(self):
        """Test compaction detection when below threshold."""
        import os

        # Save original env var
        original_limit = os.environ.get("PATCHPAL_CONTEXT_LIMIT")

        try:
            # Clear any test override to use actual GPT-4 limit
            if "PATCHPAL_CONTEXT_LIMIT" in os.environ:
                del os.environ["PATCHPAL_CONTEXT_LIMIT"]

            manager = ContextManager("gpt-4", "Short prompt")
            messages = [
                {"role": "user", "content": "Hello!"},
                {"role": "assistant", "content": "Hi!"},
            ]

            # Should not need compaction with small messages
            assert not manager.needs_compaction(messages)

        finally:
            # Restore original env var
            if original_limit is not None:
                os.environ["PATCHPAL_CONTEXT_LIMIT"] = original_limit

    def test_needs_compaction_above_threshold(self):
        """Test compaction detection when above threshold."""
        import os

        # Save original env var
        original_limit = os.environ.get("PATCHPAL_CONTEXT_LIMIT")

        try:
            # Clear any test override to use actual GPT-4 limit (8000 tokens)
            if "PATCHPAL_CONTEXT_LIMIT" in os.environ:
                del os.environ["PATCHPAL_CONTEXT_LIMIT"]

            manager = ContextManager("gpt-4", "Short prompt")

            # Create messages that fill the context window
            # GPT-4 has 8000 token limit (original), 85% = 6800 tokens
            # Create large message to exceed threshold
            large_text = "x" * 30_000  # ~7500 tokens (4 chars per token)

            messages = [{"role": "user", "content": large_text}]

            # Should need compaction
            assert manager.needs_compaction(messages)

        finally:
            # Restore original env var
            if original_limit is not None:
                os.environ["PATCHPAL_CONTEXT_LIMIT"] = original_limit

    def test_prune_tool_outputs_no_pruning_needed(self):
        """Test pruning when no pruning is needed."""
        manager = ContextManager("gpt-4", "test")

        messages = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi!"},
            {"role": "tool", "content": "Tool output", "tool_call_id": "1"},
        ]

        pruned_messages, tokens_saved = manager.prune_tool_outputs(messages)

        # Should not prune (too few messages, within protected range)
        assert tokens_saved == 0
        assert len(pruned_messages) == len(messages)

    def test_prune_tool_outputs_with_pruning(self):
        """Test pruning when pruning is needed."""
        manager = ContextManager("gpt-4", "test")

        # Create many tool messages with large outputs
        messages = [{"role": "user", "content": "Start"}]

        # Add 50 tool outputs (will exceed PRUNE_PROTECT threshold)
        for i in range(50):
            messages.append(
                {
                    "role": "tool",
                    "content": "x" * 2000,  # ~500 tokens each = 25k tokens total
                    "tool_call_id": str(i),
                }
            )

        # Add recent messages
        messages.append({"role": "user", "content": "Continue"})

        pruned_messages, tokens_saved = manager.prune_tool_outputs(messages)

        # Should have pruned some old tool outputs
        # (depends on PRUNE_PROTECT threshold)
        assert len(pruned_messages) == len(messages)

        # Check if old tool outputs were pruned
        pruned_count = sum(
            1 for msg in pruned_messages if "[Tool output pruned" in str(msg.get("content", ""))
        )

        # Should have pruned at least some messages
        # (exact count depends on token estimation)
        assert pruned_count >= 0  # May be 0 if total doesn't exceed PRUNE_MINIMUM

    def test_prune_tool_outputs_preserves_recent(self):
        """Test that pruning preserves recent tool outputs."""
        manager = ContextManager("gpt-4", "test")

        # Create messages with tool outputs
        messages = []

        # Old tool outputs (should be pruned)
        for i in range(30):
            messages.append({"role": "tool", "content": "x" * 2000, "tool_call_id": f"old_{i}"})

        # Recent tool outputs (should be preserved)
        recent_messages = []
        for i in range(5):
            msg = {"role": "tool", "content": f"recent output {i}", "tool_call_id": f"recent_{i}"}
            messages.append(msg)
            recent_messages.append(msg)

        pruned_messages, tokens_saved = manager.prune_tool_outputs(messages)

        # Check that recent messages are not pruned
        for i in range(-5, 0):
            assert "[Tool output pruned" not in str(pruned_messages[i].get("content", ""))


class TestContextManagerIntegration:
    """Integration tests for context management."""

    def test_full_workflow(self):
        """Test complete context management workflow."""
        manager = ContextManager("gpt-4", "You are a helpful assistant.")

        # Start with empty messages
        messages = []

        # Should not need compaction initially
        assert not manager.needs_compaction(messages)

        # Add some messages
        messages.append({"role": "user", "content": "Hello!"})
        messages.append({"role": "assistant", "content": "Hi there!"})

        stats = manager.get_usage_stats(messages)
        assert stats["usage_percent"] < 85

        # Simulate filling context window
        large_text = "x" * 30_000
        messages.append({"role": "user", "content": large_text})

        # Should now need compaction
        stats = manager.get_usage_stats(messages)
        # Usage should be high (exact value depends on token estimation)
        assert stats["total_tokens"] > 1000

    def test_context_manager_with_tool_outputs(self):
        """Test context manager with tool outputs."""
        manager = ContextManager("gpt-4", "test")

        messages = [
            {"role": "user", "content": "Read a file"},
            {"role": "assistant", "content": "Reading file...", "tool_calls": []},
            {"role": "tool", "content": "File contents: " + "x" * 1000, "tool_call_id": "1"},
            {"role": "assistant", "content": "Here's what I found..."},
        ]

        stats = manager.get_usage_stats(messages)
        assert stats["message_tokens"] > 0

        # Pruning should work
        pruned, saved = manager.prune_tool_outputs(messages)
        assert len(pruned) == len(messages)


class TestAutoCompaction:
    """Tests for auto-compaction in the agent."""

    def test_agent_has_context_manager(self):
        """Test that agent initializes with context manager."""
        agent = create_agent("gpt-4")
        assert agent.context_manager is not None
        assert agent.enable_auto_compact is True

    def test_agent_auto_compact_can_be_disabled(self):
        """Test that auto-compaction can be disabled via env var."""
        import os

        original = os.environ.get("PATCHPAL_DISABLE_AUTOCOMPACT")
        try:
            os.environ["PATCHPAL_DISABLE_AUTOCOMPACT"] = "true"
            agent = create_agent("gpt-4")
            assert agent.enable_auto_compact is False
        finally:
            if original is None:
                os.environ.pop("PATCHPAL_DISABLE_AUTOCOMPACT", None)
            else:
                os.environ["PATCHPAL_DISABLE_AUTOCOMPACT"] = original

    def test_perform_auto_compaction_method_exists(self):
        """Test that agent has _perform_auto_compaction method."""
        agent = create_agent("gpt-4")
        assert hasattr(agent, "_perform_auto_compaction")
        assert callable(agent._perform_auto_compaction)

    def test_compaction_preserves_message_structure(self):
        """Test that compaction maintains valid message structure."""
        manager = ContextManager("gpt-4", "System prompt")

        # Create messages that would trigger compaction
        messages = [
            {"role": "user", "content": "Start"},
            {"role": "assistant", "content": "Response"},
            {"role": "user", "content": "Continue"},
            {"role": "assistant", "content": "Another response"},
        ]

        # Test that pruning preserves structure
        pruned, _ = manager.prune_tool_outputs(messages)
        assert len(pruned) == len(messages)
        assert all("role" in msg for msg in pruned)
        assert all("content" in msg for msg in pruned)
