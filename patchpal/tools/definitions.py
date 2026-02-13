"""Tool definitions for PatchPal agent.

This module contains the tool schemas (in LiteLLM format) and the mapping
from tool names to their implementation functions.
"""

from patchpal.tools import (
    apply_patch,
    ask_user,
    code_structure,
    count_lines,
    edit_file,
    find_files,
    get_file_info,
    get_repo_map,
    git_diff,
    git_log,
    git_status,
    grep,
    list_files,
    list_skills,
    read_file,
    read_lines,
    run_shell,
    todo_add,
    todo_clear,
    todo_complete,
    todo_list,
    todo_remove,
    todo_update,
    tree,
    use_skill,
    web_fetch,
    web_search,
)
from patchpal.tools.mcp import load_mcp_tools

# Define tools in LiteLLM format
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. Can read files anywhere on the system (repository files, system configs like /etc/fstab, logs, etc.) for automation and debugging. Supports PDF, DOCX, PPTX extraction. Sensitive files (.env, credentials) are blocked for safety.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file - can be relative to repository root or an absolute path (e.g., /etc/fstab, /var/log/app.log)",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_lines",
            "description": "Read specific lines from a file without loading the entire file. Useful for viewing code sections, error context, or specific regions of large files. More efficient than read_file when you only need a few lines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file - can be relative to repository root or an absolute path",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number (1-indexed)",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Ending line number (inclusive, 1-indexed). If omitted, reads only start_line",
                    },
                },
                "required": ["path", "start_line"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "count_lines",
            "description": "Count the number of lines in a file efficiently (useful before read_lines to find total line count)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file - can be relative to repository root or an absolute path",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "code_structure",
            "description": "Analyze code structure using tree-sitter AST parsing without reading the full file. Returns a compact overview showing functions, classes, methods with their line numbers and signatures. Much more efficient than read_file for understanding large code files. Supports 40+ languages including Python, JavaScript, TypeScript, Go, Rust, Java, C/C++. Use this BEFORE read_file when exploring unfamiliar code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the code file to analyze - can be relative to repository root or absolute path",
                    },
                    "max_symbols": {
                        "type": "integer",
                        "description": "Maximum number of symbols (functions/classes) to show (default: 50)",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_repo_map",
            "description": """Generate a repository map showing code structure across the entire codebase.

This provides a consolidated view of ALL files in the repository, showing function and class
signatures without implementations. More efficient than calling code_structure on each file individually.

Use this when you need to:
- Understand the overall codebase structure
- Find relevant files without analyzing them all
- Discover related code across the project
- Get oriented in an unfamiliar codebase

Supports 20+ languages: Python, JavaScript, TypeScript, Go, Rust, Java, C/C++, C#, Ruby,
PHP, Swift, Kotlin, Scala, Elm, Elixir, and more. Language detection is automatic.

Token efficiency: 38-70% reduction compared to calling code_structure on each file
(e.g., 20 files: 4,916 tokens vs 1,459 tokens = 70% savings; 37 files: 8,052 tokens vs 4,988 tokens = 38% savings)
Combines multiple file structures into one compact output with reduced redundant formatting.

Tip: Read README first for context when exploring repositories.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_files": {
                        "type": "integer",
                        "description": "Maximum number of files to include in the map (default: 100)",
                    },
                    "include_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Glob patterns to include (e.g., ['*.py', 'src/**/*.js']). If specified, only matching files are included.",
                    },
                    "exclude_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Glob patterns to exclude (e.g., ['*test*', '*_pb2.py', 'vendor/**']). Useful for filtering out generated code, tests, or dependencies.",
                    },
                    "focus_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files to prioritize in the output (e.g., files mentioned in conversation). These appear first in the map.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List ALL files in the ENTIRE repository - no filtering by directory. This tool shows every file across all folders. To list files in a specific directory, use the 'tree' tool with a path parameter instead.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_info",
            "description": "Get detailed metadata for file(s) - size, modification time, type. Works with any file on the system. Supports single files, directories, or glob patterns (e.g., 'tests/*.py', '/etc/*.conf').",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to file, directory, or glob pattern - can be relative or absolute (e.g., 'tests/*.txt', '/var/log/', '/etc/fstab')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_files",
            "description": "Find files by name pattern using glob-style wildcards (e.g., '*.py', 'test_*.txt', '**/*.md'). Faster than list_files when searching for specific file names.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match file names (e.g., '*.py' for Python files, 'test_*.py' for test files)",
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether to match case-sensitively (default: true)",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tree",
            "description": "Show directory tree structure for a specific directory path. Use this to list files in a particular folder (e.g., './tests', 'src/components'). Works with any directory on the system - repository folders, /etc, /var/log, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Starting directory path - can be relative or absolute (default: current directory '.', examples: '/etc', '/var/log', 'src')",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth to traverse (default: 3, max: 10)",
                    },
                    "show_hidden": {
                        "type": "boolean",
                        "description": "Include hidden files/directories (default: false)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit a file by replacing an exact string. More efficient than apply_patch for small changes. Primarily for repository files. Writing outside repository requires explicit user permission. The old_string must match exactly and appear only once.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file - relative to repository root or absolute path (note: writes outside repository require permission)",
                    },
                    "old_string": {
                        "type": "string",
                        "description": "The exact string to find and replace (must match exactly including all whitespace; use read_lines to get exact text, or use apply_patch for complex changes)",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The string to replace it with",
                    },
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": "Modify a file by replacing its contents. Primarily for repository files. Writing outside repository requires explicit user permission. Returns a unified diff of changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file - relative to repository root or absolute path (note: writes outside repository require permission)",
                    },
                    "new_content": {
                        "type": "string",
                        "description": "The complete new content for the file",
                    },
                },
                "required": ["path", "new_content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Get git repository status showing modified, staged, and untracked files. No permission required - read-only operation.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Get git diff to see changes. No permission required - read-only operation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Optional: specific file path to show diff for",
                    },
                    "staged": {
                        "type": "boolean",
                        "description": "If true, show staged changes (--cached), else show unstaged changes",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_log",
            "description": "Get git commit history. No permission required - read-only operation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_count": {
                        "type": "integer",
                        "description": "Maximum number of commits to show (default: 10, max: 50)",
                    },
                    "path": {
                        "type": "string",
                        "description": "Optional: specific file path to show history for",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep",
            "description": "Search for a pattern in files. Much faster than run_shell with grep. Returns results in 'file:line:content' format.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regular expression pattern to search for",
                    },
                    "file_glob": {
                        "type": "string",
                        "description": "Optional glob pattern to filter files (e.g., '*.py', 'src/**/*.js')",
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether the search should be case-sensitive (default: true)",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 100)",
                    },
                    "path": {
                        "type": "string",
                        "description": "Optional file or directory path to search in (relative to repo root or absolute). Defaults to repository root.",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information. Requires permission to prevent information leakage about your codebase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5, max: 10)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch and read content from a URL. Supports text extraction from HTML, PDF, DOCX (Word), PPTX (PowerPoint), and plain text files. Requires permission to prevent information leakage about your codebase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch (must start with http:// or https://)",
                    },
                    "extract_text": {
                        "type": "boolean",
                        "description": "If true, extract readable text from HTML/PDF/DOCX/PPTX (default: true)",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_skills",
            "description": "List all available skills. When telling users about skills, instruct them to use /skillname syntax (e.g., /commit).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "use_skill",
            "description": "Invoke a skill programmatically when it's relevant to the user's request. Note: Users invoke skills via /skillname at the CLI, not by calling tools.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Name of the skill to invoke (without / prefix)",
                    },
                    "args": {
                        "type": "string",
                        "description": "Optional arguments to pass to the skill",
                    },
                },
                "required": ["skill_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todo_add",
            "description": "Add a new task to the TODO list. Use this to break down complex tasks into manageable subtasks. Essential for planning multi-step work.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Brief task description (one line)",
                    },
                    "details": {
                        "type": "string",
                        "description": "Optional detailed notes about the task",
                    },
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todo_list",
            "description": "List all tasks in the TODO list with their status and progress.",
            "parameters": {
                "type": "object",
                "properties": {
                    "show_completed": {
                        "type": "boolean",
                        "description": "If true, show completed tasks; if false, show only pending tasks (default: false)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todo_complete",
            "description": "Mark a task as completed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "The ID of the task to complete",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todo_update",
            "description": "Update a task's description or details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "The ID of the task to update",
                    },
                    "description": {
                        "type": "string",
                        "description": "New description (optional)",
                    },
                    "details": {
                        "type": "string",
                        "description": "New details (optional)",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todo_remove",
            "description": "Remove a task from the TODO list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "The ID of the task to remove",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todo_clear",
            "description": "Clear tasks from the TODO list (completed tasks only by default, or all tasks).",
            "parameters": {
                "type": "object",
                "properties": {
                    "completed_only": {
                        "type": "boolean",
                        "description": "If true, clear only completed tasks; if false, clear all tasks (default: true)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "Ask the user a question and wait for their response. Use this to clarify requirements, get decisions, or gather additional information during task execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to ask the user",
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of predefined answer choices (e.g., ['yes', 'no', 'skip']). User can select from these or provide custom answer.",
                    },
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a safe shell command in the repository. Commands execute from repository root automatically (no need for 'cd'). Privilege escalation (sudo, su) blocked by default unless PATCHPAL_ALLOW_SUDO=true.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {"type": "string", "description": "The shell command to execute"}
                },
                "required": ["cmd"],
            },
        },
    },
]

# Map tool names to functions
TOOL_FUNCTIONS = {
    "read_file": read_file,
    "read_lines": read_lines,
    "count_lines": count_lines,
    "code_structure": code_structure,
    "get_repo_map": get_repo_map,
    "list_files": list_files,
    "get_file_info": get_file_info,
    "find_files": find_files,
    "tree": tree,
    "edit_file": edit_file,
    "apply_patch": apply_patch,
    "git_status": git_status,
    "git_diff": git_diff,
    "git_log": git_log,
    "grep": grep,
    "web_search": web_search,
    "web_fetch": web_fetch,
    "list_skills": list_skills,
    "use_skill": use_skill,
    "todo_add": todo_add,
    "todo_list": todo_list,
    "todo_complete": todo_complete,
    "todo_update": todo_update,
    "todo_remove": todo_remove,
    "todo_clear": todo_clear,
    "ask_user": ask_user,
    "run_shell": run_shell,
}


def get_tools(web_tools_enabled: bool = True):
    """Get the list of available tools, optionally filtering out web tools.

    Args:
        web_tools_enabled: Whether to include web_search and web_fetch tools

    Returns:
        Tuple of (tools_list, tool_functions_dict)
    """
    # Start with built-in tools
    tools = TOOLS.copy()
    functions = TOOL_FUNCTIONS.copy()

    # Filter out web tools if disabled
    if not web_tools_enabled:
        tools = [
            tool for tool in tools if tool["function"]["name"] not in ("web_search", "web_fetch")
        ]
        functions = {k: v for k, v in functions.items() if k not in ("web_search", "web_fetch")}

    # Load MCP tools dynamically
    try:
        mcp_tools, mcp_functions = load_mcp_tools()
        if mcp_tools:
            tools.extend(mcp_tools)
            functions.update(mcp_functions)
    except Exception as e:
        # Graceful degradation - MCP tools are optional
        print(f"Warning: Failed to load MCP tools: {e}")

    return tools, functions
