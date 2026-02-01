"""System information tools for PatchPal.

This demonstrates how to gather system information like disk usage,
environment variables, and process information.
"""

import os
import platform
import shutil
from typing import Optional


def get_disk_usage(path: str = ".") -> str:
    """Get disk usage information for a path.

    Args:
        path: Path to check disk usage for (default: current directory)

    Returns:
        Disk usage information including total, used, and free space
    """
    try:
        # Get absolute path
        abs_path = os.path.abspath(path)

        if not os.path.exists(abs_path):
            return f"Error: Path '{path}' does not exist"

        # Get disk usage stats
        usage = shutil.disk_usage(abs_path)

        total_gb = usage.total / (1024**3)
        used_gb = usage.used / (1024**3)
        free_gb = usage.free / (1024**3)
        percent_used = (usage.used / usage.total) * 100

        result = [
            f"Disk Usage for: {abs_path}",
            "",
            f"💾 Total Space:  {total_gb:,.2f} GB",
            f"📊 Used Space:   {used_gb:,.2f} GB ({percent_used:.1f}%)",
            f"✅ Free Space:   {free_gb:,.2f} GB",
            "",
            f"Progress: [{'█' * int(percent_used / 2)}{' ' * (50 - int(percent_used / 2))}] {percent_used:.1f}%",
        ]

        return "\n".join(result)

    except PermissionError:
        return f"Error: Permission denied to access '{path}'"
    except Exception as e:
        return f"Error getting disk usage: {str(e)}"


def get_system_info() -> str:
    """Get general system information.

    Returns:
        System information including OS, Python version, and architecture
    """
    try:
        # Get username safely
        try:
            username = os.getlogin()
        except (OSError, AttributeError):
            username = os.environ.get("USER") or os.environ.get("USERNAME") or "N/A"

        result = [
            "System Information:",
            "",
            f"🖥️  Operating System: {platform.system()} {platform.release()}",
            f"📦 OS Version: {platform.version()}",
            f"🏗️  Architecture: {platform.machine()}",
            f"💻 Processor: {platform.processor() or 'N/A'}",
            f"🐍 Python Version: {platform.python_version()}",
            f"👤 User: {username}",
            f"📁 Current Directory: {os.getcwd()}",
            f"🏠 Home Directory: {os.path.expanduser('~')}",
        ]

        return "\n".join(result)

    except Exception as e:
        return f"Error getting system info: {str(e)}"


def get_env_var(var_name: str) -> str:
    """Get the value of an environment variable.

    Args:
        var_name: Name of the environment variable

    Returns:
        The value of the environment variable or an error message
    """
    value = os.environ.get(var_name)

    if value is None:
        return f"Environment variable '{var_name}' is not set"

    # Mask potential sensitive values
    sensitive_keywords = ["key", "secret", "password", "token", "auth"]
    is_sensitive = any(keyword in var_name.lower() for keyword in sensitive_keywords)

    if is_sensitive and len(value) > 4:
        masked_value = value[:4] + "*" * (len(value) - 4)
        return f"{var_name}={masked_value} (masked for security)"

    return f"{var_name}={value}"


def list_env_vars(filter_pattern: Optional[str] = None) -> str:
    """List environment variables, optionally filtered by pattern.

    Args:
        filter_pattern: Optional pattern to filter variable names (case-insensitive)

    Returns:
        List of environment variables matching the pattern
    """
    try:
        env_vars = dict(os.environ)

        # Filter if pattern provided
        if filter_pattern:
            pattern_lower = filter_pattern.lower()
            env_vars = {k: v for k, v in env_vars.items() if pattern_lower in k.lower()}

        if not env_vars:
            if filter_pattern:
                return f"No environment variables found matching '{filter_pattern}'"
            return "No environment variables found"

        # Mask sensitive values
        sensitive_keywords = ["key", "secret", "password", "token", "auth"]

        result = [f"Environment Variables ({len(env_vars)} found)"]
        if filter_pattern:
            result[0] += f" matching '{filter_pattern}'"
        result.append("")

        for key in sorted(env_vars.keys()):
            value = env_vars[key]
            is_sensitive = any(keyword in key.lower() for keyword in sensitive_keywords)

            if is_sensitive and len(value) > 4:
                display_value = value[:4] + "*" * min(20, len(value) - 4)
            elif len(value) > 100:
                display_value = value[:97] + "..."
            else:
                display_value = value

            result.append(f"  {key}={display_value}")

        if len(env_vars) > 50:
            result.append(f"\n... showing first 50 of {len(env_vars)} variables")
            result = result[:52]

        return "\n".join(result)

    except Exception as e:
        return f"Error listing environment variables: {str(e)}"


def get_directory_size(directory: str) -> str:
    """Calculate the total size of a directory and its contents.

    Args:
        directory: Path to the directory

    Returns:
        Total size of the directory with breakdown
    """
    if not os.path.exists(directory):
        return f"Error: Directory '{directory}' does not exist"

    if not os.path.isdir(directory):
        return f"Error: '{directory}' is not a directory"

    try:
        total_size = 0
        file_count = 0
        dir_count = 0

        for dirpath, dirnames, filenames in os.walk(directory):
            dir_count += len(dirnames)
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                    file_count += 1
                except (OSError, PermissionError):
                    continue

        size_bytes = total_size
        size_kb = total_size / 1024
        size_mb = total_size / (1024**2)
        size_gb = total_size / (1024**3)

        # Choose appropriate unit
        if size_gb >= 1:
            size_str = f"{size_gb:.2f} GB"
        elif size_mb >= 1:
            size_str = f"{size_mb:.2f} MB"
        elif size_kb >= 1:
            size_str = f"{size_kb:.2f} KB"
        else:
            size_str = f"{size_bytes} bytes"

        result = [
            f"Directory Size Analysis: {directory}",
            "",
            f"📊 Total Size: {size_str} ({size_bytes:,} bytes)",
            f"📄 Files: {file_count:,}",
            f"📁 Subdirectories: {dir_count:,}",
        ]

        return "\n".join(result)

    except PermissionError:
        return f"Error: Permission denied to access '{directory}'"
    except Exception as e:
        return f"Error calculating directory size: {str(e)}"


def check_path_exists(path: str) -> str:
    """Check if a path exists and return information about it.

    Args:
        path: Path to check

    Returns:
        Information about the path including type and permissions
    """
    abs_path = os.path.abspath(path)

    if not os.path.exists(path):
        return f"Path does not exist: {path}"

    try:
        is_file = os.path.isfile(path)
        is_dir = os.path.isdir(path)
        is_link = os.path.islink(path)

        result = [
            f"Path: {abs_path}",
            "",
            f"Type: {'File' if is_file else 'Directory' if is_dir else 'Other'}",
        ]

        if is_link:
            result.append(f"Symbolic Link: Yes → {os.readlink(path)}")

        # Get size
        if is_file:
            size = os.path.getsize(path)
            if size > 1024**2:
                size_str = f"{size / (1024**2):.2f} MB"
            elif size > 1024:
                size_str = f"{size / 1024:.2f} KB"
            else:
                size_str = f"{size} bytes"
            result.append(f"Size: {size_str}")

        # Check permissions
        result.append("")
        result.append("Permissions:")
        result.append(f"  Readable: {'Yes' if os.access(path, os.R_OK) else 'No'}")
        result.append(f"  Writable: {'Yes' if os.access(path, os.W_OK) else 'No'}")
        result.append(f"  Executable: {'Yes' if os.access(path, os.X_OK) else 'No'}")

        return "\n".join(result)

    except Exception as e:
        return f"Error checking path: {str(e)}"
