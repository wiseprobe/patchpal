# Air-Gapped and Offline Environments

For environments without internet access (air-gapped, offline, or restricted networks), you can disable web search and fetch tools:

```bash
# Disable web tools for air-gapped environment
export PATCHPAL_ENABLE_WEB=false
patchpal

# Or combine with local vLLM for complete offline operation (recommended)
export PATCHPAL_ENABLE_WEB=false
export HOSTED_VLLM_API_BASE=http://localhost:8000
export HOSTED_VLLM_API_KEY=token-abc123
patchpal --model hosted_vllm/openai/gpt-oss-20b
```

When web tools are disabled:
- `web_search` and `web_fetch` are removed from available tools
- With a local model, the agent won't attempt any network requests
- Perfect for secure, isolated, or offline development environments

## Viewing Help
```bash
patchpal --help
```

## Maximum Security Mode

For maximum security and control, you can require permission for **all** operations including read operations:

```bash
patchpal --require-permission-for-all
```

When enabled, the agent will prompt for permission before:
- **Read operations**: `read_file`, `list_files`, `get_file_info`, `find_files`, `tree`, `grep`, `git_status`, `git_diff`, `git_log`
- **Write operations**: `edit_file`, `apply_patch` (always require permission)
- **Shell commands**: `run_shell` (always requires permission)
- **Web operations**: `web_search`, `web_fetch` (always require permission)

**Granular session permissions:**
When you grant permission for read operations, you can choose to grant it for:
- **This specific operation only** (option 1)
- **This specific file/pattern for the session** (option 2) - e.g., grant permission to read `config.py` for the session, but still prompt for other files
- **Cancel the operation** (option 3)

This provides fine-grained control over what the agent can access during the session.

**Use cases:**
- Working with highly sensitive codebases
- Security audits where every operation must be reviewed
- Training/demonstration purposes where you want to see exactly what the agent does
- Untrusted environments where you want complete control

**Example session:**
```bash
$ patchpal --require-permission-for-all
================================================================================
PatchPal - AI coding and automation assistant
================================================================================

Using model: anthropic/claude-sonnet-4-5
🔒 Permission required for ALL operations (including reads)

You: Read config.py and database.py

================================================================================
Read File
--------------------------------------------------------------------------------
   Read: config.py
--------------------------------------------------------------------------------

Do you want to proceed?
  1. Yes
  2. Yes, and don't ask again this session for 'config.py'
  3. No, and tell me what to do differently

Choice [1-3]: 2

# Agent reads config.py, then prompts for database.py

================================================================================
Read File
--------------------------------------------------------------------------------
   Read: database.py
--------------------------------------------------------------------------------

Do you want to proceed?
  1. Yes
  2. Yes, and don't ask again this session for 'database.py'
  3. No, and tell me what to do differently

Choice [1-3]: 1

# Agent reads database.py, but will prompt again if it tries to read it later
# Won't prompt again for config.py since you chose option 2
```

**Note:** This mode is separate from and overrides `PATCHPAL_REQUIRE_PERMISSION=false`. Even if you've disabled the standard permission system, `--require-permission-for-all` will still prompt for all operations.
