"""
Sandbox API - HTTP interface for sandbox containers.
Uses SDK agentic loop (not CLI) for Claude execution.
Provides SSE streaming for real-time response delivery.
Also provides WebSocket endpoint for CLI shell execution.
"""
import asyncio
import json
import logging
import os
import subprocess
import select
import pty
import fcntl
import termios
import struct
from pathlib import Path
from typing import Optional, List, Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import socketio

from sandbox.agentic_loop import AgenticLoop

# Create Socket.IO application
sio = socketio.AsyncServer(async_mode='asyncio')
app = FastAPI(title="MAS Sandbox API")
app.mount("/", socketio.ASGIApp(sio))

logger = logging.getLogger("Sandbox.API")

# API Key middleware
from fastapi.responses import JSONResponse

SANDBOX_API_KEY = os.environ.get("SANDBOX_API_KEY")


@app.middleware("http")
async def verify_api_key(request, call_next):
    """Verify X-Sandbox-API-Key header on all endpoints except /health."""
    if SANDBOX_API_KEY and request.url.path != "/health":
        key = request.headers.get("X-Sandbox-API-Key")
        if key != SANDBOX_API_KEY:
            logger.warning("[API] Unauthorized request to %s", request.url.path)
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

# Configuration from environment
WORKSPACE_DIR = os.environ.get("WORKSPACE", "/workspace")
CLAUDE_DIR = os.environ.get("CLAUDE_DIR", "/app/claude")
DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "sonnet")

# Lazy-initialized agentic loop
_loop: Optional[AgenticLoop] = None


def get_loop() -> AgenticLoop:
    global _loop
    if _loop is None:
        _loop = AgenticLoop(
            workspace_dir=WORKSPACE_DIR,
            claude_dir=CLAUDE_DIR,
            model=DEFAULT_MODEL,
        )
    return _loop


# ============ Models ============

class ExecuteRequest(BaseModel):
    message: str
    agent_type: str = "principal"
    model: Optional[str] = None
    session_id: Optional[str] = None
    skills: Optional[List[str]] = None
    history: Optional[List[dict]] = None


class ExecuteResponse(BaseModel):
    response: str
    agent_type: str
    session_id: Optional[str] = None


class WriteFileRequest(BaseModel):
    content: str


# ============ Health / Status ============

@app.get("/health")
async def health_check():
    logger.debug("[API] GET /health")
    return {"status": "healthy", "service": "sandbox"}


@app.get("/status")
async def get_status():
    logger.info("[API] GET /status")
    return {
        "status": "ready",
        "workspace": WORKSPACE_DIR,
        "model": DEFAULT_MODEL,
        "claude_dir": CLAUDE_DIR,
    }


# ============ Execute (non-streaming) ============

@app.post("/execute", response_model=ExecuteResponse)
async def execute(request: ExecuteRequest):
    """Execute Claude with agentic loop, return final text."""
    logger.info("[API] /execute: agent=%s, model=%s, history=%d msgs, message=%s",
                request.agent_type, request.model or "default",
                len(request.history) if request.history else 0,
                request.message[:100])
    try:
        agentic = get_loop()
        response_text = agentic.invoke(
            message=request.message,
            agent_type=request.agent_type,
            model=request.model,
            session_id=request.session_id,
            skills=request.skills,
            history=request.history,
        )
        return ExecuteResponse(
            response=response_text,
            agent_type=request.agent_type,
            session_id=request.session_id,
        )
    except Exception as e:
        logger.error("[API] Execute error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============ Execute (SSE streaming) ============

@app.post("/execute/stream")
async def execute_stream(request: ExecuteRequest):
    """Execute Claude with agentic loop, return SSE event stream.

    The agentic loop is synchronous (blocking HTTP calls to Anthropic API),
    so we run it in a thread executor and bridge events via asyncio.Queue.
    """
    logger.info("[API] /execute/stream: agent=%s, model=%s, history=%d msgs, message=%s",
                request.agent_type, request.model or "default",
                len(request.history) if request.history else 0,
                request.message[:100])

    async def event_generator():
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def _run_sync():
            try:
                agentic = get_loop()
                for event in agentic.invoke_streaming(
                    message=request.message,
                    agent_type=request.agent_type,
                    model=request.model,
                    session_id=request.session_id,
                    skills=request.skills,
                    history=request.history,
                ):
                    loop.call_soon_threadsafe(queue.put_nowait, event)
            except Exception as e:
                logger.error("[API] Stream thread error: %s", e, exc_info=True)
                loop.call_soon_threadsafe(
                    queue.put_nowait, {"type": "error", "message": str(e)}
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        # Run the synchronous generator in a background thread
        thread_future = loop.run_in_executor(None, _run_sync)

        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield {"data": json.dumps(event)}
        except asyncio.CancelledError:
            logger.info("[API] SSE stream cancelled by client")
            thread_future.cancel()
        finally:
            logger.info("[API] SSE stream ended")

    return EventSourceResponse(event_generator())


# ============ Workspace Files ============

@app.get("/workspace/files")
async def list_workspace_files():
    """List files in workspace directory."""
    logger.info("[API] GET /workspace/files")
    try:
        workspace = Path(WORKSPACE_DIR)
        if not workspace.exists():
            return {"files": []}

        files = []
        for item in workspace.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(workspace)
                files.append({
                    "path": str(rel_path),
                    "size": item.stat().st_size,
                    "modified": item.stat().st_mtime,
                })

        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workspace/files/{path:path}")
async def get_workspace_file(path: str):
    """Get file content from workspace."""
    logger.info("[API] GET /workspace/files/%s", path)
    try:
        file_path = Path(WORKSPACE_DIR) / path
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")

        content = file_path.read_text(encoding="utf-8")
        return {
            "path": path,
            "content": content,
            "size": file_path.stat().st_size,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/workspace/files/{path:path}")
async def write_workspace_file(path: str, request: WriteFileRequest):
    """Write file to workspace."""
    logger.info("[API] POST /workspace/files/%s (%d bytes)", path, len(request.content))
    try:
        file_path = Path(WORKSPACE_DIR) / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(request.content, encoding="utf-8")
        return {"path": path, "size": file_path.stat().st_size}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== Shell WebSocket Handler ==============

WORKSPACE_DIR = os.environ.get("WORKSPACE", "/workspace")
SHARED_USERS_DIR = os.environ.get("SHARED_USERS", "/shared_users")


class ShellConnection:
    """Manage a single shell/PTY connection in sandbox"""

    def __init__(self, sid: str):
        self.sid = sid
        self.master_fd = None
        self.process = None
        self.task = None

    async def handle_init(self, data: dict):
        """Initialize shell process"""
        project_path = data.get("projectPath", "/workspace")
        session_id = data.get("sessionId")
        provider = data.get("provider", "plain-shell")
        cols = data.get("cols", 80)
        rows = data.get("rows", 24)
        initial_command = data.get("initialCommand")
        is_plain_shell = data.get("isPlainShell", False)

        logger.info(f"[sandbox-shell] Init: project={project_path}, provider={provider}")

        # Establish workspace symlink
        await self._setup_workspace(project_path)

        # Build shell command
        shell_command = self._build_command(
            provider=provider,
            project_path="/workspace",
            session_id=session_id,
            initial_command=initial_command,
            is_plain_shell=is_plain_shell
        )

        # Start PTY
        self.master_fd, slave_fd = pty.openpty()

        # Set terminal size
        winsize = struct.pack('HHHH', rows, cols, 0, 0)
        fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

        # Start process
        self.process = subprocess.Popen(
            shell_command,
            shell=True,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd="/workspace",
            start_new_session=True,
            env={**os.environ, "TERM": "xterm-256color"}
        )

        os.close(slave_fd)

        # Start output reading task
        self.task = asyncio.create_task(self._read_output())

        logger.info(f"[sandbox-shell] Shell started with PID: {self.process.pid}")

    async def _setup_workspace(self, project_path: str):
        """Establish workspace directory symlink"""
        # project_path format: /shared_users/user_123/workspace_A

        if os.path.islink('/workspace'):
            os.unlink('/workspace')

        # If /workspace has content, backup or clear
        if os.path.exists('/workspace') and os.listdir('/workspace'):
            # Simple handling: assume user accepts overwrite
            import shutil
            backup_dir = '/workspace.backup'
            if not os.path.exists(backup_dir):
                shutil.move('/workspace', backup_dir)

        # Create symlink
        os.symlink(project_path, '/workspace')
        logger.info(f"[sandbox-shell] Linked /workspace -> {project_path}")

    def _build_command(self, provider: str, project_path: str, session_id: Optional[str],
                      initial_command: Optional[str], is_plain_shell: bool) -> str:
        """Build shell command"""
        if is_plain_shell:
            if initial_command:
                return f'cd "{project_path}" && {initial_command}'
            return f'cd "{project_path}" && $SHELL'

        if provider == "claude" or provider == "anthropic":
            if session_id:
                return f'cd "{project_path}" && claude --resume {session_id} || claude'
            return f'cd "{project_path}" && claude'

        elif provider == "cursor":
            if session_id:
                return f'cd "{project_path}" && cursor-agent --resume="{session_id}"'
            return f'cd "{project_path}" && cursor-agent'

        elif provider == "codex":
            if session_id:
                return f'cd "{project_path}" && codex resume "{session_id}" || codex'
            return f'cd "{project_path}" && codex'

        elif provider == "gemini":
            if session_id:
                return f'cd "{project_path}" && gemini --resume="{session_id}"'
            return f'cd "{project_path}" && gemini'

        # Default
        if initial_command:
            return f'cd "{project_path}" && {initial_command}'
        return f'cd "{project_path}" && $SHELL'

    async def _read_output(self):
        """Read PTY output and emit to client"""
        try:
            while True:
                if self.master_fd is None:
                    break

                ready, _, _ = select.select([self.master_fd], [], [], 0.1)

                if ready:
                    try:
                        data = os.read(self.master_fd, 4096)
                        if data:
                            await sio.emit('output', {
                                "type": "output",
                                "data": data.decode("utf-8", errors="replace")
                            }, room=self.sid)
                    except OSError:
                        break

                if self.process and self.process.poll() is not None:
                    exit_code = self.process.returncode
                    await sio.emit('output', {
                        "type": "output",
                        "data": f"\r\nProcess exited with code {exit_code}\r\n"
                    }, room=self.sid)
                    break

                await asyncio.sleep(0.01)

        except Exception as e:
            logger.error(f"[sandbox-shell] Error reading output: {e}")
        finally:
            await self.cleanup()

    async def handle_input(self, data: dict):
        """Forward input to PTY"""
        input_data = data.get("data", "")
        if self.master_fd and input_data:
            try:
                os.write(self.master_fd, input_data.encode("utf-8"))
            except OSError as e:
                logger.error(f"[sandbox-shell] Error writing input: {e}")

    async def handle_resize(self, data: dict):
        """Handle terminal resize"""
        if self.master_fd:
            cols = data.get("cols", 80)
            rows = data.get("rows", 24)
            try:
                winsize = struct.pack('HHHH', rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
            except Exception as e:
                logger.error(f"[sandbox-shell] Error resizing: {e}")

    async def cleanup(self):
        """Clean up resources"""
        if self.master_fd:
            try:
                os.close(self.master_fd)
            except:
                pass
            self.master_fd = None

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None


# Store active shell connections
shell_connections: Dict[str, ShellConnection] = {}


@sio.event
async def connect(sid, environ):
    """Client connection"""
    logger.info(f"[sandbox-shell] Client connected: {sid}")


@sio.event
async def disconnect(sid):
    """Client disconnect"""
    logger.info(f"[sandbox-shell] Client disconnected: {sid}")
    if sid in shell_connections:
        await shell_connections[sid].cleanup()
        del shell_connections[sid]


@sio.event
async def init(sid, data):
    """Handle init message"""
    shell_conn = ShellConnection(sid)
    shell_connections[sid] = shell_conn
    await shell_conn.handle_init(data)


@sio.event
async def input(sid, data):
    """Handle input message"""
    if sid in shell_connections:
        await shell_connections[sid].handle_input(data)


@sio.event
async def resize(sid, data):
    """Handle resize message"""
    if sid in shell_connections:
        await shell_connections[sid].handle_resize(data)


@sio.event
async def disconnect_shell(sid):
    """Handle disconnect"""
    if sid in shell_connections:
        await shell_connections[sid].cleanup()
        del shell_connections[sid]

