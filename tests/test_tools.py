"""Tests for patchpal.tools module."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def temp_repo(monkeypatch):
    """Create a temporary repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create test files
        (tmpdir_path / "test.txt").write_text("Hello, World!")
        (tmpdir_path / "subdir").mkdir()
        (tmpdir_path / "subdir" / "file.py").write_text("print('test')")

        # Monkey-patch REPO_ROOT
        monkeypatch.setattr("patchpal.tools.REPO_ROOT", tmpdir_path)

        # Disable permission prompts during tests
        monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

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


def test_list_files(temp_repo):
    """Test listing files in the repository."""
    from patchpal.tools import list_files

    files = list_files()
    assert "test.txt" in files
    assert "subdir/file.py" in files
    assert len(files) == 2  # Should only list files, not directories


def test_list_files_ignores_hidden(temp_repo):
    """Test that hidden files are ignored."""
    from patchpal.tools import list_files

    # Create a hidden file
    (temp_repo / ".hidden").write_text("secret")
    (temp_repo / ".git").mkdir()
    (temp_repo / ".git" / "config").write_text("config")

    files = list_files()
    assert ".hidden" not in files
    assert ".git/config" not in files


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
        tmpdir_path = Path(tmpdir)

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
