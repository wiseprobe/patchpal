# Model Configuration

PatchPal supports any LiteLLM-compatible model. You can configure the model in three ways (in order of priority):

## 1. Command-line Argument
```bash
patchpal --model openai/gpt-5.2-codex
patchpal --model anthropic/claude-sonnet-4-5
patchpal --model hosted_vllm/openai/gpt-oss-20b # local model - no API charges
```

## 2. Environment Variable
```bash
export PATCHPAL_MODEL=openai/gpt-5.2-codex
patchpal
```

## 3. Default Model
If no model is specified, PatchPal uses `anthropic/claude-sonnet-4-5` (Claude Sonnet 4.5).

## Supported Models

PatchPal works with any model supported by LiteLLM, including:

- **Anthropic** (Recommended): `anthropic/claude-sonnet-4-5`, `anthropic/claude-opus-4-5`, `anthropic/claude-3-7-sonnet-latest`
- **OpenAI**: `openai/gpt-5.2`, `openai/gpt-5.2-codex`, `openai/gpt-5-mini`
- **AWS Bedrock**: `bedrock/anthropic.claude-sonnet-4-5-v1:0`
- **vLLM (Local)** (Recommended for local): See vLLM section below for setup
- **Ollama (Local)**:  See Ollama section below for setup
- **Google**: `gemini/gemini-pro`, `vertex_ai/gemini-pro`
- **Others**: Cohere, Azure OpenAI, and many more


See the [LiteLLM providers documentation](https://docs.litellm.ai/docs/providers) for the complete list.
