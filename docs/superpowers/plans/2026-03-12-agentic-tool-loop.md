# Agentic Tool Execution Loop Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a complete agentic tool execution loop in the MAS Python backend so the LLM can call tools (Bash, Read, Write, Edit, Glob, Grep), execute them, observe results, and loop until the task is done — matching the behavior of the original Node.js `@anthropic-ai/claude-agent-sdk`.

**Architecture:** The Python backend currently uses the Anthropic Python SDK but only streams text — it never passes tool definitions, never detects tool_use blocks, and never loops. We will: (1) define tools in Anthropic API format, (2) build a tool executor, (3) rewrite `claude_sdk.py` with a streaming agentic loop that yields structured events, (4) update `websocket.py` to consume those events and forward them in the format the frontend already understands.

**Tech Stack:** Python 3, Anthropic Python SDK (`anthropic`), FastAPI, asyncio, subprocess (for Bash tool), pathlib (for file tools)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/src/services/tools.py` | **Create** | Tool definitions (Anthropic API format) + sandboxed tool executor |
| `backend/src/services/claude_sdk.py` | **Rewrite** | Agentic loop: streaming API call → detect tool_use → execute → feed back → repeat |
| `backend/src/api/websocket.py` | **Modify** | Consume structured events from SDK, translate to frontend WebSocket protocol |
| `backend/src/services/claude_code.py` | **Minor modify** | Pass-through changes for new event-based streaming signature |

---

## Chunk 1: Tool Definitions and Executor

### Task 1: Create tool definitions module

**Files:**
- Create: `backend/src/services/tools.py`

- [ ] **Step 1: Create `tools.py` with Anthropic-format tool definitions**

```python
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
```

- [ ] **Step 2: Verify the module imports correctly**

Run: `cd /root/claudeagent/scientific_agent && poetry run python -c "from src.services.tools import TOOL_DEFINITIONS, execute_tool; print(f'{len(TOOL_DEFINITIONS)} tools defined')"`

Expected: `6 tools defined`

- [ ] **Step 3: Quick smoke test of tool executor**

Run: `cd /root/claudeagent/scientific_agent && poetry run python -c "from src.services.tools import execute_tool; r = execute_tool('Bash', {'command': 'echo hello'}); print(r)"`

Expected: `{'content': 'hello\n', 'is_error': False}`

- [ ] **Step 4: Commit**

```bash
git add backend/src/services/tools.py
git commit -m "feat: add tool definitions and executor for agentic loop"
```

---

## Chunk 2: Rewrite claude_sdk.py with Agentic Loop

### Task 2: Implement the agentic loop in claude_sdk.py

**Files:**
- Rewrite: `backend/src/services/claude_sdk.py`

The core change: replace the single-pass `stream.text_stream` reader with a loop that:
1. Calls the API with tool definitions
2. Streams text chunks as events
3. Detects tool_use blocks when `stop_reason == "tool_use"`
4. Executes tools via `tools.py`
5. Feeds results back into messages
6. Repeats until `stop_reason == "end_turn"` (or max iterations)

- [ ] **Step 1: Rewrite `claude_sdk.py` with agentic loop**

Replace the entire file with the following implementation:

```python
"""
Claude SDK Service - Agentic loop with tool execution.
Uses Anthropic Python SDK with streaming + tool definitions.
Yields structured events for WebSocket consumption.
"""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Generator, List, Optional, Any

from anthropic import Anthropic

from src.config import get_config
from src.services.tools import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger("MAS.ClaudeSDK")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CLAUDE_DIR = PROJECT_ROOT / ".claude"

MAX_TOOL_ITERATIONS = 30  # Safety limit to prevent infinite loops

MODEL_ALIASES = {
    "sonnet": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-20250514",
    "haiku": "claude-haiku-4-20250514",
}


def resolve_model(model: str) -> str:
    return MODEL_ALIASES.get(model, model)


class ClaudeSDKService:
    """Service to invoke Claude with agentic tool execution loop."""

    def __init__(self, project_dir: str = None):
        config = get_config()
        project_root = Path(__file__).parent.parent.parent.parent
        default_workspace = project_root / config.workspace.temp_dir

        self.project_dir = project_dir or str(default_workspace)
        self.claude_dir = (PROJECT_ROOT / config.project.claude_dir).resolve()
        self.default_model = config.claude.model
        self.api_key = config.claude.api_key
        self.timeout = config.claude.timeout
        self.max_tokens = 16384

        # Load env vars from settings.local.json
        env_vars = self._load_settings_env()
        for k, v in env_vars.items():
            os.environ.setdefault(k, v)

        if "ANTHROPIC_MODEL" in env_vars:
            self.default_model = env_vars["ANTHROPIC_MODEL"]

        # Initialize Anthropic client
        client_kwargs = {"max_retries": 3}
        auth_token = env_vars.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        base_url = env_vars.get("ANTHROPIC_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL")
        api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")

        if auth_token:
            client_kwargs["auth_token"] = auth_token
        elif api_key:
            client_kwargs["api_key"] = api_key
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = Anthropic(**client_kwargs)
        logger.info("[ClaudeSDK] Initialized with model: %s, base_url: %s",
                     self.default_model, base_url or "default")

    def _load_settings_env(self) -> dict:
        settings_file = self.claude_dir / "settings.local.json"
        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    return settings.get("env", {})
            except Exception as e:
                logger.warning(f"[ClaudeSDK] Failed to load settings: {e}")
        return {}

    def _load_agent_prompt(self, agent_type: str) -> str:
        agent_file = self.claude_dir / "agents" / f"{agent_type}.md"
        if agent_file.exists():
            return agent_file.read_text()
        return ""

    def _build_system_prompt(self, agent_type: str) -> str:
        """Build system prompt (without embedding the user message)."""
        agent_def = self._load_agent_prompt(agent_type)
        return f"""You are running in the Multi-Agent Scientific (MAS) Operating System.
Your role: {agent_type.upper()}

{agent_def}

You have access to tools: Bash, Read, Write, Edit, Glob, Grep.
Use tools to complete tasks. Write outputs to the file system.
Working directory: {self.project_dir}
"""

    def invoke(self, message: str, agent_type: str = "principal",
               model: str = None, session_id: str = None,
               skills: List[str] = None, history: List[dict] = None) -> str:
        """Non-streaming invocation with tool loop. Returns final text."""
        events = list(self.invoke_streaming(
            message=message, agent_type=agent_type, model=model,
            session_id=session_id, skills=skills, history=history,
        ))
        # Collect all text events
        return "".join(
            e.get("text", "") for e in events if e.get("type") == "text"
        )

    def invoke_streaming(self, message: str, agent_type: str = "principal",
                         model: str = None, session_id: str = None,
                         skills: List[str] = None,
                         history: List[dict] = None) -> Generator[Dict[str, Any], None, None]:
        """Streaming invocation with agentic tool execution loop.

        Yields structured events:
            {"type": "text", "text": "chunk"}
            {"type": "tool_use", "id": "...", "name": "Bash", "input": {...}}
            {"type": "tool_result", "tool_use_id": "...", "content": "...", "is_error": false}
            {"type": "status", "message": "Executing Bash..."}
            {"type": "error", "message": "..."}
        """
        model = resolve_model(model or self.default_model)
        system_prompt = self._build_system_prompt(agent_type)

        # Build messages array from history + current message
        messages = []
        if history:
            for msg in history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": message})

        logger.info(f"[ClaudeSDK] Agentic loop start: model={model}, history={len(messages)-1} msgs")

        for iteration in range(MAX_TOOL_ITERATIONS):
            logger.info(f"[ClaudeSDK] --- Iteration {iteration + 1} ---")

            try:
                # Call API with streaming and tool definitions
                assistant_content_blocks = []
                current_tool_use = None

                with self.client.messages.stream(
                    model=model,
                    max_tokens=self.max_tokens,
                    system=system_prompt,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                ) as stream:
                    for event in stream:
                        # Handle different stream event types
                        if event.type == "content_block_start":
                            block = event.content_block
                            if block.type == "tool_use":
                                current_tool_use = {
                                    "id": block.id,
                                    "name": block.name,
                                    "input_json": "",
                                }
                            elif block.type == "text":
                                pass  # Text will come via deltas

                        elif event.type == "content_block_delta":
                            delta = event.delta
                            if delta.type == "text_delta":
                                yield {"type": "text", "text": delta.text}
                            elif delta.type == "input_json_delta":
                                if current_tool_use is not None:
                                    current_tool_use["input_json"] += delta.partial_json

                        elif event.type == "content_block_stop":
                            if current_tool_use is not None:
                                # Parse accumulated tool input JSON
                                try:
                                    tool_input = json.loads(current_tool_use["input_json"]) \
                                        if current_tool_use["input_json"] else {}
                                except json.JSONDecodeError:
                                    tool_input = {}
                                    logger.error(f"[ClaudeSDK] Failed to parse tool input: {current_tool_use['input_json'][:200]}")

                                tool_block = {
                                    "type": "tool_use",
                                    "id": current_tool_use["id"],
                                    "name": current_tool_use["name"],
                                    "input": tool_input,
                                }
                                assistant_content_blocks.append(tool_block)
                                # Yield tool_use event to frontend
                                yield tool_block
                                current_tool_use = None

                    # Get the final message for stop_reason and text blocks
                    final_message = stream.get_final_message()

                # Collect text blocks from final message
                for block in final_message.content:
                    if block.type == "text" and block.text:
                        assistant_content_blocks.append({
                            "type": "text",
                            "text": block.text,
                        })

                # Add assistant message to conversation
                # Use the raw content from the final message for API compatibility
                messages.append({
                    "role": "assistant",
                    "content": [self._block_to_dict(b) for b in final_message.content],
                })

                # Check stop reason
                if final_message.stop_reason != "tool_use":
                    logger.info(f"[ClaudeSDK] Loop complete: stop_reason={final_message.stop_reason}")
                    break

                # Execute tools and collect results
                tool_uses = [b for b in assistant_content_blocks if b.get("type") == "tool_use"]
                tool_results = []
                for tool_use in tool_uses:
                    tool_name = tool_use["name"]
                    tool_id = tool_use["id"]
                    tool_input = tool_use["input"]

                    yield {"type": "status", "message": f"Executing {tool_name}..."}
                    logger.info(f"[ClaudeSDK] Executing tool: {tool_name}({json.dumps(tool_input)[:100]})")

                    result = execute_tool(tool_name, tool_input, cwd=self.project_dir)

                    tool_result_event = {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result["content"],
                        "is_error": result["is_error"],
                    }
                    yield tool_result_event

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result["content"],
                        "is_error": result.get("is_error", False),
                    })

                # Add tool results as user message (Anthropic API format)
                messages.append({"role": "user", "content": tool_results})

            except Exception as e:
                logger.error(f"[ClaudeSDK] Error in iteration {iteration + 1}: {e}", exc_info=True)
                yield {"type": "error", "message": str(e)}
                break
        else:
            yield {"type": "status", "message": f"Reached max iterations ({MAX_TOOL_ITERATIONS})"}
            logger.warning(f"[ClaudeSDK] Hit max iterations limit")

    @staticmethod
    def _block_to_dict(block) -> dict:
        """Convert an Anthropic SDK content block to a dict for messages array."""
        if block.type == "text":
            return {"type": "text", "text": block.text}
        elif block.type == "tool_use":
            return {
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            }
        return {"type": block.type}


_service: Optional[ClaudeSDKService] = None


def get_claude_sdk_service() -> ClaudeSDKService:
    global _service
    if _service is None:
        _service = ClaudeSDKService()
    return _service
```

- [ ] **Step 2: Verify module imports**

Run: `cd /root/claudeagent/scientific_agent && poetry run python -c "from src.services.claude_sdk import ClaudeSDKService; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/services/claude_sdk.py
git commit -m "feat: rewrite claude_sdk.py with agentic tool execution loop"
```

---

## Chunk 3: Update WebSocket Handler

### Task 3: Update websocket.py to consume structured events

**Files:**
- Modify: `backend/src/api/websocket.py` (lines 182-377, function `handle_claude_command`)

The current websocket handler treats all chunks as plain text. We need to:
1. Consume structured event dicts from `invoke_streaming()`
2. Translate each event type to the WebSocket message format the frontend expects
3. For `text` events: send as `content_block_delta` (same as before)
4. For `tool_use` events: send as message with `content` array containing `tool_use` block
5. For `tool_result` events: send as user-role message with `content` array containing `tool_result` block
6. Accumulate only text for session history storage

- [ ] **Step 1: Rewrite the `stream_to_queue` and main loop in `handle_claude_command`**

Replace lines 262-338 in `websocket.py` (from `response_text = ""` through the `claude-complete` send) with:

```python
        claude_service = get_claude_service()
        response_text = ""

        # Stream structured events using a queue to bridge thread/async
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def stream_to_queue():
            """Run streaming in a thread, put each event dict in the async queue"""
            try:
                for event in claude_service.invoke_streaming(
                    message=command,
                    agent_type="principal",
                    session_id=session_id,
                    history=history,
                ):
                    if event:
                        loop.call_soon_threadsafe(queue.put_nowait, event)
            except Exception as e:
                logger.error(f"[ws] Stream thread error: {e}", exc_info=True)
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": str(e)})
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

        import threading
        thread = threading.Thread(target=stream_to_queue, daemon=True)
        thread.start()

        while True:
            event = await queue.get()
            if event is None:
                break

            event_type = event.get("type", "")

            if event_type == "text":
                # Stream text chunk to frontend (same format as before)
                text = event.get("text", "")
                response_text += text
                await manager.send_to_user(user_id, {
                    "type": "claude-response",
                    "sessionId": session_id,
                    "data": {
                        "type": "content_block_delta",
                        "delta": {"text": text},
                    },
                })

            elif event_type == "tool_use":
                # Send tool_use as a message with content array
                await manager.send_to_user(user_id, {
                    "type": "claude-response",
                    "sessionId": session_id,
                    "data": {
                        "message": {
                            "content": [{
                                "type": "tool_use",
                                "id": event.get("id"),
                                "name": event.get("name"),
                                "input": event.get("input", {}),
                            }]
                        }
                    },
                })

            elif event_type == "tool_result":
                # Send tool_result as a user-role message with content array
                await manager.send_to_user(user_id, {
                    "type": "claude-response",
                    "sessionId": session_id,
                    "data": {
                        "message": {
                            "role": "user",
                            "content": [{
                                "type": "tool_result",
                                "tool_use_id": event.get("tool_use_id"),
                                "content": event.get("content", ""),
                                "is_error": event.get("is_error", False),
                            }]
                        }
                    },
                })

            elif event_type == "status":
                await manager.send_to_user(user_id, {
                    "type": "claude-status",
                    "sessionId": session_id,
                    "data": {"message": event.get("message", "")},
                })

            elif event_type == "error":
                await manager.send_to_user(user_id, {
                    "type": "claude-error",
                    "sessionId": session_id,
                    "error": event.get("message", "Unknown error"),
                })

        # Send content_block_stop to signal end of text stream
        await manager.send_to_user(user_id, {
            "type": "claude-response",
            "sessionId": session_id,
            "data": {"type": "content_block_stop"},
        })

        # Save messages to session (text only for history)
        save_message_to_session(session_id, "user", command)
        save_message_to_session(session_id, "assistant", response_text)

        # Send claude-complete
        await manager.send_to_user(user_id, {
            "type": "claude-complete",
            "sessionId": session_id,
            "exitCode": 0,
        })
```

- [ ] **Step 2: Verify the backend starts without errors**

Run: `cd /root/claudeagent/scientific_agent/backend && poetry run python -c "from src.api.websocket import router; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/api/websocket.py
git commit -m "feat: update websocket handler for structured tool events"
```

---

## Chunk 4: Update claude_code.py Pass-Through

### Task 4: Update claude_code.py to match new event-based signature

**Files:**
- Modify: `backend/src/services/claude_code.py` (lines 387-403)

The `invoke_streaming()` method in `claude_code.py` currently yields plain text strings. It needs to yield the structured event dicts from `claude_sdk.py`.

- [ ] **Step 1: Update return type annotation and pass-through**

Change `invoke_streaming` in `claude_code.py`:

Replace:
```python
    def invoke_streaming(self, message: str, agent_type: str = "principal",
                          model: str = None, session_id: str = None,
                          skills: List[str] = None,
                          history: List[dict] = None) -> Generator[str, None, None]:
        """Invoke Claude Code CLI or SDK with streaming output"""

        # Use SDK if available
        if self.use_sdk and self.sdk_service:
            yield from self.sdk_service.invoke_streaming(
                message=message,
                agent_type=agent_type,
                model=model,
                session_id=session_id,
                skills=skills,
                history=history,
            )
            return

        # Fallback to CLI
        yield from self._invoke_streaming_cli(message, agent_type, model, session_id, skills)
```

With:
```python
    def invoke_streaming(self, message: str, agent_type: str = "principal",
                          model: str = None, session_id: str = None,
                          skills: List[str] = None,
                          history: List[dict] = None) -> Generator[Dict, None, None]:
        """Invoke Claude Code CLI or SDK with streaming output.

        Yields structured event dicts:
            {"type": "text", "text": "..."}
            {"type": "tool_use", "id": "...", "name": "...", "input": {...}}
            {"type": "tool_result", "tool_use_id": "...", "content": "...", "is_error": bool}
        """
        # Use SDK if available
        if self.use_sdk and self.sdk_service:
            yield from self.sdk_service.invoke_streaming(
                message=message,
                agent_type=agent_type,
                model=model,
                session_id=session_id,
                skills=skills,
                history=history,
            )
            return

        # Fallback to CLI (wraps plain text in event format)
        for text in self._invoke_streaming_cli(message, agent_type, model, session_id, skills):
            yield {"type": "text", "text": text}
```

Also add `Dict` to the import at the top of the file:
```python
from typing import Dict, Generator, List, Optional
```

- [ ] **Step 2: Verify import**

Run: `cd /root/claudeagent/scientific_agent/backend && poetry run python -c "from src.services.claude_code import get_claude_service; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/services/claude_code.py
git commit -m "feat: update claude_code.py for structured event streaming"
```

---

## Chunk 5: Integration Test

### Task 5: End-to-end startup and smoke test

- [ ] **Step 1: Start the backend server**

Run: `cd /root/claudeagent/scientific_agent/backend && poetry run uvicorn src.main:app --host 0.0.0.0 --port 9000 &`

Expected: Server starts on port 9000

- [ ] **Step 2: Test health endpoint**

Run: `curl -s http://localhost:9000/health`

Expected: `{"status": "ok"}` or similar

- [ ] **Step 3: Test full system with `start.sh`**

Run: `cd /root/claudeagent/scientific_agent && ./start.sh`

Expected: Both backend (port 9000) and frontend (port 9001) start successfully

- [ ] **Step 4: Manual test via browser**

1. Open `http://localhost:9001`
2. Send a message like "List the files in the current directory"
3. Verify: The LLM should call the `Bash` or `Glob` tool
4. Verify: Tool execution appears in the chat UI (tool_use block with expandable result)
5. Verify: The LLM sees the tool result and provides a text summary

- [ ] **Step 5: Commit all remaining changes**

```bash
git add -A
git commit -m "feat: complete agentic tool execution loop implementation"
```

---

## Architecture Summary

```
User Message
    │
    ▼
WebSocket (websocket.py)
    │
    ▼
ClaudeCodeService (claude_code.py)  ← pass-through
    │
    ▼
ClaudeSDKService (claude_sdk.py)    ← AGENTIC LOOP
    │
    ├──► Anthropic API (with tools=[Bash, Read, Write, Edit, Glob, Grep])
    │         │
    │         ▼
    │    LLM Response (stop_reason="tool_use")
    │         │
    │         ▼
    ├──► Tool Executor (tools.py)   ← executes Bash/Read/Write/etc.
    │         │
    │         ▼
    │    Tool Results → appended to messages
    │         │
    │         ▼
    └──► Loop back to API call (until stop_reason="end_turn")
              │
              ▼
         Structured Events → WebSocket → Frontend
```

**Event flow to frontend:**
```
text event       → {"type":"claude-response", "data":{"type":"content_block_delta", "delta":{"text":"..."}}}
tool_use event   → {"type":"claude-response", "data":{"message":{"content":[{"type":"tool_use",...}]}}}
tool_result event→ {"type":"claude-response", "data":{"message":{"role":"user","content":[{"type":"tool_result",...}]}}}
status event     → {"type":"claude-status", "data":{"message":"..."}}
```
