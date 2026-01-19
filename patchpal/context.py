"""Context window management and token estimation."""

from datetime import datetime
from typing import Any, Callable, Dict, List, Tuple

try:
    import tiktoken

    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False


class TokenEstimator:
    """Estimate tokens in messages for context management."""

    def __init__(self, model_id: str):
        self.model_id = model_id
        self._encoder = self._get_encoder()

    def _get_encoder(self):
        """Get appropriate tokenizer based on model."""
        if not TIKTOKEN_AVAILABLE:
            return None

        try:
            # Map model families to encoders
            model_lower = self.model_id.lower()

            if "gpt-4" in model_lower or "gpt-3.5" in model_lower:
                return tiktoken.encoding_for_model("gpt-4")
            elif "claude" in model_lower or "anthropic" in model_lower:
                # Anthropic uses similar tokenization to GPT-4
                return tiktoken.encoding_for_model("gpt-4")
            else:
                # Default fallback
                return tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None

    def estimate_tokens(self, text: str) -> int:
        """Estimate tokens in text.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0

        if self._encoder:
            try:
                return len(self._encoder.encode(str(text)))
            except Exception:
                pass

        # Fallback: ~4 chars per token average
        return len(str(text)) // 4

    def estimate_message_tokens(self, message: Dict[str, Any]) -> int:
        """Estimate tokens in a single message.

        Args:
            message: Message dict with role, content, tool_calls, etc.

        Returns:
            Estimated token count
        """
        tokens = 0

        # Role and content
        if "role" in message:
            tokens += 4  # Role overhead

        if "content" in message and message["content"]:
            tokens += self.estimate_tokens(str(message["content"]))

        # Tool calls
        if message.get("tool_calls"):
            for tool_call in message["tool_calls"]:
                tokens += 10  # Tool call overhead
                if hasattr(tool_call, "function"):
                    tokens += self.estimate_tokens(tool_call.function.name)
                    tokens += self.estimate_tokens(tool_call.function.arguments)

        # Tool call ID
        if message.get("tool_call_id"):
            tokens += 5

        # Name field
        if message.get("name"):
            tokens += self.estimate_tokens(message["name"])

        return tokens

    def estimate_messages_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Estimate tokens in a list of messages.

        Args:
            messages: List of message dicts

        Returns:
            Total estimated token count
        """
        return sum(self.estimate_message_tokens(msg) for msg in messages)


class ContextManager:
    """Manage context window with auto-compaction and pruning."""

    # OpenCode-inspired thresholds
    PRUNE_PROTECT = 40_000  # Keep last 40k tokens of tool outputs
    PRUNE_MINIMUM = 20_000  # Minimum tokens to prune to make it worthwhile
    COMPACT_THRESHOLD = 0.85  # Compact at 85% capacity

    # Model context limits (tokens)
    # Conservative estimates to account for model-specific formatting
    MODEL_LIMITS = {
        "claude-3-5-sonnet": 200_000,
        "claude-3-5-haiku": 200_000,
        "claude-sonnet": 200_000,
        "claude-opus": 200_000,
        "claude-haiku": 200_000,
        "gpt-4-turbo": 128_000,
        "gpt-4o": 128_000,
        "gpt-4": 8_000,  # Original GPT-4
        "gpt-3.5-turbo": 16_385,
        "gemini-pro": 32_000,
        "gemini-1.5-pro": 1_000_000,
        "gemini-1.5-flash": 1_000_000,
    }

    # Compaction prompt
    COMPACTION_PROMPT = """You are summarizing a coding session to continue it seamlessly.

Create a detailed summary of our conversation above. This summary will be the ONLY context
available when we continue, so include:

1. **What was accomplished**: Completed tasks and changes made
2. **Current state**: Files modified, their current status
3. **In progress**: What we're working on now
4. **Next steps**: Clear actions to take next
5. **Key decisions**: Important technical choices and why
6. **User preferences**: Any constraints or preferences mentioned

Be comprehensive but concise. The goal is to continue work seamlessly without losing context."""

    def __init__(self, model_id: str, system_prompt: str):
        """Initialize context manager.

        Args:
            model_id: LiteLLM model identifier
            system_prompt: System prompt text
        """
        self.model_id = model_id
        self.system_prompt = system_prompt
        self.estimator = TokenEstimator(model_id)
        self.context_limit = self._get_context_limit()
        self.output_reserve = 4_096  # Reserve tokens for model output

    def _get_context_limit(self) -> int:
        """Get context limit for model.

        Returns:
            Context window size in tokens
        """
        model_lower = self.model_id.lower()

        # Try exact matches first
        for key, limit in self.MODEL_LIMITS.items():
            if key in model_lower:
                return limit

        # Check for model families
        if "claude" in model_lower:
            return 200_000  # Modern Claude models
        elif "gpt-4" in model_lower:
            return 128_000  # Modern GPT-4 models
        elif "gpt-3.5" in model_lower:
            return 16_385
        elif "gemini" in model_lower:
            return 32_000  # Conservative default for Gemini

        # Default conservative limit for unknown models
        return 128_000

    def needs_compaction(self, messages: List[Dict[str, Any]]) -> bool:
        """Check if context window needs compaction.

        Args:
            messages: Current message history

        Returns:
            True if compaction is needed
        """
        # Estimate total tokens
        system_tokens = self.estimator.estimate_tokens(self.system_prompt)
        message_tokens = self.estimator.estimate_messages_tokens(messages)
        total_tokens = system_tokens + message_tokens + self.output_reserve

        # Check threshold
        usage_ratio = total_tokens / self.context_limit
        return usage_ratio >= self.COMPACT_THRESHOLD

    def get_usage_stats(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get current context usage statistics.

        Args:
            messages: Current message history

        Returns:
            Dict with usage statistics
        """
        system_tokens = self.estimator.estimate_tokens(self.system_prompt)
        message_tokens = self.estimator.estimate_messages_tokens(messages)
        total_tokens = system_tokens + message_tokens + self.output_reserve

        return {
            "system_tokens": system_tokens,
            "message_tokens": message_tokens,
            "output_reserve": self.output_reserve,
            "total_tokens": total_tokens,
            "context_limit": self.context_limit,
            "usage_ratio": total_tokens / self.context_limit,
            "usage_percent": int((total_tokens / self.context_limit) * 100),
        }

    def prune_tool_outputs(
        self, messages: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Prune old tool outputs to reclaim token space.

        Walks backward through messages and prunes tool outputs beyond
        the PRUNE_PROTECT threshold (keeps last 40k tokens of tool outputs).

        Args:
            messages: Current message history

        Returns:
            Tuple of (pruned_messages, tokens_saved)
        """
        # Calculate tokens to protect (recent tool outputs)
        recent_tokens = 0
        prune_candidates = []

        # Walk backward through messages
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]

            # Only consider tool result messages
            if msg.get("role") != "tool":
                continue

            # Estimate tokens in tool output
            tokens = self.estimator.estimate_message_tokens(msg)

            if recent_tokens < self.PRUNE_PROTECT:
                # Still within protected range
                recent_tokens += tokens
            else:
                # Candidate for pruning
                prune_candidates.append((i, tokens, msg))

        # Check if we can save enough tokens
        prunable_tokens = sum(t for _, t, _ in prune_candidates)
        if prunable_tokens < self.PRUNE_MINIMUM:
            # Not worth pruning
            return messages, 0

        # Prune by replacing content with marker
        pruned_messages = []
        tokens_saved = 0

        for i, msg in enumerate(messages):
            if any(idx == i for idx, _, _ in prune_candidates):
                # Replace with pruned marker
                pruned_msg = msg.copy()
                original_content = pruned_msg.get("content", "")
                original_len = len(str(original_content))
                pruned_msg["content"] = f"[Tool output pruned - was {original_len:,} chars]"
                pruned_messages.append(pruned_msg)
                tokens_saved += self.estimator.estimate_tokens(str(original_content))
            else:
                pruned_messages.append(msg)

        return pruned_messages, tokens_saved

    def create_compaction(
        self, messages: List[Dict[str, Any]], completion_func: Callable
    ) -> Tuple[Dict[str, Any], str]:
        """Create a compaction summary using the LLM.

        Args:
            messages: Current message history
            completion_func: Function to call LLM (from agent)

        Returns:
            Tuple of (summary_message, summary_text)

        Raises:
            Exception: If LLM call fails
        """
        # Build compaction request
        compact_messages = messages + [{"role": "user", "content": self.COMPACTION_PROMPT}]

        # Call LLM to generate summary
        response = completion_func(compact_messages)
        summary_text = response.choices[0].message.content

        # Create summary message
        summary_message = {
            "role": "assistant",
            "content": f"[COMPACTION SUMMARY]\n\n{summary_text}",
            "metadata": {
                "is_compaction": True,
                "original_message_count": len(messages),
                "timestamp": datetime.now().isoformat(),
            },
        }

        return summary_message, summary_text
