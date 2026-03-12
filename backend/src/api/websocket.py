"""
WebSocket API - Real-time chat with Claude Code
Matches the frontend protocol: single /ws connection, claude-command messages,
session-created/claude-response/claude-complete response types.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from src.api.auth import decode_token, load_users
from src.api.sandboxes import load_sandboxes, load_sessions, save_sessions
from src.api.sessions import _normalize_session
from src.services.claude_code import get_claude_service

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

        claude_service = get_claude_service()
        response_text = ""

        # Stream chunks as they arrive using a queue to bridge thread/async boundary
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def stream_to_queue():
            """Run streaming in a thread, put each event dict in the async queue"""
            logger.info(f"[ws] Stream thread starting...")
            try:
                event_count = 0
                for event in claude_service.invoke_streaming(
                    message=command,
                    agent_type="principal",
                    session_id=session_id,
                    history=history,
                ):
                    event_count += 1
                    logger.info(f"[ws] Thread received event {event_count}, type={event.get('type') if event else None}")
                    if event:
                        loop.call_soon_threadsafe(queue.put_nowait, event)
                logger.info(f"[ws] Thread finished streaming, total events: {event_count}")
            except Exception as e:
                logger.error(f"[ws] Thread error during streaming: {e}", exc_info=True)
                loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "message": str(e)})
            finally:
                logger.info(f"[ws] Thread sending sentinel (None)")
                loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

        import threading
        thread = threading.Thread(target=stream_to_queue, daemon=True)
        thread.start()
        logger.info(f"[ws] Stream thread started, waiting for events...")

        event_count = 0
        while True:
            event = await queue.get()
            logger.info(f"[ws] Main loop got event from queue: {event is not None}")
            if event is None:
                logger.info(f"[ws] Received sentinel, breaking loop")
                break
            event_count += 1

            event_type = event.get("type", "")

            if event_type == "text":
                # Stream text chunk to frontend (same format as before)
                text = event.get("text", "")
                response_text += text
                logger.info(f"[ws] Sending text event {event_count} to frontend, length={len(text)}")
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
                logger.info(f"[ws] Sending tool_use event: {event.get('name')} with id {event.get('id')}")
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
                logger.info(f"[ws] Sending tool_result event for tool_use_id: {event.get('tool_use_id')}")
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
                logger.info(f"[ws] Sending status: {event.get('message')}")
                await manager.send_to_user(user_id, {
                    "type": "claude-status",
                    "sessionId": session_id,
                    "data": {"message": event.get("message", "")},
                })

            elif event_type == "error":
                logger.error(f"[ws] Received error event: {event.get('message')}")
                await manager.send_to_user(user_id, {
                    "type": "claude-error",
                    "sessionId": session_id,
                    "error": event.get("message", "Unknown error"),
                })

        logger.info(f"[ws] All events received, total: {event_count}, response length: {len(response_text)}")
        logger.info(f"[ws] >>> COMPLETE RESPONSE (length={len(response_text)}):")
        logger.info(f"[ws] ---RESPONSE START---")
        logger.info(response_text[:1000] if len(response_text) > 1000 else response_text)
        logger.info(f"[ws] ---RESPONSE END---")

        # Send content_block_stop
        logger.info(f"[ws] Sending content_block_stop")
        await manager.send_to_user(user_id, {
            "type": "claude-response",
            "sessionId": session_id,
            "data": {
                "type": "content_block_stop",
            },
        })

        # Save user message first (before assistant, so history is correct)
        logger.info(f"[ws] Saving messages to session...")
        save_message_to_session(session_id, "user", command)
        # Save assistant response
        save_message_to_session(session_id, "assistant", response_text)

        # Send claude-complete
        logger.info(f"[ws] Sending claude-complete message")
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
