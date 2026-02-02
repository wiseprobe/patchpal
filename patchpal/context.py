"""Context window management and token estimation."""

import os
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

        # Fallback: ~3 chars per token (conservative for code-heavy content)
        # This is more accurate than 4 chars/token for technical content
        return len(str(text)) // 3

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

    # OpenCode-inspired thresholds - configurable via environment variables
    PRUNE_PROTECT = int(
        os.getenv("PATCHPAL_PRUNE_PROTECT", "40000")
    )  # Keep last 40k tokens of tool outputs
    PRUNE_MINIMUM = int(
        os.getenv("PATCHPAL_PRUNE_MINIMUM", "20000")
    )  # Minimum tokens to prune to make it worthwhile
    COMPACT_THRESHOLD = float(
        os.getenv("PATCHPAL_COMPACT_THRESHOLD", "0.75")
    )  # Compact at 75% capacity (lower due to estimation inaccuracy)

    # Cache warming configuration (inspired by aider)
    # Anthropic's prompt cache expires after 5 minutes of inactivity
    # We ping slightly before expiry (295 seconds = 5 min - 5 sec buffer)
    CACHE_WARMING_DELAY = float(
        os.getenv("PATCHPAL_CACHE_WARMING_DELAY", "295")
    )  # Seconds between cache warming pings
    CACHE_WARMING_PINGS = int(
        os.getenv("PATCHPAL_CACHE_WARMING_PINGS", "0")
    )  # Number of keepalive pings (0 = disabled)

    # Model context limits (tokens)
    # From OpenCode's models.dev data - see https://models.dev/api.json
    MODEL_LIMITS = {
        # Anthropic Claude models
        "claude-opus-4": 200_000,
        "claude-sonnet-4": 200_000,
        "claude-haiku-4": 200_000,
        "claude-3-5-sonnet": 200_000,
        "claude-3-5-haiku": 200_000,
        "claude-3-7-sonnet": 200_000,
        "claude-sonnet": 200_000,
        "claude-opus": 200_000,
        "claude-haiku": 200_000,
        # OpenAI GPT models
        "gpt-5": 400_000,
        "gpt-5.1": 128_000,
        "gpt-5.2": 400_000,
        "gpt-5-mini": 400_000,
        "gpt-5-nano": 400_000,
        "gpt-4o": 128_000,
        "gpt-4-turbo": 128_000,
        "gpt-4.1": 128_000,
        "gpt-4": 8_000,
        "gpt-3.5-turbo": 16_385,
        "o3": 128_000,
        "o3-mini": 128_000,
        "o4-mini": 128_000,
        # Google Gemini models
        "gemini-3-pro": 1_000_000,
        "gemini-3-flash": 1_048_576,
        "gemini-2.5-pro": 1_048_576,
        "gemini-2.5-flash": 1_048_576,
        "gemini-2.0-flash": 1_000_000,
        "gemini-1.5-pro": 1_000_000,
        "gemini-1.5-flash": 1_000_000,
        "gemini-pro": 32_000,
        # xAI Grok models
        "grok-4": 256_000,
        "grok-4-fast": 2_000_000,
        "grok-3": 131_072,
        "grok-3-fast": 131_072,
        "grok-3-mini": 131_072,
        "grok-2": 131_072,
        "grok-code-fast": 256_000,
        # DeepSeek models
        "deepseek-v3": 128_000,
        "deepseek-v3.1": 128_000,
        "deepseek-r1": 128_000,
        "deepseek-chat": 128_000,
        "deepseek-coder": 128_000,
        "deepseek-reasoner": 128_000,
        # Qwen models
        "qwen-turbo": 1_000_000,
        "qwen-plus": 1_000_000,
        "qwen-max": 32_768,
        "qwen-flash": 1_000_000,
        "qwen3": 131_072,
        "qwen3-coder": 262_144,
        "qwen2.5": 131_072,
        "qwq": 131_072,
        "qvq": 131_072,
        # Meta Llama models
        "llama-4": 131_072,
        "llama-3.3": 128_000,
        "llama-3.2": 128_000,
        "llama-3.1": 128_000,
        "llama-3": 8_192,
        "llama-guard": 8_192,
        # Mistral models
        "mistral-large": 128_000,
        "mistral-small": 128_000,
        "codestral": 128_000,
        "ministral": 262_144,
        "devstral": 262_144,
        # Cohere models
        "command-r": 128_000,
        "command-r-plus": 128_000,
        "command-r7b": 128_000,
        "command-a": 256_000,
        # OpenAI open-source models
        "gpt-oss": 128_000,
        # MiniMax models
        "minimax": 128_000,
        # Kimi models
        "kimi": 262_144,
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

        Can be overridden with PATCHPAL_CONTEXT_LIMIT env var for testing.

        Returns:
            Context window size in tokens
        """
        # Allow override for testing
        override = os.getenv("PATCHPAL_CONTEXT_LIMIT")
        if override:
            try:
                return int(override)
            except ValueError:
                pass  # Fall through to normal detection

        model_lower = self.model_id.lower()

        # Try exact matches first (longest first to match more specific models)
        # Sort keys by length descending to match "gpt-5.1" before "gpt-5"
        for key in sorted(self.MODEL_LIMITS.keys(), key=len, reverse=True):
            if key in model_lower:
                return self.MODEL_LIMITS[key]

        # Check for model families (fallback for versions not explicitly listed)
        if "claude" in model_lower:
            return 200_000  # Modern Claude models
        elif "gpt-5" in model_lower:
            return 400_000  # GPT-5 family
        elif "gpt-4" in model_lower:
            return 128_000  # GPT-4 family
        elif "gpt-3.5" in model_lower or "gpt-3" in model_lower:
            return 16_385
        elif "gemini-3" in model_lower or "gemini-2" in model_lower or "gemini-1.5" in model_lower:
            return 1_000_000  # Modern Gemini models
        elif "gemini" in model_lower:
            return 32_000  # Older Gemini models
        elif "grok" in model_lower:
            return 131_072  # Grok models
        elif "deepseek" in model_lower:
            return 128_000  # DeepSeek models
        elif "qwen" in model_lower or "qwq" in model_lower or "qvq" in model_lower:
            return 131_072  # Qwen models
        elif "llama" in model_lower:
            return 128_000  # Llama models
        elif "mistral" in model_lower or "codestral" in model_lower or "ministral" in model_lower:
            return 128_000  # Mistral models
        elif "command" in model_lower:
            return 128_000  # Cohere Command models
        elif "kimi" in model_lower:
            return 262_144  # Kimi models
        elif "minimax" in model_lower:
            return 128_000  # MiniMax models

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
