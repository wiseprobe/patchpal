# Skills API

The Skills system allows you to create reusable workflows and custom commands.

## Skills Management

### discover_skills

::: patchpal.skills.discover_skills
    options:
      show_root_heading: true
      heading_level: 4

### list_skills

::: patchpal.skills.list_skills
    options:
      show_root_heading: true
      heading_level: 4

### get_skill

::: patchpal.skills.get_skill
    options:
      show_root_heading: true
      heading_level: 4

## Skill Class

::: patchpal.skills.Skill
    options:
      show_root_heading: true
      heading_level: 3

## Usage Example

```python
from patchpal.skills import list_skills, get_skill

# List all available skills
skills = list_skills()
for skill in skills:
    print(f"/{skill.name} - {skill.description}")

# Get a specific skill
skill = get_skill("commit")
if skill:
    print(f"Name: {skill.name}")
    print(f"Description: {skill.description}")
    print(f"Instructions:\n{skill.instructions}")
```

## Creating Skills Programmatically

While skills are typically defined as markdown files, you can also work with them programmatically:

```python
from pathlib import Path
from patchpal.skills import discover_skills

# Discover all skills in the repository and personal directories
repo_root = Path.cwd()
skills_dict = discover_skills(repo_root)

# Skills are keyed by name
for skill_name, skill in skills_dict.items():
    print(f"{skill_name}: {skill.description}")
```

## Skill File Format

Skills are markdown files with YAML frontmatter:

```markdown
---
name: myskill
description: A custom skill that does something useful
---

Instructions for the agent...

1. First do this
2. Then do that
3. Finally, complete the task
```

## Related

- [Skills System Guide](../features/skills.md) - Complete guide to creating and using skills
- [Agent API](agent.md) - Using skills through the agent
- [use_skill tool](tools.md#use_skill) - Invoking skills programmatically
