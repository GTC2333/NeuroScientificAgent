"""
WebSocket API - Real-time chat with Claude Code
Matches the frontend protocol: single /ws connection, claude-command messages,
session-created/claude-response/claude-complete response types.
"""

import asyncio
import json
import logging
import os
import pty
import select
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from src.api.auth import decode_token, load_users
from src.api.sandboxes import load_sandboxes, load_sessions, save_sessions
from src.api.sessions import _normalize_session
from src.services.claude_code import get_claude_service

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

logger = logging.getLogger("MAS.WebSocket")
router = APIRouter()


# ============ WebSocket Manager ============

class ConnectionManager:
    """Manage WebSocket connections (one per authenticated user)"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}  # user_id -> WebSocket
        self.active_tasks: Dict[str, asyncio.Task] = {}     # session_id -> Task

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        # Close existing connection for this user if any
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].close()
            except Exception:
                pass
        self.active_connections[user_id] = websocket
        logger.info(f"[ws] User {user_id} connected")

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)
        logger.info(f"[ws] User {user_id} disconnected")

    async def send_to_user(self, user_id: str, message: dict):
        ws = self.active_connections.get(user_id)
        if ws:
            try:
                msg_type = message.get("type", "unknown")
                logger.info(f"[ws] >>> send_to_user: type={msg_type}, sessionId={message.get('sessionId', 'N/A')}")
                await ws.send_json(message)
                logger.info(f"[ws] <<< send_to_user SUCCESS: type={msg_type}")
            except Exception as e:
                logger.error(f"[ws] Send error to {user_id}: {e}", exc_info=True)
        else:
            logger.warning(f"[ws] No active connection for user_id={user_id}")

    def cancel_task(self, session_id: str):
        task = self.active_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()


manager = ConnectionManager()


# ============ Auth Helper ============

def authenticate_ws_token(token: str) -> Optional[dict]:
    """Authenticate WebSocket connection via JWT token in query param.
    Returns user dict or None."""
    if not token:
        return None

    payload = decode_token(token)
    if not payload:
        return None

    username = payload.get("sub")
    if not username:
        return None

    users = load_users()
    user_data = users.get(username)
    if not user_data:
        return None

    return {
        "id": user_data["id"],
        "username": user_data["username"],
    }


# ============ Session Helper ============

def find_sandbox_for_project(project_path: str, user_id: str) -> Optional[str]:
    """Find sandbox ID for a project path belonging to user"""
    sandboxes = load_sandboxes()
    for sandbox_id, sandbox in sandboxes.items():
        if sandbox["user_id"] == user_id:
            if sandbox.get("workspace_path") == project_path or sandbox_id == project_path:
                return sandbox_id
    # Fallback: return first sandbox for user
    for sandbox_id, sandbox in sandboxes.items():
        if sandbox["user_id"] == user_id:
            return sandbox_id
    return None


def build_projects_for_user(user_id: str) -> list:
    """Build projects list for a user (same format as GET /api/projects)"""
    sandboxes = load_sandboxes()
    sessions = load_sessions()

    user_sandboxes = [s for s in sandboxes.values() if s["user_id"] == user_id]
    projects = []
    for sandbox in user_sandboxes:
        sandbox_sessions = []
        for session in sessions.values():
            s = _normalize_session(dict(session))
            if s.get("sandboxId") == sandbox["id"]:
                sandbox_sessions.append({
                    "id": s["id"],
                    "title": s.get("title", "New Chat"),
                    "created_at": s.get("createdAt", ""),
                    "updated_at": s.get("updatedAt", ""),
                })
        projects.append({
            "name": sandbox["id"],
            "displayName": sandbox["name"],
            "fullPath": sandbox["workspace_path"],
            "sessions": sandbox_sessions,
        })
    return projects


def create_session(sandbox_id: str, title: str = "New Chat") -> str:
    """Create a new session and return its ID"""
    session_id = str(uuid.uuid4())
    sessions = load_sessions()
    now = datetime.utcnow().isoformat()

    sessions[session_id] = {
        "id": session_id,
        "sandboxId": sandbox_id,
        "title": title,
        "agents": ["principal"],
        "skills": [],
        "messages": [],
        "createdAt": now,
        "updatedAt": now,
    }
    save_sessions(sessions)
    logger.info(f"[ws] Created session {session_id} for sandbox {sandbox_id}")
    return session_id


def save_message_to_session(session_id: str, role: str, content: str):
    """Append a message to session history"""
    sessions = load_sessions()
    if session_id in sessions:
        sessions[session_id]["messages"].append({
            "role": role,
            "content": content,
        })
        sessions[session_id]["updatedAt"] = datetime.utcnow().isoformat()

        # Auto-set title from first user message
        if role == "user" and sessions[session_id]["title"] == "New Chat":
            sessions[session_id]["title"] = content[:80]

        save_sessions(sessions)


# ============ Claude Invocation ============

async def handle_claude_command(user_id: str, message_data: dict):
    """Process a claude-command message and stream response back to user"""

    # ===== INCOMING MESSAGE LOGGING =====
    logger.info(f"[ws] ========== INCOMING COMMAND ==========")
    logger.info(f"[ws] user_id: {user_id}")
    logger.info(f"[ws] FULL MESSAGE DATA:")
    logger.info(f"[ws] {json.dumps(message_data, indent=2, ensure_ascii=False)[:2000]}")

    command = message_data.get("command", "")
    options = message_data.get("options", {})
    session_id = options.get("sessionId")
    project_path = options.get("projectPath", "")

    logger.info(f"[ws] Parsed command: {command[:200]}..." if len(command) > 200 else f"[ws] Parsed command: {command}")
    logger.info(f"[ws] Parsed options: session_id={session_id}, project_path={project_path}")
    logger.info(f"[ws] =======================================")

    if not command:
        await manager.send_to_user(user_id, {
            "type": "claude-error",
            "sessionId": session_id,
            "error": "Empty command",
        })
        return

    # Determine sandbox
    sandbox_id = find_sandbox_for_project(project_path, user_id)
    if not sandbox_id:
        await manager.send_to_user(user_id, {
            "type": "claude-error",
            "sessionId": session_id,
            "error": "No workspace found. Please create a workspace first.",
        })
        return

    # Create new session if needed
    is_new_session = not session_id or session_id.startswith("new-session-")
    if is_new_session:
        session_id = create_session(sandbox_id, command[:80])
        # Notify frontend of the new session ID
        await manager.send_to_user(user_id, {
            "type": "session-created",
            "sessionId": session_id,
        })

    # Load existing history (without the new message)
    sessions_data = load_sessions()
    session_data = sessions_data.get(session_id, {})
    history = session_data.get("messages", [])

    # ===== HISTORY LOGGING =====
    logger.info(f"[ws] Loaded history: {len(history)} messages")
    for i, msg in enumerate(history):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        logger.info(f"[ws]   [{i}] role={role}, content_len={len(content)}")
        logger.info(f"[ws]   [{i}] content preview: {content[:150]}..." if len(content) > 150 else f"[ws]   [{i}] content: {content}")

    # Note: user message is saved AFTER the response completes (line 283)
    # This prevents duplication since claude_sdk.py appends the message parameter

    # Send status: thinking
    await manager.send_to_user(user_id, {
        "type": "claude-status",
        "sessionId": session_id,
        "data": {
            "message": "Thinking...",
            "tokens": 0,
            "can_interrupt": True,
        },
    })

    try:
        logger.info(f"[ws] ========== HANDLING CLAUDE COMMAND ==========")
        logger.info(f"[ws] session_id: {session_id}")
        logger.info(f"[ws] command: {command[:100]}...")
        logger.info(f"[ws] history length: {len(history)}")

        # Check if sandbox has a Docker container API URL
        sandboxes_data = load_sandboxes()
        sandbox_data = sandboxes_data.get(sandbox_id, {})
        sandbox_api_url = sandbox_data.get("api_url")
        sandbox_api_key = sandbox_data.get("api_key", "")

        response_text = ""

        if sandbox_api_url and HAS_HTTPX:
            # ===== PROXY MODE: Stream from sandbox container via SSE =====
            logger.info(f"[ws] Proxy mode: streaming from {sandbox_api_url}")

            request_body = {
                "message": command,
                "agent_type": "principal",
                "session_id": session_id,
                "history": history,
            }
            proxy_headers = {}
            if sandbox_api_key:
                proxy_headers["X-Sandbox-API-Key"] = sandbox_api_key
            logger.debug(f"[ws] Proxy request body: message_len={len(command)}, history_len={len(history)}, has_api_key={bool(sandbox_api_key)}")

            event_count = 0
            async with httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0)) as client:
                async with client.stream(
                    "POST",
                    f"{sandbox_api_url}/execute/stream",
                    json=request_body,
                    headers=proxy_headers,
                ) as resp:
                    if resp.status_code != 200:
                        error_body = await resp.aread()
                        raise RuntimeError(
                            f"Sandbox returned HTTP {resp.status_code}: {error_body.decode()[:500]}"
                        )
                    logger.info(f"[ws] Proxy SSE connection established (HTTP {resp.status_code})")
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        try:
                            event = json.loads(line[6:])
                        except json.JSONDecodeError:
                            logger.warning(f"[ws] Proxy: bad SSE JSON: {line[:200]}")
                            continue

                        event_type = event.get("type", "")
                        event_count += 1
                        logger.debug(f"[ws] Proxy event #{event_count}: type={event_type}")

                        if event_type == "text":
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

            logger.info(f"[ws] Proxy mode complete: {event_count} events received")

        else:
            # ===== LOCAL MODE: Fallback to local execution (dev mode, no Docker) =====
            logger.info(f"[ws] Local mode: executing via ClaudeSDKService")

            claude_service = get_claude_service()

            # Stream chunks via queue to bridge thread/async boundary
            loop = asyncio.get_event_loop()
            queue: asyncio.Queue = asyncio.Queue()

            def stream_to_queue():
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
                    logger.error(f"[ws] Thread error: {e}", exc_info=True)
                    loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": str(e)})
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)

            import threading
            thread = threading.Thread(target=stream_to_queue, daemon=True)
            thread.start()

            while True:
                event = await queue.get()
                if event is None:
                    break

                event_type = event.get("type", "")

                if event_type == "text":
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

        logger.info(f"[ws] Response complete, length: {len(response_text)}")

        # Send content_block_stop
        await manager.send_to_user(user_id, {
            "type": "claude-response",
            "sessionId": session_id,
            "data": {
                "type": "content_block_stop",
            },
        })

        # Save user message first (before assistant, so history is correct)
        save_message_to_session(session_id, "user", command)
        save_message_to_session(session_id, "assistant", response_text)

        # Send claude-complete
        await manager.send_to_user(user_id, {
            "type": "claude-complete",
            "sessionId": session_id,
            "exitCode": 0,
        })

        # Notify frontend to refresh project list (new session appears in sidebar)
        if is_new_session:
            await manager.send_to_user(user_id, {
                "type": "projects_updated",
                "projects": build_projects_for_user(user_id),
            })

        logger.info(f"[ws] ========== SESSION COMPLETE ==========")
        logger.info(f"[ws] Session {session_id} completed, response length: {len(response_text)}")

    except asyncio.CancelledError:
        logger.info(f"[ws] Session {session_id} aborted by user")
        await manager.send_to_user(user_id, {
            "type": "session-aborted",
            "sessionId": session_id,
        })
    except Exception as e:
        logger.error(f"[ws] ========== CLAUDE EXECUTION ERROR ==========")
        logger.error(f"[ws] Exception type: {type(e).__name__}")
        logger.error(f"[ws] Exception message: {str(e)}")
        logger.error(f"[ws] Full traceback:", exc_info=True)
        await manager.send_to_user(user_id, {
            "type": "claude-error",
            "sessionId": session_id,
            "error": str(e),
        })
    finally:
        logger.info(f"[ws] Cleaning up session {session_id} from active_tasks")
        manager.active_tasks.pop(session_id, None)


# ============ WebSocket Endpoint ============

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(default="")):
    """Single WebSocket endpoint for all real-time communication.

    Frontend connects to /ws?token=JWT and sends messages with sessionId in payload.
    """
    # Authenticate via token query param
    user = authenticate_ws_token(token)
    if not user:
        # Must accept before closing with error in FastAPI
        await websocket.accept()
        await websocket.send_json({"type": "error", "error": "Unauthorized"})
        await websocket.close(code=4001, reason="Unauthorized")
        return

    user_id = user["id"]
    await manager.connect(user_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid JSON",
                })
                continue

            msg_type = message_data.get("type", "")
            logger.info(f"[ws] Received message type={msg_type} from user={user['username']}")

            if msg_type == "claude-command":
                # Process Claude command in background task
                session_id = message_data.get("options", {}).get("sessionId", "")
                task = asyncio.create_task(handle_claude_command(user_id, message_data))
                if session_id:
                    manager.active_tasks[session_id] = task

            elif msg_type == "abort-session":
                session_id = message_data.get("sessionId", "")
                if session_id:
                    manager.cancel_task(session_id)
                    await websocket.send_json({
                        "type": "session-aborted",
                        "sessionId": session_id,
                    })

            elif msg_type == "check-session-status":
                session_id = message_data.get("sessionId", "")
                is_processing = session_id in manager.active_tasks
                await websocket.send_json({
                    "type": "session-status",
                    "sessionId": session_id,
                    "isProcessing": is_processing,
                })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            else:
                logger.debug(f"[ws] Unhandled message type: {msg_type}")

    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"[ws] Error: {e}", exc_info=True)
        manager.disconnect(user_id)


# ============ Shell WebSocket Endpoint ============

class ShellConnection:
    """Manage a single shell/PTY connection"""

    def __init__(self, websocket: WebSocket, user_id: str):
        self.websocket = websocket
        self.user_id = user_id
        self.master_fd = None
        self.process = None
        self.task = None

    async def handle(self):
        """Handle shell WebSocket connection"""
        try:
            await self.websocket.accept()
            logger.info(f"[shell] User {self.user_id} connected")

            while True:
                data = await self.websocket.receive_text()
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    continue

                msg_type = message.get("type", "")
                logger.info(f"[shell] Received: {msg_type}")

                if msg_type == "init":
                    await self.handle_init(message)
                elif msg_type == "input":
                    self.handle_input(message)
                elif msg_type == "resize":
                    self.handle_resize(message)
                elif msg_type == "disconnect":
                    break

        except WebSocketDisconnect:
            logger.info(f"[shell] User {self.user_id} disconnected")
        except Exception as e:
            logger.error(f"[shell] Error: {e}", exc_info=True)
        finally:
            self.cleanup()

    async def handle_init(self, message: dict):
        """Initialize shell process"""
        project_path = message.get("projectPath", "")
        session_id = message.get("sessionId")
        has_session = message.get("hasSession", False)
        provider = message.get("provider", "plain-shell")
        cols = message.get("cols", 80)
        rows = message.get("rows", 24)
        initial_command = message.get("initialCommand")
        is_plain_shell = message.get("isPlainShell", False)

        logger.info(f"[shell] Init: project={project_path}, provider={provider}, plain={is_plain_shell}")

        # Validate project path
        if not project_path:
            await self.websocket.send_json({
                "type": "error",
                "error": "No project path provided"
            })
            return

        # Resolve project path
        project_path = os.path.abspath(project_path)
        if not os.path.exists(project_path):
            await self.websocket.send_json({
                "type": "error",
                "error": f"Project path does not exist: {project_path}"
            })
            return

        # Build shell command based on provider
        shell_command = self.build_shell_command(
            provider=provider,
            project_path=project_path,
            session_id=session_id,
            has_session=has_session,
            initial_command=initial_command,
            is_plain_shell=is_plain_shell
        )

        logger.info(f"[shell] Executing: {shell_command}")

        # Start PTY process
        try:
            self.master_fd, slave_fd = pty.openpty()

            # Set terminal size
            import fcntl
            import termios
            import struct

            # Create winsize struct with correct dimensions
            winsize = struct.pack('HHHH', rows, cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

            # Start the shell process
            self.process = subprocess.Popen(
                shell_command,
                shell=True,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                cwd=project_path,
                start_new_session=True,
                env={**os.environ, "TERM": "xterm-256color"}
            )

            # Close slave fd in parent
            os.close(slave_fd)

            # Start reading output in background task
            self.task = asyncio.create_task(self.read_output())

            logger.info(f"[shell] Shell started with PID: {self.process.pid}")

        except Exception as e:
            logger.error(f"[shell] Failed to start shell: {e}")
            await self.websocket.send_json({
                "type": "error",
                "error": f"Failed to start shell: {str(e)}"
            })

    def build_shell_command(self, provider: str, project_path: str, session_id: Optional[str],
                           has_session: bool, initial_command: Optional[str], is_plain_shell: bool) -> str:
        """Build the shell command based on provider"""

        if is_plain_shell:
            # Plain shell mode - just run initial command in project directory
            if initial_command:
                return f'cd "{project_path}" && {initial_command}'
            return f'cd "{project_path}" && $SHELL'

        # Provider-specific commands
        if provider == "claude" or provider == "anthropic":
            if session_id:
                return f'cd "{project_path}" && claude --resume {session_id} || claude'
            return f'cd "{project_path}" && claude'

        elif provider == "cursor":
            if session_id:
                return f'cd "{project_path}" && cursor-agent --resume="{session_id}"'
            return f'cd "{project_path}" && cursor-agent'

        elif provider == "codex":
            if session_id:
                return f'cd "{project_path}" && codex resume "{session_id}" || codex'
            return f'cd "{project_path}" && codex'

        elif provider == "gemini":
            if session_id:
                return f'cd "{project_path}" && gemini --resume="{session_id}"'
            return f'cd "{project_path}" && gemini'

        else:
            # Default to plain shell
            if initial_command:
                return f'cd "{project_path}" && {initial_command}'
            return f'cd "{project_path}" && $SHELL'

    async def read_output(self):
        """Read output from PTY and send to WebSocket"""
        try:
            while True:
                if self.master_fd is None:
                    break

                # Use select to check if data is available
                ready, _, _ = select.select([self.master_fd], [], [], 0.1)

                if ready:
                    try:
                        data = os.read(self.master_fd, 4096)
                        if data:
                            await self.websocket.send_json({
                                "type": "output",
                                "data": data.decode("utf-8", errors="replace")
                            })
                    except OSError:
                        break

                # Check if process exited
                if self.process and self.process.poll() is not None:
                    # Process exited, send exit code
                    exit_code = self.process.returncode
                    await self.websocket.send_json({
                        "type": "output",
                        "data": f"\r\nProcess exited with code {exit_code}\r\n"
                    })
                    break

                await asyncio.sleep(0.01)

        except Exception as e:
            logger.error(f"[shell] Error reading output: {e}")
        finally:
            self.cleanup()

    def handle_input(self, message: dict):
        """Forward input to PTY"""
        data = message.get("data", "")
        if self.master_fd and data:
            try:
                os.write(self.master_fd, data.encode("utf-8"))
            except OSError as e:
                logger.error(f"[shell] Error writing input: {e}")

    def handle_resize(self, message: dict):
        """Handle terminal resize"""
        if self.master_fd:
            cols = message.get("cols", 80)
            rows = message.get("rows", 24)
            try:
                import fcntl
                import termios
                import struct
                winsize = struct.pack('HHHH', rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
            except Exception as e:
                logger.error(f"[shell] Error resizing terminal: {e}")

    def cleanup(self):
        """Clean up resources"""
        if self.master_fd:
            try:
                os.close(self.master_fd)
            except:
                pass
            self.master_fd = None

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None


@router.websocket("/shell")
async def shell_websocket_endpoint(websocket: WebSocket, token: str = Query(default="")):
    """WebSocket endpoint for shell/terminal connections.

    Frontend connects to /shell?token=JWT and sends init/input/resize messages.
    """
    # Authenticate via token query param
    user = authenticate_ws_token(token)
    if not user:
        await websocket.accept()
        await websocket.send_json({"type": "error", "error": "Unauthorized"})
        await websocket.close(code=4001, reason="Unauthorized")
        return

    user_id = user["id"]
    shell_conn = ShellConnection(websocket, user_id)
    await shell_conn.handle()
