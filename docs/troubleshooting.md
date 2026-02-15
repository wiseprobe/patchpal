
# Troubleshooting

**Error: "maximum iterations reached"**
- The default number of iterations is 100.
- Increase with `export PATCHPAL_MAX_ITERATIONS=200` (see [Configuration](https://github.com/amaiya/patchpal?tab=readme-ov-file#configuration))

**Error: "Context Window Error - Input is too long"**
- PatchPal includes automatic context management (compaction) to prevent this error.
- **Quick fix:** Run `/prune` to remove old tool outputs, or `/compact` to compact the conversation history.
- Use `/status` to check your context window usage and see how close you are to the limit.
- If auto-compaction is disabled, re-enable it: `unset PATCHPAL_DISABLE_AUTOCOMPACT`
- Context is automatically managed at 75% capacity through pruning and compaction.
- **Note:** Token estimation may be slightly inaccurate compared to the model's actual counting. If you see this error despite auto-compaction being enabled, the 75% threshold may need to be lowered further for your workload. You can adjust it with `export PATCHPAL_COMPACT_THRESHOLD=0.70` (or lower).
- See [Configuration](https://github.com/amaiya/patchpal?tab=readme-ov-file#configuration) for context management settings.

**Reducing API Costs via Token Optimization**

When using cloud LLM providers (Anthropic, OpenAI, etc.), token usage directly impacts costs. PatchPal includes several features to help minimize token consumption:

**1. Use Pruning to Manage Long Sessions**
- **Automatic pruning** removes old tool outputs while preserving conversation context
- Configure pruning thresholds to be more aggressive:
  ```bash
  export PATCHPAL_PRUNE_PROTECT=20000    # Reduce from 40k to 20k tokens
  export PATCHPAL_PRUNE_MINIMUM=10000    # Reduce minimum saved from 20k to 10k
  ```
- Pruning happens transparently before compaction and is much faster (no LLM call needed)

**2. Monitor Session Token Usage**
- Use `/status` to see cumulative token usage in real-time
- **Session Statistics** section shows:
  - Total LLM calls made
  - Cumulative input tokens (raw totals, before caching discounts)
  - Cumulative output tokens
  - Total tokens for the session
- Check periodically during long sessions to monitor usage
- **Important**: Token counts don't reflect prompt caching discounts (Anthropic models)
- For actual costs, check your provider's usage dashboard which shows cache-adjusted billing

**3. Manual Context Management for Cost Control**
- Use `/status` regularly to monitor context window usage
- Run `/prune` to remove old tool outputs (fast, no LLM call)
- Run `/compact` proactively when context grows large (before hitting auto-compact threshold)
- Manual control gives you flexibility over when to optimize context

**4. Adjust Auto-Compaction Threshold**
- Lower threshold = more frequent compaction = smaller context = lower per-request costs
- Higher threshold = fewer compaction calls = larger context = higher per-request costs
  ```bash
  # More aggressive compaction (compact at 60% instead of 75%)
  export PATCHPAL_COMPACT_THRESHOLD=0.60
  ```
- Find the sweet spot for your workload (balance between compaction frequency and context size)

**5. Use Local Models for Zero API Costs**
- **Best option:** Run vLLM locally to eliminate API costs entirely
  ```bash
  export HOSTED_VLLM_API_BASE=http://localhost:8000
  export HOSTED_VLLM_API_KEY=token-abc123
  patchpal --model hosted_vllm/openai/gpt-oss-20b
  ```
- **Alternative:** Use Ollama (requires `OLLAMA_CONTEXT_LENGTH=32768`)
- See [Using Local Models](https://github.com/amaiya/patchpal?tab=readme-ov-file#using-local-models-vllm--ollama) for setup

**6. Start Fresh When Appropriate**
- Use `/clear` command to reset conversation history without restarting PatchPal
- Exit and restart PatchPal between unrelated tasks to clear context completely
- Each fresh start begins with minimal tokens (just the system prompt)
- Better than carrying large conversation history across different tasks

**7. Use Smaller Models for Simple Tasks**
- Use less expensive models for routine tasks:
  ```bash
  patchpal --model anthropic/claude-3-7-sonnet-latest  # Cheaper than claude-sonnet-4-5
  patchpal --model openai/gpt-5-mini                   # Cheaper than gpt-5.2
  ```
- Reserve premium models for complex reasoning tasks

**Cost Monitoring Tips:**
- Check `/status` before large operations to see current token usage
- **Anthropic models**: Prompt caching reduces costs (system prompt + last 2 messages cached)
<!--- **AWS GovCloud Bedrock**: PatchPal automatically detects GovCloud usage and applies ~1.2x pricing multiplier (based on observed Claude Sonnet pricing; may not be accurate for all models)-->
- Most cloud providers offer usage dashboards showing cache hits and actual charges
- Set up billing alerts with your provider to avoid surprises
- Consider local models (vLLM recommended) for high-volume usage or zero API costs
