# PatchPal — An Agentic Coding and Automation Assistant

<img src="https://raw.githubusercontent.com/wiseprobe/patchpal/refs/heads/main/assets/patchpal_screenshot.png" alt="PatchPal Screenshot" width="650"/>

> Supporting both local and cloud LLMs, with autopilot mode and extensible tools.

[**PatchPal**](https://github.com/wiseprobe/patchpal) is an AI coding agent that helps you build software, debug issues, and automate tasks. It supports agent skills, tool use, and executable Python generation, enabling interactive workflows for tasks such as data analysis, visualization, web scraping, API interactions, and research with synthesized findings.

Interactive coding agents (e.g., Claude Code, OpenCode, Aider) are typically mutually exclusive with programmatic agent frameworks (e.g., smolagents, PydanticAI). A key goal of this project is to marry both: use the same agent interactively in your terminal (`patchpal`) or in Python scripts (`agent.run("task")`), plus autopilot mode for autonomous runs.

**Key Features**

- [Terminal Interface](usage/interactive.md) for interactive development
- [Python API](usage/python-api.md) for flexibility and extensibility
- [Built-In](features/tools.md) and [Custom Tools](features/custom-tools.md)
- [Skills System](features/skills.md)
- [Autopilot Mode](usage/autopilot.md) using [Ralph Wiggum loops](https://ghuntley.com/ralph/)
- [Project Memory](features/memory.md) automatically loads project context from `~/.patchpal/<repo-name>/MEMORY.md` at startup.

PatchPal prioritizes customizability: custom tools, custom skills, a flexible Python API, and support for any tool-calling LLM.

## Quick Start

```bash
$ pip install patchpal  # install
$ patchpal              # start
```

## Beyond Coding: General Problem-Solving

While originally designed for software development, PatchPal is also a general-      purpose assistant. With web search, file operations, shell commands, and custom      tools/skills, it can help with research, data analysis, document processing, log     file analyses, etc.

<img src="https://raw.githubusercontent.com/wiseprobe/patchpal/refs/heads/main/assets/patchpal_assistant.png" alt="PatchPal as General Assistant" width="650"/>
