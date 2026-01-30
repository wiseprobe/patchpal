"""PatchPal - An open-source Claude Code clone implemented purely in Python."""

__version__ = "0.5.0"

from patchpal.agent import create_agent
from patchpal.tools import (
    apply_patch,
    edit_file,
    get_file_info,
    git_diff,
    git_log,
    git_status,
    grep_code,
    list_files,
    read_file,
    run_shell,
    web_fetch,
    web_search,
)

__all__ = [
    "read_file",
    "list_files",
    "get_file_info",
    "edit_file",
    "apply_patch",
    "git_status",
    "git_diff",
    "git_log",
    "grep_code",
    "web_search",
    "web_fetch",
    "run_shell",
    "create_agent",
]
