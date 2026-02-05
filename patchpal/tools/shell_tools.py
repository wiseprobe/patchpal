"""Shell command execution tools."""

import subprocess
from typing import Optional

from patchpal.tools import common
from patchpal.tools.common import (
    FORBIDDEN,
    SHELL_TIMEOUT,
    OutputFilter,
    _get_permission_manager,
    _operation_limiter,
    audit_logger,
)


def _extract_shell_command_info(cmd: str) -> tuple[Optional[str], Optional[str]]:
    """Extract the meaningful command pattern and working directory from a shell command.

    Handles compound commands (&&, ||, ;, |) by identifying the primary
    command being executed and any cd commands that change the working directory.

    Args:
        cmd: The shell command string

    Returns:
        Tuple of (command_pattern, working_directory)
        - command_pattern: The primary command name (e.g., 'python')
        - working_directory: The directory if cd is used, None otherwise

    Examples:
        >>> _extract_shell_command_info("pytest tests/")
        ('pytest', None)
        >>> _extract_shell_command_info("cd /tmp && python script.py")
        ('python', '/tmp')
        >>> _extract_shell_command_info("cd src && ls -la | grep test")
        ('ls', 'src')
    """
    if not cmd or not cmd.strip():
        return None, None

    # Shell operators that indicate compound commands
    # Split by && and || first (they group tighter than ;)
    compound_operators = ["&&", "||", ";"]

    # Split by compound operators to find all sub-commands
    commands = [cmd]
    for op in compound_operators:
        new_commands = []
        for c in commands:
            # Split but keep track of which parts are commands
            parts = c.split(op)
            new_commands.extend(parts)
        commands = new_commands

    # Now also handle pipes within each command
    # Pipes are different - we want the first command in a pipe chain
    pipe_split_commands = []
    for c in commands:
        pipe_parts = c.split("|")
        # For pipes, we only care about the first command (before the pipe)
        pipe_split_commands.append(pipe_parts[0])

    commands = pipe_split_commands

    # Commands that change directory or set context (not the actual operation)
    context_commands = {"cd", "pushd", "popd"}
    setup_commands = {"export", "set", "unset", "source", "."}

    # Track if we see a cd command and what directory it goes to
    working_dir = None
    primary_command = None

    for command_part in commands:
        command_part = command_part.strip()
        if not command_part:
            continue

        tokens = command_part.split()
        if not tokens:
            continue

        first_token = tokens[0]

        # If it's a cd command, extract the target directory
        if first_token in context_commands:
            if first_token == "cd" and len(tokens) > 1:
                working_dir = tokens[1]
            continue

        # Skip setup commands
        if first_token in setup_commands:
            continue

        # This is the primary command
        if not primary_command:
            primary_command = first_token
            # If we already found the primary command, we're done
            # (don't need to look at commands after the main one)
            if working_dir is not None or first_token not in context_commands:
                break

    # If we didn't find a primary command (e.g., only "cd /tmp"), use first token
    if not primary_command:
        first_command = commands[0].strip() if commands else ""
        first_token = first_command.split()[0] if first_command.split() else None
        primary_command = first_token

    return primary_command, working_dir


def run_shell(cmd: str) -> str:
    """
    Run a safe shell command in the repository.

    Args:
        cmd: The shell command to execute

    Returns:
        Combined stdout and stderr output

    Raises:
        ValueError: If command contains forbidden operations
    """
    # Check permission before proceeding
    permission_manager = _get_permission_manager()
    description = f"   {cmd}"
    # Extract meaningful command pattern and working directory, handling compound commands
    command_name, working_dir = _extract_shell_command_info(cmd)

    # Create composite pattern: "command@directory" for cd commands, just "command" otherwise
    # Using @ separator for cross-platform compatibility (: would conflict with Windows paths like C:\temp)
    if working_dir and command_name:
        pattern = f"{command_name}@{working_dir}"
    else:
        pattern = command_name

    # Pass working_dir separately for display purposes
    if not permission_manager.request_permission(
        "run_shell", description, pattern=pattern, context=working_dir
    ):
        return "Operation cancelled by user."

    _operation_limiter.check_limit(f"run_shell({cmd[:50]}...)")

    # Basic token-based blocking
    if any(tok in FORBIDDEN for tok in cmd.split()):
        raise ValueError(
            f"Blocked dangerous command: {cmd}\nForbidden operations: {', '.join(FORBIDDEN)}"
        )

    # Additional pattern-based blocking
    dangerous_patterns = [
        "> /dev/",  # Writing to devices
        "rm -rf /",  # Recursive delete
        "| dd",  # Piping to dd
        "--force",  # Force flags often dangerous
    ]

    for pattern in dangerous_patterns:
        if pattern in cmd:
            raise ValueError(f"Blocked dangerous pattern in command: {pattern}")

    audit_logger.info(f"SHELL: {cmd}")

    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        cwd=common.REPO_ROOT,
        timeout=SHELL_TIMEOUT,
    )

    # Decode output with error handling for problematic characters
    # Use utf-8 on all platforms with 'replace' to handle encoding issues
    stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""

    output = stdout + stderr

    # Apply output filtering to reduce token usage
    if OutputFilter.should_filter(cmd):
        filtered_output = OutputFilter.filter_output(cmd, output)
        # Log if we filtered significantly
        original_lines = len(output.split("\n"))
        filtered_lines = len(filtered_output.split("\n"))
        if filtered_lines < original_lines * 0.5:
            audit_logger.info(
                f"SHELL_FILTER: Reduced output from {original_lines} to {filtered_lines} lines "
                f"(~{int((1 - filtered_lines / original_lines) * 100)}% reduction)"
            )
        return filtered_output

    return output
