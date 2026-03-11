"""
WebSocket API - Real-time chat with Claude Code
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from src.api.auth import get_current_user, UserResponse
from src.api.sandboxes import load_sandboxes, load_sessions, save_sessions
from src.services.claude_code import get_claude_service

logger = logging.getLogger("MAS.WebSocket")
router = APIRouter()


# ============ WebSocket Manager ============

class ConnectionManager:
    """Manage WebSocket connections"""

    def __init__(self):
        # session_id -> set of WebSockets
        self.active_connections: Dict[str, set] = {}

    async def connect(self, session_id: str, websocket: WebSocket):
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()
        self.active_connections[session_id].add(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket):
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]

    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            # Send to all connections for this session
            # For now, just send to the first one
            for ws in list(self.active_connections[session_id]):
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.error(f"[ws] Send error: {e}")


manager = ConnectionManager()


# ============ Claude Code Helper ============

def get_claude_dir() -> Path:
    """Get .claude directory from project root"""
    return Path(__file__).parent.parent.parent.parent / ".claude"


def get_workspace_for_session(session_id: str, user_id: str) -> Optional[Path]:
    """Get workspace path for a session"""
    sessions = load_sessions()
    session = sessions.get(session_id)

    if not session:
        return None

    sandboxes = load_sandboxes()
    sandbox = sandboxes.get(session["sandbox_id"])

    if not sandbox or sandbox["user_id"] != user_id:
        return None

    return Path(sandbox["workspace_path"])


def build_claude_command(workspace: Path, message: str, history: list = None) -> list:
    """Build Claude Code CLI command"""
    claude_dir = get_claude_dir()

    # Build system prompt with history context
    history_context = ""
    if history:
        history_lines = []
        for msg in history[-10:]:  # Last 10 messages
            role = msg.get("role", "user")
            content = msg.get("content", "")
            history_lines.append(f"{role.upper()}: {content[:200]}")
        history_context = "\n\n## Recent Conversation\n" + "\n".join(history_lines)

    system_prompt = f"""You are Claude Code, an AI assistant. You are helpful, creative, and clever.

## Instructions
- Respond to the user's message
- You can read and write files in the workspace
- Use tools when appropriate
- Be concise but thorough{history_context}

Current message: {message}

Respond now:"""

    cmd = [
        "claude",
        "-p",
        "--print",
        "--output-format", "stream-json",
        "--include-partial-messages",
        "--add-dir", str(claude_dir),
        "--setting-sources", "project",
    ]

    # Load settings.env
    settings_file = claude_dir / "settings.local.json"
    if settings_file.exists():
        pass  # We'll load this in the environment

    return cmd, system_prompt


async def stream_claude_response(websocket: WebSocket, session_id: str, message: str, user_id: str):
    """Stream Claude Code response to WebSocket using SDK"""
    workspace = get_workspace_for_session(session_id, user_id)

    if not workspace:
        await manager.send_message(session_id, {
            "type": "error",
            "message": "Session not found"
        })
        return

    # Load session history
    sessions = load_sessions()
    session = sessions.get(session_id, {})
    history = session.get("messages", [])

    try:
        # Get Claude service (now uses SDK by default)
        claude_service = get_claude_service()

        # Send thinking status
        await manager.send_message(session_id, {"type": "status", "state": "thinking"})

        response_text = ""

        # Use SDK streaming
        for chunk in claude_service.invoke_streaming(
            message=message,
            agent_type="principal",
            session_id=session_id
        ):
            response_text += chunk
            await manager.send_message(session_id, {
                "type": "response",
                "content": chunk,
                "delta": True
            })

        # Send complete status
        await manager.send_message(session_id, {
            "type": "status",
            "state": "complete"
        })

        # Save message to history
        sessions = load_sessions()
        if session_id in sessions:
            sessions[session_id]["messages"] = history + [
                {"role": "user", "content": message},
                {"role": "assistant", "content": response_text}
            ]
            save_sessions(sessions)

        logger.info(f"[ws] Session {session_id} completed, response length: {len(response_text)}")

    except Exception as e:
        logger.error(f"[ws] Claude execution error: {e}")
        await manager.send_message(session_id, {
            "type": "error",
            "message": str(e)
        })


# ============ WebSocket Endpoint ============

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time chat"""
    # Note: For simplicity, we don't do JWT validation on WebSocket here
    # In production, you should validate the token from query params

    await manager.connect(session_id, websocket)

    try:
        # Send welcome message
        await websocket.send_json({
            "type": "status",
            "state": "connected",
            "session_id": session_id
        })

        # Handle messages
        while True:
            data = await websocket.receive_text()
            try:
                message_data = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })
                continue

            msg_type = message_data.get("type")
            message = message_data.get("content", "")
            user_id = message_data.get("user_id", "")  # In production, get from token

            if msg_type == "message":
                # Start Claude response in background
                asyncio.create_task(
                    stream_claude_response(websocket, session_id, message, user_id)
                )
            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)
        logger.info(f"[ws] Client disconnected: {session_id}")
    except Exception as e:
        logger.error(f"[ws] Error: {e}")
        manager.disconnect(session_id, websocket)


import logging
