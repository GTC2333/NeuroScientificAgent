"""
Session API - CRUD over sessions.json (System A)
All endpoints require authentication.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.auth import get_current_user, UserResponse
from src.api.sandboxes import load_sandboxes, load_sessions, save_sessions

logger = logging.getLogger("MAS.Sessions")
router = APIRouter()


# ============ Models ============

class SessionCreate(BaseModel):
    sandboxId: Optional[str] = None  # Optional - auto-associate if not provided
    title: Optional[str] = "New Chat"
    agents: List[str] = ["principal"]
    skills: List[str] = []


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    agents: Optional[List[str]] = None
    skills: Optional[List[str]] = None


class MessageItem(BaseModel):
    role: str
    content: str
    agent: Optional[str] = None
    timestamp: Optional[str] = None


class SessionResponse(BaseModel):
    id: str
    sandboxId: str
    title: str
    agents: List[str]
    skills: List[str]
    messages: List[Dict[str, Any]]
    createdAt: str
    updatedAt: str


# ============ Helpers ============

def _user_owns_sandbox(sandbox_id: str, user_id: str) -> bool:
    """Check if user owns the sandbox that the session belongs to"""
    sandboxes = load_sandboxes()
    sandbox = sandboxes.get(sandbox_id)
    return sandbox is not None and sandbox["user_id"] == user_id


def _normalize_session(session: dict) -> dict:
    """Normalize legacy snake_case keys to camelCase for backward compatibility"""
    if "sandboxId" not in session and "sandbox_id" in session:
        session["sandboxId"] = session["sandbox_id"]
    if "createdAt" not in session and "created_at" in session:
        session["createdAt"] = session["created_at"]
    if "updatedAt" not in session and "updated_at" in session:
        session["updatedAt"] = session["updated_at"]
    if "agents" not in session:
        session["agents"] = ["principal"]
    if "skills" not in session:
        session["skills"] = []
    return session


def _get_session_or_404(session_id: str, user_id: str) -> dict:
    """Load session, verify ownership via its sandbox, or raise 404/403"""
    sessions = load_sessions()
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session = _normalize_session(session)
    if not _user_owns_sandbox(session["sandboxId"], user_id):
        raise HTTPException(status_code=403, detail="Access denied")
    return session


# ============ Routes ============

@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    data: SessionCreate,
    current_user: UserResponse = Depends(get_current_user),
):
    """Create a new session within a sandbox.

    If sandboxId is not provided, automatically associates with user's default sandbox.
    """
    # Auto-associate with user's sandbox if not provided
    sandbox_id = data.sandboxId
    if not sandbox_id:
        sandboxes = load_sandboxes()
        user_sandboxes = [
            s for s in sandboxes.values()
            if s["user_id"] == current_user.id
        ]
        if not user_sandboxes:
            raise HTTPException(
                status_code=403,
                detail="No sandbox found. Please create a workspace first."
            )
        # Use the first (and only) sandbox
        sandbox_id = user_sandboxes[0]["id"]
    else:
        # Verify ownership if sandboxId is provided
        if not _user_owns_sandbox(sandbox_id, current_user.id):
            raise HTTPException(status_code=403, detail="Access denied to sandbox")

    session_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()

    session = {
        "id": session_id,
        "sandboxId": sandbox_id,
        "title": data.title or "New Chat",
        "agents": data.agents,
        "skills": data.skills,
        "messages": [],
        "createdAt": now,
        "updatedAt": now,
    }

    sessions = load_sessions()
    sessions[session_id] = session
    save_sessions(sessions)

    logger.info(f"[sessions] Created session {session_id} in sandbox {sandbox_id}")
    return SessionResponse(**session)


@router.get("/sessions")
async def list_sessions_endpoint(
    sandboxId: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user),
):
    """List sessions, optionally filtered by sandbox"""
    sessions = load_sessions()
    sandboxes = load_sandboxes()

    # Get user's sandbox IDs
    user_sandbox_ids = {
        sid for sid, s in sandboxes.items()
        if s["user_id"] == current_user.id
    }

    result = []
    for session in sessions.values():
        session = _normalize_session(session)
        if session.get("sandboxId") not in user_sandbox_ids:
            continue
        if sandboxId and session.get("sandboxId") != sandboxId:
            continue
        result.append(session)

    # Sort by updatedAt descending
    result.sort(key=lambda s: s.get("updatedAt", ""), reverse=True)
    return {"sessions": result}


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Get a specific session"""
    session = _get_session_or_404(session_id, current_user.id)
    return SessionResponse(**session)


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    data: SessionUpdate,
    current_user: UserResponse = Depends(get_current_user),
):
    """Update session metadata (title, agents, skills)"""
    session = _get_session_or_404(session_id, current_user.id)

    sessions = load_sessions()
    if data.title is not None:
        sessions[session_id]["title"] = data.title
    if data.agents is not None:
        sessions[session_id]["agents"] = data.agents
    if data.skills is not None:
        sessions[session_id]["skills"] = data.skills
    sessions[session_id]["updatedAt"] = datetime.utcnow().isoformat()

    save_sessions(sessions)
    return SessionResponse(**sessions[session_id])


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Delete a session"""
    _ = _get_session_or_404(session_id, current_user.id)

    sessions = load_sessions()
    del sessions[session_id]
    save_sessions(sessions)

    logger.info(f"[sessions] Deleted session {session_id}")
    return {"status": "ok", "message": "Session deleted"}
