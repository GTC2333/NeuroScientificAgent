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
        # Get sessions for this sandbox
        sandbox_sessions = [
            ProjectSession(
                id=session["id"],
                title=session["title"],
                created_at=session["created_at"],
                updated_at=session["updated_at"]
            )
            for session in sessions.values()
            if session["sandbox_id"] == sandbox["id"]
        ]

        projects.append(Project(
            name=sandbox["id"],
            displayName=sandbox["name"],
            fullPath=sandbox["workspace_path"],
            sessions=sandbox_sessions
        ))

    return projects


class CreateWorkspacePayload(BaseModel):
    workspaceType: str
    path: str


@router.post("/projects/create-workspace")
async def create_workspace(
    payload: CreateWorkspacePayload,
    current_user: UserResponse = Depends(get_current_user)
):
    """Create a new workspace (sandbox)"""
    import uuid
    from datetime import datetime
    from src.api.sandboxes import (
        get_workspaces_base, get_next_port, save_sandboxes,
        get_sandboxes_path, BASE_PORT
    )
    import shutil

    # Extract workspace name from path (e.g., "myproject" from "/path/to/myproject")
    workspace_path = Path(payload.path)
    workspace_name = workspace_path.name if workspace_path.name else f"workspace-{uuid.uuid4().hex[:8]}"

    # Generate sandbox details
    sandbox_id = str(uuid.uuid4())
    port = get_next_port()

    # Create workspace directory
    workspaces_base = get_workspaces_base()
    user_workspace = workspaces_base / current_user.id / workspace_name
    user_workspace.mkdir(parents=True, exist_ok=True)

    # Copy .claude directory if exists
    project_root = user_workspace.parent.parent.parent.parent
    project_claude_dir = project_root / ".claude"
    if project_claude_dir.exists():
        workspace_claude = user_workspace / ".claude"
        if not workspace_claude.exists():
            shutil.copytree(project_claude_dir, workspace_claude, dirs_exist_ok=True)

    # Load existing sandboxes and add new one
    sandboxes = load_sandboxes()

    sandbox = {
        "id": sandbox_id,
        "user_id": current_user.id,
        "name": workspace_name,
        "port": port,
        "workspace_path": str(user_workspace),
        "status": "running",
        "created_at": datetime.utcnow().isoformat()
    }

    sandboxes[sandbox_id] = sandbox
    save_sandboxes(sandboxes)

    logger.info(f"[projects] Created workspace '{workspace_name}' for user {current_user.username}")

    # Return project in the format expected by frontend
    return {
        "project": {
            "name": sandbox_id,
            "displayName": workspace_name,
            "fullPath": str(user_workspace),
            "sessions": []
        }
    }


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
    sandbox_sessions = [
        ProjectSession(
            id=session["id"],
            title=session["title"],
            created_at=session["created_at"],
            updated_at=session["updated_at"]
        )
        for session in sessions.values()
        if session["sandbox_id"] == sandbox["id"]
    ]

    return Project(
        name=sandbox["id"],
        displayName=sandbox["name"],
        fullPath=sandbox["workspace_path"],
        sessions=sandbox_sessions
    )
