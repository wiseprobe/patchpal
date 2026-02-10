
# Safety

The agent operates with a security model inspired by Claude Code:

- **Permission system**: User approval required for all shell commands and file modifications (can be customized)
- **Write boundary enforcement**: Write operations restricted to repository (matches Claude Code)
  - Read operations allowed anywhere (system files, libraries, debugging, automation)
  - Write operations outside repository require explicit permission
- **Privilege escalation blocking**: Platform-aware blocking of privilege escalation commands
  - Unix/Linux/macOS: `sudo`, `su`
  - Windows: `runas`, `psexec`
- **Dangerous pattern detection**: Blocks patterns like `> /dev/`, `rm -rf /`, `| dd`, `--force`
- **Timeout protection**: Shell commands timeout after 30 seconds

### Security Guardrails ✅ FULLY ENABLED

PatchPal includes comprehensive security protections enabled by default:

**Critical Security:**
- **Permission prompts**: Agent asks for permission before executing commands or modifying files (like Claude Code)
- **Sensitive file protection**: Blocks access to `.env`, credentials, API keys
- **File size limits**: Prevents OOM and context explosions with configurable size limits (500KB default)
- **Binary file detection**: Blocks reading non-text files
- **Critical file warnings**: Warns when modifying infrastructure files (package.json, Dockerfile, etc.)
- **Read-only mode**: Optional mode that prevents all modifications
- **Command timeout**: 30-second timeout on shell commands
- **Pattern-based blocking**: Blocks dangerous command patterns (`> /dev/`, `--force`, etc.)
- **Write boundary protection**: Requires permission for write operations

**Operational Safety:**
- **Operation audit logging**: All file operations and commands logged to `~/.patchpal/<repo-name>/audit.log` (enabled by default)
  - Includes user prompts to show what triggered each operation
  - Rotates at 10 MB with 3 backups (40 MB total max)
- **Command history**: User commands saved to `~/.patchpal/<repo-name>/history.txt` (last 1000 commands)
  - Clean, user-friendly format for reviewing past interactions
- **Automatic backups**: Optional auto-backup of files to `~/.patchpal/<repo-name>/backups/` before modification
- **Resource limits**: Configurable operation counter prevents infinite loops (10000 operations default)
- **Git state awareness**: Warns when modifying files with uncommitted changes

See the [Configuration](https://github.com/wiseprobe/patchpal?tab=readme-ov-file#configuration) section for all available `PATCHPAL_*` environment variables to customize security, permissions, logging, and more.

**Permission System:**

When the agent wants to execute a command or modify a file, you'll see a prompt like:

```
================================================================================
Run Shell
--------------------------------------------------------------------------------
   pytest tests/test_cli.py -v
--------------------------------------------------------------------------------

Do you want to proceed?
  1. Yes
  2. Yes, and don't ask again this session for 'pytest'
  3. No, and tell me what to do differently

Choice [1-3]:
```

- Option 1: Allow this one operation
- Option 2: Allow for the rest of this session (like Claude Code - resets when you restart PatchPal)
- Option 3: Cancel the operation

**Advanced:** You can manually edit `~/.patchpal/<repo-name>/permissions.json` to grant persistent permissions across sessions.

**Example permissions.json:**

```json
{
  "run_shell": ["pytest", "npm", "git"],
  "apply_patch": true,
  "edit_file": ["config.py", "settings.json"]
}
```

Format:
- `"tool_name": true` - Grant all operations for this tool (no more prompts)
- `"tool_name": ["pattern1", "pattern2"]` - Grant only specific patterns (e.g., specific commands or file names)

<!--**Test coverage:** 131 tests including 38 dedicated security tests and 11 skills tests-->
