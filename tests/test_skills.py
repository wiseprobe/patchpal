"""Tests for patchpal.skills module."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_repo(monkeypatch):
    """Create a temporary repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Monkey-patch REPO_ROOT
        monkeypatch.setattr("patchpal.tools.REPO_ROOT", tmpdir_path)

        # Disable permission prompts during tests
        monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

        # Reset operation counter before each test
        from patchpal.tools import reset_operation_counter

        reset_operation_counter()

        yield tmpdir_path


def test_parse_skill_file():
    """Test parsing a valid SKILL.md file."""
    from patchpal.skills import _parse_skill_file

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            """---
name: test-skill
description: A test skill
---
# Instructions
Do this and that."""
        )
        f.flush()

        skill = _parse_skill_file(Path(f.name))
        assert skill is not None
        assert skill.name == "test-skill"
        assert skill.description == "A test skill"
        assert "Do this and that" in skill.instructions

    Path(f.name).unlink()


def test_parse_skill_file_missing_frontmatter():
    """Test parsing a file without frontmatter."""
    from patchpal.skills import _parse_skill_file

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write("# Just some markdown")
        f.flush()

        skill = _parse_skill_file(Path(f.name))
        assert skill is None

    Path(f.name).unlink()


def test_parse_skill_file_incomplete_metadata():
    """Test parsing a file with incomplete metadata."""
    from patchpal.skills import _parse_skill_file

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        f.write(
            """---
name: test-skill
---
# Instructions"""
        )
        f.flush()

        skill = _parse_skill_file(Path(f.name))
        assert skill is None

    Path(f.name).unlink()


def test_discover_skills_personal():
    """Test discovering skills from personal directory."""
    from patchpal.skills import discover_skills

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create personal skills directory
        skills_dir = Path(tmpdir) / ".patchpal" / "skills" / "my-skill"
        skills_dir.mkdir(parents=True)

        skill_file = skills_dir / "SKILL.md"
        skill_file.write_text(
            """---
name: my-skill
description: My personal skill
---
# Do something"""
        )

        # Monkey patch home directory

        original_home = Path.home
        Path.home = lambda: Path(tmpdir)

        try:
            skills = discover_skills()
            assert "my-skill" in skills
            assert skills["my-skill"].name == "my-skill"
        finally:
            Path.home = original_home


def test_discover_skills_project():
    """Test discovering skills from project directory."""
    from patchpal.skills import discover_skills

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Create project skills directory
        skills_dir = repo_root / ".patchpal" / "skills" / "project-skill"
        skills_dir.mkdir(parents=True)

        skill_file = skills_dir / "SKILL.md"
        skill_file.write_text(
            """---
name: project-skill
description: Project specific skill
---
# Do project stuff"""
        )

        skills = discover_skills(repo_root=repo_root)
        assert "project-skill" in skills
        assert skills["project-skill"].description == "Project specific skill"


def test_discover_skills_project_overrides_personal():
    """Test that project skills override personal skills."""
    from patchpal.skills import discover_skills

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir) / "repo"
        repo_root.mkdir()

        # Create personal skill
        personal_skills_dir = Path(tmpdir) / ".patchpal" / "skills" / "shared-skill"
        personal_skills_dir.mkdir(parents=True)
        (personal_skills_dir / "SKILL.md").write_text(
            """---
name: shared-skill
description: Personal version
---
# Personal instructions"""
        )

        # Create project skill with same name
        project_skills_dir = repo_root / ".patchpal" / "skills" / "shared-skill"
        project_skills_dir.mkdir(parents=True)
        (project_skills_dir / "SKILL.md").write_text(
            """---
name: shared-skill
description: Project version
---
# Project instructions"""
        )

        # Monkey patch home directory

        original_home = Path.home
        Path.home = lambda: Path(tmpdir)

        try:
            skills = discover_skills(repo_root=repo_root)
            assert "shared-skill" in skills
            # Project version should override
            assert skills["shared-skill"].description == "Project version"
        finally:
            Path.home = original_home


def test_list_skills():
    """Test list_skills returns sorted list."""
    from patchpal.skills import list_skills

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Create multiple skills
        for skill_name in ["zebra-skill", "alpha-skill", "middle-skill"]:
            skills_dir = repo_root / ".patchpal" / "skills" / skill_name
            skills_dir.mkdir(parents=True)
            (skills_dir / "SKILL.md").write_text(
                f"""---
name: {skill_name}
description: Test skill {skill_name}
---
# Instructions"""
            )

        # Monkey patch home directory to avoid discovering personal skills

        original_home = Path.home
        Path.home = lambda: Path(tmpdir) / "home"

        try:
            skills = list_skills(repo_root=repo_root)
            assert len(skills) == 3
            # Should be sorted by name
            assert skills[0].name == "alpha-skill"
            assert skills[1].name == "middle-skill"
            assert skills[2].name == "zebra-skill"
        finally:
            Path.home = original_home


def test_get_skill():
    """Test getting a specific skill by name."""
    from patchpal.skills import get_skill

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)

        # Create a skill
        skills_dir = repo_root / ".patchpal" / "skills" / "test-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text(
            """---
name: test-skill
description: A test skill
---
# Instructions"""
        )

        # Monkey patch home directory to avoid discovering personal skills

        original_home = Path.home
        Path.home = lambda: Path(tmpdir) / "home"

        try:
            skill = get_skill("test-skill", repo_root=repo_root)
            assert skill is not None
            assert skill.name == "test-skill"

            # Non-existent skill
            skill = get_skill("nonexistent", repo_root=repo_root)
            assert skill is None
        finally:
            Path.home = original_home


def test_list_skills_tool(temp_repo, monkeypatch):
    """Test list_skills tool integration."""
    from patchpal.tools import list_skills

    # Disable permission requirement
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

    # Create a skill in temp repo
    skills_dir = temp_repo / ".patchpal" / "skills" / "test-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        """---
name: test-skill
description: A test skill
---
# Do something"""
    )

    result = list_skills()
    assert "test-skill" in result
    assert "A test skill" in result
    assert "/test-skill" in result


def test_use_skill_tool(temp_repo, monkeypatch):
    """Test use_skill tool integration."""
    from patchpal.tools import use_skill

    # Disable permission requirement
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

    # Create a skill in temp repo
    skills_dir = temp_repo / ".patchpal" / "skills" / "commit-skill"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        """---
name: commit-skill
description: Create a commit
---
# Commit Instructions
1. Stage changes
2. Create commit with message"""
    )

    result = use_skill("commit-skill", args="Fix bug")
    assert "Commit Instructions" in result
    assert "Arguments: Fix bug" in result


def test_use_skill_not_found(temp_repo, monkeypatch):
    """Test use_skill with non-existent skill."""
    from patchpal.tools import use_skill

    # Disable permission requirement
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

    result = use_skill("nonexistent")
    assert "Skill not found" in result
    assert "nonexistent" in result
