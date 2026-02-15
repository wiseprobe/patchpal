# Skills System

Skills are reusable workflows and custom commands that can be invoked by name or discovered automatically by the agent.

## Creating Your Own Skills

1. **Choose a location:**
   - Personal skills (all projects): `~/.patchpal/skills/<skill-name>/SKILL.md`
   - Project-specific skills: `<repo>/.patchpal/skills/<skill-name>/SKILL.md`

2. **Create the skill file:**
```bash
# Create a personal skill
mkdir -p ~/.patchpal/skills/my-skill
cat > ~/.patchpal/skills/my-skill/SKILL.md <<'EOF'
---
name: my-skill
description: Brief description of what this skill does
---
# Instructions
Your detailed instructions here...
EOF
```

3. **Skill File Format:**
```markdown
---
name: skill-name
description: One-line description
---
# Detailed Instructions
- Step 1: Do this
- Step 2: Do that
- Use specific PatchPal tools like git_status, read_file, etc.
```

## Example Skills

The PatchPal repository includes [example skills](https://github.com/amaiya/patchpal/tree/main/examples) you can use as templates:
- **commit**: Best practices for creating git commits
- **review**: Comprehensive code review checklist
- **add-tests**: Add comprehensive pytest tests (includes code block templates)
- **slack-gif-creator**: Create animated GIFs for Slack (from [Anthropic's official skills repo](https://github.com/anthropics/skills), demonstrates Claude Code compatibility)
- **skill-creator**: Guide for creating effective skills with bundled scripts and references (from [Anthropic's official skills repo](https://github.com/anthropics/skills/tree/main/skills/skill-creator), demonstrates full bundled resources support)

**After `pip install patchpal`, get examples:**

```bash
# Quick way: Download examples directly from GitHub
curl -L https://github.com/amaiya/patchpal/archive/main.tar.gz | tar xz --strip=1 patchpal-main/examples

# Or clone the repository
git clone https://github.com/amaiya/patchpal.git
cd patchpal

# Copy examples to your personal skills directory
cp -r examples/skills/commit ~/.patchpal/skills/
cp -r examples/skills/review ~/.patchpal/skills/
cp -r examples/skills/skill-creator ~/.patchpal/skills/
```

**View examples online:**
Browse the [examples/skills/](https://github.com/amaiya/patchpal/tree/main/examples/skills) directory on GitHub to see the skill format and create your own.

You can also try out the example skills at [anthropic/skills](https://github.com/anthropics/skills).


## Using Skills

There are two ways to invoke skills:

1. **Direct invocation** - Type `/skillname` at the prompt:
```bash
$ patchpal
You: /commit Fix authentication bug
```

2. **Natural language** - Just ask, and the agent discovers the right skill:
```bash
You: Help me commit these changes following best practices
# Agent automatically discovers and uses the commit skill
```

## Finding Available Skills

Ask the agent to list them:
```bash
You: list skills
```

## Skill Priority

Project skills (`.patchpal/skills/`) override personal skills (`~/.patchpal/skills/`) with the same name.
