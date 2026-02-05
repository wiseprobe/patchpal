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
    ENABLE_PROACTIVE_PRUNING = (
        os.getenv("PATCHPAL_PROACTIVE_PRUNING", "true").lower() == "true"
    )  # Proactively prune after tool calls when outputs exceed PRUNE_PROTECT (default: true)

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

    def _summarize_tool_output(self, tool_name: str, content: str) -> str:
        """Create an intelligent summary of a tool output.

        Different tools need different summarization strategies:
        - Navigation tools (list_files, tree, get_repo_map): Just note they ran
        - read_file: Keep first/last lines with ellipsis
        - grep_code: Keep match count and first few results
        - git_status: Simple status summary
        - run_shell: Command + exit code + key numbers

        Args:
            tool_name: Name of the tool that produced this output
            content: Original tool output content

        Returns:
            Summarized content string
        """
        content_str = str(content)
        original_len = len(content_str)

        # Tools that can be heavily summarized (low information loss)
        if tool_name == "list_files":
            # Extract file count
            lines = content_str.split("\n")
            file_count = len([line for line in lines if line.strip() and not line.startswith("[")])
            sample_files = [
                line.strip() for line in lines[:3] if line.strip() and not line.startswith("[")
            ]
            return f"[Pruned list_files: {file_count} files, e.g., {', '.join(sample_files)}...]"

        elif tool_name == "tree":
            # Extract directory count and depth
            lines = content_str.split("\n")
            dir_count = content_str.count("/")
            return f"[Pruned tree: ~{dir_count} directories, {len(lines)} lines of structure]"

        elif tool_name == "get_repo_map":
            # Extract file count and some top-level info
            if "files analyzed" in content_str:
                import re

                match = re.search(r"(\d+)\s+files? analyzed", content_str)
                file_count = match.group(1) if match else "?"
            else:
                file_count = "?"
            # Extract first few class/function names
            lines = [
                line
                for line in content_str.split("\n")[:10]
                if "class" in line.lower() or "def" in line.lower()
            ]
            return f"[Pruned repo_map: {file_count} files analyzed, ~{original_len:,} chars of structure]"

        elif tool_name == "git_status":
            # Extract just the counts
            modified = content_str.count("modified:")
            untracked = content_str.count("untracked:")
            staged = content_str.count("new file:") + content_str.count("modified:")
            return (
                f"[Pruned git_status: {modified} modified, {untracked} untracked, {staged} staged]"
            )

        elif tool_name == "run_shell":
            # Extract command and summarize output
            lines = content_str.split("\n")
            command_line = lines[0] if lines else ""
            # Look for obvious success/failure indicators
            if "error" in content_str.lower() or "failed" in content_str.lower():
                status = "⚠ errors"
            else:
                status = "✓ success"
            # Extract any numbers (line counts, file counts, etc.)
            import re

            numbers = re.findall(r"\d+", content_str)
            num_summary = f", numbers: {', '.join(numbers[:5])}" if numbers else ""
            return f"[Pruned run_shell: {command_line[:60]}... → {status}{num_summary}]"

        elif tool_name == "grep_code":
            # Keep match count and first few matches
            lines = content_str.split("\n")
            match_lines = [line for line in lines if ":" in line and line.strip()]
            match_count = len(match_lines)
            first_matches = "\n".join(match_lines[:3])
            if match_count > 3:
                return f"[Pruned grep_code: {match_count} matches, first 3:\n{first_matches}\n... +{match_count - 3} more]"
            else:
                return f"[Pruned grep_code: {match_count} matches:\n{first_matches}]"

        # Tools that should preserve more content (high information value)
        elif tool_name == "read_file":
            # Keep first/last N lines with ellipsis
            lines = content_str.split("\n")
            # For very large content, always summarize even if few lines
            if len(content_str) > 10_000 and len(lines) <= 20:
                # Large file with few/no newlines - truncate to first/last chars
                if len(content_str) > 1000:
                    return f"{content_str[:500]}\n\n... [{len(content_str) - 1000} chars omitted] ...\n\n{content_str[-500:]}"
            if len(lines) <= 20:
                # Short files: keep everything
                return content_str
            else:
                # Long files: keep first 10 and last 10 lines
                first_10 = "\n".join(lines[:10])
                last_10 = "\n".join(lines[-10:])
                return f"{first_10}\n\n... [{len(lines) - 20} lines omitted] ...\n\n{last_10}"

        elif tool_name == "code_structure":
            # Keep first 500 chars (it's already compact)
            if len(content_str) <= 500:
                return content_str
            else:
                return content_str[:500] + f"\n\n... [+{len(content_str) - 500} chars omitted]"

        elif tool_name in ("git_diff", "git_log"):
            # Keep first 300 chars of diffs/logs
            if len(content_str) <= 300:
                return content_str
            else:
                return content_str[:300] + f"\n\n... [+{len(content_str) - 300} chars omitted]"

        elif tool_name in ("find_files", "get_file_info"):
            # Keep first 200 chars
            if len(content_str) <= 200:
                return content_str
            else:
                return content_str[:200] + f"... [+{len(content_str) - 200} chars]"

        # Default: generic truncation
        else:
            return f"[Tool output pruned - {tool_name} returned {original_len:,} chars]"

    def prune_tool_outputs(
        self, messages: List[Dict[str, Any]], intelligent: bool = False
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Prune old tool outputs to reclaim token space.

        Walks backward through messages and prunes tool outputs beyond
        the PRUNE_PROTECT threshold (keeps last 40k tokens of tool outputs).

        Args:
            messages: Current message history
            intelligent: If True, use smart summarization; if False, simple deletion markers

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

        # Prune with intelligent summarization or simple markers
        pruned_messages = []
        tokens_saved = 0

        for i, msg in enumerate(messages):
            if any(idx == i for idx, _, _ in prune_candidates):
                pruned_msg = msg.copy()
                original_content = pruned_msg.get("content", "")

                # Use intelligent summarization if requested, otherwise simple pruning
                if intelligent:
                    # Get tool name for intelligent summarization
                    tool_name = msg.get("name", "unknown")
                    summarized_content = self._summarize_tool_output(tool_name, original_content)
                else:
                    # Simple pruning: just replace with a marker
                    original_len = len(str(original_content))
                    summarized_content = f"[Tool output pruned - was {original_len:,} chars]"

                # Update message with summarized content
                pruned_msg["content"] = summarized_content
                pruned_messages.append(pruned_msg)

                # Calculate tokens saved
                tokens_saved += self.estimator.estimate_tokens(str(original_content))
                tokens_saved -= self.estimator.estimate_tokens(summarized_content)
            else:
                pruned_messages.append(msg)

        # Sanitize all assistant messages to remove tool calls with invalid names
        # Bedrock validates tool names against pattern: [a-zA-Z0-9_-]+
        # This prevents validation errors when sending pruned messages to the API
        # Also removes corresponding orphaned tool response messages to maintain valid conversation structure
        import re

        valid_pattern = re.compile(r"^[a-zA-Z0-9_-]+$")
        sanitized_messages = []
        invalid_tool_call_ids = set()  # Track IDs of removed tool calls

        # First pass: identify invalid tool calls and remove them
        for msg in pruned_messages:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                tool_calls = msg["tool_calls"]

                # Filter out tool calls with invalid names
                valid_tool_calls = []
                for tc in tool_calls:
                    if hasattr(tc, "function") and hasattr(tc.function, "name"):
                        if valid_pattern.match(tc.function.name):
                            valid_tool_calls.append(tc)
                        else:
                            # Track this invalid tool call ID so we can remove its response
                            invalid_tool_call_ids.add(tc.id)

                # If we filtered out any invalid calls, create a cleaned message
                if len(valid_tool_calls) < len(tool_calls):
                    cleaned_msg = msg.copy()
                    cleaned_msg["tool_calls"] = valid_tool_calls if valid_tool_calls else None
                    sanitized_messages.append(cleaned_msg)
                else:
                    sanitized_messages.append(msg)
            else:
                sanitized_messages.append(msg)

        # Second pass: remove orphaned tool response messages
        if invalid_tool_call_ids:
            final_messages = []
            for msg in sanitized_messages:
                # Skip tool responses for invalid tool calls
                if msg.get("role") == "tool" and msg.get("tool_call_id") in invalid_tool_call_ids:
                    continue
                final_messages.append(msg)
            return final_messages, tokens_saved

        return sanitized_messages, tokens_saved

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
