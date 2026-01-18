"""Tests for enhanced security guardrails.

These tests demonstrate the additional safety features in tools.py.
Run with: pytest tests/test_enhanced_guardrails.py
"""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_repo(monkeypatch):
    """Create a temporary repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create test files
        (tmpdir_path / "normal.txt").write_text("normal file")
        (tmpdir_path / "large.txt").write_text("x" * (11 * 1024 * 1024))  # 11MB
        (tmpdir_path / ".env").write_text("SECRET_KEY=abc123")
        (tmpdir_path / "package.json").write_text('{"name": "test"}')

        # Create binary file
        (tmpdir_path / "binary.bin").write_bytes(b"\x00\x01\x02\x03")

        # Monkey-patch REPO_ROOT
        import patchpal.tools as tools_enhanced

        monkeypatch.setattr(tools_enhanced, "REPO_ROOT", tmpdir_path)

        # Disable permission prompts during tests
        monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

        yield tmpdir_path


class TestSensitiveFileProtection:
    """Test sensitive file detection and blocking."""

    def test_blocks_env_file_access(self, temp_repo):
        """Test that .env files are blocked by default."""
        from patchpal.tools import read_file

        with pytest.raises(ValueError, match="sensitive file"):
            read_file(".env")

    def test_blocks_credentials_file(self, temp_repo, monkeypatch):
        """Test that credential files are blocked."""
        from patchpal.tools import read_file

        (temp_repo / "credentials.json").write_text('{"key": "secret"}')

        with pytest.raises(ValueError, match="sensitive file"):
            read_file("credentials.json")

    def test_allows_with_override(self, temp_repo, monkeypatch):
        """Test that ALLOW_SENSITIVE override works."""
        monkeypatch.setenv("PATCHPAL_ALLOW_SENSITIVE", "true")

        # Reimport to pick up env var
        import importlib

        import patchpal.tools

        importlib.reload(patchpal.tools)

        # Re-monkeypatch REPO_ROOT after reload
        monkeypatch.setattr("patchpal.tools.REPO_ROOT", temp_repo)

        content = patchpal.tools.read_file(".env")
        assert "SECRET_KEY" in content


class TestFileSizeLimits:
    """Test file size restrictions."""

    def test_blocks_large_file_read(self, temp_repo):
        """Test that files over size limit are blocked."""
        from patchpal.tools import read_file

        with pytest.raises(ValueError, match="too large"):
            read_file("large.txt")

    def test_blocks_large_file_write(self, temp_repo):
        """Test that writing large content is blocked."""
        from patchpal.tools import apply_patch

        large_content = "x" * (11 * 1024 * 1024)

        with pytest.raises(ValueError, match="too large"):
            apply_patch("output.txt", large_content)

    def test_allows_normal_size_file(self, temp_repo):
        """Test that normal-sized files work."""
        from patchpal.tools import read_file

        content = read_file("normal.txt")
        assert content == "normal file"


class TestBinaryFileDetection:
    """Test binary file handling."""

    def test_blocks_binary_file_read(self, temp_repo):
        """Test that binary files are blocked."""
        from patchpal.tools import read_file

        with pytest.raises(ValueError, match="binary file"):
            read_file("binary.bin")

    def test_allows_text_file(self, temp_repo):
        """Test that text files are allowed."""
        from patchpal.tools import read_file

        content = read_file("normal.txt")
        assert content == "normal file"


class TestCriticalFileWarnings:
    """Test warnings for critical files."""

    def test_warns_on_package_json_modify(self, temp_repo):
        """Test that modifying package.json shows warning."""
        from patchpal.tools import apply_patch

        result = apply_patch("package.json", '{"name": "modified"}')
        assert "WARNING" in result
        assert "critical" in result.lower()

    def test_no_warning_on_normal_file(self, temp_repo):
        """Test that normal files don't show warning."""
        from patchpal.tools import apply_patch

        result = apply_patch("normal.txt", "modified content")
        assert "WARNING" not in result


class TestReadOnlyMode:
    """Test read-only mode."""

    def test_blocks_writes_in_readonly(self, temp_repo, monkeypatch):
        """Test that writes are blocked in read-only mode."""
        monkeypatch.setenv("PATCHPAL_READ_ONLY", "true")

        # Reimport to pick up env var
        import importlib

        import patchpal.tools

        importlib.reload(patchpal.tools)

        with pytest.raises(ValueError, match="read-only mode"):
            patchpal.tools.apply_patch("test.txt", "content")

    def test_allows_reads_in_readonly(self, temp_repo, monkeypatch):
        """Test that reads work in read-only mode."""
        monkeypatch.setenv("PATCHPAL_READ_ONLY", "true")

        # Reimport to pick up env var
        import importlib

        import patchpal.tools

        importlib.reload(patchpal.tools)

        # Re-monkeypatch REPO_ROOT after reload
        monkeypatch.setattr("patchpal.tools.REPO_ROOT", temp_repo)

        content = patchpal.tools.read_file("normal.txt")
        assert content == "normal file"


class TestCommandSafety:
    """Test enhanced command safety."""

    def test_blocks_dangerous_patterns(self, temp_repo):
        """Test that dangerous command patterns are blocked."""
        from patchpal.tools import run_shell

        dangerous_commands = [
            "echo test > /dev/sda",
            "rm -rf /",
            "cat file | dd of=/dev/sda",
            "git push --force",
        ]

        for cmd in dangerous_commands:
            with pytest.raises(ValueError, match="dangerous"):
                run_shell(cmd)

    def test_allows_safe_commands(self, temp_repo):
        """Test that safe commands work."""
        from patchpal.tools import run_shell

        result = run_shell("echo 'test'")
        assert "test" in result

    def test_command_timeout(self, temp_repo, monkeypatch):
        """Test that long-running commands timeout."""
        # Set a short timeout for faster testing
        monkeypatch.setenv("PATCHPAL_SHELL_TIMEOUT", "2")

        # Reload module to pick up new timeout
        import importlib

        import patchpal.tools

        importlib.reload(patchpal.tools)

        # Re-monkeypatch REPO_ROOT after reload
        monkeypatch.setattr("patchpal.tools.REPO_ROOT", temp_repo)

        import subprocess

        from patchpal.tools import run_shell

        with pytest.raises(subprocess.TimeoutExpired):
            run_shell("sleep 10")


class TestPathTraversal:
    """Test path access security model (matches Claude Code approach).

    - Read operations: Allowed anywhere (system files, libraries, etc.)
    - Write operations: Restricted to repository unless permission granted
    """

    def test_allows_reading_parent_directories(self, temp_repo):
        """Test that read operations can access parent directories."""
        from patchpal.tools import read_file

        # Create a file in parent directory for testing
        outside_file = temp_repo.parent / "test_file.txt"
        outside_file.write_text("outside content")

        try:
            # Should now allow reading files outside repository
            content = read_file(str(outside_file))
            assert content == "outside content"
        finally:
            outside_file.unlink()

    def test_allows_reading_absolute_paths(self, temp_repo):
        """Test that read operations can access absolute paths."""
        # Create a temp file with absolute path
        import tempfile

        from patchpal.tools import read_file

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("absolute path content")
            temp_path = f.name

        try:
            content = read_file(temp_path)
            assert content == "absolute path content"
        finally:
            Path(temp_path).unlink()

    def test_blocks_writing_outside_repository(self, temp_repo, monkeypatch):
        """Test that write operations outside repository are blocked/require permission."""
        # Enable permission system for this test
        monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "true")
        monkeypatch.setenv("PATCHPAL_READ_ONLY", "false")

        # Reload module to pick up new env vars
        import importlib

        import patchpal.permissions
        import patchpal.tools

        importlib.reload(patchpal.permissions)
        importlib.reload(patchpal.tools)

        # Re-monkeypatch REPO_ROOT after reload
        monkeypatch.setattr("patchpal.tools.REPO_ROOT", temp_repo)

        # Mock permission request to deny access
        def mock_request_permission(self, tool_name, description, pattern=None):
            return False  # Deny permission

        monkeypatch.setattr(
            "patchpal.permissions.PermissionManager.request_permission", mock_request_permission
        )

        from patchpal.tools import apply_patch

        # Try to write to parent directory
        outside_path = temp_repo.parent / "test_write.txt"

        # Should be blocked - permission denied returns a cancellation message
        result = apply_patch(str(outside_path), "malicious content")
        assert "cancelled" in result.lower()

    def test_blocks_editing_outside_repository(self, temp_repo, monkeypatch):
        """Test that edit operations outside repository are blocked/require permission."""
        # Enable permission system for this test
        monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "true")
        monkeypatch.setenv("PATCHPAL_READ_ONLY", "false")

        # Reload module to pick up new env vars
        import importlib

        import patchpal.permissions
        import patchpal.tools

        importlib.reload(patchpal.permissions)
        importlib.reload(patchpal.tools)

        # Re-monkeypatch REPO_ROOT after reload
        monkeypatch.setattr("patchpal.tools.REPO_ROOT", temp_repo)

        # Mock permission request to deny access
        def mock_request_permission(self, tool_name, description, pattern=None):
            return False  # Deny permission

        monkeypatch.setattr(
            "patchpal.permissions.PermissionManager.request_permission", mock_request_permission
        )

        from patchpal.tools import edit_file

        # Create a file outside repo to try editing
        outside_file = temp_repo.parent / "test_edit.txt"
        outside_file.write_text("original content")

        try:
            # Should be blocked - permission denied returns a cancellation message
            result = edit_file(str(outside_file), "original", "modified")
            assert "cancelled" in result.lower()
        finally:
            if outside_file.exists():
                outside_file.unlink()

    def test_allows_reading_symlink_outside_repo(self, temp_repo):
        """Test that symlinks pointing outside repo can be read."""
        from patchpal.tools import read_file

        # Create file outside repo and symlink to it
        outside_file = temp_repo.parent / "outside.txt"
        outside_file.write_text("outside content")

        symlink = temp_repo / "link.txt"
        symlink.symlink_to(outside_file)

        try:
            # Should now allow reading via symlink
            content = read_file("link.txt")
            assert content == "outside content"
        finally:
            symlink.unlink()
            outside_file.unlink()


class TestConfigurability:
    """Test configuration via environment variables."""

    def test_custom_max_file_size(self, temp_repo, monkeypatch):
        """Test that MAX_FILE_SIZE can be configured."""
        monkeypatch.setenv("PATCHPAL_MAX_FILE_SIZE", "1000")

        # Reimport to pick up env var
        import importlib

        import patchpal.tools

        importlib.reload(patchpal.tools)

        # Re-monkeypatch REPO_ROOT after reload
        monkeypatch.setattr("patchpal.tools.REPO_ROOT", temp_repo)

        # Should now block even small files
        (temp_repo / "medium.txt").write_text("x" * 2000)

        with pytest.raises(ValueError, match="too large"):
            patchpal.tools.read_file("medium.txt")


# Summary test to demonstrate all guardrails
def test_comprehensive_security_demo(temp_repo, monkeypatch):
    """Comprehensive test showing all security features."""
    # Mock permission request to deny only for outside-repo writes

    def mock_request_permission(self, tool_name, description, pattern=None):
        # Only deny write operations (apply_patch/edit_file) for paths outside repo
        if tool_name in ("apply_patch", "edit_file") and pattern:
            # Convert pattern to Path to handle both relative and absolute paths
            from pathlib import Path

            pattern_path = Path(pattern)
            # If it's not absolute, it's relative to repo, so it's inside repo
            if not pattern_path.is_absolute():
                return True
            # If absolute, check if it's inside repo
            if not str(pattern_path).startswith(str(temp_repo)):
                return False
        # Allow everything else by returning True or checking original behavior
        return True

    # Enable permissions but set up mock
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "true")

    import patchpal.permissions
    from patchpal.tools import apply_patch, list_files, read_file, run_shell

    # Mock the request_permission method
    monkeypatch.setattr(
        patchpal.permissions.PermissionManager, "request_permission", mock_request_permission
    )

    # 1. Normal operations work
    content = read_file("normal.txt")
    assert content == "normal file"

    result = apply_patch("test.txt", "new content")
    assert "Successfully updated" in result

    output = run_shell("ls normal.txt")
    assert "normal.txt" in output

    files = list_files()
    assert "normal.txt" in files

    # 2. Sensitive files blocked
    with pytest.raises(ValueError, match="sensitive"):
        read_file(".env")

    # 3. Large files blocked
    with pytest.raises(ValueError, match="too large"):
        read_file("large.txt")

    # 4. Binary files blocked
    with pytest.raises(ValueError, match="binary"):
        read_file("binary.bin")

    # 5. Critical files warned
    result = apply_patch("package.json", '{"modified": true}')
    assert "WARNING" in result

    # 6. Dangerous commands blocked
    with pytest.raises(ValueError, match="dangerous"):
        run_shell("rm -rf /")

    # 7. Write operations outside repo blocked
    outside_path = temp_repo.parent / "test_outside.txt"
    result = apply_patch(str(outside_path), "test")
    assert "cancelled" in result.lower()

    print("✅ All security guardrails working correctly!")
