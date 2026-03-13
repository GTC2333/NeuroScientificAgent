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
    """Create a new sandbox."""
    service = get_sandbox_service()
    sandbox_id = str(uuid.uuid4())
    user_sandboxes = service.list_sandboxes(current_user.id)
    name = data.name.strip() if data.name else f"sandbox-{len(user_sandboxes) + 1}"

    info = service.create_sandbox(sandbox_id, current_user.id, name)

    # Wait for healthy (in thread to avoid blocking event loop)
    if info.status == "running" and info.api_url:
        import asyncio
        loop = asyncio.get_event_loop()
        healthy = await loop.run_in_executor(
            None, service.wait_for_healthy, info.api_url, 30
        )
        if not healthy:
            logger.warning("[sandboxes] Container not healthy after 30s: %s", info.container_name)

    logger.info("[sandboxes] Created sandbox %s for user %s", sandbox_id[:8], current_user.username)
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
