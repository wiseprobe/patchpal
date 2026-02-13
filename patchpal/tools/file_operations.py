"""File operation tools (read, list, get info, find, tree)."""

import mimetypes
import os
from pathlib import Path
from typing import Optional

from patchpal.tools import common
from patchpal.tools.common import (
    MAX_FILE_SIZE,
    _check_path,
    _is_binary_file,
    _is_inside_repo,
    _operation_limiter,
    audit_logger,
    extract_text_from_docx,
    extract_text_from_pdf,
    extract_text_from_pptx,
    require_permission_for_read,
)


@require_permission_for_read(
    "read_file", get_description=lambda path: f"   Read: {path}", get_pattern=lambda path: path
)
def read_file(path: str) -> str:
    """
    Read the contents of a file.

    Supports text files and documents (PDF, DOCX, PPTX) with automatic text extraction.

    Args:
        path: Path to the file (relative to repository root or absolute)

    Returns:
        The file contents as a string (text extracted from documents)

    Raises:
        ValueError: If file is too large, unsupported binary format, or sensitive
    """
    _operation_limiter.check_limit(f"read_file({path})")

    p = _check_path(path)

    # Get file size and MIME type
    size = p.stat().st_size
    mime_type, _ = mimetypes.guess_type(str(p))
    ext = p.suffix.lower()

    # For document formats (PDF/DOCX/PPTX), extract text first, then check extracted size
    # This allows large binary documents as long as the extracted text fits in context
    # Check both MIME type and extension (Windows doesn't always recognize Office formats)
    if (mime_type and "pdf" in mime_type) or ext == ".pdf":
        # Extract text from PDF (no size check on binary - check extracted text instead)
        content_bytes = p.read_bytes()
        text_content = extract_text_from_pdf(content_bytes, source=str(path))
        audit_logger.info(
            f"READ: {path} ({size} bytes binary, {len(text_content)} chars text, PDF)"
        )
        return text_content
    elif (mime_type and ("wordprocessingml" in mime_type or "msword" in mime_type)) or ext in (
        ".docx",
        ".doc",
    ):
        # Extract text from DOCX/DOC
        content_bytes = p.read_bytes()
        text_content = extract_text_from_docx(content_bytes, source=str(path))
        audit_logger.info(
            f"READ: {path} ({size} bytes binary, {len(text_content)} chars text, DOCX)"
        )
        return text_content
    elif (mime_type and ("presentationml" in mime_type or "ms-powerpoint" in mime_type)) or ext in (
        ".pptx",
        ".ppt",
    ):
        # Extract text from PPTX/PPT
        content_bytes = p.read_bytes()
        text_content = extract_text_from_pptx(content_bytes, source=str(path))
        audit_logger.info(
            f"READ: {path} ({size} bytes binary, {len(text_content)} chars text, PPTX)"
        )
        return text_content

    # For non-document files, check size before reading
    if size > MAX_FILE_SIZE:
        raise ValueError(
            f"File too large: {size:,} bytes (max {MAX_FILE_SIZE:,} bytes)\n"
            f"Set PATCHPAL_MAX_FILE_SIZE env var to increase"
        )

    # Check if binary (for non-document files)
    if _is_binary_file(p):
        raise ValueError(
            f"Cannot read binary file: {path}\nType: {mime_type or 'unknown'}\n"
            f"Supported document formats: PDF, DOCX, PPTX"
        )

    # Read as text file
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

    Tip:
        Use count_lines(path) first to find total line count for reading from end
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
    "count_lines",
    get_description=lambda path: f"   Count lines: {path}",
    get_pattern=lambda path: path,
)
def count_lines(path: str) -> str:
    """
    Count the number of lines in a file efficiently.

    Args:
        path: Path to the file (relative to repository root or absolute)

    Returns:
        String containing line count and file info

    Raises:
        ValueError: If file not found, binary, or sensitive

    Examples:
        count_lines("logs/app.log")  # Returns: "logs/app.log: 15,234 lines (2.3MB)"

    Use case:
        Get total line count before using read_lines() to read last N lines:
        total = count_lines("big.log")  # "50000 lines"
        read_lines("big.log", 49900, 50000)  # Read last 100 lines
    """
    _operation_limiter.check_limit(f"count_lines({path})")

    p = _check_path(path)

    # Check if binary
    if _is_binary_file(p):
        raise ValueError(
            f"Cannot count lines in binary file: {path}\nType: {mimetypes.guess_type(str(p))[0] or 'unknown'}"
        )

    # Efficiently count lines without loading entire file into memory
    # Uses buffered reading for large files
    size = p.stat().st_size
    line_count = 0

    try:
        with open(p, "rb") as f:
            # Read in chunks for efficiency
            buf_size = 1024 * 1024  # 1MB buffer
            read_f = f.raw.read if hasattr(f, "raw") else f.read

            buf = read_f(buf_size)
            while buf:
                line_count += buf.count(b"\n")
                buf = read_f(buf_size)

        # Format size
        if size < 1024:
            size_str = f"{size}B"
        elif size < 1024 * 1024:
            size_str = f"{size / 1024:.1f}KB"
        else:
            size_str = f"{size / (1024 * 1024):.1f}MB"

        audit_logger.info(f"COUNT_LINES: {path} - {line_count:,} lines")
        return f"{path}: {line_count:,} lines ({size_str})"

    except Exception as e:
        raise ValueError(f"Error counting lines in {path}: {e}")


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
    for p in common.REPO_ROOT.rglob("*"):
        if not p.is_file():
            continue

        # Skip hidden files
        if any(part.startswith(".") for part in p.parts):
            continue

        # Skip binary files (optional - can be slow on large repos)
        # if _is_binary_file(p):
        #     continue

        files.append(str(p.relative_to(common.REPO_ROOT)))

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
            matches = list(common.REPO_ROOT.glob(path))
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
                relative_path = file_path.relative_to(common.REPO_ROOT)
            except ValueError:
                # Can't compute relative path (e.g., Windows short name mismatch)
                # Try to compute it manually by resolving both paths
                try:
                    resolved_file = file_path.resolve()
                    resolved_repo = common.REPO_ROOT.resolve()
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
                relative_path = file_path.relative_to(common.REPO_ROOT)
            except Exception:
                try:
                    resolved_file = file_path.resolve()
                    resolved_repo = common.REPO_ROOT.resolve()
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
            matches = list(common.REPO_ROOT.glob(pattern))
        else:
            # Case-insensitive: just do case-insensitive glob matching
            import fnmatch

            matches = []
            for file_path in common.REPO_ROOT.rglob("*"):
                if file_path.is_file():
                    # Skip hidden files
                    relative_path = file_path.relative_to(common.REPO_ROOT)
                    if any(part.startswith(".") for part in relative_path.parts):
                        continue
                    # Check if matches pattern (case-insensitive)
                    if fnmatch.fnmatch(str(relative_path).lower(), pattern.lower()):
                        matches.append(file_path)

        # Filter to only files (not directories) and exclude hidden
        files = []
        for match in matches:
            if match.is_file():
                relative_path = match.relative_to(common.REPO_ROOT)
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
        start_path = (common.REPO_ROOT / expanded_path).resolve()

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
                start_path.relative_to(common.REPO_ROOT)
                if start_path != common.REPO_ROOT
                else Path(".")
            )
        else:
            display_path = start_path

        result = [str(display_path) + "/"]
        result.extend(_build_tree(start_path))

        audit_logger.info(f"TREE: {path} (depth={max_depth})")
        return "\n".join(result)

    except Exception as e:
        raise ValueError(f"Error generating tree: {e}")
