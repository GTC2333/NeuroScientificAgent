"""
Tool definitions and executor for MAS agentic loop.
Provides Bash, Read, Write, Edit, Glob, Grep tools in Anthropic API format.
"""
import subprocess
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import fnmatch

logger = logging.getLogger("MAS.Tools")

# Maximum output size to prevent memory issues
MAX_OUTPUT_SIZE = 100_000  # 100KB

# Tool definitions in Anthropic API format
TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "Bash",
        "description": "Execute a bash command and return its output. Use for system commands, running tests, git operations, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 120, max 600)",
                    "default": 120
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "Read",
        "description": "Read a file's contents. Returns the file content with line numbers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to read"
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (1-based)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "Write",
        "description": "Write content to a file, creating it if it doesn't exist or overwriting if it does.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "The content to write to the file"
                }
            },
            "required": ["file_path", "content"]
        }
    },
    {
        "name": "Edit",
        "description": "Replace a specific string in a file with a new string. The old_string must be unique in the file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to edit"
                },
                "old_string": {
                    "type": "string",
                    "description": "The exact text to find and replace (must be unique in the file)"
                },
                "new_string": {
                    "type": "string",
                    "description": "The text to replace it with"
                }
            },
            "required": ["file_path", "old_string", "new_string"]
        }
    },
    {
        "name": "Glob",
        "description": "Find files matching a glob pattern. Returns matching file paths.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match files (e.g., '**/*.py', 'src/**/*.ts')"
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in (defaults to working directory)"
                }
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "Grep",
        "description": "Search file contents using regex patterns. Returns matching lines with file paths and line numbers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for"
                },
                "path": {
                    "type": "string",
                    "description": "File or directory to search in"
                },
                "glob": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g., '*.py')"
                }
            },
            "required": ["pattern"]
        }
    },
]


def execute_tool(tool_name: str, tool_input: Dict[str, Any],
                 cwd: str = None) -> Dict[str, Any]:
    """Execute a tool and return the result.

    Returns:
        {"content": str, "is_error": bool}
    """
    cwd = cwd or "/root/claudeagent/scientific_agent/temp_workspace"
    logger.info(f"[Tools] Executing {tool_name} with input: {json.dumps(tool_input)[:200]}")

    try:
        if tool_name == "Bash":
            return _exec_bash(tool_input, cwd)
        elif tool_name == "Read":
            return _exec_read(tool_input)
        elif tool_name == "Write":
            return _exec_write(tool_input)
        elif tool_name == "Edit":
            return _exec_edit(tool_input)
        elif tool_name == "Glob":
            return _exec_glob(tool_input, cwd)
        elif tool_name == "Grep":
            return _exec_grep(tool_input, cwd)
        else:
            return {"content": f"Unknown tool: {tool_name}", "is_error": True}
    except Exception as e:
        logger.error(f"[Tools] Error executing {tool_name}: {e}", exc_info=True)
        return {"content": f"Error executing {tool_name}: {str(e)}", "is_error": True}


def _exec_bash(tool_input: Dict, cwd: str) -> Dict[str, Any]:
    """Execute a bash command."""
    command = tool_input["command"]
    timeout = min(tool_input.get("timeout", 120), 600)

    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
    )

    output = result.stdout
    if result.stderr:
        output += ("\n" if output else "") + result.stderr
    if not output:
        output = f"(exit code {result.returncode})"

    return {
        "content": output[:MAX_OUTPUT_SIZE],
        "is_error": result.returncode != 0,
    }


def _exec_read(tool_input: Dict) -> Dict[str, Any]:
    """Read a file."""
    file_path = Path(tool_input["file_path"])
    if not file_path.exists():
        return {"content": f"File not found: {file_path}", "is_error": True}

    text = file_path.read_text(errors="replace")
    lines = text.splitlines(keepends=True)

    offset = tool_input.get("offset", 1) - 1  # Convert to 0-based
    limit = tool_input.get("limit", len(lines))
    selected = lines[max(0, offset):offset + limit]

    numbered = ""
    for i, line in enumerate(selected, start=max(1, offset + 1)):
        numbered += f"{i:>6}\t{line}"

    return {"content": numbered[:MAX_OUTPUT_SIZE], "is_error": False}


def _exec_write(tool_input: Dict) -> Dict[str, Any]:
    """Write content to a file."""
    file_path = Path(tool_input["file_path"])
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(tool_input["content"])
    return {"content": f"Successfully wrote to {file_path}", "is_error": False}


def _exec_edit(tool_input: Dict) -> Dict[str, Any]:
    """Edit a file by replacing a string."""
    file_path = Path(tool_input["file_path"])
    if not file_path.exists():
        return {"content": f"File not found: {file_path}", "is_error": True}

    content = file_path.read_text()
    old_string = tool_input["old_string"]
    new_string = tool_input["new_string"]

    count = content.count(old_string)
    if count == 0:
        return {"content": f"old_string not found in {file_path}", "is_error": True}
    if count > 1:
        return {"content": f"old_string found {count} times (must be unique) in {file_path}", "is_error": True}

    new_content = content.replace(old_string, new_string, 1)
    file_path.write_text(new_content)
    return {"content": f"Successfully edited {file_path}", "is_error": False}


def _exec_glob(tool_input: Dict, cwd: str) -> Dict[str, Any]:
    """Find files matching a glob pattern."""
    pattern = tool_input["pattern"]
    search_path = Path(tool_input.get("path", cwd))

    matches = sorted(search_path.glob(pattern))
    result = "\n".join(str(m) for m in matches[:500])
    if not result:
        result = "No files matched the pattern."
    return {"content": result, "is_error": False}


def _exec_grep(tool_input: Dict, cwd: str) -> Dict[str, Any]:
    """Search file contents using grep/ripgrep."""
    pattern = tool_input["pattern"]
    search_path = tool_input.get("path", cwd)
    file_glob = tool_input.get("glob", "")

    cmd = ["grep", "-rn", "--include", file_glob, pattern, search_path] if file_glob else \
          ["grep", "-rn", pattern, search_path]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, cwd=cwd,
        )
        output = result.stdout if result.stdout else "No matches found."
        return {"content": output[:MAX_OUTPUT_SIZE], "is_error": False}
    except subprocess.TimeoutExpired:
        return {"content": "Grep timed out after 30s", "is_error": True}
