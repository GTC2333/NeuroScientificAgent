"""
Sandbox API - Manage user sandboxes (workspaces)
Thin HTTP adapter over SandboxService.
"""
import json
import logging
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.auth import get_current_user, UserResponse
from src.services.sandbox_service import get_sandbox_service, SandboxInfo

logger = logging.getLogger("MAS.Sandboxes")
router = APIRouter()


# ============ Models ============

class SandboxCreate(BaseModel):
    name: Optional[str] = None


class SandboxResponse(BaseModel):
    id: str
    user_id: str
    name: str
    port: int
    workspace_path: str
    status: str
    created_at: str
    container_name: Optional[str] = None
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    host_port: Optional[int] = None
    host_api_url: Optional[str] = None


def _to_response(info: SandboxInfo) -> SandboxResponse:
    """Convert SandboxInfo to API response model."""
    return SandboxResponse(
        id=info.sandbox_id,
        user_id=info.user_id,
        name=info.name,
        port=info.host_port,
        workspace_path=info.workspace_dir,
        status=info.status,
        created_at=info.created_at,
        container_name=info.container_name,
        api_url=info.api_url,
        api_key=info.api_key,
        host_port=info.host_port,
        host_api_url=info.host_api_url,
    )


# ============ Session/Sandbox JSON helpers (used by websocket.py) ============

def get_sandboxes_path() -> Path:
    return Path(__file__).parent.parent.parent / "data" / "sandboxes.json"


def load_sandboxes() -> dict:
    db_path = get_sandboxes_path()
    if not db_path.exists():
        return {}
    with open(db_path, "r") as f:
        return json.load(f)


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


def init_default_workspace():
    """Initialize default temp_workspace on startup if it doesn't exist."""
    import shutil
    project_root = Path(__file__).parent.parent.parent.parent
    default_workspace = project_root / "temp_workspace"
    default_workspace.mkdir(parents=True, exist_ok=True)

    project_claude_dir = project_root / "claude"
    if project_claude_dir.exists():
        workspace_claude = default_workspace / ".claude"
        if not workspace_claude.exists():
            shutil.copytree(project_claude_dir, workspace_claude, dirs_exist_ok=True)

    logger.info("[sandboxes] Default workspace initialized at %s", default_workspace)


# ============ Routes ============

@router.post("/sandboxes", response_model=SandboxResponse)
async def create_sandbox(
    data: SandboxCreate,
    current_user: UserResponse = Depends(get_current_user),
):
    """Create the user's sandbox (1:1 model). Fails if one already exists."""
    service = get_sandbox_service()

    # Enforce 1:1: check if user already has a sandbox
    existing = service.find_by_user(current_user.id)
    if existing:
        raise HTTPException(status_code=409, detail="Sandbox already exists. Use rebuild to recreate.")

    sandbox_id = str(uuid.uuid4())
    name = data.name.strip() if data.name else "default"

    info = service.create_sandbox(sandbox_id, current_user.id, name, username=current_user.username)

    # Wait for healthy
    # Use host_api_url for health check from main container
    if info.status == "running" and info.host_api_url:
        import asyncio
        loop = asyncio.get_event_loop()
        healthy = await loop.run_in_executor(
            None, service.wait_for_healthy, info.host_api_url, 30
        )
        if not healthy:
            logger.warning("[sandboxes] Container not healthy after 30s: %s", info.container_name)

    logger.info("[sandboxes] Created sandbox for user %s", current_user.username)
    return _to_response(info)


@router.get("/sandboxes", response_model=List[SandboxResponse])
async def list_sandboxes_route(current_user: UserResponse = Depends(get_current_user)):
    service = get_sandbox_service()
    infos = service.list_sandboxes(current_user.id)
    return [_to_response(i) for i in infos]


@router.get("/sandboxes/{sandbox_id}", response_model=SandboxResponse)
async def get_sandbox(
    sandbox_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    service = get_sandbox_service()
    info = service.get_sandbox(sandbox_id)
    if not info:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    if info.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return _to_response(info)


@router.delete("/sandboxes/{sandbox_id}")
async def delete_sandbox(
    sandbox_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    service = get_sandbox_service()
    info = service.get_sandbox(sandbox_id)
    if not info:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    if info.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    service.delete_sandbox(sandbox_id)

    # Clean up associated sessions
    sessions = load_sessions()
    to_delete = [
        sid for sid, s in sessions.items()
        if s.get("sandbox_id") == sandbox_id or s.get("sandboxId") == sandbox_id
    ]
    for sid in to_delete:
        del sessions[sid]
    save_sessions(sessions)

    logger.info("[sandboxes] Deleted sandbox %s", sandbox_id[:8])
    return {"message": "Sandbox deleted"}


@router.post("/sandboxes/rebuild", response_model=SandboxResponse)
async def rebuild_sandbox(
    current_user: UserResponse = Depends(get_current_user),
):
    """Rebuild the user's sandbox (destroy container, recreate). Workspace files preserved."""
    service = get_sandbox_service()
    existing = service.find_by_user(current_user.id)
    if not existing:
        raise HTTPException(status_code=404, detail="No sandbox to rebuild. Create one first.")
    if existing.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    info = service.rebuild_sandbox(existing.sandbox_id, username=current_user.username)
    if not info:
        raise HTTPException(status_code=500, detail="Rebuild failed")

    # Wait for healthy
    # Use host_api_url for health check from main container
    if info.status == "running" and info.host_api_url:
        import asyncio
        loop = asyncio.get_event_loop()
        healthy = await loop.run_in_executor(
            None, service.wait_for_healthy, info.host_api_url, 30
        )
        if not healthy:
            logger.warning("[sandboxes] Rebuilt container not healthy after 30s: %s", info.container_name)

    logger.info("[sandboxes] Rebuilt sandbox for user %s", current_user.username)
    return _to_response(info)


@router.post("/sandboxes/{sandbox_id}/start")
async def start_sandbox(
    sandbox_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    service = get_sandbox_service()
    info = service.get_sandbox(sandbox_id)
    if not info:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    if info.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    service.start_sandbox(sandbox_id)
    return {"status": "running"}


@router.post("/sandboxes/{sandbox_id}/stop")
async def stop_sandbox(
    sandbox_id: str,
    current_user: UserResponse = Depends(get_current_user),
):
    service = get_sandbox_service()
    info = service.get_sandbox(sandbox_id)
    if not info:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    if info.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    service.stop_sandbox(sandbox_id)
    return {"status": "stopped"}


# ============== Username-based sandbox endpoints ==============

@router.get("/sandboxes/by-username/{username}", response_model=SandboxResponse)
async def get_sandbox_by_username(
    username: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Get sandbox by username"""
    sandboxes = load_sandboxes()
    for sandbox_id, sandbox in sandboxes.items():
        if sandbox.get("username") == username:
            return _to_response(SandboxInfo.from_dict(sandbox))
    raise HTTPException(status_code=404, detail="Sandbox not found")


@router.post("/sandboxes/create-for-user", response_model=SandboxResponse)
async def create_sandbox_for_current_user(
    current_user: UserResponse = Depends(get_current_user),
):
    """Create sandbox for current user (called on first login)"""
    import uuid

    # Check if sandbox already exists
    sandboxes = load_sandboxes()
    for sb in sandboxes.values():
        if sb.get("user_id") == current_user.id:
            return _to_response(SandboxInfo.from_dict(sb))

    # Create new sandbox
    service = get_sandbox_service()
    info = service.create_sandbox(
        sandbox_id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=current_user.username,
        username=current_user.username
    )
    return _to_response(info)
