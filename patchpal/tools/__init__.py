"""Tools package - Re-exports all tools for backward compatibility.

This package organizes tools into logical modules while maintaining backward
compatibility with the old `from patchpal.tools import func` imports.
"""

# Re-export all tools from their respective modules
from patchpal.tools.code_analysis import (
    code_structure,
)
from patchpal.tools.common import (
    ALLOW_SENSITIVE,
    AUDIT_LOG_FILE,
    BACKUP_DIR,
    ENABLE_AUDIT_LOG,
    ENABLE_BACKUPS,
    ENABLE_OUTPUT_FILTERING,
    MAX_FILE_SIZE,
    MAX_OPERATIONS,
    MAX_OUTPUT_LINES,
    MAX_TOOL_OUTPUT_CHARS,
    MAX_TOOL_OUTPUT_LINES,
    MAX_WEB_CONTENT_SIZE,
    # Directories
    PATCHPAL_DIR,
    READ_ONLY_MODE,
    # Configuration
    REPO_ROOT,
    SHELL_TIMEOUT,
    WEB_REQUEST_TIMEOUT,
    # Logging
    audit_logger,
    get_operation_count,
    get_require_permission_for_all,
    # Operation counter
    reset_operation_counter,
    # Permission functions
    set_require_permission_for_all,
)
from patchpal.tools.file_editing import (
    apply_patch,
    edit_file,
)
from patchpal.tools.file_operations import (
    count_lines,
    find_files,
    get_file_info,
    list_files,
    read_file,
    read_lines,
    tree,
)
from patchpal.tools.git_tools import (
    git_diff,
    git_log,
    git_status,
    grep,
)
from patchpal.tools.repo_map import (
    clear_repo_map_cache,
    get_repo_map,
    get_repo_map_stats,
)
from patchpal.tools.shell_tools import (
    run_shell,
)
from patchpal.tools.todo_tools import (
    reset_session_todos,
    todo_add,
    todo_clear,
    todo_complete,
    todo_list,
    todo_remove,
    todo_update,
)
from patchpal.tools.user_interaction import (
    ask_user,
    list_skills,
    use_skill,
)
from patchpal.tools.web_tools import (
    web_fetch,
    web_search,
)

__all__ = [
    # File operations
    "read_file",
    "read_lines",
    "count_lines",
    "list_files",
    "get_file_info",
    "find_files",
    "tree",
    # Code analysis
    "code_structure",
    # Repository map
    "get_repo_map",
    "get_repo_map_stats",
    "clear_repo_map_cache",
    # File editing
    "apply_patch",
    "edit_file",
    # Git tools
    "git_status",
    "git_diff",
    "git_log",
    "grep",
    # TODO tools
    "reset_session_todos",
    "todo_add",
    "todo_list",
    "todo_complete",
    "todo_update",
    "todo_remove",
    "todo_clear",
    # Web tools
    "web_fetch",
    "web_search",
    # Shell tools
    "run_shell",
    # User interaction
    "ask_user",
    "list_skills",
    "use_skill",
    # Configuration
    "REPO_ROOT",
    "MAX_FILE_SIZE",
    "MAX_TOOL_OUTPUT_LINES",
    "MAX_TOOL_OUTPUT_CHARS",
    "READ_ONLY_MODE",
    "ALLOW_SENSITIVE",
    "ENABLE_AUDIT_LOG",
    "ENABLE_BACKUPS",
    "MAX_OPERATIONS",
    "WEB_REQUEST_TIMEOUT",
    "MAX_WEB_CONTENT_SIZE",
    "SHELL_TIMEOUT",
    "ENABLE_OUTPUT_FILTERING",
    "MAX_OUTPUT_LINES",
    # Directories
    "PATCHPAL_DIR",
    "BACKUP_DIR",
    "AUDIT_LOG_FILE",
    # Logging
    "audit_logger",
    # Permission functions
    "set_require_permission_for_all",
    "get_require_permission_for_all",
    # Operation counter
    "reset_operation_counter",
    "get_operation_count",
]
