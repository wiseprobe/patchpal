# PatchPal — A Claude Code–Style Agent in Python

<img src="https://raw.githubusercontent.com/wiseprobe/patchpal/refs/heads/main/patchpal_screenshot.png" alt="PatchPal Screenshot" width="650"/>

> An agentic coding and automation assistant, supporting both local and cloud LLMs.

**PatchPal** is an AI coding agent that helps you build software, debug issues, and automate tasks.  Like Claude Code, it supports agent skills, tool use, and executable Python generation, enabling interactive workflows for tasks such as data analysis, visualization, web scraping, API interactions, and research with synthesized findings.

A key goal of this project is to approximate Claude Code's core functionality while remaining lean, accessible, and configurable, enabling learning, experimentation, and broad applicability across use cases.

```bash
$ls ./patchpal
__init__.py agent.py  cli.py context.py permissions.py  skills.py system_prompt.md tool_schema.py tools
```

## Quick Start

```bash
$ pip install patchpal  # install
$ patchpal              # start
```
