# Built-In Tools

The agent has the following tools:

## File Operations
- **read_file**: Read contents of files in the repository
  - Limited to 500KB by default (configurable with `PATCHPAL_MAX_FILE_SIZE`)
  - For larger files, use `read_lines` or `grep` for targeted access
- **read_lines**: Read specific line ranges from a file without loading the entire file
  - Example: `read_lines("app.py", 100, 150)` - read lines 100-150
  - More efficient than read_file when you only need a few lines
  - Useful for viewing code sections, error context, or specific regions of large files
- **count_lines**: Count the number of lines in a file efficiently
  - Example: `count_lines("logs/app.log")` - returns "15,234 lines (2.3MB)"
  - Useful before using read_lines to determine total line count (e.g., to read last N lines)
  - Uses 1MB buffered chunks for fast counting of large files
- **code_structure**: Analyze code structure using tree-sitter AST parsing without reading full files
  - Example: `code_structure("app.py")` - see all classes, functions, methods with line numbers
  - 95% token savings vs read_file for large code files
  - Supports 40+ languages (Python, JavaScript, TypeScript, Go, Rust, Java, C/C++, Ruby, PHP, and more)
  - Shows function signatures and line numbers for easy navigation
  - Use with read_lines: analyze structure first, then read specific sections
- **get_repo_map**: Get an overview of the entire codebase in one call
  - Example: `get_repo_map(max_files=100)` - see structure of up to 100 files at once
  - Shows function/class signatures from ALL files in a consolidated view
  - Supports filtering: `get_repo_map(include_patterns=["*.py"], exclude_patterns=["*test*"])`
  - Ideal for understanding codebase structure and finding relevant files
- **list_files**: List all files in the repository
- **get_file_info**: Get detailed metadata for file(s) - size, modification time, type
  - Supports single files: `get_file_info("file.txt")`
  - Supports directories: `get_file_info("src/")`
  - Supports glob patterns: `get_file_info("tests/*.py")`
- **find_files**: Find files by name pattern using glob-style wildcards
  - Example: `find_files("*.py")` - all Python files
  - Example: `find_files("test_*.py")` - all test files
  - Example: `find_files("**/*.md")` - all markdown files recursively
  - Supports case-insensitive matching
- **tree**: Show directory tree structure to understand folder organization
  - Example: `tree(".")` - show tree from current directory
  - Configurable max depth (default: 3, max: 10)
  - Option to show/hide hidden files
- **grep**: Search for patterns in code files (regex support, file filtering)
- **edit_file**: Edit a file by replacing an exact string (efficient for small changes)
  - Example: `edit_file("config.py", "port = 3000", "port = 8080")`
  - More efficient than apply_patch for targeted changes
  - Old string must appear exactly once in the file
- **apply_patch**: Modify files by providing complete new content
- **run_shell**: Execute shell commands (requires user permission; privilege escalation blocked)

## Task Planning (TODO System)
- **todo_add**: Add a new task to break down complex work into manageable subtasks
  - Example: `todo_add("Implement authentication", details="Use JWT tokens")`
  - Each task gets a unique ID for tracking
- **todo_list**: Show all tasks with their status and progress
  - Example: `todo_list()` - show pending tasks only
  - Example: `todo_list(show_completed=True)` - show all tasks including completed
- **todo_complete**: Mark a task as done
  - Example: `todo_complete(1)` - mark task #1 as completed
- **todo_update**: Update task description or details
  - Example: `todo_update(1, description="Implement OAuth2 authentication")`
- **todo_remove**: Remove a task from the list
  - Example: `todo_remove(1)` - remove task #1
- **todo_clear**: Clear completed tasks or start fresh
  - Example: `todo_clear()` - clear completed tasks only
  - Example: `todo_clear(completed_only=False)` - clear all tasks

## User Interaction
- **ask_user**: Ask the user a question during task execution
  - Example: `ask_user("Which database should I use?", options=["PostgreSQL", "MySQL", "SQLite"])`
  - Useful for clarifying requirements, getting decisions, or gathering additional information
  - Supports multiple choice options or free-form answers

## Git Operations (No Permission Required)
- **git_status**: Show modified, staged, and untracked files
- **git_diff**: Show changes in working directory or staged area
  - Optional parameters: `path` (specific file), `staged` (show staged changes)
- **git_log**: Show commit history
  - Optional parameters: `max_count` (number of commits, max 50), `path` (specific file history)

## Web Capabilities (Requires Permission)
- **web_search**: Search the web using DuckDuckGo (no API key required!)
  - Look up error messages and solutions
  - Find current documentation and best practices
  - Research library versions and compatibility
  - Requires permission to prevent information leakage about your codebase
- **web_fetch**: Fetch and read content from URLs
  - Read documentation pages and API references
  - Extract text from HTML, PDF, DOCX (Word), and PPTX (PowerPoint) files
  - Support for plain text, JSON, XML, and other text formats
  - Warns about unsupported binary formats (images, videos, archives)
  - Requires permission to prevent information leakage about your codebase
