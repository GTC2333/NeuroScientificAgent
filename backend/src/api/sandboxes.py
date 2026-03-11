"""
Sandbox API - Manage user sandboxes (workspaces)
"""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.api.auth import get_current_user, UserResponse

logger = logging.getLogger("MAS.Sandboxes")
router = APIRouter()

# Base port for sandboxes
BASE_PORT = 9002


# ============ Models ============

class SandboxCreate(BaseModel):
    name: Optional[str] = None  # User can provide custom name like "myproject"


class SandboxResponse(BaseModel):
    id: str
    user_id: str
    name: str
    port: int
    workspace_path: str
    status: str
    created_at: str


class SessionCreate(BaseModel):
    title: str
    sandbox_id: Optional[str] = None


class SessionResponse(BaseModel):
    id: str
    sandbox_id: str
    title: str
    messages: List[dict] = []
    created_at: str
    updated_at: str


# ============ Database Helpers ============

def get_sandboxes_path() -> Path:
    return Path(__file__).parent.parent.parent / "data" / "sandboxes.json"


def load_sandboxes() -> dict:
    db_path = get_sandboxes_path()
    if not db_path.exists():
        return {}
    with open(db_path, "r") as f:
        return json.load(f)


def save_sandboxes(sandboxes: dict):
    db_path = get_sandboxes_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with open(db_path, "w") as f:
        json.dump(sandboxes, f, indent=2)


def get_sessions_path() -> Path:
    return Path(__file__).parent.parent.parent / "data" / "sessions.json"


def load_sessions() -> dict:
    db_path = get_sessions_path()
    if not db_path.exists():
        return {}
    with open(db_path, "r") as f:
        return json.load(f)


def save_sessions(sessions: dict):
    db_path = get_sessions_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with open(db_path, "w") as f:
        json.dump(sessions, f, indent=2)


def get_workspaces_base() -> Path:
    """Get base workspace directory"""
    base = Path(__file__).parent.parent.parent / "data" / "workspaces"
    base.mkdir(parents=True, exist_ok=True)
    return base


def init_default_workspace():
    """Initialize default temp_workspace on startup if it doesn't exist"""
    import shutil

    # Use the project's temp_workspace directory
    project_root = Path(__file__).parent.parent.parent.parent
    default_workspace = project_root / "temp_workspace"

    # Ensure the directory exists
    default_workspace.mkdir(parents=True, exist_ok=True)

    # Copy .claude directory if exists
    project_claude_dir = project_root / ".claude"
    if project_claude_dir.exists():
        workspace_claude = default_workspace / ".claude"
        if not workspace_claude.exists():
            shutil.copytree(project_claude_dir, workspace_claude, dirs_exist_ok=True)

    logger.info(f"[sandboxes] Default workspace initialized at {default_workspace}")


def get_default_workspace_path() -> Path:
    """Get the default temp_workspace path"""
    return Path(__file__).parent.parent.parent.parent / "temp_workspace"


def get_next_port() -> int:
    """Get next available port"""
    sandboxes = load_sandboxes()
    used_ports = {s["port"] for s in sandboxes.values()}

    port = BASE_PORT
    while port in used_ports:
        port += 1

    return port


# ============ Routes ============

@router.post("/sandboxes", response_model=SandboxResponse)
async def create_sandbox(
    data: SandboxCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new sandbox (workspace)"""
    sandboxes = load_sandboxes()

    # Check user's existing sandboxes
    user_sandboxes = [s for s in sandboxes.values() if s["user_id"] == current_user.id]
    # No limit for MVP

    # Generate sandbox details
    sandbox_id = str(uuid.uuid4())
    port = get_next_port()

    # Use user-provided name or default
    sandbox_name = data.name.strip() if data.name else f"sandbox-{len(user_sandboxes) + 1}"

    # Create workspace directory - use custom name if provided
    workspace_path = get_workspaces_base() / current_user.id / sandbox_name
    workspace_path.mkdir(parents=True, exist_ok=True)

    # Copy .claude directory to workspace
    project_claude_dir = Path(__file__).parent.parent.parent.parent / ".claude"
    if project_claude_dir.exists():
        workspace_claude = workspace_path / ".claude"
        import shutil
        if not workspace_claude.exists():
            shutil.copytree(project_claude_dir, workspace_claude, dirs_exist_ok=True)

    sandbox = {
        "id": sandbox_id,
        "user_id": current_user.id,
        "name": sandbox_name,
        "port": port,
        "workspace_path": str(workspace_path),
        "status": "running",  # Auto-start for now
        "created_at": datetime.utcnow().isoformat()
    }

    sandboxes[sandbox_id] = sandbox
    save_sandboxes(sandboxes)

    logger.info(f"[sandboxes] Created sandbox {sandbox_id} for user {current_user.username} with name '{sandbox_name}'")

    return SandboxResponse(**sandbox)


@router.get("/sandboxes", response_model=List[SandboxResponse])
async def list_sandboxes(current_user: UserResponse = Depends(get_current_user)):
    """List user's sandboxes"""
    sandboxes = load_sandboxes()
    user_sandboxes = [
        SandboxResponse(**s)
        for s in sandboxes.values()
        if s["user_id"] == current_user.id
    ]
    return user_sandboxes


@router.get("/sandboxes/{sandbox_id}", response_model=SandboxResponse)
async def get_sandbox(
    sandbox_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get sandbox details"""
    sandboxes = load_sandboxes()
    sandbox = sandboxes.get(sandbox_id)

    if not sandbox:
        raise HTTPException(status_code=404, detail="Sandbox not found")

    if sandbox["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    return SandboxResponse(**sandbox)


@router.delete("/sandboxes/{sandbox_id}")
async def delete_sandbox(
    sandbox_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete a sandbox"""
    sandboxes = load_sandboxes()
    sandbox = sandboxes.get(sandbox_id)

    if not sandbox:
        raise HTTPException(status_code=404, detail="Sandbox not found")

    if sandbox["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Delete workspace directory
    import shutil
    workspace_path = Path(sandbox["workspace_path"])
    if workspace_path.exists():
        shutil.rmtree(workspace_path)

    # Delete sandbox
    del sandboxes[sandbox_id]
    save_sandboxes(sandboxes)

    # Delete associated sessions
    sessions = load_sessions()
    sessions_to_delete = [sid for sid, s in sessions.items() if s["sandbox_id"] == sandbox_id]
    for sid in sessions_to_delete:
        del sessions[sid]
    save_sessions(sessions)

    logger.info(f"[sandboxes] Deleted sandbox {sandbox_id}")

    return {"message": "Sandbox deleted"}


@router.post("/sandboxes/{sandbox_id}/start")
async def start_sandbox(
    sandbox_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Start a sandbox"""
    sandboxes = load_sandboxes()
    sandbox = sandboxes.get(sandbox_id)

    if not sandbox:
        raise HTTPException(status_code=404, detail="Sandbox not found")

    if sandbox["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    sandbox["status"] = "running"
    sandboxes[sandbox_id] = sandbox
    save_sandboxes(sandboxes)

    return {"status": "running"}


@router.post("/sandboxes/{sandbox_id}/stop")
async def stop_sandbox(
    sandbox_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Stop a sandbox"""
    sandboxes = load_sandboxes()
    sandbox = sandboxes.get(sandbox_id)

    if not sandbox:
        raise HTTPException(status_code=404, detail="Sandbox not found")

    if sandbox["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    sandbox["status"] = "stopped"
    sandboxes[sandbox_id] = sandbox
    save_sandboxes(sandboxes)

    return {"status": "stopped"}


# ============ Sessions ============

@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    data: SessionCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new session in a sandbox"""
    # Find user's sandbox (use provided or first one)
    sandboxes = load_sandboxes()
    user_sandboxes = [s for s in sandboxes.values() if s["user_id"] == current_user.id]

    if not user_sandboxes:
        raise HTTPException(status_code=400, detail="No sandbox available. Create one first.")

    sandbox = None
    if data.sandbox_id:
        for s in user_sandboxes:
            if s["id"] == data.sandbox_id:
                sandbox = s
                break
        if not sandbox:
            raise HTTPException(status_code=404, detail="Sandbox not found")
    else:
        sandbox = user_sandboxes[0]  # Use first sandbox

    # Create session
    sessions = load_sessions()
    session_id = str(uuid.uuid4())

    session = {
        "id": session_id,
        "sandbox_id": sandbox["id"],
        "title": data.title,
        "messages": [],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }

    sessions[session_id] = session
    save_sessions(sessions)

    logger.info(f"[sessions] Created session {session_id} in sandbox {sandbox['id']}")

    return SessionResponse(**session)


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    sandbox_id: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user)
):
    """List sessions"""
    sandboxes = load_sandboxes()
    user_sandbox_ids = {s["id"] for s in sandboxes.values() if s["user_id"] == current_user.id}

    sessions = load_sessions()
    user_sessions = [
        SessionResponse(**s)
        for s in sessions.values()
        if s["sandbox_id"] in user_sandbox_ids
        and (not sandbox_id or s["sandbox_id"] == sandbox_id)
    ]
    return user_sessions


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get session details"""
    sandboxes = load_sandboxes()
    user_sandbox_ids = {s["id"] for s in sandboxes.values() if s["user_id"] == current_user.id}

    sessions = load_sessions()
    session = sessions.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["sandbox_id"] not in user_sandbox_ids:
        raise HTTPException(status_code=403, detail="Access denied")

    return SessionResponse(**session)


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete a session"""
    sandboxes = load_sandboxes()
    user_sandbox_ids = {s["id"] for s in sandboxes.values() if s["user_id"] == current_user.id}

    sessions = load_sessions()
    session = sessions.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["sandbox_id"] not in user_sandbox_ids:
        raise HTTPException(status_code=403, detail="Access denied")

    del sessions[session_id]
    save_sessions(sessions)

    return {"message": "Session deleted"}


@router.put("/sessions/{session_id}/messages")
async def update_session_messages(
    session_id: str,
    messages: list,
    current_user: UserResponse = Depends(get_current_user)
):
    """Update session messages"""
    sandboxes = load_sandboxes()
    user_sandbox_ids = {s["id"] for s in sandboxes.values() if s["user_id"] == current_user.id}

    sessions = load_sessions()
    session = sessions.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["sandbox_id"] not in user_sandbox_ids:
        raise HTTPException(status_code=403, detail="Access denied")

    session["messages"] = messages
    session["updated_at"] = datetime.utcnow().isoformat()
    sessions[session_id] = session
    save_sessions(sessions)

    return {"message": "Messages updated"}
