"""Tools with security guardrails for safe code modification."""

from pathlib import Path
import subprocess
import difflib
import os
import mimetypes

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

    return p.read_text()


def list_files() -> list[str]:
    """
    List all files in the repository.

    Returns:
        A list of relative file paths (excludes hidden and binary files)
    """
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

    return f"Successfully updated {path}{warning}\n\nDiff:\n{diff_str}"


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

    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        timeout=30,  # 30 second timeout
    )

    return result.stdout + result.stderr
