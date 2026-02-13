"""Code structure analysis using tree-sitter AST parsing.

This module provides tools to analyze code structure without reading full files,
significantly reducing token usage for large codebases.
"""

from pathlib import Path
from typing import Dict, List, Optional

try:
    from tree_sitter_language_pack import get_parser

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

from patchpal.tools.common import _check_path, _operation_limiter, audit_logger

# Language mapping from file extensions
LANGUAGE_MAP = {
    "py": "python",
    "js": "javascript",
    "jsx": "javascript",
    "ts": "typescript",
    "tsx": "typescript",
    "go": "go",
    "rs": "rust",
    "java": "java",
    "cpp": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "c": "c",
    "h": "c",
    "cs": "c_sharp",
    "rb": "ruby",
    "php": "php",
    "swift": "swift",
    "kt": "kotlin",
    "scala": "scala",
    "r": "r",
    "R": "r",
    "sh": "bash",
    "bash": "bash",
    "elm": "elm",
    "ex": "elixir",
    "exs": "elixir",
}

# Node types for different languages
FUNCTION_NODE_TYPES = {
    "python": ["function_definition"],
    "javascript": ["function_declaration", "function", "method_definition"],
    "typescript": ["function_declaration", "function", "method_definition"],
    "go": ["function_declaration", "method_declaration"],
    "rust": ["function_item"],
    "java": ["method_declaration"],
    "cpp": ["function_definition"],
    "c": ["function_definition"],
    "c_sharp": ["method_declaration"],
    "ruby": ["method", "singleton_method"],
    "php": ["function_definition", "method_declaration"],
}

CLASS_NODE_TYPES = {
    "python": ["class_definition"],
    "javascript": ["class_declaration"],
    "typescript": ["class_declaration"],
    "go": ["type_declaration"],
    "rust": ["struct_item", "enum_item", "trait_item", "impl_item"],
    "java": ["class_declaration", "interface_declaration"],
    "cpp": ["class_specifier", "struct_specifier"],
    "c": ["struct_specifier"],
    "c_sharp": ["class_declaration", "interface_declaration"],
    "ruby": ["class", "module"],
    "php": ["class_declaration"],
}


def code_structure(path: str, max_symbols: int = 50) -> str:
    """
    Analyze code structure using tree-sitter AST parsing.

    Returns a compact view of:
    - File statistics (lines, size)
    - Functions with signatures and line numbers
    - Classes with methods
    - Module/file docstring (if present)

    This is much more efficient than read_file for understanding code layout.
    Supports 40+ languages via tree-sitter.

    Args:
        path: File path to analyze (relative or absolute)
        max_symbols: Maximum number of symbols to show (default: 50)

    Returns:
        Formatted code structure overview

    Examples:
        >>> code_structure("patchpal/tools.py")
        File: patchpal/tools.py (2883 lines, 89.2 KB)

        Functions (45):
          Line  123: def read_file(path: str, *, encoding: str = "utf-8") -> str
          Line  234: def apply_patch(path: str, new_content: str) -> str
          ...

        Use read_lines('patchpal/tools.py', start, end) to read specific sections.
    """
    _operation_limiter.check_limit(f"code_structure({path})")

    if not TREE_SITTER_AVAILABLE:
        return (
            "❌ Tree-sitter not available. Install with: pip install tree-sitter-language-pack\n\n"
            "Fallback: Use read_lines() to read specific sections of the file."
        )

    # Validate and resolve path
    resolved_path = _check_path(path, must_exist=True)

    # Detect language
    ext = resolved_path.suffix.lstrip(".")
    language_name = LANGUAGE_MAP.get(ext)

    if not language_name:
        # Unsupported language, return basic info
        return _basic_file_info(resolved_path, path)

    try:
        # Get parser for language
        parser = get_parser(language_name)

        # Read and parse file
        with open(resolved_path, "rb") as f:
            source = f.read()

        tree = parser.parse(source)
        root = tree.root_node

        # Extract symbols
        symbols = _extract_symbols(root, language_name, source)

        # Format output
        result = _format_output(resolved_path, path, symbols, max_symbols, source)

        audit_logger.info(f"CODE_STRUCTURE: {path} ({len(symbols)} symbols)")
        return result

    except Exception as e:
        # Fallback to basic info if parsing fails
        audit_logger.warning(f"CODE_STRUCTURE failed for {path}: {e}")
        return _basic_file_info(resolved_path, path) + f"\n\n⚠️  Tree-sitter parsing failed: {e}"


def _extract_symbols(node, language_name: str, source: bytes) -> List[Dict]:
    """Extract function and class symbols from AST."""
    symbols = []
    function_types = FUNCTION_NODE_TYPES.get(language_name, [])
    class_types = CLASS_NODE_TYPES.get(language_name, [])

    def visit(n, depth=0, parent_type=None):
        # Extract functions
        if n.type in function_types:
            name = _get_identifier(n, "name", source) or _get_identifier(n, "identifier", source)
            if name:
                # Get signature by extracting relevant source
                signature_bytes = source[n.start_byte : n.end_byte]
                # Extract just the declaration line(s)
                lines = signature_bytes.decode("utf-8", errors="ignore").split("\n")
                signature = lines[0].strip()
                if len(lines) > 1 and not lines[0].rstrip().endswith(":"):
                    signature += " " + lines[1].strip()

                symbols.append(
                    {
                        "type": "method" if parent_type == "class" else "function",
                        "name": name,
                        "signature": signature,
                        "line": n.start_point[0] + 1,
                        "depth": depth,
                    }
                )

        # Extract classes/structs
        elif n.type in class_types:
            name = _get_identifier(n, "name", source) or _get_identifier(n, "identifier", source)
            if name:
                symbols.append(
                    {
                        "type": "class",
                        "name": name,
                        "line": n.start_point[0] + 1,
                        "depth": depth,
                    }
                )
                # Visit children to find methods
                for child in n.children:
                    visit(child, depth + 1, parent_type="class")
                return  # Don't visit children again

        # Visit children
        for child in n.children:
            visit(child, depth, parent_type)

    visit(node)
    return symbols


def _get_identifier(node, field_name: str, source: bytes) -> Optional[str]:
    """Extract identifier from a node field."""
    child = node.child_by_field_name(field_name)
    if child:
        return source[child.start_byte : child.end_byte].decode("utf-8", errors="ignore")
    return None


def _format_output(
    resolved_path: Path, display_path: str, symbols: List[Dict], max_symbols: int, source: bytes
) -> str:
    """Format symbols into human-readable output."""
    lines = []

    # File header
    line_count = source.decode("utf-8", errors="ignore").count("\n") + 1
    size_kb = len(source) / 1024
    lines.append(f"File: {display_path} ({line_count:,} lines, {size_kb:.1f} KB)\n")

    # Group symbols
    classes = [s for s in symbols if s["type"] == "class" and s["depth"] == 0]
    functions = [s for s in symbols if s["type"] == "function" and s["depth"] == 0]
    methods = [s for s in symbols if s["type"] == "method"]

    # Show classes with their methods
    if classes:
        lines.append(f"\nClasses ({len(classes)}):")
        for cls in classes[: max_symbols // 2]:
            lines.append(f"  Line {cls['line']:4d}: class {cls['name']}")
            # Find methods for this class
            class_line = cls["line"]
            next_class_line = (
                min([c["line"] for c in classes if c["line"] > class_line] + [999999])
                if len(classes) > 1
                else 999999
            )
            class_methods = [
                m
                for m in methods
                if m["line"] > class_line and m["line"] < next_class_line and m["depth"] == 1
            ]
            for method in class_methods[:10]:  # Max 10 methods per class
                lines.append(f"           {method['line']:4d}:   {method['signature'][:80]}")

    # Show top-level functions
    if functions:
        lines.append(f"\nFunctions ({len(functions)}):")
        for func in functions[: max_symbols // 2]:
            lines.append(f"  Line {func['line']:4d}: {func['signature'][:90]}")

    # Summary
    if not classes and not functions:
        lines.append("\n(No functions or classes found)")

    # Add helpful hint
    lines.append(f"\n💡 Use read_lines('{display_path}', start, end) to read specific sections.")

    return "\n".join(lines)


def _basic_file_info(resolved_path: Path, display_path: str) -> str:
    """Return basic file info when tree-sitter is unavailable or fails."""
    try:
        with open(resolved_path, "rb") as f:
            content = f.read()
        line_count = content.decode("utf-8", errors="ignore").count("\n") + 1
        size_kb = len(content) / 1024

        return (
            f"File: {display_path} ({line_count:,} lines, {size_kb:.1f} KB)\n\n"
            f"💡 Use read_lines('{display_path}', start, end) to read specific sections.\n"
            f"💡 Use grep(pattern, '{display_path}') to search within this file."
        )
    except Exception as e:
        return f"❌ Unable to read file: {e}"
