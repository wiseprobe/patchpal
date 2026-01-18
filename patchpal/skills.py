"""Skills system for PatchPal - inspired by Claude Code's skills.

Skills are reusable workflows/prompts defined as markdown files with YAML frontmatter.
They can be invoked manually via /skillname or discovered and used by the agent.
"""

from pathlib import Path
from typing import Dict, List, Optional

import yaml


class Skill:
    """Represents a PatchPal skill."""

    def __init__(self, name: str, description: str, instructions: str, path: Path):
        self.name = name
        self.description = description
        self.instructions = instructions
        self.path = path

    def __repr__(self):
        return f"Skill(name={self.name}, description={self.description[:50]}...)"


def _parse_skill_file(skill_path: Path) -> Optional[Skill]:
    """Parse a SKILL.md file with YAML frontmatter.

    Args:
        skill_path: Path to SKILL.md file

    Returns:
        Skill object or None if parsing fails

    Example SKILL.md:
        ---
        name: my-skill
        description: Does something useful
        ---
        # Instructions
        Do this and that...
    """
    try:
        content = skill_path.read_text()

        # Check for YAML frontmatter
        if not content.startswith("---"):
            return None

        # Split frontmatter and content
        parts = content.split("---", 2)
        if len(parts) < 3:
            return None

        frontmatter = parts[1].strip()
        instructions = parts[2].strip()

        # Parse YAML
        metadata = yaml.safe_load(frontmatter)
        if not metadata or "name" not in metadata or "description" not in metadata:
            return None

        return Skill(
            name=metadata["name"],
            description=metadata["description"],
            instructions=instructions,
            path=skill_path,
        )
    except Exception:
        return None


def discover_skills(repo_root: Optional[Path] = None) -> Dict[str, Skill]:
    """Discover all available skills from personal and project directories.

    Args:
        repo_root: Repository root path (for project-specific skills)

    Returns:
        Dictionary mapping skill names to Skill objects
    """
    skills = {}

    # Personal skills: ~/.patchpal/skills/
    personal_skills_dir = Path.home() / ".patchpal" / "skills"
    if personal_skills_dir.exists():
        for skill_dir in personal_skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_file = skill_dir / "SKILL.md"
                if skill_file.exists():
                    skill = _parse_skill_file(skill_file)
                    if skill:
                        skills[skill.name] = skill

    # Project-specific skills: <repo>/.patchpal/skills/
    if repo_root:
        project_skills_dir = repo_root / ".patchpal" / "skills"
        if project_skills_dir.exists():
            for skill_dir in project_skills_dir.iterdir():
                if skill_dir.is_dir():
                    skill_file = skill_dir / "SKILL.md"
                    if skill_file.exists():
                        skill = _parse_skill_file(skill_file)
                        if skill:
                            # Project skills override personal skills
                            skills[skill.name] = skill

    return skills


def list_skills(repo_root: Optional[Path] = None) -> List[Skill]:
    """Get a list of all available skills.

    Args:
        repo_root: Repository root path

    Returns:
        List of Skill objects sorted by name
    """
    skills = discover_skills(repo_root)
    return sorted(skills.values(), key=lambda s: s.name)


def get_skill(name: str, repo_root: Optional[Path] = None) -> Optional[Skill]:
    """Get a specific skill by name.

    Args:
        name: Skill name
        repo_root: Repository root path

    Returns:
        Skill object or None if not found
    """
    skills = discover_skills(repo_root)
    return skills.get(name)
