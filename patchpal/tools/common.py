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

from patchpal.permissions import PermissionManager

try:
    from ddgs import DDGS  # noqa: F401
except ImportError:
    # Fall back to old package name if new one not installed
    pass

try:
    import pymupdf  # noqa: F401

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import docx  # noqa: F401

    PYTHON_DOCX_AVAILABLE = True
except ImportError:
    PYTHON_DOCX_AVAILABLE = False

try:
    import pptx  # noqa: F401

    PYTHON_PPTX_AVAILABLE = True
except ImportError:
    PYTHON_PPTX_AVAILABLE = False

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
# Reduced from 10MB to 500KB to prevent context window explosions
# A 3.46MB file = ~1.15M tokens which exceeds most model context limits (128K-200K)
# 500KB ≈ 166K tokens which is safe for most models
MAX_FILE_SIZE = int(os.getenv("PATCHPAL_MAX_FILE_SIZE", 500 * 1024))  # 500KB default
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
# Use browser-like User-Agent to avoid bot blocking (e.g., GitHub redirects work with browser UA)
WEB_USER_AGENT = f"Mozilla/5.0 (compatible; PatchPal/{__version__}; +AI Code Assistant)"
WEB_HEADERS = {
    "User-Agent": WEB_USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,text/plain,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

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

    # Check if file is sensitive FIRST (regardless of whether it exists)
    # This prevents attempts to read/write sensitive files
    if _is_sensitive_file(p) and not ALLOW_SENSITIVE:
        raise ValueError(
            f"Access to sensitive file blocked: {path}\n"
            f"Set PATCHPAL_ALLOW_SENSITIVE=true to override (not recommended)"
        )

    # Check if file exists when required
    if must_exist and not p.is_file():
        raise ValueError(f"File not found: {path}")

    return p
