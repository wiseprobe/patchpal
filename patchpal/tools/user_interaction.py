"""User interaction tools (ask questions, list/use skills)."""

from typing import Optional

from patchpal.tools import common
from patchpal.tools.common import (
    _operation_limiter,
    audit_logger,
)


def list_skills() -> str:
    """
    List all available skills that can be invoked.

    Skills are reusable workflows stored in:
    - Personal: ~/.patchpal/skills/
    - Project: <repo>/.patchpal/skills/

    Returns:
        Formatted list of available skills with names and descriptions
    """
    _operation_limiter.check_limit("list_skills()")

    from patchpal.skills import list_skills as discover_all_skills

    skills = discover_all_skills(repo_root=common.REPO_ROOT)

    if not skills:
        return """No skills found.

To get started:
1. View examples: https://github.com/wiseprobe/patchpal/tree/main/examples/skills
2. Copy examples to your personal skills directory:
   mkdir -p ~/.patchpal/skills
   # Download and copy the commit and review skills from the examples folder
3. Or create your own skill in ~/.patchpal/skills/<skill-name>/SKILL.md

Skills are markdown files with YAML frontmatter. See the examples for the format."""

    header = f"Available Skills ({len(skills)}):"
    separator = "-" * 100

    lines = [header, separator]
    for skill in skills:
        lines.append(f"  /{skill.name}")
        lines.append(f"    {skill.description}")
        lines.append("")

    lines.append("How to invoke skills:")
    lines.append("  - User types: /skill_name (e.g., /commit)")
    lines.append("  - Or just ask naturally and the agent will discover the right skill")

    audit_logger.info(f"LIST_SKILLS: {len(skills)} skill(s)")
    return "\n".join(lines)


def use_skill(skill_name: str, args: str = "") -> str:
    """
    Invoke a skill with optional arguments.

    Args:
        skill_name: Name of the skill to invoke (without / prefix)
        args: Optional arguments to pass to the skill

    Returns:
        The skill's instructions formatted with any provided arguments

    Example:
        use_skill("commit", args="Fix bug in auth")
    """
    _operation_limiter.check_limit(f"use_skill({skill_name})")

    from patchpal.skills import get_skill

    skill = get_skill(skill_name, repo_root=common.REPO_ROOT)

    if not skill:
        available_skills = list_skills()
        return f"Skill not found: {skill_name}\n\n{available_skills}"

    # Format the skill instructions with arguments if provided
    instructions = skill.instructions
    if args:
        instructions = f"{instructions}\n\nArguments: {args}"

    audit_logger.info(f"USE_SKILL: {skill_name} (args={args[:50]})")

    return f"Skill: {skill.name}\n\n{instructions}"


# ============================================================================
# User Interaction - Ask Questions
# ============================================================================


def ask_user(question: str, options: Optional[list] = None) -> str:
    """
    Ask the user a question and wait for their response.

    This allows the agent to interactively clarify requirements, get decisions,
    or gather additional information during task execution.

    Args:
        question: The question to ask the user
        options: Optional list of predefined answer choices (e.g., ["yes", "no", "skip"])
                If provided, user can select from these or type a custom answer

    Returns:
        The user's answer as a string

    Example:
        ask_user("Which authentication method should I use?", options=["JWT", "OAuth2", "Session"])
        ask_user("Should I add error handling to all endpoints?")
    """
    _operation_limiter.check_limit(f"ask_user({question[:30]}...)")

    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt

    console = Console()

    # Format the question in a panel
    console.print()
    console.print(
        Panel(
            question,
            title="[bold cyan]Question from Agent[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    # Show options if provided
    if options:
        console.print("\n[bold]Available options:[/bold]")
        for i, option in enumerate(options, 1):
            console.print(f"  {i}. {option}")
        console.print(
            "\n[dim]You can select a number, type an option, or provide a custom answer.[/dim]\n"
        )

        # Get user input
        user_input = Prompt.ask("[bold green]Your answer[/bold green]")

        # Check if user entered a number corresponding to an option
        try:
            choice_num = int(user_input)
            if 1 <= choice_num <= len(options):
                answer = options[choice_num - 1]
                console.print(f"[dim]Selected: {answer}[/dim]\n")
            else:
                answer = user_input
        except ValueError:
            # Not a number, use as-is
            answer = user_input
    else:
        # No options, just get free-form answer
        answer = Prompt.ask("[bold green]Your answer[/bold green]")
        console.print()

    audit_logger.info(f"ASK_USER: Q: {question[:50]}... A: {answer[:50]}")
    return answer
