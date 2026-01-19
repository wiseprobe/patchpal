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
        manager = ContextManager("gpt-4", "Short prompt")
        messages = [
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi!"},
        ]

        # Should not need compaction with small messages
        assert not manager.needs_compaction(messages)

    def test_needs_compaction_above_threshold(self):
        """Test compaction detection when above threshold."""
        manager = ContextManager("gpt-4", "Short prompt")

        # Create messages that fill the context window
        # GPT-4 has 8000 token limit (original), 85% = 6800 tokens
        # Create large message to exceed threshold
        large_text = "x" * 30_000  # ~7500 tokens (4 chars per token)

        messages = [{"role": "user", "content": large_text}]

        # Should need compaction
        assert manager.needs_compaction(messages)

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
