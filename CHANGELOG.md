# Changes

Most recent releases are shown at the top. Each release shows:

- **New**: New classes, methods, functions, etc
- **Changed**: Additional parameters, changes to inputs or outputs, etc
- **Fixed**: Bug fixes that don't change documented behaviour


## 0.4.0 (TBD)

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
