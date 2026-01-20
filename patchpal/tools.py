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
if platform.system() == "Windows":
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
        """Reset operation counter."""
        self.operations = 0


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

    # Check MIME type first
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type and not mime_type.startswith("text/"):
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
    return str(path).startswith(str(REPO_ROOT))


def _check_path(path: str, must_exist: bool = True) -> Path:
    """
    Validate and resolve a path.

    Args:
        path: Path to validate (relative or absolute)
        must_exist: Whether the file must exist

    Returns:
        Resolved Path object

    Raises:
        ValueError: If path validation fails

    Note:
        Can access files anywhere on the system (repository or outside).
        Sensitive files (.env, credentials) are always blocked for safety.
    """
    # Resolve path (handle both absolute and relative paths)
    path_obj = Path(path)
    if path_obj.is_absolute():
        p = path_obj.resolve()
    else:
        p = (REPO_ROOT / path).resolve()

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

    # Resolve path (handle both absolute and relative paths)
    path_obj = Path(path)
    if path_obj.is_absolute():
        start_path = path_obj.resolve()
    else:
        start_path = (REPO_ROOT / path).resolve()

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

    # Add warning if writing outside repository
    outside_repo_warning = ""
    if not _is_inside_repo(p):
        outside_repo_warning = "\n   ⚠️  WARNING: Writing file outside repository\n"

    description = f"   ● {operation}({path}){outside_repo_warning}\n{diff_display}"

    if not permission_manager.request_permission("apply_patch", description, pattern=path):
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
    Edit a file by replacing an exact string match.

    Args:
        path: Relative path to the file from the repository root
        old_string: The exact string to find and replace
        new_string: The string to replace it with

    Returns:
        Confirmation message with the changes made

    Raises:
        ValueError: If file not found, old_string not found, or multiple matches
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

    # Check for old_string
    if old_string not in content:
        raise ValueError(
            f"String not found in {path}:\n{old_string[:100]}"
            + ("..." if len(old_string) > 100 else "")
        )

    # Count occurrences
    count = content.count(old_string)
    if count > 1:
        raise ValueError(
            f"String appears {count} times in {path}. "
            f"Please provide a more specific string to ensure correct replacement.\n"
            f"First occurrence context:\n{content[max(0, content.find(old_string) - 50) : content.find(old_string) + len(old_string) + 50]}"
        )

    # Check permission before proceeding
    permission_manager = _get_permission_manager()

    # Format colored diff for permission prompt
    diff_display = _format_colored_diff(old_string, new_string, file_path=path)

    # Add warning if writing outside repository
    outside_repo_warning = ""
    if not _is_inside_repo(p):
        outside_repo_warning = "\n   ⚠️  WARNING: Writing file outside repository\n"

    description = f"   ● Update({path}){outside_repo_warning}\n{diff_display}"

    if not permission_manager.request_permission("edit_file", description, pattern=path):
        return "Operation cancelled by user."

    # Backup if enabled
    backup_path = _backup_file(p)

    # Perform replacement
    new_content = content.replace(old_string, new_string)

    # Write the new content
    p.write_text(new_content)

    # Generate diff for the specific change
    old_lines = old_string.split("\n")
    new_lines = new_string.split("\n")
    diff = difflib.unified_diff(old_lines, new_lines, fromfile="old", tofile="new", lineterm="")
    diff_str = "\n".join(diff)

    audit_logger.info(f"EDIT: {path} ({len(old_string)} -> {len(new_string)} chars)")

    backup_msg = f"\n[Backup saved: {backup_path}]" if backup_path else ""
    return f"Successfully edited {path}{backup_msg}\n\nChange:\n{diff_str}"


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
    _operation_limiter.check_limit(f"web_search({query[:30]}...)")

    # Limit max_results
    max_results = min(max_results, 10)

    try:
        # Perform search using DuckDuckGo
        with DDGS() as ddgs:
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
    pattern = cmd.split()[0] if cmd.split() else None
    if not permission_manager.request_permission("run_shell", description, pattern=pattern):
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

    return stdout + stderr
