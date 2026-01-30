"""Permission management for PatchPal tool execution."""

import json
import os
from functools import wraps
from pathlib import Path
from typing import Optional


class PermissionManager:
    """Manages user permissions for tool execution."""

    def __init__(self, repo_dir: Path):
        """Initialize permission manager.

        Args:
            repo_dir: Path to the repository-specific patchpal directory
        """
        self.repo_dir = repo_dir
        self.permissions_file = repo_dir / "permissions.json"
        self.session_grants = {}  # In-memory grants for this session
        self.persistent_grants = self._load_persistent_grants()

        # Check if permissions are globally disabled
        # Using streaming mode in CLI allows permissions to work properly
        self.enabled = os.getenv("PATCHPAL_REQUIRE_PERMISSION", "true").lower() == "true"

    def _load_persistent_grants(self) -> dict:
        """Load persistent permission grants from file."""
        if self.permissions_file.exists():
            try:
                with open(self.permissions_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_persistent_grants(self):
        """Save persistent permission grants to file."""
        try:
            with open(self.permissions_file, "w") as f:
                json.dump(self.persistent_grants, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save permissions: {e}")

    def _check_existing_grant(self, tool_name: str, pattern: Optional[str] = None) -> bool:
        """Check if permission was previously granted.

        Args:
            tool_name: Name of the tool (e.g., 'run_shell', 'apply_patch')
            pattern: Optional pattern for matching (e.g., 'pytest' for pytest commands)

        Returns:
            True if permission was previously granted
        """
        # Check session grants first
        if tool_name in self.session_grants:
            if self.session_grants[tool_name] is True:  # Granted for all
                return True
            if pattern and isinstance(self.session_grants[tool_name], list):
                if pattern in self.session_grants[tool_name]:
                    return True

        # Check persistent grants
        if tool_name in self.persistent_grants:
            if self.persistent_grants[tool_name] is True:  # Granted for all
                return True
            if pattern and isinstance(self.persistent_grants[tool_name], list):
                if pattern in self.persistent_grants[tool_name]:
                    return True

        return False

    def _grant_permission(
        self, tool_name: str, persistent: bool = False, pattern: Optional[str] = None
    ):
        """Grant permission for a tool.

        Args:
            tool_name: Name of the tool
            persistent: If True, save to disk for future sessions
            pattern: Optional pattern to grant (e.g., 'pytest' for pytest commands)
        """
        if persistent:
            if pattern:
                if tool_name not in self.persistent_grants:
                    self.persistent_grants[tool_name] = []
                if isinstance(self.persistent_grants[tool_name], list):
                    if pattern not in self.persistent_grants[tool_name]:
                        self.persistent_grants[tool_name].append(pattern)
                else:
                    # Already granted for all, no need to add pattern
                    pass
            else:
                self.persistent_grants[tool_name] = True
            self._save_persistent_grants()
        else:
            if pattern:
                if tool_name not in self.session_grants:
                    self.session_grants[tool_name] = []
                if isinstance(self.session_grants[tool_name], list):
                    if pattern not in self.session_grants[tool_name]:
                        self.session_grants[tool_name].append(pattern)
            else:
                self.session_grants[tool_name] = True

    def request_permission(
        self,
        tool_name: str,
        description: str,
        pattern: Optional[str] = None,
        context: Optional[str] = None,
    ) -> bool:
        """Request permission from user to execute a tool.

        Args:
            tool_name: Name of the tool (e.g., 'run_shell', 'apply_patch')
            description: Human-readable description of what will be executed
            pattern: Optional pattern for matching (e.g., 'pytest' for pytest commands, 'python:/tmp' for python in /tmp)
            context: Optional context string for display (e.g., working directory)

        Returns:
            True if permission granted, False otherwise
        """
        # If permissions are disabled globally, always grant
        if not self.enabled:
            return True

        # Check if already granted
        if self._check_existing_grant(tool_name, pattern):
            return True

        # Display the request - use stderr to avoid Rich console capture
        import sys

        sys.stderr.write("\n" + "=" * 80 + "\n")
        sys.stderr.write(f"\033[1;33m{tool_name.replace('_', ' ').title()}\033[0m\n")
        sys.stderr.write("-" * 80 + "\n")
        sys.stderr.write(description + "\n")
        sys.stderr.write("-" * 80 + "\n")

        # Get user input
        # Get the actual repository root for display (match Claude Code's UX)
        from pathlib import Path

        repo_root = Path(".").resolve()

        sys.stderr.write("\nDo you want to proceed?\n")
        sys.stderr.write("  1. Yes\n")
        if pattern:
            # For file operations, pattern is the directory (e.g., "tmp/")
            # For shell commands, pattern is the command name (e.g., "python")
            if tool_name in ("edit_file", "apply_patch"):
                # File operation - show directory context
                if pattern.endswith("/"):
                    # Outside repo - directory pattern like "tmp/"
                    sys.stderr.write(
                        f"  2. Yes, and don't ask again this session for edits in {pattern}\n"
                    )
                else:
                    # Inside repo - file path pattern
                    sys.stderr.write(
                        f"  2. Yes, and don't ask again this session for edits to {pattern}\n"
                    )
            elif tool_name == "run_shell":
                # Shell command - show working directory context
                # Extract command name from pattern (could be "python" or "python@/tmp")
                # Using @ separator for cross-platform compatibility (: conflicts with Windows paths)
                command_name = pattern.split("@")[0] if "@" in pattern else pattern

                # Use context (working_dir) if provided, otherwise use repo_root
                display_dir = context if context else str(repo_root)

                sys.stderr.write(
                    f"  2. Yes, and don't ask again this session for '{command_name}' commands in {display_dir}\n"
                )
            else:
                # Other tools
                sys.stderr.write(f"  2. Yes, and don't ask again this session for '{pattern}'\n")
        else:
            sys.stderr.write(f"  2. Yes, and don't ask again this session for {tool_name}\n")
        sys.stderr.write("  3. No, and tell me what to do differently\n")
        sys.stderr.flush()

        while True:
            try:
                # Use input() with prompt parameter to avoid terminal issues
                # The prompt parameter ensures the prompt stays visible during editing
                choice = input("\n\033[1;36mChoice [1-3]:\033[0m ").strip()

                if choice == "1":
                    return True
                elif choice == "2":
                    # Grant session-only permission (like Claude Code)
                    self._grant_permission(tool_name, persistent=False, pattern=pattern)
                    return True
                elif choice == "3":
                    sys.stderr.write("\n\033[1;31mOperation cancelled.\033[0m\n")
                    sys.stderr.flush()
                    return False
                else:
                    sys.stderr.write("Invalid choice. Please enter 1, 2, or 3.\n")
                    sys.stderr.flush()
            except (EOFError, KeyboardInterrupt):
                sys.stderr.write("\n\033[1;31mOperation cancelled.\033[0m\n")
                sys.stderr.flush()
                return False


def require_permission(tool_name: str, get_description, get_pattern=None):
    """Decorator to require user permission before executing a tool.

    Args:
        tool_name: Name of the tool
        get_description: Function that takes tool args and returns a description string
        get_pattern: Optional function that takes tool args and returns a pattern string

    Example:
        @require_permission('run_shell',
                          get_description=lambda cmd: f"   {cmd}",
                          get_pattern=lambda cmd: cmd.split()[0] if cmd else None)
        def run_shell(command: str):
            ...
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get the permission manager from environment/global state
            # Import here to avoid circular dependency
            from pathlib import Path

            try:
                # Get patchpal directory (same logic as in tools.py and cli.py)
                repo_root = Path(".").resolve()
                home = Path.home()
                patchpal_root = home / ".patchpal"
                repo_name = repo_root.name
                repo_dir = patchpal_root / repo_name
                repo_dir.mkdir(parents=True, exist_ok=True)

                manager = PermissionManager(repo_dir)

                # Get description and pattern
                # First arg is usually 'self', but for @tool decorated functions it's the actual arg
                tool_args = args
                description = get_description(*tool_args, **kwargs)
                pattern = get_pattern(*tool_args, **kwargs) if get_pattern else None

                # Request permission
                if not manager.request_permission(tool_name, description, pattern):
                    return "Operation cancelled by user."

            except Exception as e:
                # If permission check fails, print warning but continue
                print(f"Warning: Permission check failed: {e}")

            # Execute the tool
            return func(*args, **kwargs)

        return wrapper

    return decorator
