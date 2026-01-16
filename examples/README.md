# PatchPal Examples

This directory contains example skills and configurations for PatchPal.

## Skills

Example skills demonstrate how to create reusable workflows:

### Available Examples

- **commit**: Best practices for creating git commits with proper formatting
- **review**: Comprehensive code review checklist
- **add-tests**: Add comprehensive pytest tests with code templates and examples

### Using These Examples

Copy any skill to your personal skills directory to use it across all projects:

```bash
# Copy all examples
cp -r examples/skills/* ~/.patchpal/skills/

# Or copy individual skills
cp -r examples/skills/commit ~/.patchpal/skills/
cp -r examples/skills/review ~/.patchpal/skills/
cp -r examples/skills/add-tests ~/.patchpal/skills/
```

For project-specific skills, copy to your repository:

```bash
mkdir -p .patchpal/skills
cp -r examples/skills/commit .patchpal/skills/
```

### Creating Your Own Skills

1. Create a directory: `~/.patchpal/skills/<your-skill-name>/`
2. Add a `SKILL.md` file with YAML frontmatter:

```markdown
---
name: your-skill-name
description: What your skill does
---
# Instructions
Your step-by-step instructions here...
```

3. Invoke with `/your-skill-name` or let the agent discover it automatically

See the example skills for inspiration!
