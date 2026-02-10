# Interactive Usage

Simply run the `patchpal` command and type your requests interactively:

```bash
$ patchpal
 ╔═══════════════════════════════════════════════════════════╗
 ║  PatchPal - AI Coding and Automation Assistant  🤖        ║
 ╚═══════════════════════════════════════════════════════════╝

Using model: anthropic/claude-sonnet-4-5

Type 'exit' to quit or '/help' to see available commands.

You: Add type hints and basic logging to my_module.py
```

The agent will process your request and show you the results. You can continue with follow-up tasks or type `exit` to quit.

## Interactive Features

- **Path Autocompletion**: Press `Tab` while typing file paths to see suggestions (e.g., `./src/mo` + Tab → `./src/models.py`)
- **Skill Autocompletion**: Type `/` followed by Tab to see available skills (e.g., `/comm` + Tab → `/commit`)
- **Command History**: Use ↑ (up arrow) and ↓ (down arrow) to navigate through previous commands within the current session
- **Interrupt Agent**: Press `Ctrl-C` during agent execution to stop the current task without exiting PatchPal
- **Exit**: Type `exit`, `quit`, or press `Ctrl-C` at the prompt to exit PatchPal
- **Project Memory**: PatchPal automatically loads project context from `~/.patchpal/<repo-name>/MEMORY.md` at startup. Use this file to store project-specific information, technical decisions, conventions, and known issues that persist across sessions. The agent can read and update this file to maintain continuity.
