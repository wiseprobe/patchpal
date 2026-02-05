"""TODO management system for multi-step tasks."""

from datetime import datetime

from patchpal.tools.common import (
    _operation_limiter,
    audit_logger,
)

# ============================================================================
# TODO Management System
# ============================================================================
# Session-scoped TODO list for complex multi-step tasks
# Tasks are stored in-memory and reset when a new session starts

# Session-level TODO storage (resets each session)
_session_todos: dict = {"tasks": [], "next_id": 1}


def reset_session_todos():
    """Reset the session TODO list. Called when starting a new session."""
    global _session_todos
    _session_todos = {"tasks": [], "next_id": 1}
    audit_logger.info("TODO: Session todos reset")


def _load_todos() -> dict:
    """Get the session todos."""
    return _session_todos


def _save_todos(data: dict):
    """Save todos to session storage."""
    global _session_todos
    _session_todos = data
    audit_logger.info(f"TODOS: Updated session with {len(data['tasks'])} tasks")


def todo_add(description: str, details: str = "") -> str:
    """
    Add a new task to the TODO list.

    Use this to break down complex tasks into manageable subtasks.
    Each task gets a unique ID for tracking and completion.

    Args:
        description: Brief task description (one line)
        details: Optional detailed notes about the task

    Returns:
        Confirmation with the task ID

    Example:
        todo_add("Read authentication module", details="Focus on session handling logic")
        todo_add("Add input validation to login endpoint")
    """
    _operation_limiter.check_limit(f"todo_add({description[:30]}...)")

    data = _load_todos()

    # Create new task
    task = {
        "id": data["next_id"],
        "description": description,
        "details": details,
        "completed": False,
        "created_at": datetime.now().isoformat(),
    }

    data["tasks"].append(task)
    data["next_id"] += 1

    _save_todos(data)

    result = f"✓ Added task #{task['id']}: {description}"
    if details:
        result += f"\n  Details: {details}"

    audit_logger.info(f"TODO_ADD: #{task['id']} - {description[:50]}")
    return result


def todo_list(show_completed: bool = False) -> str:
    """
    List all tasks in the TODO list.

    Args:
        show_completed: If True, show completed tasks; if False, show only pending tasks (default: False)

    Returns:
        Formatted list of tasks with IDs, status, and descriptions
    """
    _operation_limiter.check_limit("todo_list()")

    data = _load_todos()
    tasks = data["tasks"]

    if not tasks:
        return "No tasks in TODO list.\n\nUse todo_add() to create a new task plan."

    # Filter tasks based on show_completed
    if show_completed:
        display_tasks = tasks
        header = "TODO List (All Tasks):"
    else:
        display_tasks = [t for t in tasks if not t["completed"]]
        header = "TODO List (Pending Tasks):"
        if not display_tasks:
            return "No pending tasks. All tasks completed! ✓\n\nUse todo_list(show_completed=True) to see completed tasks."

    separator = "=" * 80

    lines = [header, separator]

    for task in display_tasks:
        status = "✓" if task["completed"] else "○"
        lines.append(f"\n{status} Task #{task['id']}: {task['description']}")

        if task.get("details"):
            # Indent details
            detail_lines = task["details"].split("\n")
            for line in detail_lines:
                lines.append(f"  {line}")

        # Show creation time
        try:
            created = datetime.fromisoformat(task["created_at"])
            lines.append(f"  Created: {created.strftime('%Y-%m-%d %H:%M')}")
        except Exception:
            pass

        # Show completion time if completed
        if task["completed"] and task.get("completed_at"):
            try:
                completed = datetime.fromisoformat(task["completed_at"])
                lines.append(f"  Completed: {completed.strftime('%Y-%m-%d %H:%M')}")
            except Exception:
                pass

    # Summary
    total = len(tasks)
    completed = sum(1 for t in tasks if t["completed"])
    pending = total - completed

    lines.append(f"\n{separator}")
    lines.append(f"Summary: {pending} pending, {completed} completed, {total} total")

    audit_logger.info(f"TODO_LIST: {pending} pending, {completed} completed")
    return "\n".join(lines)


def todo_complete(task_id: int) -> str:
    """
    Mark a task as completed.

    Args:
        task_id: The ID of the task to complete

    Returns:
        Confirmation message

    Example:
        todo_complete(1)  # Mark task #1 as done
    """
    _operation_limiter.check_limit(f"todo_complete({task_id})")

    data = _load_todos()

    # Find the task
    task = None
    for t in data["tasks"]:
        if t["id"] == task_id:
            task = t
            break

    if not task:
        available_ids = [t["id"] for t in data["tasks"]]
        return f"Task #{task_id} not found.\n\nAvailable task IDs: {available_ids}\n\nUse todo_list() to see all tasks."

    if task["completed"]:
        return f"Task #{task_id} is already completed: {task['description']}"

    # Mark as completed
    task["completed"] = True
    task["completed_at"] = datetime.now().isoformat()

    _save_todos(data)

    # Show progress
    total = len(data["tasks"])
    completed = sum(1 for t in data["tasks"] if t["completed"])

    result = f"✓ Completed task #{task_id}: {task['description']}"
    result += f"\n\nProgress: {completed}/{total} tasks completed"

    audit_logger.info(f"TODO_COMPLETE: #{task_id} - {task['description'][:50]}")
    return result


def todo_update(task_id: int, description: str = None, details: str = None) -> str:
    """
    Update a task's description or details.

    Args:
        task_id: The ID of the task to update
        description: New description (optional)
        details: New details (optional)

    Returns:
        Confirmation message

    Example:
        todo_update(1, description="Read auth module and session handling")
        todo_update(2, details="Need to check for SQL injection vulnerabilities")
    """
    _operation_limiter.check_limit(f"todo_update({task_id})")

    if description is None and details is None:
        return "Error: Must provide either description or details to update"

    data = _load_todos()

    # Find the task
    task = None
    for t in data["tasks"]:
        if t["id"] == task_id:
            task = t
            break

    if not task:
        available_ids = [t["id"] for t in data["tasks"]]
        return f"Task #{task_id} not found.\n\nAvailable task IDs: {available_ids}"

    # Update fields
    changes = []
    if description is not None:
        old_desc = task["description"]
        task["description"] = description
        changes.append(f"Description: '{old_desc}' → '{description}'")

    if details is not None:
        task["details"] = details
        changes.append("Details updated")

    _save_todos(data)

    result = f"✓ Updated task #{task_id}\n"
    result += "\n".join(f"  • {change}" for change in changes)

    audit_logger.info(f"TODO_UPDATE: #{task_id} - {changes}")
    return result


def todo_remove(task_id: int) -> str:
    """
    Remove a task from the TODO list.

    Args:
        task_id: The ID of the task to remove

    Returns:
        Confirmation message

    Example:
        todo_remove(1)  # Remove task #1
    """
    _operation_limiter.check_limit(f"todo_remove({task_id})")

    data = _load_todos()

    # Find and remove the task
    task = None
    for i, t in enumerate(data["tasks"]):
        if t["id"] == task_id:
            task = data["tasks"].pop(i)
            break

    if not task:
        available_ids = [t["id"] for t in data["tasks"]]
        return f"Task #{task_id} not found.\n\nAvailable task IDs: {available_ids}"

    _save_todos(data)

    result = f"✓ Removed task #{task_id}: {task['description']}"
    remaining = len(data["tasks"])
    result += f"\n\n{remaining} task(s) remaining in TODO list"

    audit_logger.info(f"TODO_REMOVE: #{task_id} - {task['description'][:50]}")
    return result


def todo_clear(completed_only: bool = True) -> str:
    """
    Clear tasks from the TODO list.

    Args:
        completed_only: If True, clear only completed tasks; if False, clear all tasks (default: True)

    Returns:
        Confirmation message

    Example:
        todo_clear()              # Clear completed tasks
        todo_clear(completed_only=False)  # Clear all tasks (start fresh)
    """
    _operation_limiter.check_limit("todo_clear()")

    data = _load_todos()

    if not data["tasks"]:
        return "TODO list is already empty."

    if completed_only:
        completed_tasks = [t for t in data["tasks"] if t["completed"]]
        if not completed_tasks:
            return "No completed tasks to clear."

        # Keep only pending tasks
        data["tasks"] = [t for t in data["tasks"] if not t["completed"]]
        count = len(completed_tasks)
        _save_todos(data)

        result = f"✓ Cleared {count} completed task(s)"
        remaining = len(data["tasks"])
        if remaining > 0:
            result += f"\n\n{remaining} pending task(s) remaining"
    else:
        # Clear all tasks
        count = len(data["tasks"])
        data["tasks"] = []
        _save_todos(data)

        result = f"✓ Cleared all {count} task(s)\n\nTODO list is now empty. Use todo_add() to create a new task plan."

    audit_logger.info(f"TODO_CLEAR: {count} task(s) cleared (completed_only={completed_only})")
    return result
