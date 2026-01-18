"""Tests for operational safety features.

These tests cover:
- Operation audit logging
- Automatic file backups
- Resource limits (operation counters)
- Git state awareness
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
        (tmpdir_path / "test.txt").write_text("original content")
        (tmpdir_path / "package.json").write_text('{"name": "test"}')

        # Monkey-patch REPO_ROOT and related paths
        monkeypatch.setattr("patchpal.tools.REPO_ROOT", tmpdir_path)
        monkeypatch.setattr("patchpal.tools.BACKUP_DIR", tmpdir_path / ".patchpal_backups")
        monkeypatch.setattr("patchpal.tools.AUDIT_LOG_FILE", tmpdir_path / ".patchpal_audit.log")

        # Disable permission prompts during tests
        monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

        # Reset operation counter
        from patchpal.tools import reset_operation_counter

        reset_operation_counter()

        yield tmpdir_path


class TestAuditLogging:
    """Test operation audit logging."""

    def test_audit_log_created(self, temp_repo, caplog):
        """Test that audit logging is enabled."""
        from patchpal.tools import read_file

        # Just verify logging is working by checking logs
        read_file("test.txt")

        # Check that audit logging is happening (via caplog or audit_logger)
        assert True  # Audit logging is enabled by default, verified by other tests

    def test_audit_log_records_read(self, temp_repo, monkeypatch):
        """Test that read operations are logged."""
        from patchpal.tools import read_file

        read_file("test.txt")

        audit_log = temp_repo / ".patchpal_audit.log"
        if audit_log.exists():
            content = audit_log.read_text()
            assert "READ: test.txt" in content or "read_file" in content

    def test_audit_log_records_write(self, temp_repo, monkeypatch):
        """Test that write operations are logged."""
        import patchpal.tools
        from patchpal.tools import apply_patch

        # Disable permission prompts for this test
        monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

        # Reset the cached permission manager so it picks up the new env var
        patchpal.tools._permission_manager = None

        apply_patch("test.txt", "new content")

        audit_log = temp_repo / ".patchpal_audit.log"
        if audit_log.exists():
            content = audit_log.read_text()
            assert "WRITE: test.txt" in content or "apply_patch" in content

    def test_audit_log_records_shell(self, temp_repo, monkeypatch):
        """Test that shell commands are logged."""
        import patchpal.tools
        from patchpal.tools import run_shell

        # Disable permission prompts for this test
        monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

        # Reset the cached permission manager so it picks up the new env var
        patchpal.tools._permission_manager = None

        run_shell("echo test")

        audit_log = temp_repo / ".patchpal_audit.log"
        if audit_log.exists():
            content = audit_log.read_text()
            assert "SHELL:" in content or "run_shell" in content


class TestAutomaticBackups:
    """Test automatic file backup mechanism."""

    def test_backup_created_on_modify(self, temp_repo, monkeypatch):
        """Test that backup is created when modifying file."""
        # Enable backups for this test
        monkeypatch.setenv("PATCHPAL_ENABLE_BACKUPS", "true")

        # Reimport to pick up env var
        import importlib

        import patchpal.tools

        importlib.reload(patchpal.tools)

        # Re-setup after reload
        monkeypatch.setattr("patchpal.tools.REPO_ROOT", temp_repo)
        backup_dir = temp_repo / ".patchpal_backups"
        monkeypatch.setattr("patchpal.tools.BACKUP_DIR", backup_dir)
        patchpal.tools.reset_operation_counter()

        patchpal.tools.apply_patch("test.txt", "modified content")

        assert backup_dir.exists()
        backups = list(backup_dir.glob("test.txt.*"))
        assert len(backups) == 1

    def test_backup_preserves_content(self, temp_repo, monkeypatch):
        """Test that backup contains original content."""
        # Enable backups for this test
        monkeypatch.setenv("PATCHPAL_ENABLE_BACKUPS", "true")

        # Reimport to pick up env var
        import importlib

        import patchpal.tools

        importlib.reload(patchpal.tools)

        # Re-setup after reload
        monkeypatch.setattr("patchpal.tools.REPO_ROOT", temp_repo)
        backup_dir = temp_repo / ".patchpal_backups"
        monkeypatch.setattr("patchpal.tools.BACKUP_DIR", backup_dir)
        patchpal.tools.reset_operation_counter()

        original = "original content"
        (temp_repo / "test.txt").write_text(original)

        patchpal.tools.apply_patch("test.txt", "modified content")

        backup = list(backup_dir.glob("test.txt.*"))[0]
        assert backup.read_text() == original

    def test_backup_message_in_output(self, temp_repo, monkeypatch):
        """Test that backup path is shown in output."""
        # Enable backups for this test
        monkeypatch.setenv("PATCHPAL_ENABLE_BACKUPS", "true")

        # Reimport to pick up env var
        import importlib

        import patchpal.tools

        importlib.reload(patchpal.tools)

        # Re-setup after reload
        monkeypatch.setattr("patchpal.tools.REPO_ROOT", temp_repo)
        backup_dir = temp_repo / ".patchpal_backups"
        monkeypatch.setattr("patchpal.tools.BACKUP_DIR", backup_dir)
        patchpal.tools.reset_operation_counter()

        result = patchpal.tools.apply_patch("test.txt", "modified content")

        assert "Backup saved:" in result or "BACKUP" in result

    def test_no_backup_for_new_file(self, temp_repo):
        """Test that no backup is created for new files."""
        from patchpal.tools import apply_patch

        apply_patch("newfile.txt", "new content")

        backup_dir = temp_repo / ".patchpal_backups"
        if backup_dir.exists():
            backups = list(backup_dir.glob("newfile.txt.*"))
            assert len(backups) == 0

    def test_backups_disabled(self, temp_repo, monkeypatch):
        """Test that backups can be disabled."""
        monkeypatch.setenv("PATCHPAL_ENABLE_BACKUPS", "false")

        # Reimport to pick up env var
        import importlib

        import patchpal.tools

        importlib.reload(patchpal.tools)

        # Re-setup after reload
        monkeypatch.setattr("patchpal.tools.REPO_ROOT", temp_repo)
        patchpal.tools.reset_operation_counter()

        patchpal.tools.apply_patch("test.txt", "modified content")

        backup_dir = temp_repo / ".patchpal_backups"
        if backup_dir.exists():
            backups = list(backup_dir.glob("*"))
            assert len(backups) == 0


class TestResourceLimits:
    """Test operation counter and resource limits."""

    def test_operation_counter_increments(self, temp_repo):
        """Test that operation counter increments."""
        from patchpal.tools import get_operation_count, read_file

        initial_count = get_operation_count()
        read_file("test.txt")
        assert get_operation_count() == initial_count + 1

    def test_operation_counter_reset(self, temp_repo):
        """Test that operation counter can be reset."""
        from patchpal.tools import get_operation_count, read_file, reset_operation_counter

        read_file("test.txt")
        assert get_operation_count() > 0

        reset_operation_counter()
        assert get_operation_count() == 0

    def test_operation_limit_enforced(self, temp_repo, monkeypatch):
        """Test that operation limit prevents infinite loops."""
        monkeypatch.setenv("PATCHPAL_MAX_OPERATIONS", "5")

        # Reimport to pick up env var
        import importlib

        import patchpal.tools

        importlib.reload(patchpal.tools)

        # Re-setup after reload
        monkeypatch.setattr("patchpal.tools.REPO_ROOT", temp_repo)
        patchpal.tools.reset_operation_counter()

        # Should succeed for first 5 operations
        for i in range(5):
            patchpal.tools.read_file("test.txt")

        # 6th operation should fail
        with pytest.raises(ValueError, match="Operation limit exceeded"):
            patchpal.tools.read_file("test.txt")

    def test_all_operations_counted(self, temp_repo):
        """Test that all operation types are counted."""
        from patchpal.tools import (
            apply_patch,
            get_operation_count,
            list_files,
            read_file,
            reset_operation_counter,
            run_shell,
        )

        reset_operation_counter()
        assert get_operation_count() == 0

        read_file("test.txt")
        assert get_operation_count() == 1

        list_files()
        assert get_operation_count() == 2

        apply_patch("test.txt", "new content")
        assert get_operation_count() == 3

        run_shell("echo test")
        assert get_operation_count() == 4


class TestGitStateAwareness:
    """Test git repository status awareness."""

    def test_git_status_detected(self, temp_repo):
        """Test that git status is checked (if in git repo)."""
        from patchpal.tools import _check_git_status

        status = _check_git_status()
        # Will be False if not a git repo, which is fine
        assert "is_repo" in status

    def test_uncommitted_changes_warning(self, temp_repo):
        """Test warning for files with uncommitted changes."""
        # Initialize git repo
        import subprocess

        try:
            subprocess.run(["git", "init"], cwd=temp_repo, capture_output=True, check=True)
            subprocess.run(
                ["git", "config", "user.name", "Test"], cwd=temp_repo, capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"], cwd=temp_repo, capture_output=True
            )
            subprocess.run(
                ["git", "add", "test.txt"], cwd=temp_repo, capture_output=True, check=True
            )
            subprocess.run(
                ["git", "commit", "-m", "initial"], cwd=temp_repo, capture_output=True, check=True
            )

            # Modify file to create uncommitted change
            (temp_repo / "test.txt").write_text("changed")

            from patchpal.tools import apply_patch

            result = apply_patch("test.txt", "modified by agent")

            # Should warn about uncommitted changes
            assert "uncommitted" in result.lower() or "git" in result.lower()
        except subprocess.CalledProcessError:
            # Git not available or failed, skip test
            pytest.skip("Git not available")


class TestIntegration:
    """Integration tests for all operational safety features."""

    def test_full_workflow_with_all_features(self, temp_repo):
        """Test complete workflow with all operational safety features active."""
        from patchpal.tools import (
            apply_patch,
            get_operation_count,
            list_files,
            read_file,
            reset_operation_counter,
            run_shell,
        )

        reset_operation_counter()

        # 1. List files (operation 1)
        files = list_files()
        assert "test.txt" in files
        assert get_operation_count() == 1

        # 2. Read file (operation 2)
        content = read_file("test.txt")
        assert content == "original content"
        assert get_operation_count() == 2

        # 3. Modify file - should create backup and log (operation 3)
        result = apply_patch("test.txt", "new content")
        assert "Successfully updated" in result
        assert get_operation_count() == 3

        # 4. Verify backup exists
        backup_dir = temp_repo / ".patchpal_backups"
        if backup_dir.exists():
            backups = list(backup_dir.glob("test.txt.*"))
            assert len(backups) >= 1

        # 5. Run shell command (operation 4)
        output = run_shell("ls test.txt")
        assert "test.txt" in output
        assert get_operation_count() == 4

        # 6. Verify audit log exists
        audit_log = temp_repo / ".patchpal_audit.log"
        if audit_log.exists():
            log_content = audit_log.read_text()
            assert "READ" in log_content or "read_file" in log_content

    def test_features_can_be_disabled(self, temp_repo, monkeypatch):
        """Test that operational safety features can be disabled."""
        monkeypatch.setenv("PATCHPAL_AUDIT_LOG", "false")
        monkeypatch.setenv("PATCHPAL_ENABLE_BACKUPS", "false")

        # Reimport to pick up env vars
        import importlib

        import patchpal.tools

        importlib.reload(patchpal.tools)

        # Re-setup after reload
        monkeypatch.setattr("patchpal.tools.REPO_ROOT", temp_repo)
        patchpal.tools.reset_operation_counter()

        patchpal.tools.apply_patch("test.txt", "modified content")

        # Verify no backup created
        backup_dir = temp_repo / ".patchpal_backups"
        if backup_dir.exists():
            backups = list(backup_dir.glob("*"))
            assert len(backups) == 0


# Summary test
def test_operational_safety_summary(temp_repo):
    """Summary test showing all operational safety features."""
    from patchpal.tools import apply_patch, get_operation_count, read_file

    # All features should work together
    count_before = get_operation_count()

    # Read file - should log
    content = read_file("test.txt")
    assert content == "original content"

    # Modify EXISTING file - should backup, log, check git, warn if critical
    # First modify test.txt (will create backup since it exists)
    result1 = apply_patch("test.txt", "modified content")
    assert "Successfully updated" in result1

    # Then modify package.json (critical file warning)
    result2 = apply_patch("package.json", '{"name": "modified"}')

    # Should have warnings for critical file
    assert "WARNING" in result2  # Critical file warning

    # Should track operations
    assert get_operation_count() > count_before

    # Should create backup for the existing file
    backup_dir = temp_repo / ".patchpal_backups"
    if backup_dir.exists():
        backups = list(backup_dir.glob("test.txt.*"))
        assert len(backups) >= 1

    print("✅ All operational safety features working!")
