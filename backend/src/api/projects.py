"""
Projects API - Maps sandboxes to projects for frontend compatibility
"""

import json
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.auth import get_current_user, UserResponse
from src.api.sandboxes import load_sandboxes, load_sessions, create_sandbox as create_sandbox_db
from src.api.sessions import _normalize_session

logger = logging.getLogger("MAS.Projects")
router = APIRouter()


class ProjectSession(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class Project(BaseModel):
    name: str
    displayName: str
    fullPath: str
    sessions: List[ProjectSession] = []


# ============ Routes ============

@router.get("/projects")
async def list_projects(current_user: UserResponse = Depends(get_current_user)) -> List[Project]:
    """List user's projects (mapped from sandboxes)"""
    sandboxes = load_sandboxes()
    sessions = load_sessions()

    user_sandboxes = [
        s for s in sandboxes.values()
        if s["user_id"] == current_user.id
    ]

    projects = []
    for sandbox in user_sandboxes:
        # Get sessions for this sandbox (handle both camelCase and snake_case keys)
        sandbox_sessions = []
        for session in sessions.values():
            s = _normalize_session(dict(session))  # normalize snake_case → camelCase
            if s.get("sandboxId") == sandbox["id"]:
                sandbox_sessions.append(ProjectSession(
                    id=s["id"],
                    title=s.get("title", "New Chat"),
                    created_at=s.get("createdAt", ""),
                    updated_at=s.get("updatedAt", ""),
                ))

        projects.append(Project(
            name=sandbox["id"],
            displayName=sandbox["name"],
            fullPath=sandbox["workspace_path"],
            sessions=sandbox_sessions,
        ))

    return projects


class CreateWorkspacePayload(BaseModel):
    workspaceType: str
    path: str


# NOTE: 此端点已禁用 - 项目/沙盒由系统自动管理
# 沙盒创建逻辑在其他地方实现（sandbox_service）
# Disabled: Project creation is now system-managed
@router.post("/projects/create-workspace")
async def create_workspace(
    payload: CreateWorkspacePayload,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new workspace (sandbox)

    ⚠️ DEPRECATED: 此功能已禁用
    沙盒由系统在其他地方自动创建，用户无需手动创建项目
    """
    # Return error message
    raise HTTPException(
        status_code=403,
        detail="项目由系统自动管理，无法手动创建"
    )


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    """Get project details"""
    sandboxes = load_sandboxes()
    sandbox = sandboxes.get(project_id)

    if not sandbox:
        raise HTTPException(status_code=404, detail="Project not found")

    if sandbox["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    sessions = load_sessions()
    sandbox_sessions = []
    for session in sessions.values():
        s = _normalize_session(dict(session))
        if s.get("sandboxId") == sandbox["id"]:
            sandbox_sessions.append(ProjectSession(
                id=s["id"],
                title=s.get("title", "New Chat"),
                created_at=s.get("createdAt", ""),
                updated_at=s.get("updatedAt", ""),
            ))

    return Project(
        name=sandbox["id"],
        displayName=sandbox["name"],
        fullPath=sandbox["workspace_path"],
        sessions=sandbox_sessions,
    )


@router.get("/projects/{project_id}/sessions/{session_id}/messages")
async def get_session_messages(
    project_id: str,
    session_id: str,
    limit: Optional[int] = None,
    offset: int = 0,
    current_user: UserResponse = Depends(get_current_user),
):
    """Get messages for a session, with optional pagination"""
    sandboxes = load_sandboxes()
    sandbox = sandboxes.get(project_id)

    if not sandbox:
        raise HTTPException(status_code=404, detail="Project not found")
    if sandbox["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    sessions = load_sessions()
    session = sessions.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    s = _normalize_session(dict(session))
    if s.get("sandboxId") != project_id:
        raise HTTPException(status_code=403, detail="Session does not belong to this project")

    raw_messages = session.get("messages", [])

    # Convert to the format the frontend expects
    messages = []
    for msg in raw_messages:
        messages.append({
            "role": msg.get("role", "user"),
            "content": msg.get("content", ""),
            "timestamp": msg.get("timestamp", s.get("createdAt", "")),
        })

    total = len(messages)

    if limit is not None:
        # Paginate: return `limit` messages starting from end minus offset
        start = max(0, total - offset - limit)
        end = max(0, total - offset)
        page = messages[start:end]
        has_more = start > 0
    else:
        page = messages
        has_more = False

    return {
        "messages": page,
        "total": total,
        "hasMore": has_more,
    }


@router.get("/projects/{project_id}/sessions/{session_id}/token-usage")
async def get_session_token_usage(
    project_id: str,
    session_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Return token usage stats for a session (stub)"""
    return {
        "inputTokens": 0,
        "outputTokens": 0,
        "totalTokens": 0,
        "costUsd": 0.0,
    }


@router.delete("/projects/{project_id}/sessions/{session_id}")
async def delete_project_session(
    project_id: str,
    session_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Delete a session from a project"""
    from src.api.sandboxes import save_sessions

    sandboxes = load_sandboxes()
    sandbox = sandboxes.get(project_id)

    if not sandbox:
        raise HTTPException(status_code=404, detail="Project not found")
    if sandbox["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    sessions = load_sessions()
    session = sessions.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    s = _normalize_session(dict(session))
    if s.get("sandboxId") != project_id:
        raise HTTPException(status_code=403, detail="Session does not belong to this project")

    # Delete the session
    del sessions[session_id]
    save_sessions(sessions)

    logger.info(f"[projects] Deleted session {session_id} from project {project_id}")
    return {"status": "ok", "message": "Session deleted"}


# NOTE: 此端点已禁用 - 项目由系统自动管理
# Disabled: Project deletion is now system-managed
@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    force: bool = False,
    current_user: UserResponse = Depends(get_current_user)
):
    """Delete a project (sandbox) and all its sessions

    ⚠️ DEPRECATED: 此功能已禁用
    项目/沙盒由系统自动管理，用户无法删除
    """
    raise HTTPException(
        status_code=403,
        detail="项目由系统自动管理，无法手动删除"
    )


@router.get("/projects/{project_id}/files")
async def list_project_files(
    project_id: str,
    path: str = "",
    current_user: UserResponse = Depends(get_current_user),
):
    """List files in a project's workspace directory"""
    sandboxes = load_sandboxes()
    sandbox = sandboxes.get(project_id)

    if not sandbox:
        raise HTTPException(status_code=404, detail="Project not found")
    if sandbox["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    workspace_path = Path(sandbox["workspace_path"])
    target = (workspace_path / path).resolve()

    # Security: ensure target is inside workspace
    try:
        target.relative_to(workspace_path.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")

    if not target.exists():
        return {"files": [], "path": path}

    files = []
    try:
        for entry in sorted(target.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            files.append({
                "name": entry.name,
                "path": str(entry.relative_to(workspace_path)),
                "type": "directory" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else 0,
            })
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    # Return as array — frontend (useFileMentions.tsx) expects ProjectFileNode[]
    return files

