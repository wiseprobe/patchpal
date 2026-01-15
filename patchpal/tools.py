"""Tools with security guardrails for safe code modification."""

from pathlib import Path
import subprocess
import difflib
import os
import mimetypes
import logging
import shutil
from datetime import datetime
from typing import Optional
from patchpal.permissions import PermissionManager

REPO_ROOT = Path(".").resolve()

# Command blocking
FORBIDDEN = {"rm", "mv", "sudo", "chmod", "chown", "dd", "curl", "wget"}

# Sensitive file patterns
SENSITIVE_PATTERNS = {
    '.env', '.env.local', '.env.production', '.env.development',
    'credentials.json', 'secrets.yaml', 'secrets.yml',
    '.aws/credentials', '.ssh/id_rsa', '.ssh/id_ed25519',
    'config/master.key', 'config/credentials.yml.enc',
    '.npmrc', '.pypirc', 'keyring.cfg'
}

# Critical files that should have warnings
CRITICAL_FILES = {
    'package.json', 'package-lock.json',
    'pyproject.toml', 'setup.py', 'requirements.txt',
    'Cargo.toml', 'Cargo.lock',
    'Dockerfile', 'docker-compose.yml',
    'Makefile', '.github/workflows'
}

# Configuration
MAX_FILE_SIZE = int(os.getenv('PATCHPAL_MAX_FILE_SIZE', 10 * 1024 * 1024))  # 10MB default
READ_ONLY_MODE = os.getenv('PATCHPAL_READ_ONLY', 'false').lower() == 'true'
ALLOW_SENSITIVE = os.getenv('PATCHPAL_ALLOW_SENSITIVE', 'false').lower() == 'true'
ENABLE_AUDIT_LOG = os.getenv('PATCHPAL_AUDIT_LOG', 'true').lower() == 'true'
ENABLE_BACKUPS = os.getenv('PATCHPAL_ENABLE_BACKUPS', 'false').lower() == 'true'
MAX_OPERATIONS = int(os.getenv('PATCHPAL_MAX_OPERATIONS', 1000))

# Create patchpal directory structure in home directory
# Format: ~/.patchpal/<repo-name>/
def _get_patchpal_dir() -> Path:
    """Get the patchpal directory for this repository."""
    home = Path.home()
    patchpal_root = home / '.patchpal'

    # Use repo name (last part of path) to create unique directory
    repo_name = REPO_ROOT.name
    repo_dir = patchpal_root / repo_name

    # Create directories if they don't exist
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / 'backups').mkdir(exist_ok=True)

    return repo_dir

PATCHPAL_DIR = _get_patchpal_dir()
BACKUP_DIR = PATCHPAL_DIR / 'backups'
AUDIT_LOG_FILE = PATCHPAL_DIR / 'audit.log'

# Permission manager
_permission_manager = None

def _get_permission_manager() -> PermissionManager:
    """Get or create the global permission manager."""
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager(PATCHPAL_DIR)
    return _permission_manager

# Audit logging setup
audit_logger = logging.getLogger('patchpal.audit')
if ENABLE_AUDIT_LOG and not audit_logger.handlers:
    audit_logger.setLevel(logging.INFO)
    handler = logging.FileHandler(AUDIT_LOG_FILE)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
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


def _check_git_status() -> dict:
    """Check git repository status."""
    try:
        # Check if we're in a git repo
        result = subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=5
        )
        if result.returncode != 0:
            return {'is_repo': False}

        # Get status
        result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=5
        )

        return {
            'is_repo': True,
            'has_uncommitted': bool(result.stdout.strip()),
            'changes': result.stdout.strip().split('\n') if result.stdout.strip() else []
        }
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return {'is_repo': False}


def _backup_file(path: Path) -> Optional[Path]:
    """Create backup of file before modification."""
    if not ENABLE_BACKUPS or not path.exists():
        return None

    try:
        BACKUP_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # Include path structure in backup name to handle same filenames
        relative = path.relative_to(REPO_ROOT)
        backup_name = f"{str(relative).replace('/', '_')}.{timestamp}"
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
    if mime_type and not mime_type.startswith('text/'):
        return True

    # Fallback: check for null bytes in first 8KB
    try:
        with open(path, 'rb') as f:
            chunk = f.read(8192)
            return b'\x00' in chunk
    except:
        return True


def _check_path(path: str, must_exist: bool = True) -> Path:
    """Validate and resolve a path within the repository."""
    p = (REPO_ROOT / path).resolve()

    # Check if path is within repository
    if not str(p).startswith(str(REPO_ROOT)):
        raise ValueError(f"Path outside repository: {path}")

    # Check if file exists when required
    if must_exist and not p.is_file():
        raise ValueError(f"File not found: {path}")

    # Check if file is sensitive
    if _is_sensitive_file(p) and not ALLOW_SENSITIVE:
        raise ValueError(
            f"Access to sensitive file blocked: {path}\n"
            f"Set PATCHPAL_ALLOW_SENSITIVE=true to override (not recommended)"
        )

    return p


def read_file(path: str) -> str:
    """
    Read the contents of a file in the repository.

    Args:
        path: Relative path to the file from the repository root

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
            f"Cannot read binary file: {path}\n"
            f"Type: {mimetypes.guess_type(str(p))[0] or 'unknown'}"
        )

    content = p.read_text()
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
        if any(part.startswith('.') for part in p.parts):
            continue

        # Skip binary files (optional - can be slow on large repos)
        # if _is_binary_file(p):
        #     continue

        files.append(str(p.relative_to(REPO_ROOT)))

    audit_logger.info(f"LIST: Found {len(files)} files")
    return files


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
    # Check permission before proceeding
    permission_manager = _get_permission_manager()
    description = f"   Modify file: {path}\n   New content size: {len(new_content)} bytes"
    if not permission_manager.request_permission('apply_patch', description, pattern=path):
        return "Operation cancelled by user."

    _operation_limiter.check_limit(f"apply_patch({path})")

    if READ_ONLY_MODE:
        raise ValueError(
            "Cannot modify files in read-only mode\n"
            "Set PATCHPAL_READ_ONLY=false to allow modifications"
        )

    p = _check_path(path, must_exist=False)

    # Check size of new content
    new_size = len(new_content.encode('utf-8'))
    if new_size > MAX_FILE_SIZE:
        raise ValueError(
            f"New content too large: {new_size:,} bytes (max {MAX_FILE_SIZE:,} bytes)"
        )

    # Check git status for uncommitted changes
    git_status = _check_git_status()
    git_warning = ""
    if git_status.get('is_repo') and git_status.get('has_uncommitted'):
        relative_path = str(p.relative_to(REPO_ROOT))
        if any(relative_path in change for change in git_status.get('changes', [])):
            git_warning = "\n⚠️  Note: File has uncommitted changes in git\n"

    # Backup existing file
    backup_path = None
    if p.exists():
        backup_path = _backup_file(p)

    # Read old content if file exists
    if p.exists():
        old = p.read_text().splitlines(keepends=True)
    else:
        old = []

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
    audit_logger.info(f"WRITE: {path} ({new_size} bytes)" +
                     (f" [BACKUP: {backup_path}]" if backup_path else ""))

    backup_msg = f"\n[Backup saved: {backup_path}]" if backup_path else ""

    return f"Successfully updated {path}{warning}{git_warning}{backup_msg}\n\nDiff:\n{diff_str}"


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
    if not permission_manager.request_permission('run_shell', description, pattern=pattern):
        return "Operation cancelled by user."

    _operation_limiter.check_limit(f"run_shell({cmd[:50]}...)")

    # Basic token-based blocking
    if any(tok in FORBIDDEN for tok in cmd.split()):
        raise ValueError(
            f"Blocked dangerous command: {cmd}\n"
            f"Forbidden operations: {', '.join(FORBIDDEN)}"
        )

    # Additional pattern-based blocking
    dangerous_patterns = [
        '> /dev/',  # Writing to devices
        'rm -rf /',  # Recursive delete
        '| dd',  # Piping to dd
        '--force',  # Force flags often dangerous
    ]

    for pattern in dangerous_patterns:
        if pattern in cmd:
            raise ValueError(f"Blocked dangerous pattern in command: {pattern}")

    audit_logger.info(f"SHELL: {cmd}")

    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=30,  # 30 second timeout
    )

    return result.stdout + result.stderr
