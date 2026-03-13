"""
Sandbox API - HTTP interface for sandbox containers.
Uses SDK agentic loop (not CLI) for Claude execution.
Provides SSE streaming for real-time response delivery.
"""
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from sandbox.agentic_loop import AgenticLoop

app = FastAPI(title="MAS Sandbox API")
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
