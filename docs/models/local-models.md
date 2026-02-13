# Using Local Models (vLLM & Ollama)

Run models locally on your machine without needing API keys or internet access.

**⚠️ IMPORTANT: For local models, we recommend vLLM.**

vLLM provides:
- ✅ Robust multi-turn tool calling
- ✅ 3-10x faster inference than Ollama
- ✅ Production-ready reliability

## vLLM (Recommended for Local Models)

vLLM is significantly faster than Ollama due to optimized inference with continuous batching and PagedAttention.

**Important:** vLLM >= 0.10.2 is required for proper tool calling support.

**Using Local vLLM Server:**

```bash
# 1. Install vLLM (>= 0.10.2)
pip install vllm

# 2. Start vLLM server with tool calling enabled
vllm serve openai/gpt-oss-20b \
  --dtype auto \
  --api-key token-abc123 \
  --tool-call-parser openai \
  --enable-auto-tool-choice

# 3. Use with PatchPal (in another terminal)
export HOSTED_VLLM_API_BASE=http://localhost:8000
export HOSTED_VLLM_API_KEY=token-abc123
patchpal --model hosted_vllm/openai/gpt-oss-20b
```

**Using Remote/Hosted vLLM Server:**

```bash
# For remote vLLM servers (e.g., hosted by your organization)
export HOSTED_VLLM_API_BASE=https://your-vllm-server.com
export HOSTED_VLLM_API_KEY=your_api_key_here
patchpal --model hosted_vllm/openai/gpt-oss-20b
```

**Environment Variables:**
- Use `HOSTED_VLLM_API_BASE` and `HOSTED_VLLM_API_KEY`

**Using YAML Configuration (Alternative):**

Create a `config.yaml`:
```yaml
host: "0.0.0.0"
port: 8000
api-key: "token-abc123"
tool-call-parser: "openai"  # Use appropriate parser for your model
enable-auto-tool-choice: true
dtype: "auto"
```

Then start vLLM:
```bash
vllm serve openai/gpt-oss-20b --config config.yaml

# Use with PatchPal
export HOSTED_VLLM_API_BASE=http://localhost:8000
export HOSTED_VLLM_API_KEY=token-abc123
patchpal --model hosted_vllm/openai/gpt-oss-20b
```

**Recommended models for vLLM:**
- `openai/gpt-oss-20b` - OpenAI's open-source model (use parser: `openai`)

**Tool Call Parser Reference:**
Different models require different parsers. Common parsers include: `qwen3_xml`, `openai`, `deepseek_v3`, `llama3_json`, `mistral`, `hermes`, `pythonic`, `xlam`. See [vLLM Tool Calling docs](https://docs.vllm.ai/en/latest/features/tool_calling/) for the complete list.

## Ollama

Ollama v0.14+ supports tool calling for agentic workflows. However, proper configuration is **critical** for reliable operation.

**Requirements:**

1. **Ollama v0.14.0 or later** - Required for tool calling support
2. **Sufficient context window** - Default 4096 tokens is too small; increase to at least 32K

**Setup Instructions:**

**For Native Ollama Installation:**

```bash
# Set context window size (required!)
export OLLAMA_CONTEXT_LENGTH=32768

# Start Ollama server
ollama serve

# In another terminal, use with PatchPal
patchpal --model ollama_chat/gpt-oss:20b
```

**For Docker:**

```bash
# Stop existing container (if running)
docker stop ollama
docker rm ollama

# Start with proper configuration
docker run -d \
  --gpus all \
  -e OLLAMA_CONTEXT_LENGTH=32768 \
  -v ollama:/root/.ollama \
  -p 11434:11434 \
  --name ollama \
  ollama/ollama

# Verify configuration
docker exec -it ollama ollama run gpt-oss:20b
# In the Ollama prompt, type: /show parameters
# Should show num_ctx much larger than default 4096

# Use with PatchPal
patchpal --model ollama_chat/gpt-oss:20b
```

**Verifying Context Window Size:**

```bash
# Check your Ollama container configuration
docker inspect ollama | grep OLLAMA_CONTEXT_LENGTH

# Or run a model and check parameters
docker exec -it ollama ollama run gpt-oss:20b
>>> /show parameters
```

**Recommended Models for Tool Calling:**

- `gpt-oss:20b` - OpenAI's open-source model, excellent tool calling
- `qwen3:32b` - Qwen3 model with good agentic capabilities
- `qwen3-coder` - Specialized for coding tasks

**Performance Note:**

While Ollama now works with proper configuration, vLLM is still recommended for production use due to:
- 3-10x faster inference
- More robust tool calling implementation
- Better memory management

**Examples:**

```bash
# Ollama (works with proper configuration)
export OLLAMA_CONTEXT_LENGTH=32768
patchpal --model ollama_chat/qwen3:32b
patchpal --model ollama_chat/gpt-oss:20b

# vLLM (recommended for production)
patchpal --model hosted_vllm/openai/gpt-oss-20b
```
