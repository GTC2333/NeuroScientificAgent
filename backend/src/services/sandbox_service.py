"""
Unified Sandbox Service - Manages sandbox lifecycle including Docker containers,
port allocation, API key auth, user directories, and process-exit cleanup.

Replaces: sandbox_manager.py + docker_sandbox_manager.py
"""
import atexit
import json
import logging
import os
import signal
import socket
import sys
import time
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import docker
import docker.types
import requests

from src.config import get_config, SandboxConfig

logger = logging.getLogger("MAS.SandboxService")

DATA_DIR = Path(__file__).parent.parent.parent / "data"
SANDBOXES_FILE = DATA_DIR / "sandboxes.json"


# ============ Data Model ============

@dataclass
class SandboxInfo:
    sandbox_id: str
    user_id: str
    name: str
    container_name: str
    api_url: str
    host_port: int
    host_api_url: str
    api_key: str
    workspace_dir: str
    data_dir: str
    status: str
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SandboxInfo":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ============ Port Allocator ============

class PortAllocator:
    """Allocates host ports for sandbox containers from a configured range."""

    def __init__(self, range_start: int, range_end: int):
        self.range_start = range_start
        self.range_end = range_end
        self.allocated: Dict[str, int] = {}  # sandbox_id -> port

    def allocate(self, sandbox_id: str) -> int:
        """Allocate an available port for a sandbox."""
        used = set(self.allocated.values())
        for port in range(self.range_start, self.range_end + 1):
            if port not in used and self._is_port_available(port):
                self.allocated[sandbox_id] = port
                logger.info("[PortAllocator] Allocated port %d for sandbox %s", port, sandbox_id[:8])
                return port
        raise RuntimeError(
            f"No available ports in range {self.range_start}-{self.range_end}"
        )

    def release(self, sandbox_id: str) -> None:
        """Release a port allocation."""
        port = self.allocated.pop(sandbox_id, None)
        if port:
            logger.info("[PortAllocator] Released port %d for sandbox %s", port, sandbox_id[:8])

    def restore(self, sandbox_id: str, port: int) -> None:
        """Restore a port allocation from persisted state (startup recovery)."""
        self.allocated[sandbox_id] = port

    @staticmethod
    def _is_port_available(port: int) -> bool:
        """Check if a port is available by attempting to bind."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("0.0.0.0", port))
                return True
        except OSError:
            return False


# ============ JSON Persistence ============

def _load_sandboxes_json() -> Dict:
    if SANDBOXES_FILE.exists():
        with open(SANDBOXES_FILE, "r") as f:
            return json.load(f)
    return {}


def _save_sandboxes_json(sandboxes: Dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SANDBOXES_FILE, "w") as f:
        json.dump(sandboxes, f, indent=2)


# ============ Sandbox Service ============

class SandboxService:
    """Unified sandbox lifecycle manager.

    Handles: Docker containers, port allocation, API key generation,
    user directory setup, JSON persistence, and process-exit cleanup.
    """

    def __init__(self):
        config = get_config()
        self.config: SandboxConfig = config.sandbox
        self.docker_client: Optional[docker.DockerClient] = None
        self.port_allocator = PortAllocator(
            self.config.port_range_start, self.config.port_range_end
        )

        # Try to connect to Docker
        try:
            self.docker_client = docker.from_env()
            logger.info("[SandboxService] Docker connected: image=%s, network=%s",
                        self.config.image, self.config.network)
        except Exception as e:
            logger.warning("[SandboxService] Docker not available: %s. Running in local-only mode.", e)

        # Restore port allocations from persisted state
        self._restore_ports()

        # Register cleanup handlers
        atexit.register(self._cleanup_all)
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        logger.info("[SandboxService] Initialized: base_dir=%s, ports=%d-%d",
                    self.config.base_dir, self.config.port_range_start, self.config.port_range_end)

    def _restore_ports(self):
        """Restore port allocations from sandboxes.json on startup."""
        sandboxes = _load_sandboxes_json()
        for sid, data in sandboxes.items():
            port = data.get("host_port")
            if port and data.get("status") == "running":
                self.port_allocator.restore(sid, port)
        logger.info("[SandboxService] Restored %d port allocations", len(self.port_allocator.allocated))

    # ---- User Directory Management ----

    def _ensure_user_dirs(self, user_id: str, sandbox_name: str) -> tuple:
        """Create user directory structure. Returns (workspace_dir, data_dir)."""
        base = Path(self.config.base_dir)
        workspace_dir = base / user_id / "workspaces" / sandbox_name
        data_dir = base / user_id / "data"

        workspace_dir.mkdir(parents=True, exist_ok=True)
        data_dir.mkdir(parents=True, exist_ok=True)

        # Copy claude agent definitions to workspace
        project_root = Path(__file__).parent.parent.parent.parent
        claude_src = project_root / "claude"
        claude_dest = workspace_dir / ".claude"
        if claude_src.exists() and not claude_dest.exists():
            import shutil
            shutil.copytree(claude_src, claude_dest, dirs_exist_ok=True)

        logger.info("[SandboxService] User dirs ready: workspace=%s", workspace_dir)
        return str(workspace_dir), str(data_dir)

    # ---- Docker Environment ----

    def _build_env(self, api_key: str) -> dict:
        """Build environment variables for sandbox container."""
        env = {
            "WORKSPACE": "/workspace",
            "CLAUDE_DIR": "/app/claude",
            "SANDBOX_API_KEY": api_key,
        }
        # Pass through Anthropic credentials from host environment
        for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL"):
            val = os.environ.get(var)
            if val:
                env[var] = val
        # Model
        model = os.environ.get("CLAUDE_MODEL")
        if model:
            env["ANTHROPIC_MODEL"] = model
        return env

    def _build_volumes(self, workspace_dir: str, data_dir: str) -> dict:
        """Build volume mounts for sandbox container."""
        volumes = {
            workspace_dir: {"bind": "/workspace", "mode": "rw"},
        }
        # User data directory (read-only)
        if Path(data_dir).exists():
            volumes[data_dir] = {"bind": "/data", "mode": "ro"}
        # Global shared data (read-only)
        shared = Path(self.config.shared_data_dir)
        if shared.exists():
            volumes[str(shared)] = {"bind": "/shared", "mode": "ro"}
        return volumes

    def _build_device_requests(self) -> list:
        """Build GPU device requests if enabled."""
        if not self.config.gpu_enabled:
            return []
        if self.config.gpu_devices == "all" or not self.config.gpu_devices:
            return [docker.types.DeviceRequest(count=-1, capabilities=[["gpu"]])]
        device_ids = [d.strip() for d in self.config.gpu_devices.split(",")]
        return [docker.types.DeviceRequest(device_ids=device_ids, capabilities=[["gpu"]])]

    # ---- Core CRUD ----

    def create_sandbox(self, sandbox_id: str, user_id: str, name: str, username: str = "") -> SandboxInfo:
        """Create a new sandbox with Docker container."""
        # 1. Create user directories
        workspace_dir, data_dir = self._ensure_user_dirs(user_id, name)

        # 2. Allocate host port
        host_port = self.port_allocator.allocate(sandbox_id)

        # 3. Generate API key
        api_key = str(uuid.uuid4())

        # 4. Container naming (use username if provided for 1:1 model)
        container_name = f"mas-sandbox-{username}" if username else f"mas-sandbox-{sandbox_id[:8]}"
        api_url = f"http://{container_name}:9002"
        host_api_url = f"http://localhost:{host_port}"

        status = "created"

        # 5. Start Docker container if available
        if self.docker_client:
            try:
                # Remove stale container with same name
                try:
                    old = self.docker_client.containers.get(container_name)
                    old.remove(force=True)
                    logger.info("[SandboxService] Removed stale container: %s", container_name)
                except docker.errors.NotFound:
                    pass

                env = self._build_env(api_key)
                volumes = self._build_volumes(workspace_dir, data_dir)
                device_requests = self._build_device_requests()

                run_kwargs = {
                    "image": self.config.image,
                    "name": container_name,
                    "detach": True,
                    "environment": env,
                    "volumes": volumes,
                    "mem_limit": self.config.mem_limit,
                    "cpu_quota": self.config.cpu_quota,
                    "network": self.config.network,
                    "ports": {"9002/tcp": ("0.0.0.0", host_port)},
                    "restart_policy": {"Name": "unless-stopped"},
                }
                if device_requests:
                    run_kwargs["device_requests"] = device_requests
                # Merge user-provided docker kwargs
                run_kwargs.update(self.config.docker_kwargs)

                container = self.docker_client.containers.run(**run_kwargs)
                status = "running"
                logger.info("[SandboxService] Started container %s (port %d)", container_name, host_port)

            except Exception as e:
                logger.error("[SandboxService] Failed to start container: %s", e, exc_info=True)
                status = "error"
                self.port_allocator.release(sandbox_id)

        # 6. Build SandboxInfo
        info = SandboxInfo(
            sandbox_id=sandbox_id,
            user_id=user_id,
            name=name,
            container_name=container_name,
            api_url=api_url,
            host_port=host_port,
            host_api_url=host_api_url,
            api_key=api_key,
            workspace_dir=workspace_dir,
            data_dir=data_dir,
            status=status,
            created_at=datetime.utcnow().isoformat(),
        )

        # 7. Persist
        sandboxes = _load_sandboxes_json()
        sandboxes[sandbox_id] = info.to_dict()
        _save_sandboxes_json(sandboxes)

        logger.info("[SandboxService] Created sandbox %s for user %s", sandbox_id[:8], user_id)
        return info

    def delete_sandbox(self, sandbox_id: str) -> bool:
        """Delete sandbox: stop container, release port, remove from JSON.
        NOTE: User workspace directory is preserved (not deleted).
        """
        sandboxes = _load_sandboxes_json()
        if sandbox_id not in sandboxes:
            return False

        data = sandboxes[sandbox_id]
        container_name = data.get("container_name", "")

        # Stop and remove Docker container
        if self.docker_client and container_name:
            try:
                container = self.docker_client.containers.get(container_name)
                container.stop(timeout=5)
                container.remove(force=True)
                logger.info("[SandboxService] Removed container: %s", container_name)
            except docker.errors.NotFound:
                logger.warning("[SandboxService] Container not found: %s", container_name)
            except Exception as e:
                logger.error("[SandboxService] Error removing container %s: %s", container_name, e)

        # Release port
        self.port_allocator.release(sandbox_id)

        # Remove from JSON
        del sandboxes[sandbox_id]
        _save_sandboxes_json(sandboxes)

        logger.info("[SandboxService] Deleted sandbox %s", sandbox_id[:8])
        return True

    def get_sandbox(self, sandbox_id: str) -> Optional[SandboxInfo]:
        """Get sandbox by ID."""
        sandboxes = _load_sandboxes_json()
        data = sandboxes.get(sandbox_id)
        if not data:
            return None
        return SandboxInfo.from_dict(data)

    def list_sandboxes(self, user_id: str) -> List[SandboxInfo]:
        """List all sandboxes for a user."""
        sandboxes = _load_sandboxes_json()
        return [
            SandboxInfo.from_dict(s)
            for s in sandboxes.values()
            if s.get("user_id") == user_id
        ]

    def find_by_user(self, user_id: str) -> Optional[SandboxInfo]:
        """Find the single sandbox for a user (1:1 model)."""
        sandboxes = _load_sandboxes_json()
        for sid, data in sandboxes.items():
            if data.get("user_id") == user_id:
                return SandboxInfo.from_dict(data)
        return None

    def start_sandbox(self, sandbox_id: str) -> Optional[SandboxInfo]:
        """Start a stopped sandbox container."""
        sandboxes = _load_sandboxes_json()
        if sandbox_id not in sandboxes:
            return None
        data = sandboxes[sandbox_id]
        container_name = data.get("container_name", "")
        if self.docker_client and container_name:
            try:
                container = self.docker_client.containers.get(container_name)
                container.start()
                logger.info("[SandboxService] Started: %s", container_name)
            except Exception as e:
                logger.error("[SandboxService] Failed to start %s: %s", container_name, e)
        data["status"] = "running"
        sandboxes[sandbox_id] = data
        _save_sandboxes_json(sandboxes)
        return SandboxInfo.from_dict(data)

    def stop_sandbox(self, sandbox_id: str) -> Optional[SandboxInfo]:
        """Stop a running sandbox container."""
        sandboxes = _load_sandboxes_json()
        if sandbox_id not in sandboxes:
            return None
        data = sandboxes[sandbox_id]
        container_name = data.get("container_name", "")
        if self.docker_client and container_name:
            try:
                container = self.docker_client.containers.get(container_name)
                container.stop(timeout=5)
                logger.info("[SandboxService] Stopped: %s", container_name)
            except Exception as e:
                logger.error("[SandboxService] Failed to stop %s: %s", container_name, e)
        data["status"] = "stopped"
        sandboxes[sandbox_id] = data
        _save_sandboxes_json(sandboxes)
        return SandboxInfo.from_dict(data)

    def rebuild_sandbox(self, sandbox_id: str, username: str = "") -> Optional[SandboxInfo]:
        """Rebuild a sandbox: delete container, recreate with same config.
        Workspace directory is preserved (not deleted).
        """
        sandboxes = _load_sandboxes_json()
        if sandbox_id not in sandboxes:
            return None

        data = sandboxes[sandbox_id]
        user_id = data["user_id"]
        name = data["name"]
        container_name = data.get("container_name", "")

        # Stop and remove existing container
        if self.docker_client and container_name:
            try:
                container = self.docker_client.containers.get(container_name)
                container.stop(timeout=5)
                container.remove(force=True)
                logger.info("[SandboxService] Removed container for rebuild: %s", container_name)
            except docker.errors.NotFound:
                pass
            except Exception as e:
                logger.error("[SandboxService] Error removing container %s: %s", container_name, e)

        # Release old port
        self.port_allocator.release(sandbox_id)

        # Remove old JSON entry
        del sandboxes[sandbox_id]
        _save_sandboxes_json(sandboxes)

        # Create new sandbox with same user/name
        new_id = str(uuid.uuid4())
        return self.create_sandbox(new_id, user_id, name, username=username)

    def verify_access(self, sandbox_id: str, user_id: str) -> bool:
        """Check if user owns this sandbox."""
        info = self.get_sandbox(sandbox_id)
        return info is not None and info.user_id == user_id

    def health_check(self, api_url: str, timeout: int = 5) -> bool:
        """Check if sandbox API is healthy."""
        try:
            resp = requests.get(f"{api_url}/health", timeout=timeout)
            return resp.status_code == 200
        except Exception:
            return False

    def wait_for_healthy(self, api_url: str, max_wait: int = 30) -> bool:
        """Wait until sandbox API is healthy or timeout."""
        for i in range(max_wait):
            if self.health_check(api_url, timeout=2):
                logger.info("[SandboxService] Healthy after %ds: %s", i + 1, api_url)
                return True
            time.sleep(1)
        logger.error("[SandboxService] Health timeout after %ds: %s", max_wait, api_url)
        return False

    # ---- Reconciliation ----

    def reconcile(self) -> None:
        """On startup: remove orphan containers not in sandboxes.json."""
        if not self.docker_client:
            return
        try:
            sandboxes = _load_sandboxes_json()
            known_names = {
                s.get("container_name") for s in sandboxes.values()
                if s.get("container_name")
            }
            containers = self.docker_client.containers.list(
                all=True, filters={"name": "mas-sandbox-"}
            )
            for container in containers:
                if container.name not in known_names:
                    logger.warning("[SandboxService] Removing orphan container: %s", container.name)
                    container.remove(force=True)
        except Exception as e:
            logger.error("[SandboxService] Reconcile error: %s", e)

    # ---- Cleanup ----

    def _cleanup_all(self):
        """atexit handler: stop all managed containers."""
        if not self.docker_client:
            return
        sandboxes = _load_sandboxes_json()
        for sid, data in sandboxes.items():
            container_name = data.get("container_name", "")
            if container_name and data.get("status") == "running":
                try:
                    container = self.docker_client.containers.get(container_name)
                    container.stop(timeout=5)
                    container.remove(force=True)
                    logger.info("[SandboxService] Cleanup: removed %s", container_name)
                except Exception:
                    pass

    def _signal_handler(self, signum, frame):
        logger.info("[SandboxService] Signal %d received, cleaning up...", signum)
        self._cleanup_all()
        sys.exit(0)


# ============ Singleton ============

_service: Optional[SandboxService] = None


def get_sandbox_service() -> SandboxService:
    global _service
    if _service is None:
        _service = SandboxService()
    return _service
