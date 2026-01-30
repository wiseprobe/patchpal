"""Tests for patchpal.tools module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def temp_repo(monkeypatch):
    """Create a temporary repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Resolve path to handle Windows short names (RUNNER~1) and macOS symlinks (/private)
        tmpdir_path = Path(tmpdir).resolve()

        # Create test files
        (tmpdir_path / "test.txt").write_text("Hello, World!")
        (tmpdir_path / "subdir").mkdir()
        (tmpdir_path / "subdir" / "file.py").write_text("print('test')")

        # Monkey-patch REPO_ROOT
        monkeypatch.setattr("patchpal.tools.REPO_ROOT", tmpdir_path)

        # Disable permission prompts during tests
        monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

        # Reset the cached permission manager so it picks up the new env var
        import patchpal.tools

        patchpal.tools._permission_manager = None

        # Reset operation counter before each test
        from patchpal.tools import reset_operation_counter

        reset_operation_counter()

        yield tmpdir_path


def test_read_file(temp_repo):
    """Test reading a file."""
    from patchpal.tools import read_file

    content = read_file("test.txt")
    assert content == "Hello, World!"


def test_read_file_in_subdir(temp_repo):
    """Test reading a file in a subdirectory."""
    from patchpal.tools import read_file

    content = read_file("subdir/file.py")
    assert content == "print('test')"


def test_read_file_not_found(temp_repo):
    """Test reading a non-existent file raises an error."""
    from patchpal.tools import read_file

    with pytest.raises(ValueError, match="File not found"):
        read_file("nonexistent.txt")


def test_read_lines_single_line(temp_repo):
    """Test reading a single line from a file."""
    from patchpal.tools import read_lines

    # Create a test file with multiple lines
    (temp_repo / "multiline.txt").write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5")

    result = read_lines("multiline.txt", 3)
    assert "Line 3" in result
    assert "   3  Line 3" in result
    # Should not include other lines
    assert "Line 1" not in result
    assert "Line 2" not in result
    assert "Line 4" not in result


def test_read_lines_range(temp_repo):
    """Test reading a range of lines from a file."""
    from patchpal.tools import read_lines

    (temp_repo / "multiline.txt").write_text("Line 1\nLine 2\nLine 3\nLine 4\nLine 5")

    result = read_lines("multiline.txt", 2, 4)
    assert "Line 2" in result
    assert "Line 3" in result
    assert "Line 4" in result
    # Should not include lines outside range
    assert "Line 1" not in result
    assert "Line 5" not in result
    # Check line numbers
    assert "   2  Line 2" in result
    assert "   3  Line 3" in result
    assert "   4  Line 4" in result


def test_read_lines_entire_file(temp_repo):
    """Test reading all lines when range exceeds file length."""
    from patchpal.tools import read_lines

    (temp_repo / "small.txt").write_text("Line 1\nLine 2\nLine 3")

    result = read_lines("small.txt", 1, 100)
    assert "Line 1" in result
    assert "Line 2" in result
    assert "Line 3" in result
    # Should include note about truncation
    assert "file only has 3 lines" in result


def test_read_lines_invalid_range(temp_repo):
    """Test reading with invalid line numbers."""
    from patchpal.tools import read_lines

    (temp_repo / "test.txt").write_text("Line 1\nLine 2")

    # Start line less than 1
    with pytest.raises(ValueError, match="start_line must be >= 1"):
        read_lines("test.txt", 0)

    # End line less than start line
    with pytest.raises(ValueError, match="end_line.*must be >= start_line"):
        read_lines("test.txt", 5, 2)


def test_read_lines_beyond_file_end(temp_repo):
    """Test reading starting beyond file end."""
    from patchpal.tools import read_lines

    (temp_repo / "short.txt").write_text("Line 1\nLine 2")

    with pytest.raises(ValueError, match="exceeds file length"):
        read_lines("short.txt", 10)


def test_read_lines_file_not_found(temp_repo):
    """Test read_lines with non-existent file."""
    from patchpal.tools import read_lines

    with pytest.raises(ValueError, match="File not found"):
        read_lines("nonexistent.txt", 1, 5)


def test_read_lines_binary_file(temp_repo):
    """Test read_lines rejects binary files."""
    from patchpal.tools import read_lines

    # Create a binary file
    (temp_repo / "binary.bin").write_bytes(b"\x00\x01\x02\x03")

    with pytest.raises(ValueError, match="Cannot read binary file"):
        read_lines("binary.bin", 1, 5)


def test_read_file_json(temp_repo):
    """Test reading JSON files (application/json MIME type)."""
    from patchpal.tools import read_file

    # Create a JSON file
    json_content = '{"name": "test", "value": 123}'
    (temp_repo / "test.json").write_text(json_content)

    content = read_file("test.json")
    assert content == json_content


def test_read_file_xml(temp_repo):
    """Test reading XML files (application/xml MIME type)."""
    from patchpal.tools import read_file

    # Create an XML file
    xml_content = '<?xml version="1.0"?><root><item>test</item></root>'
    (temp_repo / "test.xml").write_text(xml_content)

    content = read_file("test.xml")
    assert content == xml_content


def test_list_files(temp_repo):
    """Test listing files in the repository."""
    from patchpal.tools import list_files

    files = list_files()
    # Normalize paths to use forward slashes for cross-platform compatibility
    files_normalized = [f.replace("\\", "/") for f in files]
    assert "test.txt" in files_normalized
    assert "subdir/file.py" in files_normalized
    assert len(files) == 2  # Should only list files, not directories


def test_list_files_ignores_hidden(temp_repo):
    """Test that hidden files are ignored."""
    from patchpal.tools import list_files

    # Create a hidden file
    (temp_repo / ".hidden").write_text("secret")
    (temp_repo / ".git").mkdir()
    (temp_repo / ".git" / "config").write_text("config")

    files = list_files()
    # Normalize paths for cross-platform compatibility
    files_normalized = [f.replace("\\", "/") for f in files]
    assert ".hidden" not in files_normalized
    assert ".git/config" not in files_normalized


def test_apply_patch_existing_file(temp_repo):
    """Test applying a patch to an existing file."""
    from patchpal.tools import apply_patch

    result = apply_patch("test.txt", "New content!")
    assert "Successfully updated test.txt" in result
    assert (temp_repo / "test.txt").read_text() == "New content!"


def test_apply_patch_new_file(temp_repo):
    """Test creating a new file with apply_patch."""
    from patchpal.tools import apply_patch

    result = apply_patch("newfile.txt", "Brand new file")
    assert "Successfully updated newfile.txt" in result
    assert (temp_repo / "newfile.txt").read_text() == "Brand new file"


def test_apply_patch_in_new_subdir(temp_repo):
    """Test creating a file in a new subdirectory."""
    from patchpal.tools import apply_patch

    result = apply_patch("newdir/newfile.txt", "Content")
    assert "Successfully updated newdir/newfile.txt" in result
    assert (temp_repo / "newdir" / "newfile.txt").read_text() == "Content"


def test_apply_patch_shows_diff(temp_repo):
    """Test that apply_patch shows a diff."""
    from patchpal.tools import apply_patch

    result = apply_patch("test.txt", "Modified content")
    assert "Diff:" in result
    assert "-Hello, World!" in result
    assert "+Modified content" in result


def test_run_shell_success(temp_repo):
    """Test running a safe shell command."""
    from patchpal.tools import run_shell

    result = run_shell("echo 'Hello'")
    assert "Hello" in result


def test_run_shell_with_output(temp_repo):
    """Test running a shell command with output."""
    from patchpal.tools import run_shell

    result = run_shell("ls test.txt")
    assert "test.txt" in result


def test_run_shell_forbidden_commands(temp_repo):
    """Test that privilege escalation commands are blocked (platform-specific)."""
    import platform

    from patchpal.tools import run_shell

    # Only privilege escalation commands are blocked now (permission system handles the rest)
    if platform.system() == "Windows":
        forbidden_cmds = ["runas /user:Administrator cmd", "psexec -s cmd"]
    else:
        forbidden_cmds = ["sudo ls", "su root"]

    for cmd in forbidden_cmds:
        with pytest.raises(ValueError, match="Blocked dangerous command|Blocked command"):
            run_shell(cmd)


def test_run_shell_allow_sudo(temp_repo, monkeypatch):
    """Test that sudo can be allowed via PATCHPAL_ALLOW_SUDO."""
    import platform

    from patchpal.tools import run_shell

    # Set environment variable to allow sudo
    monkeypatch.setenv("PATCHPAL_ALLOW_SUDO", "true")

    # Need to reload the module to pick up the new environment variable
    import importlib

    import patchpal.tools

    importlib.reload(patchpal.tools)

    # Re-patch REPO_ROOT after reload
    monkeypatch.setattr("patchpal.tools.REPO_ROOT", temp_repo)

    if platform.system() != "Windows":
        # On Unix-like systems, sudo should now be allowed (will fail but not blocked)
        # We can't actually test sudo execution without root, but we can verify
        # it's not blocked by the FORBIDDEN check
        try:
            # This will fail with "sudo: a terminal is required" or similar
            # but NOT with "Blocked dangerous command"
            run_shell("sudo --version")
            # If it succeeds, that's fine too
        except ValueError as e:
            # Should not be blocked by our FORBIDDEN check
            assert "Blocked dangerous command" not in str(e)
            # Might fail for other reasons (e.g., sudo not installed in test env)
            assert "sudo" not in str(e).lower() or "not found" in str(e).lower()
    else:
        # On Windows, test runas
        try:
            run_shell("runas /?")
        except ValueError as e:
            assert "Blocked dangerous command" not in str(e)


def test_run_shell_complex_safe_command(temp_repo):
    """Test that complex but safe commands work."""
    from patchpal.tools import run_shell

    # Create a file first
    (temp_repo / "count.txt").write_text("line1\nline2\nline3")

    result = run_shell("wc -l count.txt")
    assert "3" in result or "count.txt" in result


def test_check_path_validates_existence():
    """Test that _check_path validates file existence."""
    from patchpal.tools import _check_path

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir).resolve()  # Resolve to handle symlinks (e.g., macOS /private)

        with patch("patchpal.tools.REPO_ROOT", tmpdir_path):
            # Test non-existent file with must_exist=True
            with pytest.raises(ValueError, match="File not found"):
                _check_path("nonexistent.txt", must_exist=True)

            # Test non-existent file with must_exist=False
            result = _check_path("nonexistent.txt", must_exist=False)
            assert result == tmpdir_path / "nonexistent.txt"


def test_grep_code_finds_matches(temp_repo):
    """Test that grep_code finds matches in files."""
    from patchpal.tools import grep_code

    # Create a test file with searchable content
    (temp_repo / "search.py").write_text("def hello():\n    print('Hello')\n    return True")

    result = grep_code("hello")
    assert "search.py" in result
    assert "hello" in result.lower()


def test_grep_code_case_insensitive(temp_repo):
    """Test case-insensitive search."""
    from patchpal.tools import grep_code

    (temp_repo / "case.txt").write_text("Hello World\nHELLO WORLD\nhello world")

    result = grep_code("HELLO", case_sensitive=False)
    assert "case.txt" in result
    # Should find all three lines
    assert result.count("case.txt") >= 3


def test_grep_code_with_file_glob(temp_repo):
    """Test filtering by file glob pattern."""
    from patchpal.tools import grep_code

    (temp_repo / "test.py").write_text("def test(): pass")
    (temp_repo / "test.txt").write_text("def test(): pass")

    # Search only in .py files
    result = grep_code("test", file_glob="*.py")
    assert "test.py" in result
    assert "test.txt" not in result


def test_grep_code_no_matches(temp_repo):
    """Test behavior when no matches are found."""
    from patchpal.tools import grep_code

    result = grep_code("nonexistent_pattern_xyz")
    assert "No matches found" in result


def test_grep_code_max_results(temp_repo):
    """Test that max_results limits output."""
    from patchpal.tools import grep_code

    # Create a file with many matching lines
    content = "\n".join([f"line {i} with match" for i in range(200)])
    (temp_repo / "many.txt").write_text(content)

    result = grep_code("match", max_results=50)
    # Should mention truncation
    assert "showing first 50" in result.lower() or result.count("\n") <= 55  # ~50 lines + header


def test_web_fetch_success(monkeypatch):
    """Test fetching content from a URL."""
    from unittest.mock import Mock

    from patchpal.tools import web_fetch

    # Mock requests.get
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "text/html", "Content-Length": "100"}
    mock_response.encoding = "utf-8"
    mock_response.iter_content = lambda chunk_size: [
        b"<html><body><h1>Test</h1><p>Content</p></body></html>"
    ]

    mock_get = Mock(return_value=mock_response)
    monkeypatch.setattr("patchpal.tools.requests.get", mock_get)

    # Disable permission prompts
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

    # Reset operation counter
    from patchpal.tools import reset_operation_counter

    reset_operation_counter()

    result = web_fetch("https://example.com")
    assert "Test" in result
    assert "Content" in result


def test_web_fetch_invalid_url():
    """Test that invalid URLs are rejected."""
    from patchpal.tools import reset_operation_counter, web_fetch

    reset_operation_counter()

    with pytest.raises(ValueError, match="URL must start with"):
        web_fetch("not-a-url")


def test_web_fetch_content_too_large(monkeypatch):
    """Test that large content is rejected."""
    from unittest.mock import Mock

    from patchpal.tools import web_fetch

    # Mock a response with large content
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "text/plain", "Content-Length": str(10 * 1024 * 1024)}
    mock_response.encoding = "utf-8"

    mock_get = Mock(return_value=mock_response)
    monkeypatch.setattr("patchpal.tools.requests.get", mock_get)

    # Disable permission prompts
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

    from patchpal.tools import reset_operation_counter

    reset_operation_counter()

    with pytest.raises(ValueError, match="Content too large"):
        web_fetch("https://example.com")


def test_web_search_success(monkeypatch):
    """Test web search returns results."""
    from unittest.mock import MagicMock, Mock

    from patchpal.tools import web_search

    # Mock DDGS
    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.text.return_value = [
        {"title": "Result 1", "href": "https://example.com/1", "body": "Description 1"},
        {"title": "Result 2", "href": "https://example.com/2", "body": "Description 2"},
    ]
    mock_ddgs_instance.__enter__.return_value = mock_ddgs_instance
    mock_ddgs_instance.__exit__.return_value = None

    mock_ddgs_class = Mock(return_value=mock_ddgs_instance)
    monkeypatch.setattr("patchpal.tools.DDGS", mock_ddgs_class)

    # Disable permission prompts
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

    from patchpal.tools import reset_operation_counter

    reset_operation_counter()

    result = web_search("test query")
    assert "Result 1" in result
    assert "Result 2" in result
    assert "https://example.com/1" in result
    assert "Description 1" in result


def test_web_search_no_results(monkeypatch):
    """Test web search with no results."""
    from unittest.mock import MagicMock, Mock

    from patchpal.tools import web_search

    # Mock DDGS with empty results
    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.text.return_value = []
    mock_ddgs_instance.__enter__.return_value = mock_ddgs_instance
    mock_ddgs_instance.__exit__.return_value = None

    mock_ddgs_class = Mock(return_value=mock_ddgs_instance)
    monkeypatch.setattr("patchpal.tools.DDGS", mock_ddgs_class)

    # Disable permission prompts
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

    from patchpal.tools import reset_operation_counter

    reset_operation_counter()

    result = web_search("nonexistent query")
    assert "No search results found" in result


def test_web_search_limits_results(monkeypatch):
    """Test that web search respects max_results limit."""
    from unittest.mock import MagicMock, Mock

    from patchpal.tools import web_search

    # Mock DDGS with many results
    mock_results = [
        {"title": f"Result {i}", "href": f"https://example.com/{i}", "body": f"Desc {i}"}
        for i in range(20)
    ]
    mock_ddgs_instance = MagicMock()
    mock_ddgs_instance.text.return_value = mock_results[:3]  # Should only get 3 results
    mock_ddgs_instance.__enter__.return_value = mock_ddgs_instance
    mock_ddgs_instance.__exit__.return_value = None

    mock_ddgs_class = Mock(return_value=mock_ddgs_instance)
    monkeypatch.setattr("patchpal.tools.DDGS", mock_ddgs_class)

    # Disable permission prompts
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

    from patchpal.tools import reset_operation_counter

    reset_operation_counter()

    web_search("test", max_results=3)
    # Should call with max_results=3
    mock_ddgs_instance.text.assert_called_once_with("test", max_results=3)


def test_get_file_info_single_file(temp_repo):
    """Test getting info for a single file."""
    from patchpal.tools import get_file_info

    # Create a test file
    (temp_repo / "info_test.txt").write_text("test content")

    result = get_file_info("info_test.txt")
    assert "info_test.txt" in result
    assert "B" in result or "KB" in result  # Size should be shown
    assert "20" in result  # Year in timestamp


def test_get_file_info_directory(temp_repo):
    """Test getting info for files in a directory."""
    from patchpal.tools import get_file_info

    # Files already exist in temp_repo: test.txt and subdir/file.py
    result = get_file_info("subdir")
    assert "file.py" in result
    assert "B" in result or "KB" in result


def test_get_file_info_glob_pattern(temp_repo):
    """Test getting info with glob pattern."""
    from patchpal.tools import get_file_info

    # Create multiple Python files
    (temp_repo / "test1.py").write_text("# test 1")
    (temp_repo / "test2.py").write_text("# test 2")
    (temp_repo / "test.txt").write_text("not python")

    result = get_file_info("*.py")
    assert "test1.py" in result
    assert "test2.py" in result
    assert "test.txt" not in result  # Should not match .txt files


def test_get_file_info_nonexistent(temp_repo):
    """Test getting info for nonexistent file."""
    from patchpal.tools import get_file_info

    result = get_file_info("nonexistent.txt")
    assert "does not exist" in result.lower()


def test_get_file_info_no_matches(temp_repo):
    """Test getting info with pattern that matches nothing."""
    from patchpal.tools import get_file_info

    result = get_file_info("*.xyz")
    assert "No files found" in result


def test_edit_file_success(temp_repo):
    """Test successfully editing a file."""
    from patchpal.tools import edit_file

    # Create a test file
    (temp_repo / "edit_test.txt").write_text("Hello World\nThis is a test\nGoodbye World")

    result = edit_file("edit_test.txt", "This is a test", "This is EDITED")
    assert "Successfully edited" in result

    # Verify the edit
    content = (temp_repo / "edit_test.txt").read_text()
    assert "This is EDITED" in content
    assert "This is a test" not in content


def test_edit_file_not_found(temp_repo):
    """Test editing with string not found."""
    from patchpal.tools import edit_file

    (temp_repo / "edit_test.txt").write_text("Hello World")

    with pytest.raises(ValueError, match="String not found"):
        edit_file("edit_test.txt", "Nonexistent", "Replaced")


def test_edit_file_multiple_matches(temp_repo):
    """Test editing with multiple occurrences."""
    from patchpal.tools import edit_file

    (temp_repo / "edit_test.txt").write_text("test\ntest\ntest")

    with pytest.raises(ValueError, match="appears 3 times"):
        edit_file("edit_test.txt", "test", "replaced")


def test_git_status_not_a_repo(temp_repo, monkeypatch):
    """Test git_status when not in a git repo."""
    from patchpal.tools import git_status

    # Mock git command to return non-zero (not a git repo)
    def mock_run(*args, **kwargs):
        result = MagicMock()
        result.returncode = 1
        result.stderr = "not a git repository"
        return result

    monkeypatch.setattr("patchpal.tools.subprocess.run", mock_run)

    result = git_status()
    assert "Not a git repository" in result


def test_git_status_clean(temp_repo, monkeypatch):
    """Test git_status with clean working tree."""
    from patchpal.tools import git_status

    call_count = [0]

    def mock_run(cmd, *args, **kwargs):
        result = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:  # First call: check if git repo
            result.returncode = 0
        else:  # Second call: git status
            result.returncode = 0
            result.stdout = ""  # Clean working tree
        return result

    monkeypatch.setattr("patchpal.tools.subprocess.run", mock_run)

    result = git_status()
    assert "No changes" in result or "clean" in result


def test_git_diff_no_repo(temp_repo, monkeypatch):
    """Test git_diff when not in a git repo."""
    from patchpal.tools import git_diff

    def mock_run(*args, **kwargs):
        result = MagicMock()
        result.returncode = 1
        return result

    monkeypatch.setattr("patchpal.tools.subprocess.run", mock_run)

    result = git_diff()
    assert "Not a git repository" in result


def test_git_diff_no_changes(temp_repo, monkeypatch):
    """Test git_diff with no changes."""
    from patchpal.tools import git_diff

    call_count = [0]

    def mock_run(cmd, *args, **kwargs):
        result = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:  # First call: check if git repo
            result.returncode = 0
        else:  # Second call: git diff
            result.returncode = 0
            result.stdout = ""  # No changes
        return result

    monkeypatch.setattr("patchpal.tools.subprocess.run", mock_run)

    result = git_diff()
    assert "No" in result and "changes" in result


def test_git_log_not_a_repo(temp_repo, monkeypatch):
    """Test git_log when not in a git repo."""
    from patchpal.tools import git_log

    def mock_run(*args, **kwargs):
        result = MagicMock()
        result.returncode = 1
        return result

    monkeypatch.setattr("patchpal.tools.subprocess.run", mock_run)

    result = git_log()
    assert "Not a git repository" in result


def test_git_log_success(temp_repo, monkeypatch):
    """Test git_log with commits."""
    from patchpal.tools import git_log

    call_count = [0]

    def mock_run(cmd, *args, **kwargs):
        result = MagicMock()
        call_count[0] += 1
        if call_count[0] == 1:  # First call: check if git repo
            result.returncode = 0
        else:  # Second call: git log
            result.returncode = 0
            result.stdout = "abc123 - John Doe, 2 hours ago : Initial commit\ndef456 - Jane Doe, 1 day ago : Add feature"
        return result

    monkeypatch.setattr("patchpal.tools.subprocess.run", mock_run)

    result = git_log(max_count=10)
    assert "Recent commits" in result
    assert "abc123" in result
    assert "John Doe" in result


def test_web_fetch_truncation(temp_repo, monkeypatch):
    """Test that web_fetch truncates large content to prevent context window overflow."""
    import patchpal.tools
    from patchpal.tools import web_fetch

    # Disable permission requirement
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

    # Set a small character limit for testing
    original_limit = patchpal.tools.MAX_WEB_CONTENT_CHARS
    patchpal.tools.MAX_WEB_CONTENT_CHARS = 100

    try:
        # Create large content (200 chars)
        large_content = "A" * 200

        # Mock requests.get
        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "text/plain", "Content-Length": "200"}
        mock_response.encoding = "utf-8"
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(return_value=[large_content.encode("utf-8")])

        with patch("patchpal.tools.requests.get", return_value=mock_response):
            result = web_fetch("http://example.com/large.txt", extract_text=False)

            # Verify content was truncated (100 chars + "\n\n" before warning)
            truncated_part = result.split("[WARNING")[0]
            assert truncated_part.rstrip() == "A" * 100  # Content without trailing newlines
            assert "[WARNING: Content truncated" in result
            assert "200 to 100 characters" in result
            assert "PATCHPAL_MAX_WEB_CHARS" in result
    finally:
        # Restore original limit
        patchpal.tools.MAX_WEB_CONTENT_CHARS = original_limit


def test_web_fetch_no_truncation_needed(temp_repo, monkeypatch):
    """Test that web_fetch doesn't truncate when content is within limit."""
    from patchpal.tools import web_fetch

    # Disable permission requirement
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

    # Create small content
    small_content = "Hello World"

    # Mock requests.get
    mock_response = MagicMock()
    mock_response.headers = {"Content-Type": "text/plain", "Content-Length": "11"}
    mock_response.encoding = "utf-8"
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_content = MagicMock(return_value=[small_content.encode("utf-8")])

    with patch("patchpal.tools.requests.get", return_value=mock_response):
        result = web_fetch("http://example.com/small.txt", extract_text=False)

        # Verify content was not truncated
        assert result == "Hello World"


def test_find_files_simple_pattern(temp_repo):
    """Test finding files with simple pattern."""
    from patchpal.tools import find_files

    # Create test files
    (temp_repo / "test1.py").write_text("test")
    (temp_repo / "test2.py").write_text("test")
    (temp_repo / "readme.md").write_text("test")

    result = find_files("*.py")
    assert "test1.py" in result
    assert "test2.py" in result
    assert "readme.md" not in result
    assert "2 found" in result


def test_find_files_recursive_pattern(temp_repo):
    """Test finding files recursively."""
    from patchpal.tools import find_files

    # Create nested structure
    (temp_repo / "src").mkdir()
    (temp_repo / "src" / "main.py").write_text("test")
    (temp_repo / "tests").mkdir()
    (temp_repo / "tests" / "test_main.py").write_text("test")

    result = find_files("**/*.py")
    assert "src/main.py" in result or "src\\main.py" in result  # Handle Windows paths
    assert "test_main.py" in result
    # Note: temp_repo already has subdir/file.py, so 3 total
    assert "3 found" in result


def test_find_files_case_insensitive(temp_repo):
    """Test case-insensitive file finding."""
    from patchpal.tools import find_files

    (temp_repo / "README.TXT").write_text("test")
    (temp_repo / "notes.txt").write_text("test")

    result = find_files("*.txt", case_sensitive=False)
    assert "README.TXT" in result
    assert "notes.txt" in result
    # Note: temp_repo already has test.txt, so 3 total
    assert "3 found" in result


def test_find_files_no_matches(temp_repo):
    """Test find_files with no matches."""
    from patchpal.tools import find_files

    result = find_files("*.nonexistent")
    assert "No files matching pattern" in result


def test_find_files_excludes_hidden(temp_repo):
    """Test that find_files excludes hidden files."""
    from patchpal.tools import find_files

    (temp_repo / ".hidden.py").write_text("test")
    (temp_repo / "visible.py").write_text("test")
    (temp_repo / ".git").mkdir()
    (temp_repo / ".git" / "config.py").write_text("test")

    result = find_files("*.py")
    assert ".hidden.py" not in result
    assert ".git" not in result
    assert "visible.py" in result


def test_tree_basic(temp_repo):
    """Test basic tree functionality."""
    from patchpal.tools import tree

    result = tree(".")
    assert "test.txt" in result
    assert "subdir/" in result
    assert "file.py" in result
    # Check for tree characters
    assert "├──" in result or "└──" in result


def test_tree_max_depth(temp_repo):
    """Test tree respects max_depth."""
    from patchpal.tools import tree

    # Create deep directory structure
    (temp_repo / "level1").mkdir()
    (temp_repo / "level1" / "level2").mkdir()
    (temp_repo / "level1" / "level2" / "level3").mkdir()
    (temp_repo / "level1" / "level2" / "level3" / "deep.txt").write_text("test")

    result = tree(".", max_depth=2)
    assert "level1" in result
    assert "level2" in result
    # level3 should not appear due to max_depth=2
    assert "level3" not in result


def test_tree_specific_directory(temp_repo):
    """Test tree on specific directory."""
    from patchpal.tools import tree

    result = tree("subdir")
    assert "file.py" in result
    # Should not show files from parent directory
    assert "test.txt" not in result


def test_tree_hidden_files(temp_repo):
    """Test tree with show_hidden option."""
    from patchpal.tools import tree

    (temp_repo / ".hidden").write_text("test")
    (temp_repo / ".git").mkdir()
    (temp_repo / ".git" / "config").write_text("test")

    # Without show_hidden
    result_no_hidden = tree(".", show_hidden=False)
    assert ".hidden" not in result_no_hidden
    assert ".git" not in result_no_hidden

    # With show_hidden
    result_with_hidden = tree(".", show_hidden=True)
    assert ".hidden" in result_with_hidden
    assert ".git" in result_with_hidden


def test_tree_limits_max_depth_to_10(temp_repo):
    """Test that tree limits max_depth to 10."""
    from patchpal.tools import tree

    # This should not raise an error, but internally limit to 10
    result = tree(".", max_depth=100)
    # Should succeed without errors
    assert "test.txt" in result


def test_tree_nonexistent_path(temp_repo):
    """Test tree on nonexistent path."""
    from patchpal.tools import tree

    with pytest.raises(ValueError, match="not found") as exc_info:
        tree("nonexistent_directory")

    # Verify the error message doesn't contain WARNING
    assert "[WARNING" not in str(exc_info.value)


# ============================================================================
# TODO System Tests
# ============================================================================


@pytest.fixture
def todo_repo(monkeypatch, temp_repo):
    """Set up a temporary repository for TODO testing."""
    # Ensure PATCHPAL_DIR points to temp location
    todo_dir = temp_repo / ".patchpal"
    todo_dir.mkdir(exist_ok=True)
    monkeypatch.setattr("patchpal.tools.PATCHPAL_DIR", todo_dir)

    # Reset operation counter
    from patchpal.tools import reset_operation_counter, reset_session_todos

    reset_operation_counter()

    # Reset session todos for each test
    reset_session_todos()

    yield temp_repo


def test_todo_add_simple(todo_repo):
    """Test adding a simple TODO task."""
    from patchpal.tools import todo_add

    result = todo_add("Implement authentication")
    assert "✓ Added task #1" in result
    assert "Implement authentication" in result


def test_todo_add_with_details(todo_repo):
    """Test adding a TODO task with details."""
    from patchpal.tools import todo_add

    result = todo_add("Add login endpoint", details="Use JWT tokens with refresh mechanism")
    assert "✓ Added task #1" in result
    assert "Add login endpoint" in result
    assert "JWT tokens" in result


def test_todo_add_multiple_tasks(todo_repo):
    """Test adding multiple TODO tasks."""
    from patchpal.tools import todo_add

    result1 = todo_add("Task 1")
    result2 = todo_add("Task 2")
    result3 = todo_add("Task 3")

    assert "task #1" in result1
    assert "task #2" in result2
    assert "task #3" in result3


def test_todo_list_empty(todo_repo):
    """Test listing TODOs when list is empty."""
    from patchpal.tools import todo_list

    result = todo_list()
    assert "No tasks in TODO list" in result
    assert "todo_add()" in result


def test_todo_list_pending_only(todo_repo):
    """Test listing only pending tasks."""
    from patchpal.tools import todo_add, todo_complete, todo_list

    todo_add("Task 1")
    todo_add("Task 2")
    todo_add("Task 3")
    todo_complete(2)

    result = todo_list(show_completed=False)
    assert "Task 1" in result
    assert "Task 3" in result
    assert "Task 2" not in result  # Completed task should not appear
    assert "○ Task #1" in result
    assert "○ Task #3" in result


def test_todo_list_all_tasks(todo_repo):
    """Test listing all tasks including completed."""
    from patchpal.tools import todo_add, todo_complete, todo_list

    todo_add("Task 1")
    todo_add("Task 2")
    todo_complete(1)

    result = todo_list(show_completed=True)
    assert "Task 1" in result
    assert "Task 2" in result
    assert "✓ Task #1" in result  # Completed
    assert "○ Task #2" in result  # Pending


def test_todo_list_shows_details(todo_repo):
    """Test that todo_list shows task details."""
    from patchpal.tools import todo_add, todo_list

    todo_add("Implement auth", details="Use OAuth2 with PKCE flow\nHandle token refresh")

    result = todo_list()
    assert "Implement auth" in result
    assert "OAuth2" in result
    assert "token refresh" in result


def test_todo_list_shows_progress(todo_repo):
    """Test that todo_list shows progress summary."""
    from patchpal.tools import todo_add, todo_complete, todo_list

    todo_add("Task 1")
    todo_add("Task 2")
    todo_add("Task 3")
    todo_complete(1)
    todo_complete(2)

    result = todo_list(show_completed=True)
    assert "Summary:" in result
    assert "1 pending" in result
    assert "2 completed" in result
    assert "3 total" in result


def test_todo_list_all_completed(todo_repo):
    """Test listing when all tasks are completed."""
    from patchpal.tools import todo_add, todo_complete, todo_list

    todo_add("Task 1")
    todo_add("Task 2")
    todo_complete(1)
    todo_complete(2)

    result = todo_list(show_completed=False)
    assert "No pending tasks" in result
    assert "All tasks completed" in result
    assert "show_completed=True" in result


def test_todo_complete_success(todo_repo):
    """Test completing a TODO task."""
    from patchpal.tools import todo_add, todo_complete

    todo_add("Task to complete")
    result = todo_complete(1)

    assert "✓ Completed task #1" in result
    assert "Task to complete" in result
    assert "Progress: 1/1" in result


def test_todo_complete_shows_progress(todo_repo):
    """Test that todo_complete shows progress."""
    from patchpal.tools import todo_add, todo_complete

    todo_add("Task 1")
    todo_add("Task 2")
    todo_add("Task 3")

    result = todo_complete(2)
    assert "Progress: 1/3" in result


def test_todo_complete_nonexistent(todo_repo):
    """Test completing a nonexistent task."""
    from patchpal.tools import todo_add, todo_complete

    todo_add("Task 1")
    result = todo_complete(999)

    assert "Task #999 not found" in result
    assert "Available task IDs: [1]" in result


def test_todo_complete_already_completed(todo_repo):
    """Test completing an already completed task."""
    from patchpal.tools import todo_add, todo_complete

    todo_add("Task 1")
    todo_complete(1)

    result = todo_complete(1)
    assert "already completed" in result


def test_todo_update_description(todo_repo):
    """Test updating task description."""
    from patchpal.tools import todo_add, todo_update

    todo_add("Original description")
    result = todo_update(1, description="Updated description")

    assert "✓ Updated task #1" in result
    assert "Original description" in result
    assert "Updated description" in result


def test_todo_update_details(todo_repo):
    """Test updating task details."""
    from patchpal.tools import todo_add, todo_list, todo_update

    todo_add("Task 1", details="Old details")
    todo_update(1, details="New details with more information")

    result = todo_list()
    assert "New details with more information" in result
    assert "Old details" not in result


def test_todo_update_both_fields(todo_repo):
    """Test updating both description and details."""
    from patchpal.tools import todo_add, todo_update

    todo_add("Old task", details="Old details")
    result = todo_update(1, description="New task", details="New details")

    assert "✓ Updated task #1" in result
    assert "Old task" in result
    assert "New task" in result


def test_todo_update_no_fields(todo_repo):
    """Test updating without providing any fields."""
    from patchpal.tools import todo_add, todo_update

    todo_add("Task 1")
    result = todo_update(1)

    assert "Error: Must provide either description or details" in result


def test_todo_update_nonexistent(todo_repo):
    """Test updating a nonexistent task."""
    from patchpal.tools import todo_update

    result = todo_update(999, description="New description")
    assert "Task #999 not found" in result


def test_todo_remove_success(todo_repo):
    """Test removing a TODO task."""
    from patchpal.tools import todo_add, todo_remove

    todo_add("Task to remove")
    result = todo_remove(1)

    assert "✓ Removed task #1" in result
    assert "Task to remove" in result
    assert "0 task(s) remaining" in result


def test_todo_remove_with_remaining_tasks(todo_repo):
    """Test removing a task when others remain."""
    from patchpal.tools import todo_add, todo_list, todo_remove

    todo_add("Task 1")
    todo_add("Task 2")
    todo_add("Task 3")

    result = todo_remove(2)
    assert "✓ Removed task #2" in result
    assert "2 task(s) remaining" in result

    # Verify remaining tasks
    list_result = todo_list()
    assert "Task 1" in list_result
    assert "Task 3" in list_result
    assert "Task 2" not in list_result


def test_todo_remove_nonexistent(todo_repo):
    """Test removing a nonexistent task."""
    from patchpal.tools import todo_add, todo_remove

    todo_add("Task 1")
    result = todo_remove(999)

    assert "Task #999 not found" in result
    assert "Available task IDs: [1]" in result


def test_todo_clear_completed_only(todo_repo):
    """Test clearing only completed tasks."""
    from patchpal.tools import todo_add, todo_clear, todo_complete, todo_list

    todo_add("Task 1")
    todo_add("Task 2")
    todo_add("Task 3")
    todo_complete(1)
    todo_complete(3)

    result = todo_clear(completed_only=True)
    assert "✓ Cleared 2 completed task(s)" in result
    assert "1 pending task(s) remaining" in result

    # Verify only pending task remains
    list_result = todo_list()
    assert "Task 2" in list_result
    assert "Task 1" not in list_result
    assert "Task 3" not in list_result


def test_todo_clear_all_tasks(todo_repo):
    """Test clearing all tasks."""
    from patchpal.tools import todo_add, todo_clear, todo_complete, todo_list

    todo_add("Task 1")
    todo_add("Task 2")
    todo_complete(1)

    result = todo_clear(completed_only=False)
    assert "✓ Cleared all 2 task(s)" in result
    assert "TODO list is now empty" in result

    # Verify list is empty
    list_result = todo_list()
    assert "No tasks in TODO list" in list_result


def test_todo_clear_empty_list(todo_repo):
    """Test clearing when TODO list is already empty."""
    from patchpal.tools import todo_clear

    result = todo_clear()
    assert "TODO list is already empty" in result


def test_todo_clear_no_completed_tasks(todo_repo):
    """Test clearing completed tasks when none are completed."""
    from patchpal.tools import todo_add, todo_clear

    todo_add("Task 1")
    todo_add("Task 2")

    result = todo_clear(completed_only=True)
    assert "No completed tasks to clear" in result


def test_todo_persistence(todo_repo):
    """Test that TODO list persists across function calls."""
    from patchpal.tools import todo_add, todo_complete, todo_list

    # Add tasks
    todo_add("Task 1")
    todo_add("Task 2")

    # Complete one
    todo_complete(1)

    # Verify state persists
    result = todo_list(show_completed=True)
    assert "Task 1" in result
    assert "Task 2" in result
    assert "✓ Task #1" in result  # Should be completed


def test_todo_json_structure(todo_repo):
    """Test that TODO session storage has correct structure."""
    from patchpal.tools import _load_todos, todo_add

    todo_add("Test task", details="Test details")

    # Check the in-memory session storage structure
    data = _load_todos()

    assert "tasks" in data
    assert "next_id" in data
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["id"] == 1
    assert data["tasks"][0]["description"] == "Test task"
    assert data["tasks"][0]["details"] == "Test details"
    assert data["tasks"][0]["completed"] is False
    assert "created_at" in data["tasks"][0]


def test_todo_timestamps(todo_repo):
    """Test that TODO tasks have proper timestamps."""
    from datetime import datetime

    from patchpal.tools import todo_add, todo_complete, todo_list

    todo_add("Task with timestamp")
    todo_complete(1)

    result = todo_list(show_completed=True)
    # Should show created and completed times
    assert "Created:" in result
    assert "Completed:" in result
    # Should have year
    assert str(datetime.now().year) in result


# ============================================================================
# ask_user Tool Tests
# ============================================================================


def test_ask_user_simple_question(monkeypatch):
    """Test asking a simple question."""
    from patchpal.tools import ask_user, reset_operation_counter

    reset_operation_counter()

    # Mock Prompt.ask to return an answer
    with patch("rich.prompt.Prompt.ask", return_value="Yes"):
        result = ask_user("Should we proceed?")
        assert result == "Yes"


def test_ask_user_with_options(monkeypatch):
    """Test asking a question with multiple choice options."""
    from patchpal.tools import ask_user, reset_operation_counter

    reset_operation_counter()

    # Mock user selecting option 1
    with patch("rich.prompt.Prompt.ask", return_value="1"):
        result = ask_user("Which database?", options=["PostgreSQL", "MySQL", "SQLite"])
        assert result == "PostgreSQL"


def test_ask_user_with_options_by_name(monkeypatch):
    """Test user typing option name directly."""
    from patchpal.tools import ask_user, reset_operation_counter

    reset_operation_counter()

    # Mock user typing the option name
    with patch("rich.prompt.Prompt.ask", return_value="MySQL"):
        result = ask_user("Which database?", options=["PostgreSQL", "MySQL", "SQLite"])
        assert result == "MySQL"


def test_ask_user_with_options_custom_answer(monkeypatch):
    """Test user providing custom answer when options are given."""
    from patchpal.tools import ask_user, reset_operation_counter

    reset_operation_counter()

    # Mock user typing a custom answer
    with patch("rich.prompt.Prompt.ask", return_value="MongoDB"):
        result = ask_user("Which database?", options=["PostgreSQL", "MySQL", "SQLite"])
        assert result == "MongoDB"


def test_ask_user_with_options_out_of_range(monkeypatch):
    """Test user selecting a number out of range."""
    from patchpal.tools import ask_user, reset_operation_counter

    reset_operation_counter()

    # Mock user entering invalid number
    with patch("rich.prompt.Prompt.ask", return_value="99"):
        result = ask_user("Which database?", options=["PostgreSQL", "MySQL", "SQLite"])
        # Should treat as custom answer
        assert result == "99"


def test_ask_user_audit_logging(monkeypatch, caplog):
    """Test that ask_user logs to audit log."""
    from patchpal.tools import ask_user, reset_operation_counter

    reset_operation_counter()

    with patch("rich.prompt.Prompt.ask", return_value="Test answer"):
        ask_user("Test question?")

        # Check audit logger was called (in real usage, would be in audit.log)
        # We can't easily verify the log file in tests, but we verify the function completes


def test_ask_user_long_question(monkeypatch):
    """Test asking a long question."""
    from patchpal.tools import ask_user, reset_operation_counter

    reset_operation_counter()

    long_question = (
        "This is a very long question that spans multiple lines and contains lots of details about what we're asking the user to decide on. "
        * 3
    )

    with patch("rich.prompt.Prompt.ask", return_value="Answer"):
        result = ask_user(long_question)
        assert result == "Answer"


def test_ask_user_empty_options_list(monkeypatch):
    """Test asking with empty options list."""
    from patchpal.tools import ask_user, reset_operation_counter

    reset_operation_counter()

    # Empty list should be treated as no options
    with patch("rich.prompt.Prompt.ask", return_value="Free form answer"):
        result = ask_user("What do you think?", options=[])
        assert result == "Free form answer"


# ============================================================================
# Flexible edit_file Matching Strategy Tests
# ============================================================================


def test_edit_file_with_wrong_indentation(temp_repo):
    """Test edit_file with flexible matching but proper indentation in new_string."""
    from patchpal.tools import edit_file

    # Create a Python file with proper indentation
    content = """def hello():
    if True:
        print("world")
        return 42
"""
    (temp_repo / "indent_test.py").write_text(content)

    # Search without indentation (flexible matching finds it),
    # but provide new_string WITH proper indentation (OpenCode behavior)
    result = edit_file("indent_test.py", 'print("world")', '        print("universe")')

    assert "Successfully edited" in result

    # Verify the edit preserved indentation (because we provided it in new_string)
    new_content = (temp_repo / "indent_test.py").read_text()
    assert '        print("universe")' in new_content  # 8 spaces preserved
    assert '        print("world")' not in new_content
    # Other lines should be unchanged
    assert "def hello():" in new_content
    assert "    if True:" in new_content


def test_edit_file_multiline_wrong_indentation(temp_repo):
    """Test edit_file with multi-line blocks - new_string must have proper indentation."""
    from patchpal.tools import edit_file

    content = """class MyClass:
    def process(self):
        if self.valid:
            result = self.compute()
            return result
        return None
"""
    (temp_repo / "multiline_test.py").write_text(content)

    # Search without proper indentation (flexible matching),
    # but provide replacement WITH proper indentation
    old_string = """if self.valid:
    result = self.compute()
    return result"""

    new_string = """        if self.valid:
            result = self.compute_new()
            return result"""

    result = edit_file("multiline_test.py", old_string, new_string)

    assert "Successfully edited" in result

    # Verify correct indentation (because we provided it in new_string)
    new_content = (temp_repo / "multiline_test.py").read_text()
    assert "        if self.valid:" in new_content
    assert "            result = self.compute_new()" in new_content
    assert "            return result" in new_content


def test_edit_file_whitespace_normalization(temp_repo):
    """Test edit_file handles extra whitespace in search string."""
    from patchpal.tools import edit_file

    content = """x = 42
y = 100
z = x + y
"""
    (temp_repo / "whitespace_test.py").write_text(content)

    # User provides with extra spaces (e.g., copied from terminal with weird formatting)
    old_string = "x    =    42"

    result = edit_file("whitespace_test.py", old_string, "x = 99")

    assert "Successfully edited" in result

    # Verify the edit worked
    new_content = (temp_repo / "whitespace_test.py").read_text()
    assert "x = 99" in new_content
    assert "x = 42" not in new_content


def test_edit_file_real_world_agent_scenario(temp_repo):
    """Test the actual scenario that failed before: editing agent.py with indentation issues."""
    from patchpal.tools import edit_file

    # Simulate content from agent.py around tool execution
    content = """                              )

                                  # Silently filter out invalid args (models sometimes hallucinate parameters)

                                  tool_result = tool_func(**filtered_args)
                              except Exception as e:
                                  tool_result = f"Error executing {tool_name}: {e}"
                                  print(f"\\033[1;31mX {tool_display}: {e}\\033[0m")

                      # Add tool result to messages"""

    (temp_repo / "agent_snippet.py").write_text(content)

    # What the LLM might provide (without correct indentation)
    old_string = """# Silently filter out invalid args (models sometimes hallucinate parameters)

                                  tool_result = tool_func(**filtered_args)"""

    new_string = """# Silently filter out invalid args (models sometimes hallucinate parameters)

                                  tool_result = tool_func(**filtered_args)

                                  # Display result for certain tools where the result contains important info
                                  if tool_name == "todo_add" and not isinstance(tool_result, Exception):
                                      # Extract and display the task number from the result
                                      print(f"\\033[2m{tool_result.split(':')[0]}\\033[0m", flush=True)"""

    result = edit_file("agent_snippet.py", old_string, new_string)

    assert "Successfully edited" in result

    # Verify the edit preserved original indentation
    new_content = (temp_repo / "agent_snippet.py").read_text()
    assert "                                  # Display result for certain tools" in new_content
    assert "tool_result.split" in new_content


def test_edit_file_code_without_indentation_prefers_line_match(temp_repo):
    """Test that code patterns without indentation prefer line-level matching over substring."""
    from patchpal.tools import edit_file

    content = """def calculate():
    result = compute()
    return result
"""
    (temp_repo / "code_test.py").write_text(content)

    # Search without indentation (flexible matching finds full line),
    # provide replacement WITH proper indentation
    old_string = "return result"
    new_string = "    return final_result"  # With proper indentation

    edit_file("code_test.py", old_string, new_string)

    new_content = (temp_repo / "code_test.py").read_text()
    assert "    return final_result" in new_content
    assert "result = compute()" in new_content  # Should not have changed this line


def test_edit_file_preserves_exact_match_when_possible(temp_repo):
    """Test that exact matches are still preferred when indentation is correct."""
    from patchpal.tools import edit_file

    content = """def hello():
    print("world")
"""
    (temp_repo / "exact_test.py").write_text(content)

    # With correct indentation, should use exact match
    old_string = '    print("world")'

    result = edit_file("exact_test.py", old_string, '    print("universe")')

    assert "Successfully edited" in result

    new_content = (temp_repo / "exact_test.py").read_text()
    assert '    print("universe")' in new_content


def test_edit_file_flexible_matching_error_message(temp_repo):
    """Test error message when string not found."""
    from patchpal.tools import edit_file

    (temp_repo / "test_error.py").write_text("def hello():\n    pass\n")

    # Try to find something that doesn't exist
    with pytest.raises(ValueError) as exc_info:
        edit_file("test_error.py", "goodbye()", "farewell()")

    error_msg = str(exc_info.value)
    assert "String not found" in error_msg
    assert "read_lines()" in error_msg  # Should suggest using read_lines()


def test_edit_file_matching_strategies_helper_functions(temp_repo):
    """Test the underlying matching strategy helper functions directly."""
    from patchpal.tools import (
        _try_line_trimmed_match,
        _try_simple_match,
        _try_whitespace_normalized_match,
    )

    content = """def hello():
    print("world")
    return 42
"""

    # Test simple match
    assert _try_simple_match(content, 'print("world")') == 'print("world")'
    assert _try_simple_match(content, "nonexistent") is None

    # Test line trimmed match (should find with correct indentation AND trailing newline)
    match = _try_line_trimmed_match(content, 'print("world")')
    assert match == '    print("world")\n'  # Now preserves trailing newline

    # Test whitespace normalized match
    content2 = "x    =    42"
    match = _try_whitespace_normalized_match(content2, "x = 42")
    assert match == "x    =    42"


def test_edit_file_multiline_trimmed_match_helper(temp_repo):
    """Test line-trimmed matching with multi-line blocks."""
    from patchpal.tools import _try_line_trimmed_match

    content = """class Test:
    def method(self):
        if True:
            do_something()
            return value
"""

    # Search without proper indentation
    search = """if True:
    do_something()
    return value"""

    match = _try_line_trimmed_match(content, search)
    # Should return with proper indentation (8 spaces) AND trailing newline
    assert match == "        if True:\n            do_something()\n            return value\n"


def test_edit_file_finds_match_with_strategy_order(temp_repo):
    """Test that strategies are tried in correct order."""
    from patchpal.tools import _find_match_with_strategies

    # Scenario: content has both a substring and a full line
    # Should prefer full line match for code patterns
    content = """def calculate():
    result = process()  # result is important
    return result
"""

    # Without indentation, should match the full line not substring in comment
    match = _find_match_with_strategies(content, "return result")
    assert match == "    return result\n"  # Now includes trailing newline
    # Should prefer full line match for code patterns
    content = """def calculate():
    result = process()  # result is important
    return result
"""

    # Without indentation, should match the full line not substring in comment
    match = _find_match_with_strategies(content, "return result")
    assert match == "    return result\n"  # Now includes trailing newline
    # Should NOT match just "result" in the comment or variable name


def test_edit_file_preserves_trailing_newline(temp_repo):
    """Test that flexible matching preserves trailing newlines in matched blocks."""
    from patchpal.tools import edit_file

    # Test case 1: Match in middle of file (should preserve ONE trailing newline, not blank lines)
    content_middle = """def function1():
    print("hello")
    return 1

def function2():
    print("world")
    return 2
"""
    (temp_repo / "newline_test1.py").write_text(content_middle)

    # Edit a block in the middle - the matched block should include ONE trailing newline
    # but NOT the blank line that follows (blank line is not part of the function)
    old_string = """def function1():
    print("hello")
    return 1"""

    new_string = """def function1():
    print("modified")
    return 1"""

    edit_file("newline_test1.py", old_string, new_string)

    # Verify: the matched section gets replaced, preserving structure
    # The blank line should remain because it's between the two functions
    new_content = (temp_repo / "newline_test1.py").read_text()
    # After editing, there should still be a blank line between functions
    assert "\n\ndef function2():" in new_content
    assert 'print("modified")' in new_content

    # Test case 2: Match at end of file WITH trailing newline
    content_end_with = """def function():
    print("test")
    return True
"""
    (temp_repo / "newline_test2.py").write_text(content_end_with)

    old_string = 'print("test")\n    return True'
    new_string = 'print("modified")\n    return True'

    edit_file("newline_test2.py", old_string, new_string)

    new_content = (temp_repo / "newline_test2.py").read_text()
    # File should still end with newline
    assert new_content.endswith("\n")
    assert 'print("modified")' in new_content

    # Test case 3: Match at end of file WITHOUT trailing newline
    content_end_without = """def function():
    print("test")
    return False"""  # No trailing newline

    (temp_repo / "newline_test3.py").write_text(content_end_without)

    old_string = 'print("test")\n    return False'
    new_string = 'print("changed")\n    return False'

    edit_file("newline_test3.py", old_string, new_string)

    new_content = (temp_repo / "newline_test3.py").read_text()
    # File should NOT have trailing newline (preserving original)
    assert not new_content.endswith("\n")
    assert 'print("changed")' in new_content


def test_edit_file_auto_adjusts_indentation(temp_repo):
    """Test that edit_file automatically adjusts indentation of new_string to match matched_string."""
    from patchpal.tools import edit_file

    # Create a file with specific indentation (28 spaces for elif)
    content = """                            elif tool_name == "todo_add":
                                print(
                                    f"Adding TODO",
                                    flush=True,
                                )
"""
    (temp_repo / "indent_adjust_test.py").write_text(content)

    # Provide new_string with WRONG indentation (30 spaces)
    old_string = """elif tool_name == "todo_add":
    print(
        f"Adding TODO",
        flush=True,
    )"""

    new_string = """                              elif tool_name == "todo_add":
                                  print(
                                      f"Modified TODO",
                                      flush=True,
                                  )"""

    edit_file("indent_adjust_test.py", old_string, new_string)

    # Verify the indentation was AUTO-ADJUSTED to match original (28 spaces)
    new_content = (temp_repo / "indent_adjust_test.py").read_text()

    # Should have 28 spaces before elif (not 30)
    assert "                            elif tool_name" in new_content
    # Should have 32 spaces before print (not 34)
    assert "                                print(" in new_content
    # Content should be updated
    assert "Modified TODO" in new_content
    assert "Adding TODO" not in new_content
