# Configuration

PatchPal can be configured through `PATCHPAL_*` environment variables to customize behavior, security, and performance.

### Model Selection

```bash
export PATCHPAL_MODEL=openai/gpt-5.2          # Override default model
# Priority: CLI arg > PATCHPAL_MODEL env var > default (anthropic/claude-sonnet-4-5)
```

### Security & Permissions

```bash
# Permission System
export PATCHPAL_REQUIRE_PERMISSION=true      # Prompt before executing commands/modifying files (default: true)
                                              # ⚠️  WARNING: Setting to false disables prompts - only use in trusted environments

# File Safety
export PATCHPAL_MAX_FILE_SIZE=512000         # Maximum file size in bytes for read/write (default: 500KB)
                                             # Reduced from 10MB to prevent context window explosions
export PATCHPAL_MAX_TOOL_OUTPUT_LINES=2000   # Maximum lines per tool output (default: 2000)
                                             # Prevents any single tool from dominating context
export PATCHPAL_MAX_TOOL_OUTPUT_CHARS=100000 # Maximum characters per tool output (default: 100K)
                                             # Applied after tool execution to all tool results
                                             # Character-based (not bytes) to avoid breaking Unicode
export PATCHPAL_READ_ONLY=true               # Prevent ALL file modifications (default: false)
                                             # Useful for: code review, exploration, security audits
export PATCHPAL_ALLOW_SENSITIVE=true         # Allow access to .env, credentials (default: false - blocked)
                                             # Only enable with test/dummy credentials

# Command Safety
export PATCHPAL_ALLOW_SUDO=true              # Allow sudo/privilege escalation (default: false - blocked)
                                              # ⚠️  WARNING: Only enable in trusted, controlled environments
export PATCHPAL_SHELL_TIMEOUT=60             # Shell command timeout in seconds (default: 30)
```

### Operational Controls

```bash
# Logging & Auditing
export PATCHPAL_AUDIT_LOG=false              # Log operations to ~/.patchpal/<repo-name>/audit.log (default: true)
export PATCHPAL_ENABLE_BACKUPS=true          # Auto-backup files before modification (default: false)

# Resource Limits
export PATCHPAL_MAX_OPERATIONS=10000         # Max operations per session (default: 10000)
export PATCHPAL_MAX_ITERATIONS=150           # Max agent iterations per task (default: 100)
                                              # Increase for complex multi-file tasks
export PATCHPAL_LLM_TIMEOUT=300              # LLM API timeout in seconds (default: 300 = 5 minutes)
                                              # Prevents indefinite stalls when API is unresponsive
```

### Context Window Management

```bash
# Auto-Compaction
export PATCHPAL_DISABLE_AUTOCOMPACT=true     # Disable auto-compaction (default: false - enabled)
export PATCHPAL_COMPACT_THRESHOLD=0.75       # Trigger compaction at % full (default: 0.75 = 75%)

# Context Limits
export PATCHPAL_CONTEXT_LIMIT=100000         # Override model's context limit (for testing)
                                              # Leave unset to use model's actual capacity

# Pruning Controls
export PATCHPAL_PROACTIVE_PRUNING=true       # Prune tool outputs after calls when > PRUNE_PROTECT (default: true)
                                              # Uses intelligent summarization to preserve context
export PATCHPAL_PRUNE_PROTECT=40000          # Keep last N tokens of tool outputs (default: 40000)
export PATCHPAL_PRUNE_MINIMUM=20000          # Minimum tokens to prune (default: 20000)
```

### Web Tools

```bash
# Enable/Disable Web Access
export PATCHPAL_ENABLE_WEB=false             # Disable web search/fetch for air-gapped environments (default: true)

# SSL Certificate Verification (for web_search)
export PATCHPAL_VERIFY_SSL=true              # SSL verification for web searches (default: true)
                                              # Set to 'false' to disable (not recommended for production)
                                              # Or set to path of CA bundle file for corporate certificates
                                              # Auto-detects SSL_CERT_FILE and REQUESTS_CA_BUNDLE if not set
                                              # Examples:
                                              #   export PATCHPAL_VERIFY_SSL=false  # Disable verification
                                              #   export PATCHPAL_VERIFY_SSL=/path/to/ca-bundle.crt  # Custom CA bundle
                                              #   (Leave unset to auto-detect from SSL_CERT_FILE/REQUESTS_CA_BUNDLE)

# Web Request Limits
export PATCHPAL_WEB_TIMEOUT=60               # Web request timeout in seconds (default: 30)
export PATCHPAL_MAX_WEB_SIZE=10485760        # Max web content size in bytes (default: 5MB)
                                              # Character limits are controlled by PATCHPAL_MAX_TOOL_OUTPUT_CHARS
```

### Custom System Prompt

```bash
export PATCHPAL_SYSTEM_PROMPT=~/.patchpal/my_prompt.md  # Use custom system prompt
                                                         # File can use template variables: {current_date}, {platform_info}
                                                         # Useful for: custom behavior, team standards, domain-specific instructions
```

### Configuration Examples

**Air-Gapped Environment (Offline, No Web Access):**
```bash
export PATCHPAL_ENABLE_WEB=false
patchpal --model hosted_vllm/openai/gpt-oss-20b
```

**Maximum Security (Read-Only Analysis):**
```bash
export PATCHPAL_READ_ONLY=true
export PATCHPAL_REQUIRE_PERMISSION=true
patchpal --require-permission-for-all
```

**Testing Context Management:**
```bash
export PATCHPAL_CONTEXT_LIMIT=10000          # Small limit to trigger compaction quickly
export PATCHPAL_COMPACT_THRESHOLD=0.75       # Trigger at 75% instead of 85%
export PATCHPAL_PRUNE_PROTECT=500            # Keep only last 500 tokens
patchpal
```

**Autonomous Mode (Trusted Environment Only):**
```bash
export PATCHPAL_REQUIRE_PERMISSION=false     # ⚠️  Disables all permission prompts
export PATCHPAL_MAX_ITERATIONS=200           # Allow longer runs
patchpal
```
