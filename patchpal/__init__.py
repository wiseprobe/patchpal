"""PatchPal - An open-source Claude Code clone implemented purely in Python."""

__version__ = "0.1.0"

from patchpal.tools import read_file, list_files, apply_patch, run_shell, grep_code, web_search, web_fetch
from patchpal.agent import create_agent

__all__ = [
    "read_file",
    "list_files",
    "grep_code",
    "web_search",
    "web_fetch",
    "apply_patch",
    "run_shell",
    "create_agent",
]
