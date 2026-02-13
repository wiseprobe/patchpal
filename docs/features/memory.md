# Project Memory

PatchPal automatically loads project context from `~/.patchpal/<repo-name>/MEMORY.md` at startup. Use this file to store project-specific information, technical decisions, conventions, and known issues that persist across sessions. The agent can read and update this file to maintain continuity.

## What to Store in MEMORY.md

- **Project context**: What this project is and what it does
- **Important decisions**: Technical choices and why they were made
- **Key facts**: Deployment info, database details, API endpoints
- **Known issues**: Bugs to fix, technical debt, TODOs
- **Team conventions**: Code style preferences, workflow guidelines

## How It Works

When you start PatchPal in a git repository, it automatically:
1. Detects the repository name
2. Looks for `~/.patchpal/<repo-name>/MEMORY.md`
3. Loads the content into the agent's context
4. Makes it available for reference throughout the session

The agent can also read and update MEMORY.md during a session to maintain continuity across multiple sessions.

## Location

Memory files are stored per-repository in:
```
~/.patchpal/<repo-name>/MEMORY.md
```

For example, if you're working in a repository named `patchpal`, the memory file is at:
```
~/.patchpal/patchpal/MEMORY.md
```

## Availability

Project memory is available in:
- **CLI mode**: Loaded automatically at startup
- **Python API**: Loaded automatically when agent is created
- **Autopilot mode**: Available throughout autonomous execution

## Example MEMORY.md

```markdown
# Project Notes

This file persists across PatchPal sessions.

## Project Context
This is a REST API for managing user accounts built with FastAPI.

## Important Decisions
- Using PostgreSQL for the database (MySQL had performance issues)
- JWT tokens expire after 24 hours
- API rate limit: 100 requests per minute per IP

## Key Facts
- Production: https://api.example.com
- Database: PostgreSQL 14 on RDS
- Redis cache on ElastiCache

## Known Issues
- TODO: Add pagination to /users endpoint
- TODO: Implement proper error logging
- Technical debt: Refactor authentication module

## Team Conventions
- Use Black for code formatting
- All API endpoints require authentication except /health
- Write tests for all new endpoints
```
