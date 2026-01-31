"""Tools with security guardrails for safe code modification."""

import difflib
import logging
import mimetypes
import os
import platform
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

from patchpal.permissions import PermissionManager

try:
    from ddgs import DDGS
except ImportError:
    # Fall back to old package name if new one not installed
    from duckduckgo_search import DDGS

# Import version for user agent
try:
    from patchpal import __version__
except ImportError:
    __version__ = "unknown"

REPO_ROOT = Path(".").resolve()

# Platform-aware command blocking - minimal list since we have permission system
# Only block privilege escalation commands specific to each platform
# Allow sudo if explicitly enabled via environment variable
ALLOW_SUDO = os.getenv("PATCHPAL_ALLOW_SUDO", "false").lower() == "true"

if ALLOW_SUDO:
    # Sudo allowed - no command blocking
    FORBIDDEN = set()
elif platform.system() == "Windows":
    # Windows privilege escalation commands
    FORBIDDEN = {"runas", "psexec"}  # Run as different user, SysInternals elevated execution
else:
    # Unix/Linux/macOS privilege escalation commands
    FORBIDDEN = {"sudo", "su"}  # Privilege escalation

# Sensitive file patterns
SENSITIVE_PATTERNS = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "credentials.json",
    "secrets.yaml",
    "secrets.yml",
    ".aws/credentials",
    ".ssh/id_rsa",
    ".ssh/id_ed25519",
    "config/master.key",
    "config/credentials.yml.enc",
    ".npmrc",
    ".pypirc",
    "keyring.cfg",
}

# Critical files that should have warnings
CRITICAL_FILES = {
    "package.json",
    "package-lock.json",
    "pyproject.toml",
    "setup.py",
    "requirements.txt",
    "Cargo.toml",
    "Cargo.lock",
    "Dockerfile",
    "docker-compose.yml",
    "Makefile",
    ".github/workflows",
}

# Configuration
MAX_FILE_SIZE = int(os.getenv("PATCHPAL_MAX_FILE_SIZE", 10 * 1024 * 1024))  # 10MB default
READ_ONLY_MODE = os.getenv("PATCHPAL_READ_ONLY", "false").lower() == "true"
ALLOW_SENSITIVE = os.getenv("PATCHPAL_ALLOW_SENSITIVE", "false").lower() == "true"
ENABLE_AUDIT_LOG = os.getenv("PATCHPAL_AUDIT_LOG", "true").lower() == "true"
ENABLE_BACKUPS = os.getenv("PATCHPAL_ENABLE_BACKUPS", "false").lower() == "true"
MAX_OPERATIONS = int(os.getenv("PATCHPAL_MAX_OPERATIONS", 10000))

# Web request configuration
WEB_REQUEST_TIMEOUT = int(os.getenv("PATCHPAL_WEB_TIMEOUT", 30))  # 30 seconds
MAX_WEB_CONTENT_SIZE = int(
    os.getenv("PATCHPAL_MAX_WEB_SIZE", 5 * 1024 * 1024)
)  # 5MB download limit
MAX_WEB_CONTENT_CHARS = int(
    os.getenv("PATCHPAL_MAX_WEB_CHARS", 100_000)
)  # 100k chars (~25k tokens) - reduced to prevent context overflow
WEB_USER_AGENT = f"PatchPal/{__version__} (AI Code Assistant)"

# Shell command configuration
SHELL_TIMEOUT = int(os.getenv("PATCHPAL_SHELL_TIMEOUT", 30))  # 30 seconds default

# Output filtering configuration - reduce token usage from verbose commands
ENABLE_OUTPUT_FILTERING = os.getenv("PATCHPAL_FILTER_OUTPUTS", "true").lower() == "true"
MAX_OUTPUT_LINES = int(os.getenv("PATCHPAL_MAX_OUTPUT_LINES", 500))  # Max lines of output

# Global flag for requiring permission on ALL operations (including reads)
# Set via CLI flag --require-permission-for-all
_REQUIRE_PERMISSION_FOR_ALL = False


def set_require_permission_for_all(enabled: bool):
    """Set the global flag for requiring permission on all operations.

    This is called by the CLI when --require-permission-for-all is used.

    Args:
        enabled: If True, require permission for all operations including reads
    """
    global _REQUIRE_PERMISSION_FOR_ALL
    _REQUIRE_PERMISSION_FOR_ALL = enabled


def get_require_permission_for_all() -> bool:
    """Check if permission is required for all operations.

    Returns:
        True if --require-permission-for-all mode is active
    """
    return _REQUIRE_PERMISSION_FOR_ALL


# Create patchpal directory structure in home directory
# Format: ~/.patchpal/<repo-name>/
def _get_patchpal_dir() -> Path:
    """Get the patchpal directory for this repository."""
    home = Path.home()
    patchpal_root = home / ".patchpal"

    # Use repo name (last part of path) to create unique directory
    repo_name = REPO_ROOT.name
    repo_dir = patchpal_root / repo_name

    # Create directories if they don't exist
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "backups").mkdir(exist_ok=True)

    return repo_dir


PATCHPAL_DIR = _get_patchpal_dir()
BACKUP_DIR = PATCHPAL_DIR / "backups"
AUDIT_LOG_FILE = PATCHPAL_DIR / "audit.log"

# Permission manager
_permission_manager = None


def _get_permission_manager() -> PermissionManager:
    """Get or create the global permission manager."""
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager(PATCHPAL_DIR)
    return _permission_manager


# Audit logging setup with rotation
audit_logger = logging.getLogger("patchpal.audit")
if ENABLE_AUDIT_LOG and not audit_logger.handlers:
    from logging.handlers import RotatingFileHandler

    audit_logger.setLevel(logging.INFO)
    # Rotate at 10MB, keep 3 backup files (30MB total max)
    handler = RotatingFileHandler(
        AUDIT_LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=3,
    )
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    audit_logger.addHandler(handler)


# Operation counter for resource limits
class OperationLimiter:
    """Track operations to prevent abuse."""

    def __init__(self):
        self.operations = 0
        self.max_operations = MAX_OPERATIONS

    def check_limit(self, operation: str):
        """Check if operation limit has been exceeded."""
        self.operations += 1
        if self.operations > self.max_operations:
            raise ValueError(
                f"Operation limit exceeded ({self.max_operations} operations)\n"
                f"This prevents infinite loops. Increase with PATCHPAL_MAX_OPERATIONS env var."
            )
        audit_logger.info(f"Operation {self.operations}/{self.max_operations}: {operation}")

    def reset(self):
        """Reset the operation counter (used in tests)."""
        self.operations = 0


class OutputFilter:
    """Filter verbose command outputs to reduce token usage.

    This class implements Claude Code's strategy of filtering verbose outputs
    to show only relevant information (e.g., test failures, error messages).
    Can save 75% or more on output tokens for verbose commands.
    """

    @staticmethod
    def should_filter(cmd: str) -> bool:
        """Check if a command should have its output filtered.

        Args:
            cmd: The shell command

        Returns:
            True if filtering should be applied
        """
        if not ENABLE_OUTPUT_FILTERING:
            return False

        # Test runners - show only failures
        test_patterns = [
            "pytest",
            "npm test",
            "npm run test",
            "yarn test",
            "go test",
            "cargo test",
            "mvn test",
            "gradle test",
            "ruby -I test",
            "rspec",
        ]

        # Version control - limit log output
        vcs_patterns = [
            "git log",
            "git reflog",
        ]

        # Package managers - show only important info
        pkg_patterns = [
            "npm install",
            "pip install",
            "cargo build",
            "go build",
        ]

        all_patterns = test_patterns + vcs_patterns + pkg_patterns
        return any(pattern in cmd for pattern in all_patterns)

    @staticmethod
    def filter_output(cmd: str, output: str) -> str:
        """Filter command output to reduce token usage.

        Args:
            cmd: The shell command
            output: The raw command output

        Returns:
            Filtered output with only relevant information
        """
        if not output or not ENABLE_OUTPUT_FILTERING:
            return output

        lines = output.split("\n")
        original_lines = len(lines)

        # Test output - show only failures and summary
        if any(
            pattern in cmd
            for pattern in ["pytest", "npm test", "yarn test", "go test", "cargo test", "rspec"]
        ):
            filtered_lines = []
            in_failure = False
            failure_context = []

            for line in lines:
                # Capture failure indicators
                if any(
                    keyword in line.upper()
                    for keyword in ["FAIL", "ERROR", "FAILED", "✗", "✖", "FAILURE"]
                ):
                    in_failure = True
                    failure_context = [line]
                elif in_failure:
                    # Capture context after failure (up to 10 lines or until next test/blank line)
                    failure_context.append(line)
                    # End failure context on: blank line, next test case, or 10 lines
                    if (
                        not line.strip()
                        or "::" in line
                        or line.startswith("=")
                        or len(failure_context) >= 10
                    ):
                        filtered_lines.extend(failure_context)
                        in_failure = False
                        failure_context = []
                # Always capture summary lines
                elif any(
                    keyword in line.lower()
                    for keyword in ["passed", "failed", "error", "summary", "total"]
                ):
                    filtered_lines.append(line)

            # Add remaining failure context
            if failure_context:
                filtered_lines.extend(failure_context)

            # If we filtered significantly, add header
            if filtered_lines and len(filtered_lines) < original_lines * 0.5:
                header = f"[Filtered test output - showing failures only ({len(filtered_lines)}/{original_lines} lines)]"
                return header + "\n" + "\n".join(filtered_lines)
            else:
                # Not much to filter, return original but truncated if too long
                return OutputFilter._truncate_output(output, lines, original_lines)

        # Git log - limit to reasonable number of commits
        elif "git log" in cmd or "git reflog" in cmd:
            # Take first 50 lines (typically ~5-10 commits with details)
            if len(lines) > 50:
                truncated = "\n".join(lines[:50])
                footer = f"\n[Output truncated: showing first 50/{original_lines} lines. Use --max-count to limit commits]"
                return truncated + footer
            return output

        # Build/install output - show only errors and final status
        elif any(
            pattern in cmd for pattern in ["npm install", "pip install", "cargo build", "go build"]
        ):
            filtered_lines = []

            for line in lines:
                # Keep error/warning lines
                if any(
                    keyword in line.upper()
                    for keyword in ["ERROR", "WARN", "FAIL", "SUCCESSFULLY", "COMPLETE"]
                ):
                    filtered_lines.append(line)
                # Keep final summary lines
                elif any(
                    keyword in line.lower()
                    for keyword in ["installed", "built", "compiled", "finished"]
                ):
                    filtered_lines.append(line)

            if filtered_lines and len(filtered_lines) < original_lines * 0.3:
                header = f"[Filtered build output - showing errors and summary only ({len(filtered_lines)}/{original_lines} lines)]"
                return header + "\n" + "\n".join(filtered_lines)
            else:
                return OutputFilter._truncate_output(output, lines, original_lines)

        # Default: truncate if too long
        return OutputFilter._truncate_output(output, lines, original_lines)

    @staticmethod
    def _truncate_output(output: str, lines: list, original_lines: int) -> str:
        """Truncate output if it exceeds maximum lines.

        Args:
            output: Original output string
            lines: Split lines
            original_lines: Count of original lines

        Returns:
            Truncated output if necessary
        """
        if original_lines > MAX_OUTPUT_LINES:
            # Show first and last portions
            keep_start = MAX_OUTPUT_LINES // 2
            keep_end = MAX_OUTPUT_LINES // 2

            truncated_lines = (
                lines[:keep_start]
                + ["", f"... [truncated {original_lines - MAX_OUTPUT_LINES} lines] ...", ""]
                + lines[-keep_end:]
            )

            return "\n".join(truncated_lines)

        return output


# Global operation limiter
_operation_limiter = OperationLimiter()


def reset_operation_counter():
    """Reset the operation counter. Useful for testing or starting new tasks."""
    _operation_limiter.reset()


def get_operation_count() -> int:
    """Get current operation count."""
    return _operation_limiter.operations


def _format_colored_diff(
    old_text: str,
    new_text: str,
    max_lines: int = 50,
    file_path: Optional[str] = None,
    start_line: Optional[int] = None,
) -> str:
    """Format text changes with colors showing actual differences.

    Args:
        old_text: Original text
        new_text: New text
        max_lines: Maximum diff lines to show (default: 50)
        file_path: Optional file path to read full content for accurate line numbers
        start_line: Optional starting line number for context (for edit_file)

    Returns:
        Formatted string with colored unified diff with line numbers
    """
    import difflib

    # If we have a file path, read the full content to get accurate line numbers
    if file_path:
        try:
            p = Path(file_path)
            if not p.is_absolute():
                p = REPO_ROOT / file_path
            if p.exists():
                full_content = p.read_text(encoding="utf-8", errors="replace")
                # Find the position of old_text in the full file
                pos = full_content.find(old_text)
                if pos != -1:
                    # Count lines before the match to get the starting line number
                    start_line = full_content[:pos].count("\n") + 1
        except Exception:
            pass  # If reading fails, fall back to relative line numbers

    # Split into lines for diffing
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    # Use SequenceMatcher for a cleaner diff that shows true changes
    # instead of unified diff which can be confusing with context lines
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines)

    result = []
    line_count = 0
    old_line_num = start_line if start_line else 1
    new_line_num = start_line if start_line else 1

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if line_count >= max_lines:
            result.append("   \033[90m... (truncated)\033[0m")
            break

        if tag == "equal":
            # Show context lines in gray (only once, not as -/+)
            for i in range(i1, i2):
                if line_count >= max_lines:
                    break
                # Only show a few context lines at boundaries
                if i < i1 + 2 or i >= i2 - 2:
                    result.append(f"   \033[90m{old_line_num:4d}  {old_lines[i].rstrip()}\033[0m")
                    line_count += 1
                elif i == i1 + 2:
                    # Show ellipsis for skipped context
                    result.append("   \033[90m     ...\033[0m")
                    line_count += 1
                old_line_num += 1
                new_line_num += 1

        elif tag == "delete":
            # Lines only in old (removed)
            for i in range(i1, i2):
                if line_count >= max_lines:
                    break
                result.append(f"   \033[31m{old_line_num:4d} -{old_lines[i].rstrip()}\033[0m")
                old_line_num += 1
                line_count += 1

        elif tag == "insert":
            # Lines only in new (added)
            for j in range(j1, j2):
                if line_count >= max_lines:
                    break
                result.append(f"   \033[32m{new_line_num:4d} +{new_lines[j].rstrip()}\033[0m")
                new_line_num += 1
                line_count += 1

        elif tag == "replace":
            # Lines changed (show old then new)
            for i in range(i1, i2):
                if line_count >= max_lines:
                    break
                result.append(f"   \033[31m{old_line_num:4d} -{old_lines[i].rstrip()}\033[0m")
                old_line_num += 1
                line_count += 1
            for j in range(j1, j2):
                if line_count >= max_lines:
                    break
                result.append(f"   \033[32m{new_line_num:4d} +{new_lines[j].rstrip()}\033[0m")
                new_line_num += 1
                line_count += 1

    # If no diff output (identical content), show a message
    if not result:
        return "   \033[90m(no changes)\033[0m"

    return "\n".join(result)


def _check_git_status() -> dict:
    """Check git repository status."""
    try:
        # Check if we're in a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=5,
        )
        if result.returncode != 0:
            return {"is_repo": False}

        # Get status
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=5,
        )

        return {
            "is_repo": True,
            "has_uncommitted": bool(result.stdout.strip()),
            "changes": result.stdout.strip().split("\n") if result.stdout.strip() else [],
        }
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return {"is_repo": False}


def _backup_file(path: Path) -> Optional[Path]:
    """Create backup of file before modification."""
    if not ENABLE_BACKUPS or not path.exists():
        return None

    try:
        BACKUP_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Include path structure in backup name to handle same filenames
        # Handle both repo-relative and absolute paths
        if _is_inside_repo(path):
            relative = path.relative_to(REPO_ROOT)
            backup_name = f"{str(relative).replace('/', '_')}.{timestamp}"
        else:
            # For files outside repo, use absolute path in backup name
            backup_name = f"{str(path).replace('/', '_')}.{timestamp}"

        backup_path = BACKUP_DIR / backup_name

        shutil.copy2(path, backup_path)
        audit_logger.info(f"BACKUP: {path} -> {backup_path}")
        return backup_path
    except Exception as e:
        audit_logger.warning(f"BACKUP FAILED: {path} - {e}")
        return None


def _is_sensitive_file(path: Path) -> bool:
    """Check if file contains sensitive data."""
    path_str = str(path).lower()
    return any(pattern in path_str for pattern in SENSITIVE_PATTERNS)


def _is_critical_file(path: Path) -> bool:
    """Check if file is critical infrastructure."""
    path_str = str(path).lower()
    return any(pattern in path_str for pattern in CRITICAL_FILES)


def _is_binary_file(path: Path) -> bool:
    """Check if file is binary."""
    if not path.exists():
        return False

    # Text-based application MIME types that should be treated as text
    text_application_mimes = {
        "application/json",
        "application/xml",
        "application/javascript",
        "application/x-yaml",
        "application/x-sh",
        "application/x-shellscript",
        "application/x-python",
        "application/x-perl",
        "application/x-ruby",
        "application/x-php",
    }

    # Check MIME type first
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type:
        # Allow text/* and whitelisted application/* types
        if mime_type.startswith("text/") or mime_type in text_application_mimes:
            return False
        # Everything else is binary
        return True

    # Fallback: check for null bytes in first 8KB
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
            return b"\x00" in chunk
    except Exception:
        return True


def _is_inside_repo(path: Path) -> bool:
    """Check if a path is inside the repository."""
    try:
        # Use is_relative_to() for proper path comparison (available in Python 3.9+)
        # This handles case-insensitivity on Windows and symbolic links properly
        path.relative_to(REPO_ROOT)
        return True
    except ValueError:
        return False


def _get_permission_pattern_for_path(path: str, resolved_path: Path) -> str:
    """Get permission pattern for a file path (matches Claude Code's behavior).

    For paths outside the repository, uses the directory (like Claude Code shows "tmp/").
    For paths inside the repository, uses the relative path from repo root.

    Args:
        path: Original path string from user
        resolved_path: Resolved absolute path

    Returns:
        Pattern string for permission matching

    Example:
        ../../../../../tmp/test.py -> "tmp/" (directory for files outside repo)
        src/app.py -> "src/app.py" (relative path for files inside repo)
    """
    # If inside repository, use relative path from repo root
    if _is_inside_repo(resolved_path):
        try:
            relative = resolved_path.relative_to(REPO_ROOT)
            # Use forward slashes for cross-platform consistency
            return str(relative).replace("\\", "/")
        except ValueError:
            pass

    # Outside repository: use directory name (match Claude Code)
    # e.g., /tmp/test.py -> "tmp/"
    # e.g., /home/user/other/file.py -> "other/"
    parent = resolved_path.parent
    dir_name = parent.name if parent.name else str(parent)
    return f"{dir_name}/"


def require_permission_for_read(tool_name: str, get_description, get_pattern=None):
    """Decorator to optionally require permission for read operations.

    This decorator only prompts if --require-permission-for-all mode is active.

    Args:
        tool_name: Name of the tool (e.g., 'read_file')
        get_description: Function that takes tool args and returns a description string
        get_pattern: Optional function that takes tool args and returns a pattern string for session grants

    Example:
        @require_permission_for_read('read_file',
                                     get_description=lambda path: f"   Read: {path}",
                                     get_pattern=lambda path: path)
        def read_file(path: str):
            ...
    """
    from functools import wraps

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Only check permission if --require-permission-for-all is active
            if not _REQUIRE_PERMISSION_FOR_ALL:
                return func(*args, **kwargs)

            # Get the permission manager
            try:
                permission_manager = _get_permission_manager()

                # Get description and pattern
                description = get_description(*args, **kwargs)
                pattern = get_pattern(*args, **kwargs) if get_pattern else None

                # Request permission with pattern for granular session grants
                if not permission_manager.request_permission(
                    tool_name, description, pattern=pattern
                ):
                    return "Operation cancelled by user."

            except Exception as e:
                # If permission check fails, print warning but continue
                print(f"Warning: Permission check failed: {e}")

            # Execute the tool
            return func(*args, **kwargs)

        return wrapper

    return decorator


def _check_path(path: str, must_exist: bool = True) -> Path:
    """
    Validate and resolve a path.

    Args:
        path: Path to validate (relative, absolute, or with ~ for home directory)
        must_exist: Whether the file must exist

    Returns:
        Resolved Path object

    Raises:
        ValueError: If path validation fails

    Note:
        Can access files anywhere on the system (repository or outside).
        Sensitive files (.env, credentials) are always blocked for safety.
    """
    # Expand ~ for home directory first
    expanded_path = os.path.expanduser(path)

    # Resolve path (handle both absolute and relative paths)
    path_obj = Path(expanded_path)
    if path_obj.is_absolute():
        p = path_obj.resolve()
    else:
        p = (REPO_ROOT / expanded_path).resolve()

    # Check if file exists when required
    if must_exist and not p.is_file():
        raise ValueError(f"File not found: {path}")

    # Check if file is sensitive (regardless of location)
    if _is_sensitive_file(p) and not ALLOW_SENSITIVE:
        raise ValueError(
            f"Access to sensitive file blocked: {path}\n"
            f"Set PATCHPAL_ALLOW_SENSITIVE=true to override (not recommended)"
        )

    return p


@require_permission_for_read(
    "read_file", get_description=lambda path: f"   Read: {path}", get_pattern=lambda path: path
)
def read_file(path: str) -> str:
    """
    Read the contents of a file.

    Args:
        path: Path to the file (relative to repository root or absolute)

    Returns:
        The file contents as a string

    Raises:
        ValueError: If file is too large, binary, or sensitive
    """
    _operation_limiter.check_limit(f"read_file({path})")

    p = _check_path(path)

    # Check file size
    size = p.stat().st_size
    if size > MAX_FILE_SIZE:
        raise ValueError(
            f"File too large: {size:,} bytes (max {MAX_FILE_SIZE:,} bytes)\n"
            f"Set PATCHPAL_MAX_FILE_SIZE env var to increase"
        )

    # Check if binary
    if _is_binary_file(p):
        raise ValueError(
            f"Cannot read binary file: {path}\nType: {mimetypes.guess_type(str(p))[0] or 'unknown'}"
        )

    content = p.read_text(encoding="utf-8", errors="replace")
    audit_logger.info(f"READ: {path} ({size} bytes)")
    return content


@require_permission_for_read(
    "read_lines",
    get_description=lambda path,
    start_line,
    end_line=None: f"   Read lines {start_line}-{end_line or start_line}: {path}",
    get_pattern=lambda path, start_line, end_line=None: path,
)
def read_lines(path: str, start_line: int, end_line: Optional[int] = None) -> str:
    """
    Read specific lines from a file.

    Args:
        path: Path to the file (relative to repository root or absolute)
        start_line: Starting line number (1-indexed)
        end_line: Ending line number (inclusive, 1-indexed). If omitted, reads only start_line

    Returns:
        The requested lines with line numbers

    Raises:
        ValueError: If file not found, binary, sensitive, or line numbers invalid

    Examples:
        read_lines("src/auth.py", 45, 60)  # Read lines 45-60
        read_lines("src/auth.py", 45)       # Read only line 45
    """
    _operation_limiter.check_limit(f"read_lines({path}, {start_line}-{end_line or start_line})")

    # Validate line numbers
    if start_line < 1:
        raise ValueError(f"start_line must be >= 1, got {start_line}")

    if end_line is None:
        end_line = start_line
    elif end_line < start_line:
        raise ValueError(f"end_line ({end_line}) must be >= start_line ({start_line})")

    p = _check_path(path)

    # Check if binary
    if _is_binary_file(p):
        raise ValueError(
            f"Cannot read binary file: {path}\nType: {mimetypes.guess_type(str(p))[0] or 'unknown'}"
        )

    # Read file and extract lines
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        raise ValueError(f"Failed to read file: {e}")

    total_lines = len(lines)

    # Check if line numbers are within range
    if start_line > total_lines:
        raise ValueError(f"start_line {start_line} exceeds file length ({total_lines} lines)")

    # Adjust end_line if it exceeds file length
    actual_end_line = min(end_line, total_lines)

    # Extract requested lines (convert to 0-indexed)
    requested_lines = lines[start_line - 1 : actual_end_line]

    # Format output with line numbers
    result = []
    for i, line in enumerate(requested_lines, start=start_line):
        # Remove trailing newline for cleaner output
        result.append(f"{i:4d}  {line.rstrip()}")

    output = "\n".join(result)

    # Add note if we truncated end_line
    if actual_end_line < end_line:
        output += (
            f"\n\n(Note: Requested lines up to {end_line}, but file only has {total_lines} lines)"
        )

    audit_logger.info(
        f"READ_LINES: {path} lines {start_line}-{actual_end_line} ({len(requested_lines)} lines)"
    )
    return output


@require_permission_for_read(
    "list_files", get_description=lambda: "   List all files in repository"
)
def list_files() -> list[str]:
    """
    List all files in the repository.

    Returns:
        A list of relative file paths (excludes hidden and binary files)
    """
    _operation_limiter.check_limit("list_files()")

    files = []
    for p in REPO_ROOT.rglob("*"):
        if not p.is_file():
            continue

        # Skip hidden files
        if any(part.startswith(".") for part in p.parts):
            continue

        # Skip binary files (optional - can be slow on large repos)
        # if _is_binary_file(p):
        #     continue

        files.append(str(p.relative_to(REPO_ROOT)))

    audit_logger.info(f"LIST: Found {len(files)} files")
    return files


@require_permission_for_read(
    "get_file_info",
    get_description=lambda path: f"   Get info: {path}",
    get_pattern=lambda path: path,
)
def get_file_info(path: str) -> str:
    """
    Get metadata for file(s) at the specified path.

    Args:
        path: Path to file, directory, or glob pattern (e.g., "tests/*.txt")
              Can be relative to repository root or absolute

    Returns:
        Formatted string with file metadata (name, size, modified time, type)
        For multiple files, returns one line per file

    Raises:
        ValueError: If no files found
    """
    _operation_limiter.check_limit(f"get_file_info({path[:30]}...)")

    # Handle glob patterns
    if "*" in path or "?" in path:
        # It's a glob pattern
        # Use glob to find matching files
        try:
            matches = list(REPO_ROOT.glob(path))
        except Exception as e:
            raise ValueError(f"Invalid glob pattern: {e}")

        if not matches:
            return f"No files found matching pattern: {path}"

        # Filter to files only
        files = [p for p in matches if p.is_file()]
        if not files:
            return f"No files found matching pattern: {path}"
    else:
        # Single path
        p = _check_path(path, must_exist=False)

        if not p.exists():
            return f"Path does not exist: {path}"

        if p.is_file():
            files = [p]
        elif p.is_dir():
            # List all files in directory (non-recursive)
            files = [f for f in p.iterdir() if f.is_file() and not f.name.startswith(".")]
            if not files:
                return f"No files found in directory: {path}"
        else:
            return f"Path is not a file or directory: {path}"

    # Format file information
    results = []
    for file_path in sorted(files):
        try:
            stat = file_path.stat()

            # Try to get relative path; if it fails (e.g., Windows short names),
            # use the file name or absolute path
            try:
                relative_path = file_path.relative_to(REPO_ROOT)
            except ValueError:
                # Can't compute relative path (e.g., Windows short name mismatch)
                # Try to compute it manually by resolving both paths
                try:
                    resolved_file = file_path.resolve()
                    resolved_repo = REPO_ROOT.resolve()
                    relative_path = resolved_file.relative_to(resolved_repo)
                except (ValueError, OSError):
                    # Last resort: just use the file name
                    relative_path = file_path.name

            # Format size
            size = stat.st_size
            if size < 1024:
                size_str = f"{size}B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f}KB"
            else:
                size_str = f"{size / (1024 * 1024):.1f}MB"

            # Format modification time
            from datetime import datetime

            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

            # Detect file type
            if _is_binary_file(file_path):
                file_type = "binary"
            else:
                mime_type, _ = mimetypes.guess_type(str(file_path))
                file_type = mime_type or "text"

            results.append(f"{str(relative_path):<50} {size_str:>10}  {mtime}  {file_type}")

        except Exception as e:
            # Get relative path for error message (may fail if path is invalid)
            try:
                relative_path = file_path.relative_to(REPO_ROOT)
            except Exception:
                try:
                    resolved_file = file_path.resolve()
                    resolved_repo = REPO_ROOT.resolve()
                    relative_path = resolved_file.relative_to(resolved_repo)
                except Exception:
                    relative_path = file_path.name
            results.append(f"{str(relative_path):<50} ERROR: {e}")

    header = f"{'Path':<50} {'Size':>10}  {'Modified'}            {'Type'}"
    separator = "-" * 100

    output = f"{header}\n{separator}\n" + "\n".join(results)
    audit_logger.info(f"FILE_INFO: {path} - {len(files)} file(s)")
    return output


@require_permission_for_read(
    "find_files",
    get_description=lambda pattern, case_sensitive=True: f"   Find files: {pattern}",
    get_pattern=lambda pattern, case_sensitive=True: pattern,
)
def find_files(pattern: str, case_sensitive: bool = True) -> str:
    """
    Find files by name pattern (glob-style wildcards).

    Args:
        pattern: Glob pattern (e.g., '*.py', 'test_*.txt', 'src/**/*.js')
        case_sensitive: Whether to match case-sensitively (default: True)

    Returns:
        List of matching file paths, one per line

    Examples:
        find_files("*.py")           # All Python files in repo
        find_files("test_*.py")      # All test files
        find_files("**/*.md")        # All markdown files recursively
        find_files("*.TXT", False)   # All .txt files (case-insensitive)
    """
    _operation_limiter.check_limit(f"find_files({pattern})")

    try:
        # Use glob to find matching files
        if case_sensitive:
            matches = list(REPO_ROOT.glob(pattern))
        else:
            # Case-insensitive: just do case-insensitive glob matching
            import fnmatch

            matches = []
            for file_path in REPO_ROOT.rglob("*"):
                if file_path.is_file():
                    # Skip hidden files
                    relative_path = file_path.relative_to(REPO_ROOT)
                    if any(part.startswith(".") for part in relative_path.parts):
                        continue
                    # Check if matches pattern (case-insensitive)
                    if fnmatch.fnmatch(str(relative_path).lower(), pattern.lower()):
                        matches.append(file_path)

        # Filter to only files (not directories) and exclude hidden
        files = []
        for match in matches:
            if match.is_file():
                relative_path = match.relative_to(REPO_ROOT)
                # Skip hidden files/directories
                if not any(part.startswith(".") for part in relative_path.parts):
                    files.append(str(relative_path))

        if not files:
            audit_logger.info(f"FIND_FILES: {pattern} - No matches")
            return f"No files matching pattern: {pattern}"

        # Sort for consistent output
        files.sort()

        header = f"Files matching '{pattern}' ({len(files)} found):"
        separator = "-" * 100

        audit_logger.info(f"FIND_FILES: {pattern} - {len(files)} file(s)")
        return f"{header}\n{separator}\n" + "\n".join(files)

    except Exception as e:
        raise ValueError(f"Error finding files: {e}")


@require_permission_for_read(
    "tree",
    get_description=lambda path=".", max_depth=3, show_hidden=False: f"   Show tree: {path}",
    get_pattern=lambda path=".", max_depth=3, show_hidden=False: path,
)
def tree(path: str = ".", max_depth: int = 3, show_hidden: bool = False) -> str:
    """
    Show directory tree structure.

    Args:
        path: Starting directory path (relative to repo or absolute)
        max_depth: Maximum depth to traverse (default: 3, max: 10)
        show_hidden: Include hidden files/directories (default: False)

    Returns:
        Visual tree structure of the directory

    Example output:
        .
        ├── patchpal/
        │   ├── __init__.py
        │   ├── agent.py
        │   └── tools.py
        └── tests/
            ├── test_agent.py
            └── test_tools.py
    """
    _operation_limiter.check_limit(f"tree({path})")

    # Limit max_depth
    max_depth = min(max_depth, 10)

    # Expand ~ for home directory and resolve path (handle both absolute and relative paths)
    expanded_path = os.path.expanduser(path)
    path_obj = Path(expanded_path)
    if path_obj.is_absolute():
        start_path = path_obj.resolve()
    else:
        start_path = (REPO_ROOT / expanded_path).resolve()

    # Check if path exists and is a directory
    if not start_path.exists():
        raise ValueError(f"Path not found: {path}")

    if not start_path.is_dir():
        raise ValueError(f"Path is not a directory: {path}")

    def _build_tree(dir_path: Path, prefix: str = "", depth: int = 0) -> list:
        """Recursively build tree structure."""
        if depth >= max_depth:
            return []

        try:
            # Get all items in directory
            items = sorted(dir_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))

            # Filter hidden files if needed
            if not show_hidden:
                items = [item for item in items if not item.name.startswith(".")]

            lines = []
            for i, item in enumerate(items):
                is_last = i == len(items) - 1

                # Build the tree characters
                connector = "└── " if is_last else "├── "
                item_name = item.name + "/" if item.is_dir() else item.name

                lines.append(f"{prefix}{connector}{item_name}")

                # Recurse into directories
                if item.is_dir():
                    extension = "    " if is_last else "│   "
                    lines.extend(_build_tree(item, prefix + extension, depth + 1))

            return lines

        except PermissionError:
            return [f"{prefix}[Permission Denied]"]

    try:
        # Build the tree
        # Show relative path if inside repo, absolute path if outside
        if _is_inside_repo(start_path):
            display_path = (
                start_path.relative_to(REPO_ROOT) if start_path != REPO_ROOT else Path(".")
            )
        else:
            display_path = start_path

        result = [str(display_path) + "/"]
        result.extend(_build_tree(start_path))

        audit_logger.info(f"TREE: {path} (depth={max_depth})")
        return "\n".join(result)

    except Exception as e:
        raise ValueError(f"Error generating tree: {e}")


def list_skills() -> str:
    """
    List all available skills that can be invoked.

    Skills are reusable workflows stored in:
    - Personal: ~/.patchpal/skills/
    - Project: <repo>/.patchpal/skills/

    Returns:
        Formatted list of available skills with names and descriptions
    """
    _operation_limiter.check_limit("list_skills()")

    from patchpal.skills import list_skills as discover_all_skills

    skills = discover_all_skills(repo_root=REPO_ROOT)

    if not skills:
        return """No skills found.

To get started:
1. View examples: https://github.com/amaiya/patchpal/tree/main/examples/skills
2. Copy examples to your personal skills directory:
   mkdir -p ~/.patchpal/skills
   # Download and copy the commit and review skills from the examples folder
3. Or create your own skill in ~/.patchpal/skills/<skill-name>/SKILL.md

Skills are markdown files with YAML frontmatter. See the examples for the format."""

    header = f"Available Skills ({len(skills)}):"
    separator = "-" * 100

    lines = [header, separator]
    for skill in skills:
        lines.append(f"  /{skill.name}")
        lines.append(f"    {skill.description}")
        lines.append("")

    lines.append("How to invoke skills:")
    lines.append("  - User types: /skill_name (e.g., /commit)")
    lines.append("  - Or just ask naturally and the agent will discover the right skill")

    audit_logger.info(f"LIST_SKILLS: {len(skills)} skill(s)")
    return "\n".join(lines)


def use_skill(skill_name: str, args: str = "") -> str:
    """
    Invoke a skill with optional arguments.

    Args:
        skill_name: Name of the skill to invoke (without / prefix)
        args: Optional arguments to pass to the skill

    Returns:
        The skill's instructions formatted with any provided arguments

    Example:
        use_skill("commit", args="Fix bug in auth")
    """
    _operation_limiter.check_limit(f"use_skill({skill_name})")

    from patchpal.skills import get_skill

    skill = get_skill(skill_name, repo_root=REPO_ROOT)

    if not skill:
        available_skills = list_skills()
        return f"Skill not found: {skill_name}\n\n{available_skills}"

    # Format the skill instructions with arguments if provided
    instructions = skill.instructions
    if args:
        instructions = f"{instructions}\n\nArguments: {args}"

    audit_logger.info(f"USE_SKILL: {skill_name} (args={args[:50]})")

    return f"Skill: {skill.name}\n\n{instructions}"


# ============================================================================
# TODO Management System
# ============================================================================
# Session-scoped TODO list for complex multi-step tasks
# Tasks are stored in-memory and reset when a new session starts

# Session-level TODO storage (resets each session)
_session_todos: dict = {"tasks": [], "next_id": 1}


def reset_session_todos():
    """Reset the session TODO list. Called when starting a new session."""
    global _session_todos
    _session_todos = {"tasks": [], "next_id": 1}
    audit_logger.info("TODO: Session todos reset")


def _load_todos() -> dict:
    """Get the session todos."""
    return _session_todos


def _save_todos(data: dict):
    """Save todos to session storage."""
    global _session_todos
    _session_todos = data
    audit_logger.info(f"TODOS: Updated session with {len(data['tasks'])} tasks")


def todo_add(description: str, details: str = "") -> str:
    """
    Add a new task to the TODO list.

    Use this to break down complex tasks into manageable subtasks.
    Each task gets a unique ID for tracking and completion.

    Args:
        description: Brief task description (one line)
        details: Optional detailed notes about the task

    Returns:
        Confirmation with the task ID

    Example:
        todo_add("Read authentication module", details="Focus on session handling logic")
        todo_add("Add input validation to login endpoint")
    """
    _operation_limiter.check_limit(f"todo_add({description[:30]}...)")

    data = _load_todos()

    # Create new task
    task = {
        "id": data["next_id"],
        "description": description,
        "details": details,
        "completed": False,
        "created_at": datetime.now().isoformat(),
    }

    data["tasks"].append(task)
    data["next_id"] += 1

    _save_todos(data)

    result = f"✓ Added task #{task['id']}: {description}"
    if details:
        result += f"\n  Details: {details}"

    audit_logger.info(f"TODO_ADD: #{task['id']} - {description[:50]}")
    return result


def todo_list(show_completed: bool = False) -> str:
    """
    List all tasks in the TODO list.

    Args:
        show_completed: If True, show completed tasks; if False, show only pending tasks (default: False)

    Returns:
        Formatted list of tasks with IDs, status, and descriptions
    """
    _operation_limiter.check_limit("todo_list()")

    data = _load_todos()
    tasks = data["tasks"]

    if not tasks:
        return "No tasks in TODO list.\n\nUse todo_add() to create a new task plan."

    # Filter tasks based on show_completed
    if show_completed:
        display_tasks = tasks
        header = "TODO List (All Tasks):"
    else:
        display_tasks = [t for t in tasks if not t["completed"]]
        header = "TODO List (Pending Tasks):"
        if not display_tasks:
            return "No pending tasks. All tasks completed! ✓\n\nUse todo_list(show_completed=True) to see completed tasks."

    separator = "=" * 80

    lines = [header, separator]

    for task in display_tasks:
        status = "✓" if task["completed"] else "○"
        lines.append(f"\n{status} Task #{task['id']}: {task['description']}")

        if task.get("details"):
            # Indent details
            detail_lines = task["details"].split("\n")
            for line in detail_lines:
                lines.append(f"  {line}")

        # Show creation time
        try:
            created = datetime.fromisoformat(task["created_at"])
            lines.append(f"  Created: {created.strftime('%Y-%m-%d %H:%M')}")
        except Exception:
            pass

        # Show completion time if completed
        if task["completed"] and task.get("completed_at"):
            try:
                completed = datetime.fromisoformat(task["completed_at"])
                lines.append(f"  Completed: {completed.strftime('%Y-%m-%d %H:%M')}")
            except Exception:
                pass

    # Summary
    total = len(tasks)
    completed = sum(1 for t in tasks if t["completed"])
    pending = total - completed

    lines.append(f"\n{separator}")
    lines.append(f"Summary: {pending} pending, {completed} completed, {total} total")

    audit_logger.info(f"TODO_LIST: {pending} pending, {completed} completed")
    return "\n".join(lines)


def todo_complete(task_id: int) -> str:
    """
    Mark a task as completed.

    Args:
        task_id: The ID of the task to complete

    Returns:
        Confirmation message

    Example:
        todo_complete(1)  # Mark task #1 as done
    """
    _operation_limiter.check_limit(f"todo_complete({task_id})")

    data = _load_todos()

    # Find the task
    task = None
    for t in data["tasks"]:
        if t["id"] == task_id:
            task = t
            break

    if not task:
        available_ids = [t["id"] for t in data["tasks"]]
        return f"Task #{task_id} not found.\n\nAvailable task IDs: {available_ids}\n\nUse todo_list() to see all tasks."

    if task["completed"]:
        return f"Task #{task_id} is already completed: {task['description']}"

    # Mark as completed
    task["completed"] = True
    task["completed_at"] = datetime.now().isoformat()

    _save_todos(data)

    # Show progress
    total = len(data["tasks"])
    completed = sum(1 for t in data["tasks"] if t["completed"])

    result = f"✓ Completed task #{task_id}: {task['description']}"
    result += f"\n\nProgress: {completed}/{total} tasks completed"

    audit_logger.info(f"TODO_COMPLETE: #{task_id} - {task['description'][:50]}")
    return result


def todo_update(task_id: int, description: str = None, details: str = None) -> str:
    """
    Update a task's description or details.

    Args:
        task_id: The ID of the task to update
        description: New description (optional)
        details: New details (optional)

    Returns:
        Confirmation message

    Example:
        todo_update(1, description="Read auth module and session handling")
        todo_update(2, details="Need to check for SQL injection vulnerabilities")
    """
    _operation_limiter.check_limit(f"todo_update({task_id})")

    if description is None and details is None:
        return "Error: Must provide either description or details to update"

    data = _load_todos()

    # Find the task
    task = None
    for t in data["tasks"]:
        if t["id"] == task_id:
            task = t
            break

    if not task:
        available_ids = [t["id"] for t in data["tasks"]]
        return f"Task #{task_id} not found.\n\nAvailable task IDs: {available_ids}"

    # Update fields
    changes = []
    if description is not None:
        old_desc = task["description"]
        task["description"] = description
        changes.append(f"Description: '{old_desc}' → '{description}'")

    if details is not None:
        task["details"] = details
        changes.append("Details updated")

    _save_todos(data)

    result = f"✓ Updated task #{task_id}\n"
    result += "\n".join(f"  • {change}" for change in changes)

    audit_logger.info(f"TODO_UPDATE: #{task_id} - {changes}")
    return result


def todo_remove(task_id: int) -> str:
    """
    Remove a task from the TODO list.

    Args:
        task_id: The ID of the task to remove

    Returns:
        Confirmation message

    Example:
        todo_remove(1)  # Remove task #1
    """
    _operation_limiter.check_limit(f"todo_remove({task_id})")

    data = _load_todos()

    # Find and remove the task
    task = None
    for i, t in enumerate(data["tasks"]):
        if t["id"] == task_id:
            task = data["tasks"].pop(i)
            break

    if not task:
        available_ids = [t["id"] for t in data["tasks"]]
        return f"Task #{task_id} not found.\n\nAvailable task IDs: {available_ids}"

    _save_todos(data)

    result = f"✓ Removed task #{task_id}: {task['description']}"
    remaining = len(data["tasks"])
    result += f"\n\n{remaining} task(s) remaining in TODO list"

    audit_logger.info(f"TODO_REMOVE: #{task_id} - {task['description'][:50]}")
    return result


def todo_clear(completed_only: bool = True) -> str:
    """
    Clear tasks from the TODO list.

    Args:
        completed_only: If True, clear only completed tasks; if False, clear all tasks (default: True)

    Returns:
        Confirmation message

    Example:
        todo_clear()              # Clear completed tasks
        todo_clear(completed_only=False)  # Clear all tasks (start fresh)
    """
    _operation_limiter.check_limit("todo_clear()")

    data = _load_todos()

    if not data["tasks"]:
        return "TODO list is already empty."

    if completed_only:
        completed_tasks = [t for t in data["tasks"] if t["completed"]]
        if not completed_tasks:
            return "No completed tasks to clear."

        # Keep only pending tasks
        data["tasks"] = [t for t in data["tasks"] if not t["completed"]]
        count = len(completed_tasks)
        _save_todos(data)

        result = f"✓ Cleared {count} completed task(s)"
        remaining = len(data["tasks"])
        if remaining > 0:
            result += f"\n\n{remaining} pending task(s) remaining"
    else:
        # Clear all tasks
        count = len(data["tasks"])
        data["tasks"] = []
        _save_todos(data)

        result = f"✓ Cleared all {count} task(s)\n\nTODO list is now empty. Use todo_add() to create a new task plan."

    audit_logger.info(f"TODO_CLEAR: {count} task(s) cleared (completed_only={completed_only})")
    return result


# ============================================================================
# User Interaction - Ask Questions
# ============================================================================


def ask_user(question: str, options: Optional[list] = None) -> str:
    """
    Ask the user a question and wait for their response.

    This allows the agent to interactively clarify requirements, get decisions,
    or gather additional information during task execution.

    Args:
        question: The question to ask the user
        options: Optional list of predefined answer choices (e.g., ["yes", "no", "skip"])
                If provided, user can select from these or type a custom answer

    Returns:
        The user's answer as a string

    Example:
        ask_user("Which authentication method should I use?", options=["JWT", "OAuth2", "Session"])
        ask_user("Should I add error handling to all endpoints?")
    """
    _operation_limiter.check_limit(f"ask_user({question[:30]}...)")

    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt

    console = Console()

    # Format the question in a panel
    console.print()
    console.print(
        Panel(
            question,
            title="[bold cyan]Question from Agent[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    # Show options if provided
    if options:
        console.print("\n[bold]Available options:[/bold]")
        for i, option in enumerate(options, 1):
            console.print(f"  {i}. {option}")
        console.print(
            "\n[dim]You can select a number, type an option, or provide a custom answer.[/dim]\n"
        )

        # Get user input
        user_input = Prompt.ask("[bold green]Your answer[/bold green]")

        # Check if user entered a number corresponding to an option
        try:
            choice_num = int(user_input)
            if 1 <= choice_num <= len(options):
                answer = options[choice_num - 1]
                console.print(f"[dim]Selected: {answer}[/dim]\n")
            else:
                answer = user_input
        except ValueError:
            # Not a number, use as-is
            answer = user_input
    else:
        # No options, just get free-form answer
        answer = Prompt.ask("[bold green]Your answer[/bold green]")
        console.print()

    audit_logger.info(f"ASK_USER: Q: {question[:50]}... A: {answer[:50]}")
    return answer


# ============================================================================
# Edit File - Multi-Strategy String Matching
# ============================================================================
# Based on approaches from gemini-cli and OpenCode: try multiple matching
# strategies to handle # whitespace/indentation issues without requiring
# exact character-by-character matching


def _try_simple_match(content: str, old_string: str) -> Optional[str]:
    """Try exact string match."""
    if old_string in content:
        return old_string
    return None


def _try_line_trimmed_match(content: str, old_string: str) -> Optional[str]:
    """Try matching lines where content is the same when trimmed."""
    content_lines = content.split("\n")
    search_lines = old_string.split("\n")

    # Remove trailing empty line if present in search
    if search_lines and search_lines[-1] == "":
        search_lines.pop()

    # Scan through content looking for matching block
    for i in range(len(content_lines) - len(search_lines) + 1):
        matches = True
        for j, search_line in enumerate(search_lines):
            if content_lines[i + j].strip() != search_line.strip():
                matches = False
                break

        if matches:
            # Found a match - return the original lines (with indentation) joined
            matched_lines = content_lines[i : i + len(search_lines)]
            result = "\n".join(matched_lines)

            # Preserve trailing newlines if present in the matched section
            # After the matched lines, check if there's more content (indicating trailing newline)
            end_index = i + len(search_lines)
            if end_index < len(content_lines):
                # There's more content after match, so add the newline that separates them
                result += "\n"
            elif content.endswith("\n"):
                # At end of file and file ends with newline, preserve it
                result += "\n"

            return result

    return None


def _try_whitespace_normalized_match(content: str, old_string: str) -> Optional[str]:
    """Try matching with normalized whitespace (all whitespace becomes single space)."""

    def normalize(text: str) -> str:
        return " ".join(text.split())

    normalized_search = normalize(old_string)

    # Try single line matches
    for line in content.split("\n"):
        if normalize(line) == normalized_search:
            return line

    # Try multi-line matches
    search_lines = old_string.split("\n")
    if len(search_lines) > 1:
        content_lines = content.split("\n")
        for i in range(len(content_lines) - len(search_lines) + 1):
            block_lines = content_lines[i : i + len(search_lines)]
            if normalize("\n".join(block_lines)) == normalized_search:
                return "\n".join(block_lines)

    return None


def _find_match_with_strategies(content: str, old_string: str) -> Optional[str]:
    """
    Try multiple matching strategies in order.
    Returns the matched string from content (preserving original formatting).
    """
    # Strategy 1: Exact match (but only if it's not a substring that would match better with trimming)
    # Skip exact match if old_string doesn't have leading/trailing whitespace
    # and we're searching for what looks like a complete statement
    use_exact = old_string in content

    # If the old_string has no leading whitespace but contains a newline or looks like code,
    # skip exact match and try trimmed matching first
    if use_exact and not old_string.startswith((" ", "\t", "\n")):
        # Check if this looks like we're searching for a line of code
        # (contains common code patterns but no leading indentation)
        code_patterns = [
            "(",
            ")",
            "=",
            "def ",
            "class ",
            "if ",
            "for ",
            "while ",
            "return ",
            "print(",
        ]
        if any(pattern in old_string for pattern in code_patterns):
            # Try trimmed match first for code-like patterns
            match = _try_line_trimmed_match(content, old_string)
            if match:
                return match

    # Now try exact match
    match = _try_simple_match(content, old_string)
    if match:
        return match

    # Strategy 2: Line-trimmed match (handles indentation differences)
    match = _try_line_trimmed_match(content, old_string)
    if match:
        return match

    # Strategy 3: Whitespace-normalized match (handles spacing differences)
    match = _try_whitespace_normalized_match(content, old_string)
    if match:
        return match

    return None


# ============================================================================


def apply_patch(path: str, new_content: str) -> str:
    """
    Apply changes to a file by replacing its contents.

    Args:
        path: Relative path to the file from the repository root
        new_content: The new complete content for the file

    Returns:
        A confirmation message with the unified diff

    Raises:
        ValueError: If in read-only mode or file is too large
    """
    _operation_limiter.check_limit(f"apply_patch({path})")

    if READ_ONLY_MODE:
        raise ValueError(
            "Cannot modify files in read-only mode\n"
            "Set PATCHPAL_READ_ONLY=false to allow modifications"
        )

    p = _check_path(path, must_exist=False)

    # Check size of new content
    new_size = len(new_content.encode("utf-8"))
    if new_size > MAX_FILE_SIZE:
        raise ValueError(f"New content too large: {new_size:,} bytes (max {MAX_FILE_SIZE:,} bytes)")

    # Read old content if file exists (needed for diff in permission prompt)
    old_content = ""
    if p.exists():
        old_content = p.read_text(encoding="utf-8", errors="replace")
        old = old_content.splitlines(keepends=True)
    else:
        old = []

    # Check permission with colored diff
    permission_manager = _get_permission_manager()
    operation = "Create" if not p.exists() else "Update"
    diff_display = _format_colored_diff(old_content, new_content, file_path=path)

    # Get permission pattern (directory for outside repo, relative path for inside)
    permission_pattern = _get_permission_pattern_for_path(path, p)

    # Add warning if writing outside repository
    outside_repo_warning = ""
    if not _is_inside_repo(p):
        outside_repo_warning = "\n   ⚠️  WARNING: Writing file outside repository\n"

    description = f"   ● {operation}({path}){outside_repo_warning}\n{diff_display}"

    if not permission_manager.request_permission(
        "apply_patch", description, pattern=permission_pattern
    ):
        return "Operation cancelled by user."

    # Check git status for uncommitted changes (only for files inside repo)
    git_status = _check_git_status()
    git_warning = ""
    if _is_inside_repo(p) and git_status.get("is_repo") and git_status.get("has_uncommitted"):
        relative_path = str(p.relative_to(REPO_ROOT))
        if any(relative_path in change for change in git_status.get("changes", [])):
            git_warning = "\n⚠️  Note: File has uncommitted changes in git\n"

    # Backup existing file
    backup_path = None
    if p.exists():
        backup_path = _backup_file(p)

    new = new_content.splitlines(keepends=True)

    # Generate diff
    diff = difflib.unified_diff(
        old,
        new,
        fromfile=f"{path} (before)",
        tofile=f"{path} (after)",
    )
    diff_str = "".join(diff)

    # Check if critical file
    warning = ""
    if _is_critical_file(p):
        warning = "\n⚠️  WARNING: Modifying critical infrastructure file!\n"

    # Write the new content
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(new_content)

    # Audit log
    audit_logger.info(
        f"WRITE: {path} ({new_size} bytes)" + (f" [BACKUP: {backup_path}]" if backup_path else "")
    )

    backup_msg = f"\n[Backup saved: {backup_path}]" if backup_path else ""

    return f"Successfully updated {path}{warning}{git_warning}{backup_msg}\n\nDiff:\n{diff_str}"


def edit_file(path: str, old_string: str, new_string: str) -> str:
    """
    Edit a file by replacing a string match with flexible whitespace handling.

    Uses multiple matching strategies to find old_string:
    1. Exact match
    2. Trimmed line match (ignores indentation differences in search)
    3. Normalized whitespace match (ignores spacing differences in search)

    Important: The flexible matching only applies to FINDING old_string.
    The new_string is used exactly as provided, so it should include proper
    indentation/formatting to match the surrounding code.

    Args:
        path: Relative path to the file from the repository root
        old_string: The string to find (whitespace can be approximate)
        new_string: The replacement string (use exact whitespace/indentation you want)

    Returns:
        Confirmation message with the changes made

    Raises:
        ValueError: If file not found, old_string not found, or multiple matches

    Example:
        # Find with flexible matching, but provide new_string with proper indent
        edit_file("test.py", "print('hello')", "    print('world')")  # 4 spaces
    """
    _operation_limiter.check_limit(f"edit_file({path[:30]}...)")

    if READ_ONLY_MODE:
        raise ValueError(
            "Cannot edit files in read-only mode\n"
            "Set PATCHPAL_READ_ONLY=false to allow modifications"
        )

    p = _check_path(path, must_exist=True)

    # Read current content
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise ValueError(f"Failed to read file: {e}")

    # Try to find a match using multiple strategies
    matched_string = _find_match_with_strategies(content, old_string)

    if not matched_string:
        # No match found with any strategy
        raise ValueError(
            f"String not found in {path}.\n\n"
            f"Searched for:\n{old_string[:200]}\n\n"
            f"💡 Tip: Use read_lines() to see exact content, or use apply_patch() for larger changes."
        )

    # Count occurrences of the matched string
    count = content.count(matched_string)
    if count > 1:
        # Show WHERE the matches are
        positions = []
        start = 0
        while True:
            pos = content.find(matched_string, start)
            if pos == -1:
                break
            line_num = content[:pos].count("\n") + 1
            positions.append(line_num)
            start = pos + 1

        raise ValueError(
            f"String appears {count} times in {path} at lines: {positions}\n"
            f"Add more context (3-5 surrounding lines) to make it unique.\n\n"
            f"💡 Tip: Use read_lines() to see the exact context, or use apply_patch() for multiple changes."
        )

    # Perform indentation adjustment and trailing newline preservation BEFORE showing diff
    # Important: Adjust indentation and preserve trailing newlines to maintain file structure
    adjusted_new_string = new_string

    # Step 1: Adjust indentation if needed
    # Get the indentation of the first line in matched_string vs new_string
    matched_lines = matched_string.split("\n")
    new_lines = new_string.split("\n")

    if matched_lines and new_lines and matched_lines[0] and new_lines[0]:
        # Get leading whitespace of first line in matched string
        matched_indent = len(matched_lines[0]) - len(matched_lines[0].lstrip())
        new_indent = len(new_lines[0]) - len(new_lines[0].lstrip())

        if matched_indent != new_indent:
            # Need to adjust indentation
            indent_diff = matched_indent - new_indent

            # Apply the indentation adjustment to all non-empty lines in new_string
            adjusted_lines = []
            for line in new_lines:
                if line.strip():  # Non-empty line
                    if indent_diff > 0:
                        # Need to add spaces
                        adjusted_lines.append((" " * indent_diff) + line)
                    else:
                        # Need to remove spaces (if possible)
                        spaces_to_remove = abs(indent_diff)
                        if line[:spaces_to_remove].strip() == "":  # All spaces
                            adjusted_lines.append(line[spaces_to_remove:])
                        else:
                            # Can't remove that many spaces, keep as-is
                            adjusted_lines.append(line)
                else:
                    # Empty line, keep as-is
                    adjusted_lines.append(line)

            adjusted_new_string = "\n".join(adjusted_lines)

    # Step 2: Preserve trailing newlines from matched_string
    if matched_string.endswith("\n") and not adjusted_new_string.endswith("\n"):
        # Matched block had trailing newline(s), preserve them
        # Count consecutive trailing newlines in matched_string
        trailing_newlines = len(matched_string) - len(matched_string.rstrip("\n"))
        adjusted_new_string = adjusted_new_string + ("\n" * trailing_newlines)

    # Check permission before proceeding (use adjusted_new_string for accurate diff display)
    permission_manager = _get_permission_manager()

    # Format colored diff for permission prompt (use adjusted_new_string so user sees what will actually be written)
    diff_display = _format_colored_diff(matched_string, adjusted_new_string, file_path=path)

    # Get permission pattern (directory for outside repo, relative path for inside)
    permission_pattern = _get_permission_pattern_for_path(path, p)

    # Add warning if writing outside repository
    outside_repo_warning = ""
    if not _is_inside_repo(p):
        outside_repo_warning = "\n   ⚠️  WARNING: Writing file outside repository\n"

    description = f"   ● Update({path}){outside_repo_warning}\n{diff_display}"

    if not permission_manager.request_permission(
        "edit_file", description, pattern=permission_pattern
    ):
        return "Operation cancelled by user."

    # Backup if enabled
    backup_path = _backup_file(p)

    new_content = content.replace(matched_string, adjusted_new_string)

    # Write the new content
    p.write_text(new_content)

    # Generate diff for the specific change (use adjusted_new_string for accurate diff)
    old_lines = matched_string.split("\n")
    new_lines = adjusted_new_string.split("\n")
    diff = difflib.unified_diff(old_lines, new_lines, fromfile="old", tofile="new", lineterm="")
    diff_str = "\n".join(diff)

    audit_logger.info(f"EDIT: {path} ({len(matched_string)} -> {len(adjusted_new_string)} chars)")

    backup_msg = f"\n[Backup saved: {backup_path}]" if backup_path else ""
    return f"Successfully edited {path}{backup_msg}\n\nChange:\n{diff_str}"


@require_permission_for_read("git_status", get_description=lambda: "   Git status")
def git_status() -> str:
    """
    Get the status of the git repository.

    Returns:
        Formatted git status output showing modified, staged, and untracked files

    Raises:
        ValueError: If not in a git repository or git command fails
    """
    _operation_limiter.check_limit("git_status()")

    try:
        # Check if we're in a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=5,
        )
        if result.returncode != 0:
            return "Not a git repository"

        # Get status with short format
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=10,
        )

        if result.returncode != 0:
            raise ValueError(f"Git status failed: {result.stderr}")

        output = result.stdout.strip()
        if not output:
            return "Git repository: No changes (working tree clean)"

        audit_logger.info("GIT_STATUS: executed")
        return f"Git status:\n{output}"

    except subprocess.TimeoutExpired:
        raise ValueError("Git status timed out")
    except FileNotFoundError:
        raise ValueError("Git command not found. Is git installed?")
    except Exception as e:
        raise ValueError(f"Git status error: {e}")


@require_permission_for_read(
    "git_diff",
    get_description=lambda path=None, staged=False: f"   Git diff{': ' + path if path else ''}",
    get_pattern=lambda path=None, staged=False: path if path else None,
)
def git_diff(path: Optional[str] = None, staged: bool = False) -> str:
    """
    Get the git diff for the repository or a specific file.

    Args:
        path: Optional path to a specific file (relative to repo root)
        staged: If True, show staged changes (--cached), else show unstaged changes

    Returns:
        Git diff output

    Raises:
        ValueError: If not in a git repository or git command fails
    """
    _operation_limiter.check_limit(f"git_diff({path or 'all'})")

    try:
        # Check if we're in a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=5,
        )
        if result.returncode != 0:
            return "Not a git repository"

        # Build git diff command
        cmd = ["git", "diff"]
        if staged:
            cmd.append("--cached")

        if path:
            # Validate path
            p = _check_path(path, must_exist=False)
            # Git operations only work on repository files
            if not _is_inside_repo(p):
                raise ValueError(
                    f"Git operations only work on repository files. Path {path} is outside the repository."
                )
            cmd.append(str(p.relative_to(REPO_ROOT)))

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, timeout=30)

        if result.returncode != 0:
            raise ValueError(f"Git diff failed: {result.stderr}")

        output = result.stdout.strip()
        if not output:
            stage_msg = "staged " if staged else ""
            path_msg = f" for {path}" if path else ""
            return f"No {stage_msg}changes{path_msg}"

        audit_logger.info(f"GIT_DIFF: {path or 'all'} (staged={staged})")
        return output

    except subprocess.TimeoutExpired:
        raise ValueError("Git diff timed out")
    except FileNotFoundError:
        raise ValueError("Git command not found. Is git installed?")
    except Exception as e:
        raise ValueError(f"Git diff error: {e}")


@require_permission_for_read(
    "git_log",
    get_description=lambda max_count=10,
    path=None: f"   Git log ({max_count} commits{': ' + path if path else ''})",
    get_pattern=lambda max_count=10, path=None: path if path else None,
)
def git_log(max_count: int = 10, path: Optional[str] = None) -> str:
    """
    Get the git commit history.

    Args:
        max_count: Maximum number of commits to show (default: 10, max: 50)
        path: Optional path to show history for a specific file

    Returns:
        Formatted git log output

    Raises:
        ValueError: If not in a git repository or git command fails
    """
    _operation_limiter.check_limit(f"git_log({max_count})")

    # Limit max_count
    max_count = min(max_count, 50)

    try:
        # Check if we're in a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=5,
        )
        if result.returncode != 0:
            return "Not a git repository"

        # Build git log command with formatting
        cmd = [
            "git",
            "log",
            f"-{max_count}",
            "--pretty=format:%h - %an, %ar : %s",
            "--abbrev-commit",
        ]

        if path:
            # Validate path
            p = _check_path(path, must_exist=False)
            # Git operations only work on repository files
            if not _is_inside_repo(p):
                raise ValueError(
                    f"Git operations only work on repository files. Path {path} is outside the repository."
                )
            cmd.append("--")
            cmd.append(str(p.relative_to(REPO_ROOT)))

        result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, timeout=30)

        if result.returncode != 0:
            raise ValueError(f"Git log failed: {result.stderr}")

        output = result.stdout.strip()
        if not output:
            return "No commits found"

        audit_logger.info(f"GIT_LOG: {max_count} commits" + (f" for {path}" if path else ""))
        return f"Recent commits:\n{output}"

    except subprocess.TimeoutExpired:
        raise ValueError("Git log timed out")
    except FileNotFoundError:
        raise ValueError("Git command not found. Is git installed?")
    except Exception as e:
        raise ValueError(f"Git log error: {e}")


@require_permission_for_read(
    "grep_code",
    get_description=lambda pattern,
    file_glob=None,
    case_sensitive=True,
    max_results=100: f"   Search code: {pattern}",
    get_pattern=lambda pattern, file_glob=None, case_sensitive=True, max_results=100: pattern,
)
def grep_code(
    pattern: str,
    file_glob: Optional[str] = None,
    case_sensitive: bool = True,
    max_results: int = 100,
) -> str:
    """
    Search for a pattern in repository files using grep.

    Args:
        pattern: Regular expression pattern to search for
        file_glob: Optional glob pattern to filter files (e.g., "*.py", "src/**/*.js")
        case_sensitive: Whether the search should be case-sensitive (default: True)
        max_results: Maximum number of results to return (default: 100)

    Returns:
        Search results in format "file:line:content" or a message if no results found

    Raises:
        ValueError: If pattern is invalid or search fails
    """
    _operation_limiter.check_limit(f"grep_code({pattern[:30]}...)")

    # Try ripgrep first (faster), fall back to grep
    use_rg = shutil.which("rg") is not None

    try:
        if use_rg:
            # Build ripgrep command
            cmd = [
                "rg",
                "--no-heading",  # Don't group by file
                "--line-number",  # Show line numbers
                "--color",
                "never",  # No color codes
                "--max-count",
                str(max_results),  # Limit results per file
            ]

            if not case_sensitive:
                cmd.append("--ignore-case")

            # Add glob pattern if provided
            if file_glob:
                cmd.extend(["--glob", file_glob])

            # Add the search pattern
            cmd.append(pattern)

        else:
            # Fall back to grep
            cmd = [
                "grep",
                "--recursive",
                "--line-number",
                "--binary-files=without-match",  # Skip binary files
            ]

            if not case_sensitive:
                cmd.append("--ignore-case")

            # Add pattern
            cmd.extend(["--regexp", pattern])

            # Add file glob if provided (grep uses --include)
            if file_glob:
                cmd.extend(["--include", file_glob])

            # Current directory (will be executed with cwd=REPO_ROOT)
            cmd.append(".")

        # Execute search from repository root
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=REPO_ROOT)

        # ripgrep/grep return exit code 1 when no matches found (not an error)
        # exit code 0 = matches found
        # exit code 1 = no matches
        # exit code 2+ = actual error

        if result.returncode > 1:
            # Actual error occurred
            raise ValueError(f"Search failed: {result.stderr or 'Unknown error'}")

        # Process output
        output = result.stdout.strip()

        if not output or result.returncode == 1:
            audit_logger.info(f"GREP: {pattern} - No matches found")
            return f"No matches found for pattern: {pattern}"

        # Count and limit results
        lines = output.split("\n")
        total_matches = len(lines)

        if total_matches > max_results:
            lines = lines[:max_results]
            output = "\n".join(lines)
            output += f"\n\n... (showing first {max_results} of {total_matches} matches)"

        audit_logger.info(f"GREP: {pattern} - Found {total_matches} matches")
        return output

    except subprocess.TimeoutExpired:
        raise ValueError(
            "Search timed out after 30 seconds\n"
            "Try narrowing your search with a file_glob parameter"
        )
    except ValueError:
        # Re-raise ValueError (from our checks above)
        raise
    except Exception as e:
        raise ValueError(f"Search error: {e}")


def web_fetch(url: str, extract_text: bool = True) -> str:
    """
    Fetch content from a URL and optionally extract readable text.

    Args:
        url: The URL to fetch
        extract_text: If True, extract readable text from HTML (default: True)

    Returns:
        The fetched content (text extracted from HTML if extract_text=True)

    Raises:
        ValueError: If request fails or content is too large
    """
    # Check permission before proceeding
    permission_manager = _get_permission_manager()
    description = f"   Fetch: {url}"
    if not permission_manager.request_permission("web_fetch", description):
        return "Operation cancelled by user."

    _operation_limiter.check_limit(f"web_fetch({url[:50]}...)")

    # Validate URL format
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")

    try:
        # Make request with timeout
        response = requests.get(
            url,
            timeout=WEB_REQUEST_TIMEOUT,
            headers={"User-Agent": WEB_USER_AGENT},
            stream=True,  # Stream to check size first
        )
        response.raise_for_status()

        # Check content size
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > MAX_WEB_CONTENT_SIZE:
            raise ValueError(
                f"Content too large: {int(content_length):,} bytes "
                f"(max {MAX_WEB_CONTENT_SIZE:,} bytes)"
            )

        # Read content with size limit
        content = b""
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > MAX_WEB_CONTENT_SIZE:
                raise ValueError(f"Content exceeds size limit ({MAX_WEB_CONTENT_SIZE:,} bytes)")

        # Decode content
        text_content = content.decode(response.encoding or "utf-8", errors="replace")

        # Extract readable text from HTML if requested
        if extract_text and "html" in response.headers.get("Content-Type", "").lower():
            soup = BeautifulSoup(text_content, "html.parser")

            # Remove script and style elements
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()

            # Get text
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text_content = "\n".join(chunk for chunk in chunks if chunk)

        # Truncate content if it exceeds character limit to prevent context window overflow
        if len(text_content) > MAX_WEB_CONTENT_CHARS:
            truncated_content = text_content[:MAX_WEB_CONTENT_CHARS]
            warning_msg = (
                f"\n\n[WARNING: Content truncated from {len(text_content):,} to "
                f"{MAX_WEB_CONTENT_CHARS:,} characters to prevent context window overflow. "
                f"Set PATCHPAL_MAX_WEB_CHARS environment variable to adjust limit.]"
            )
            audit_logger.info(
                f"WEB_FETCH: {url} ({len(text_content)} chars, truncated to {MAX_WEB_CONTENT_CHARS})"
            )
            return truncated_content + warning_msg

        audit_logger.info(f"WEB_FETCH: {url} ({len(text_content)} chars)")
        return text_content

    except requests.Timeout:
        raise ValueError(f"Request timed out after {WEB_REQUEST_TIMEOUT} seconds")
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch URL: {e}")
    except Exception as e:
        raise ValueError(f"Error processing content: {e}")


def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo and return results.

    Args:
        query: The search query
        max_results: Maximum number of results to return (default: 5, max: 10)

    Returns:
        Formatted search results with titles, URLs, and snippets

    Raises:
        ValueError: If search fails
    """
    # Check permission before proceeding
    permission_manager = _get_permission_manager()
    description = f"   Search: {query}"
    if not permission_manager.request_permission("web_search", description):
        return "Operation cancelled by user."

    _operation_limiter.check_limit(f"web_search({query[:30]}...)")

    # Limit max_results
    max_results = min(max_results, 10)

    try:
        # Determine SSL verification setting
        # Priority: PATCHPAL_VERIFY_SSL env var > SSL_CERT_FILE > REQUESTS_CA_BUNDLE > default True
        verify_ssl = os.getenv("PATCHPAL_VERIFY_SSL")
        if verify_ssl is not None:
            # User explicitly set PATCHPAL_VERIFY_SSL
            if verify_ssl.lower() in ("false", "0", "no"):
                verify = False
            elif verify_ssl.lower() in ("true", "1", "yes"):
                verify = True
            else:
                # Treat as path to CA bundle
                verify = verify_ssl
        else:
            # Use SSL_CERT_FILE or REQUESTS_CA_BUNDLE if set (for corporate environments)
            verify = os.getenv("SSL_CERT_FILE") or os.getenv("REQUESTS_CA_BUNDLE") or True

        # Perform search using DuckDuckGo
        with DDGS(verify=verify) as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

        if not results:
            audit_logger.info(f"WEB_SEARCH: {query} - No results")
            return f"No search results found for: {query}"

        # Format results
        formatted_results = [f"Search results for: {query}\n"]
        for i, result in enumerate(results, 1):
            title = result.get("title", "No title")
            url = result.get("href", "No URL")
            snippet = result.get("body", "No description")

            formatted_results.append(f"\n{i}. {title}\n   URL: {url}\n   {snippet}")

        output = "\n".join(formatted_results)
        audit_logger.info(f"WEB_SEARCH: {query} - Found {len(results)} results")
        return output

    except Exception as e:
        error_msg = str(e)

        # Provide helpful error messages for common issues
        if "CERTIFICATE_VERIFY_FAILED" in error_msg or "TLS handshake failed" in error_msg:
            return (
                "Web search unavailable: SSL certificate verification failed.\n"
                "This may be due to:\n"
                "- Corporate proxy/firewall blocking requests\n"
                "- Network configuration issues\n"
                "- VPN interference\n\n"
                "Consider using web_fetch with a specific URL if you have one."
            )
        elif "RuntimeError" in error_msg or "error sending request" in error_msg:
            return (
                "Web search unavailable: Network connection failed.\n"
                "Please check your internet connection and try again."
            )
        else:
            raise ValueError(f"Web search failed: {e}")


def _extract_shell_command_info(cmd: str) -> tuple[Optional[str], Optional[str]]:
    """Extract the meaningful command pattern and working directory from a shell command.

    Handles compound commands (&&, ||, ;, |) by identifying the primary
    command being executed and any cd commands that change the working directory.

    Args:
        cmd: The shell command string

    Returns:
        Tuple of (command_pattern, working_directory)
        - command_pattern: The primary command name (e.g., 'python')
        - working_directory: The directory if cd is used, None otherwise

    Examples:
        >>> _extract_shell_command_info("pytest tests/")
        ('pytest', None)
        >>> _extract_shell_command_info("cd /tmp && python script.py")
        ('python', '/tmp')
        >>> _extract_shell_command_info("cd src && ls -la | grep test")
        ('ls', 'src')
    """
    if not cmd or not cmd.strip():
        return None, None

    # Shell operators that indicate compound commands
    # Split by && and || first (they group tighter than ;)
    compound_operators = ["&&", "||", ";"]

    # Split by compound operators to find all sub-commands
    commands = [cmd]
    for op in compound_operators:
        new_commands = []
        for c in commands:
            # Split but keep track of which parts are commands
            parts = c.split(op)
            new_commands.extend(parts)
        commands = new_commands

    # Now also handle pipes within each command
    # Pipes are different - we want the first command in a pipe chain
    pipe_split_commands = []
    for c in commands:
        pipe_parts = c.split("|")
        # For pipes, we only care about the first command (before the pipe)
        pipe_split_commands.append(pipe_parts[0])

    commands = pipe_split_commands

    # Commands that change directory or set context (not the actual operation)
    context_commands = {"cd", "pushd", "popd"}
    setup_commands = {"export", "set", "unset", "source", "."}

    # Track if we see a cd command and what directory it goes to
    working_dir = None
    primary_command = None

    for command_part in commands:
        command_part = command_part.strip()
        if not command_part:
            continue

        tokens = command_part.split()
        if not tokens:
            continue

        first_token = tokens[0]

        # If it's a cd command, extract the target directory
        if first_token in context_commands:
            if first_token == "cd" and len(tokens) > 1:
                working_dir = tokens[1]
            continue

        # Skip setup commands
        if first_token in setup_commands:
            continue

        # This is the primary command
        if not primary_command:
            primary_command = first_token
            # If we already found the primary command, we're done
            # (don't need to look at commands after the main one)
            if working_dir is not None or first_token not in context_commands:
                break

    # If we didn't find a primary command (e.g., only "cd /tmp"), use first token
    if not primary_command:
        first_command = commands[0].strip() if commands else ""
        first_token = first_command.split()[0] if first_command.split() else None
        primary_command = first_token

    return primary_command, working_dir


def run_shell(cmd: str) -> str:
    """
    Run a safe shell command in the repository.

    Args:
        cmd: The shell command to execute

    Returns:
        Combined stdout and stderr output

    Raises:
        ValueError: If command contains forbidden operations
    """
    # Check permission before proceeding
    permission_manager = _get_permission_manager()
    description = f"   {cmd}"
    # Extract meaningful command pattern and working directory, handling compound commands
    command_name, working_dir = _extract_shell_command_info(cmd)

    # Create composite pattern: "command@directory" for cd commands, just "command" otherwise
    # Using @ separator for cross-platform compatibility (: would conflict with Windows paths like C:\temp)
    if working_dir and command_name:
        pattern = f"{command_name}@{working_dir}"
    else:
        pattern = command_name

    # Pass working_dir separately for display purposes
    if not permission_manager.request_permission(
        "run_shell", description, pattern=pattern, context=working_dir
    ):
        return "Operation cancelled by user."

    _operation_limiter.check_limit(f"run_shell({cmd[:50]}...)")

    # Basic token-based blocking
    if any(tok in FORBIDDEN for tok in cmd.split()):
        raise ValueError(
            f"Blocked dangerous command: {cmd}\nForbidden operations: {', '.join(FORBIDDEN)}"
        )

    # Additional pattern-based blocking
    dangerous_patterns = [
        "> /dev/",  # Writing to devices
        "rm -rf /",  # Recursive delete
        "| dd",  # Piping to dd
        "--force",  # Force flags often dangerous
    ]

    for pattern in dangerous_patterns:
        if pattern in cmd:
            raise ValueError(f"Blocked dangerous pattern in command: {pattern}")

    audit_logger.info(f"SHELL: {cmd}")

    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        cwd=REPO_ROOT,
        timeout=SHELL_TIMEOUT,
    )

    # Decode output with error handling for problematic characters
    # Use utf-8 on all platforms with 'replace' to handle encoding issues
    stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""

    output = stdout + stderr

    # Apply output filtering to reduce token usage
    if OutputFilter.should_filter(cmd):
        filtered_output = OutputFilter.filter_output(cmd, output)
        # Log if we filtered significantly
        original_lines = len(output.split("\n"))
        filtered_lines = len(filtered_output.split("\n"))
        if filtered_lines < original_lines * 0.5:
            audit_logger.info(
                f"SHELL_FILTER: Reduced output from {original_lines} to {filtered_lines} lines "
                f"(~{int((1 - filtered_lines / original_lines) * 100)}% reduction)"
            )
        return filtered_output

    return output
