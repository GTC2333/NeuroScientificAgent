"""
Sandbox Manager - Manages isolated sandbox instances
Each sandbox = independent workspace + Claude session
"""
import json
import uuid
import logging
import os
import shutil
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger("MAS.Sandbox")

DATA_DIR = Path(__file__).parent.parent.parent / "data"
SANDBOXES_FILE = DATA_DIR / "sandboxes.json"

# Port pool for sandboxes (9002-9999)
PORT_POOL_START = 9002
PORT_POOL_END = 9999


def _load_sandboxes() -> Dict:
    """Load sandboxes from JSON"""
    if SANDBOXES_FILE.exists():
        with open(SANDBOXES_FILE, 'r') as f:
            return json.load(f)
    return {}


def _save_sandboxes(sandboxes: Dict):
    """Save sandboxes to JSON"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SANDBOXES_FILE, 'w') as f:
        json.dump(sandboxes, f, indent=2)


def _allocate_port() -> int:
    """Allocate available port from pool"""
    sandboxes = _load_sandboxes()
    used = {s.get('port') for s in sandboxes.values() if s.get('port')}

    for port in range(PORT_POOL_START, PORT_POOL_END + 1):
        if port not in used:
            return port

    raise RuntimeError("No available ports in pool")


def create_sandbox(user_id: str, name: str = None) -> Dict:
    """Create new sandbox for user"""
    sandbox_id = str(uuid.uuid4())
    port = _allocate_port()

    # Create workspace directory
    workspace_path = DATA_DIR / "workspaces" / user_id / sandbox_id
    workspace_path.mkdir(parents=True, exist_ok=True)

    # Copy .claude settings if exists
    project_root = Path(__file__).parent.parent.parent.parent
    claude_src = project_root / ".claude"
    claude_dest = workspace_path / ".claude"
    if claude_src.exists():
        shutil.copytree(claude_src, claude_dest, dirs_exist_ok=True)

    sandbox = {
        "id": sandbox_id,
        "user_id": user_id,
        "name": name or f"sandbox-{len(_load_sandboxes()) + 1}",
        "port": port,
        "workspace_path": str(workspace_path),
        "status": "created",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }

    sandboxes = _load_sandboxes()
    sandboxes[sandbox_id] = sandbox
    _save_sandboxes(sandboxes)

    logger.info(f"[Sandbox] Created: {sandbox_id} for user {user_id}")
    return sandbox


def get_sandbox(sandbox_id: str) -> Optional[Dict]:
    """Get sandbox by ID"""
    sandboxes = _load_sandboxes()
    return sandboxes.get(sandbox_id)


def list_user_sandboxes(user_id: str) -> List[Dict]:
    """List all sandboxes for user"""
    sandboxes = _load_sandboxes()
    return [s for s in sandboxes.values() if s.get('user_id') == user_id]


def update_sandbox(sandbox_id: str, updates: Dict) -> Optional[Dict]:
    """Update sandbox"""
    sandboxes = _load_sandboxes()
    if sandbox_id not in sandboxes:
        return None

    sandboxes[sandbox_id].update(updates)
    sandboxes[sandbox_id]['updated_at'] = datetime.utcnow().isoformat()
    _save_sandboxes(sandboxes)
    return sandboxes[sandbox_id]


def delete_sandbox(sandbox_id: str) -> bool:
    """Delete sandbox and cleanup workspace"""
    sandboxes = _load_sandboxes()
    if sandbox_id not in sandboxes:
        return False

    sandbox = sandboxes[sandbox_id]

    # Remove workspace directory
    workspace = Path(sandbox.get('workspace_path', ''))
    if workspace.exists():
        shutil.rmtree(workspace)

    del sandboxes[sandbox_id]
    _save_sandboxes(sandboxes)

    logger.info(f"[Sandbox] Deleted: {sandbox_id}")
    return True


def start_sandbox(sandbox_id: str) -> Optional[Dict]:
    """Start sandbox (mark as running)"""
    return update_sandbox(sandbox_id, {"status": "running"})


def stop_sandbox(sandbox_id: str) -> Optional[Dict]:
    """Stop sandbox (mark as stopped)"""
    return update_sandbox(sandbox_id, {"status": "stopped"})


def verify_sandbox_access(sandbox_id: str, user_id: str) -> bool:
    """Verify user has access to sandbox"""
    sandbox = get_sandbox(sandbox_id)
    if not sandbox:
        return False
    return sandbox.get('user_id') == user_id
