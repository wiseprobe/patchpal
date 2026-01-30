"""Tests for permission pattern extraction (Claude Code compatibility)."""

from pathlib import Path

import pytest


@pytest.fixture
def mock_repo(tmp_path):
    """Create a mock repository directory."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()
    return repo_dir


def test_permission_pattern_inside_repo(mock_repo, monkeypatch):
    """Test that files inside repo use relative path as pattern."""
    # Mock REPO_ROOT
    monkeypatch.setattr("patchpal.tools.REPO_ROOT", mock_repo)

    from patchpal.tools import _get_permission_pattern_for_path

    # Test file inside repo
    test_file = mock_repo / "src" / "app.py"
    pattern = _get_permission_pattern_for_path("src/app.py", test_file)

    assert pattern == "src/app.py"
    assert not pattern.endswith("/")


def test_permission_pattern_outside_repo_tmp(mock_repo, monkeypatch):
    """Test that files outside repo use directory name as pattern."""
    # Mock REPO_ROOT
    monkeypatch.setattr("patchpal.tools.REPO_ROOT", mock_repo)

    from patchpal.tools import _get_permission_pattern_for_path

    # Test file in /tmp/
    tmp_file = Path("/tmp/test.py")
    pattern = _get_permission_pattern_for_path("../../../../../tmp/test.py", tmp_file)

    assert pattern == "tmp/"
    assert pattern.endswith("/")


def test_permission_pattern_outside_repo_home(mock_repo, monkeypatch):
    """Test path traversal to other directories."""
    # Mock REPO_ROOT
    monkeypatch.setattr("patchpal.tools.REPO_ROOT", mock_repo)

    from patchpal.tools import _get_permission_pattern_for_path

    # Test file in /home/user/other/
    other_file = Path("/home/user/other/file.py")
    pattern = _get_permission_pattern_for_path("/home/user/other/file.py", other_file)

    assert pattern == "other/"
    assert pattern.endswith("/")


def test_permission_pattern_multiple_traversals_same_dir(mock_repo, monkeypatch):
    """Test that different path traversals to same directory produce same pattern."""
    # Mock REPO_ROOT
    monkeypatch.setattr("patchpal.tools.REPO_ROOT", mock_repo)

    from patchpal.tools import _get_permission_pattern_for_path

    tmp_file = Path("/tmp/test.py")

    # Different path traversals to /tmp/
    pattern1 = _get_permission_pattern_for_path("../../../../../tmp/test.py", tmp_file)
    pattern2 = _get_permission_pattern_for_path("../../tmp/test.py", tmp_file)

    # Both should produce same pattern
    assert pattern1 == pattern2 == "tmp/"


def test_apply_patch_uses_correct_pattern(mock_repo, monkeypatch, tmp_path):
    """Test that apply_patch uses directory-based pattern for outside-repo files."""
    # Setup
    monkeypatch.setattr("patchpal.tools.REPO_ROOT", mock_repo)
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "true")
    monkeypatch.setenv("PATCHPAL_READ_ONLY", "false")

    # Reload to pick up env vars
    import importlib

    import patchpal.permissions
    import patchpal.tools

    importlib.reload(patchpal.permissions)
    importlib.reload(patchpal.tools)

    # Re-apply repo root after reload
    monkeypatch.setattr("patchpal.tools.REPO_ROOT", mock_repo)

    # Track what pattern is passed to permission request
    captured_pattern = {}

    def mock_request_permission(self, tool_name, description, pattern=None):
        captured_pattern["pattern"] = pattern
        return False  # Deny to prevent actual file write

    monkeypatch.setattr(
        "patchpal.permissions.PermissionManager.request_permission", mock_request_permission
    )

    from patchpal.tools import apply_patch

    # Test writing to /tmp/ using path traversal
    tmp_file = tmp_path / "test_outside.txt"
    apply_patch(str(tmp_file), "test content")

    # Should use directory pattern (last component of parent)
    assert captured_pattern["pattern"].endswith("/")


def test_edit_file_uses_correct_pattern(mock_repo, monkeypatch, tmp_path):
    """Test that edit_file uses directory-based pattern for outside-repo files."""
    # Setup
    monkeypatch.setattr("patchpal.tools.REPO_ROOT", mock_repo)
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "true")
    monkeypatch.setenv("PATCHPAL_READ_ONLY", "false")

    # Reload to pick up env vars
    import importlib

    import patchpal.permissions
    import patchpal.tools

    importlib.reload(patchpal.permissions)
    importlib.reload(patchpal.tools)

    # Re-apply repo root after reload
    monkeypatch.setattr("patchpal.tools.REPO_ROOT", mock_repo)

    # Create test file outside repo
    test_file = tmp_path / "test_edit.txt"
    test_file.write_text("original content")

    # Track what pattern is passed to permission request
    captured_pattern = {}

    def mock_request_permission(self, tool_name, description, pattern=None):
        captured_pattern["pattern"] = pattern
        return False  # Deny to prevent actual edit

    monkeypatch.setattr(
        "patchpal.permissions.PermissionManager.request_permission", mock_request_permission
    )

    from patchpal.tools import edit_file

    # Test editing file outside repo
    edit_file(str(test_file), "original", "modified")

    # Should use directory pattern
    assert captured_pattern["pattern"].endswith("/")


def test_permission_pattern_consistency_across_tools(mock_repo, monkeypatch, tmp_path):
    """Test that apply_patch and edit_file use same pattern for same file."""
    # Setup
    monkeypatch.setattr("patchpal.tools.REPO_ROOT", mock_repo)
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "true")
    monkeypatch.setenv("PATCHPAL_READ_ONLY", "false")

    # Reload to pick up env vars
    import importlib

    import patchpal.permissions
    import patchpal.tools

    importlib.reload(patchpal.permissions)
    importlib.reload(patchpal.tools)

    # Re-apply repo root after reload
    monkeypatch.setattr("patchpal.tools.REPO_ROOT", mock_repo)

    test_file = tmp_path / "consistency_test.txt"
    test_file.write_text("original")

    captured_patterns = []

    def mock_request_permission(self, tool_name, description, pattern=None):
        captured_patterns.append(pattern)
        return False

    monkeypatch.setattr(
        "patchpal.permissions.PermissionManager.request_permission", mock_request_permission
    )

    from patchpal.tools import apply_patch, edit_file

    # Try both tools on same file
    apply_patch(str(test_file), "new content")
    edit_file(str(test_file), "original", "modified")

    # Both should use same pattern
    assert len(captured_patterns) == 2
    assert captured_patterns[0] == captured_patterns[1]
    assert captured_patterns[0].endswith("/")
