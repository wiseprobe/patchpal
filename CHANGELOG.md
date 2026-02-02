# Changes

Most recent releases are shown at the top. Each release shows:

- **New**: New classes, methods, functions, etc
- **Changed**: Additional parameters, changes to inputs or outputs, etc
- **Fixed**: Bug fixes that don't change documented behaviour


## 0.7.1 (2026-02-02)

### new:
- N/A

### changed
- N/A

### fixed:
- **Context window management**: Fixed critical bug where reading large files (3.46MB) could push context to 1234% capacity, causing compaction to fail. Implemented three-layer defense: (1) Reduced `MAX_FILE_SIZE` from 10MB to 500KB, (2) Added runtime monitoring and truncation of tool outputs (warns at >100K chars, truncates to 50K chars if adding would exceed 150% capacity), (3) Smart compaction strategy with aggressive pruning for few-message/high-capacity scenarios and emergency mode at ≥100% capacity. (#39)


## 0.7.0 (2026-02-01)

### new:
- Added **prompt caching statistics tracking**: `/status` command now displays cache write tokens, cache read tokens, cache hit rate, and cost-adjusted input tokens for Anthropic/Bedrock models, providing visibility into caching effectiveness and actual costs. (#38)

### changed
- N/A

### fixed:
- N/A


## 0.6.0 (2026-01-31)

### new:
- Added **custom tools support for CLI**: Tools are now auto-discovered from `~/.patchpal/tools/*.py` at startup, extending the existing Python API support to CLI users. Custom tools appear alongside built-in tools with automatic schema generation from type hints and docstrings. (#37)

### changed
- N/A

### fixed:
- N/A


## 0.5.1 (2026-01-30)

### new:
- N/A

### changed
- N/A

### fixed:
- Fixed `web_search` SSL certificate verification in corporate environments: Now automatically detects and uses `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` environment variables for custom CA certificates. Added `PATCHPAL_VERIFY_SSL` environment variable for explicit SSL configuration. (#36)


## 0.5.0 (2026-01-30)

### new:
- Added **custom tools support** for Python API: Users can now pass Python functions to `create_agent(custom_tools=[...])` with automatic schema generation from type hints and docstrings (#35)

### changed
- N/A

### fixed:
- Fixed conversation state corruption when pressing CTRL-C during tool execution. Previously, interrupting the agent would leave the conversation history in an invalid state (assistant message with `tool_calls` but no corresponding tool responses), causing OpenAI API to reject subsequent requests. The agent now properly cleans up interrupted state by adding error responses for all pending tool calls, ensuring conversation remains valid after interruption.


## 0.4.5 (2026-01-30)

### new:
- N/A

### changed
- File operation permissions now use directory-based patterns (matches Claude Code behavior) (#33)
- Permission prompts now show scope context (working directory for shell, directory for files) (#33)
- Shell command permissions now use composite patterns `command@directory` for `cd` commands, properly isolating different working directories (#33)

### fixed:
- Fixed `read_file` and `read_lines` incorrectly detecting JSON, XML, and other text-based files as binary. Added whitelist for common text-based `application/*` MIME types including JSON, XML, JavaScript, YAML, and shell scripts. (#32)
- Fixed test fixture to properly reset cached permission manager
- Fixed shell command permission patterns to extract actual command from compound commands (e.g., `cd /tmp && python test.py` now correctly identifies `python` as the command, not `cd`) (#33)
- Fixed shell command permission prompts to show the correct working directory when `cd` is used (e.g., shows `/tmp` instead of repo root) (#33)
- Fixed Windows compatibility: shell command patterns now use `@` separator instead of `:` to avoid conflicts with Windows drive letters (e.g., `python@C:\temp` instead of `python:C:\temp`) (#33)
- Fixed Windows compatibility: file permission patterns now normalize path separators to forward slashes for cross-platform consistency (e.g., `src/app.py` instead of `src\app.py`), preventing permission grant mismatches when mixing slash styles (#33)
- Windows fixes


## 0.4.4 (2026-01-29)

### new:
- N/A

### changed
- N/A

### fixed:
- Fixed Bedrock prompt caching to use correct marker format: Anthropic models on Bedrock now use `cache_control` (same as direct Anthropic API), while non-Anthropic Bedrock models (Nova, etc.) use `cachePoint`. Previous implementation incorrectly used `cachePoint` for all Bedrock models.
- Added support for Amazon Nova models prompt caching on Bedrock


## 0.4.3 (2026-01-29)

### new:
- N/A

### changed
- N/A

### fixed:
- Fixed prompt caching structure to place `cache_control` markers inside content blocks instead of at message level. Previous implementation was completely ignored by Anthropic API, resulting in 0% cache rate. After this fix, users should see actual cache hits and significant cost reduction on cached content.


## 0.4.2 (2026-01-29)

### new:
- N/A

### changed
- N/A

### fixed:
- Fixed tilde (~) expansion in file paths - tools like `read_file` and `tree` now properly handle paths like `~/path/to/file`


## 0.4.1 (2026-01-29)

### new:
- N/A

### changed
- N/A

### fixed:
- **CRITICAL**: Fixed prompt caching field name from `cacheControl` (camelCase) to `cache_control` (snake_case). This bug caused Anthropic API to ignore all cache markers, resulting in ~10x higher costs than expected. Users should see ~90% cost reduction after this fix. (#31)


## 0.4.0 (2026-01-29)

### new:
- Track cumulative token counts in `/status`

### changed
- N/A

### fixed:
- N/A


## 0.3.2 (2026-01-28)

### new:
- N/A

### changed
- Updated tool description for `run_shell`

### fixed:
- Ensure colored diff in `edit_file` displays proper indentation (#29)


## 0.3.1 (2026-01-28)

### new:
- N/A

### changed
- N/A

### fixed:
- Fix `edit_file` but with trailing new lines (#28)



## 0.3.0 (2026-01-28)

### new:
- Support for prompt-caching Anthropic models (#26)

### changed
- change default compaction threshold to 75% (#27)

### fixed:
- Make `edit_file` more robust (#25)


## 0.2.1 (2026-01-27)

### new:
- N/A

### changed
- N/A

### fixed:
- Refine `edit_file` to mitigate edit fails (#23)
- Ensure TODO tasks are tracked in session (#24)

## 0.2.0 (2026-01-26)

### new:
- Added `read_lines` tool (#21)
- Added `todo` tools (#22)
- Added `ask_user` tool (#22)

### changed
- N/A

### fixed:
- N/A


## 0.1.6 (2026-01-22)

### new:
- N/A

### changed
- Added `--require-permission-for-all` (#20)

### fixed:
- N/A


## 0.1.5 (2026-01-21)

### new:
- N/A

### changed
- N/A

### fixed:
- Ensure `web_search` and `web_fetch` tools require permission by default


## 0.1.4 (2026-01-21)

### new:
- N/A

### changed
- Added `PATCHPAL_ALLOW_SUDO` environment variable.
- Enhanced README.md security documentation with clearer warning for
  `PATCHPAL_REQUIRE_PERMISSION` environment variable

### fixed:
- N/A


## 0.1.3 (2026-01-20)

### new:
- N/A

### changed
- N/A

### fixed:
- Added `--version` argument to CLI
- Added `boto3` as dependency


## 0.1.2 (2026-01-20)

### new:
- N/A

### changed
- N/A

### fixed:
- Fix Ollama support (925fb47840c777ed53224fa450ea33b52ba3cb5d)


## 0.1.1 (2026-01-20)

### new:
- N/A

### changed
- N/A

### fixed:
- Increase `PATCHPAL_MAX_OPERATIONS` default


## 0.1.0 (2026-01-20)

### new:
- first release

### changed
- N/A

### fixed:
- N/A
