"""
Multi-Agent Scientific Operating System - Backend
"""

import logging
import sys
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from src.api import chat, tasks, skills, papers, sessions, files, pdf

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MAS")

app = FastAPI(
    title="MAS API",
    description="Multi-Agent Scientific Operating System Backend",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:9001", "http://127.0.0.1:9001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(tasks.router, prefix="/api", tags=["Tasks"])
app.include_router(skills.router, prefix="/api", tags=["Skills"])
app.include_router(papers.router, prefix="/api", tags=["Papers"])
app.include_router(sessions.router, prefix="/api", tags=["Sessions"])
app.include_router(files.router, prefix="/api", tags=["Files"])
app.include_router(pdf.router, prefix="/api", tags=["PDF"])

# In-memory log storage
_log_store: list = []


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests"""
    logger.info(f"→ {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        logger.info(f"← {request.method} {request.url.path} - {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"✗ {request.method} {request.url.path} - Error: {str(e)}")
        raise


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler - logs and returns error to client"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "type": type(exc).__name__,
            "path": str(request.url)
        }
    )


# Log API endpoints
@app.get("/api/logs")
async def get_logs(level: str = None, limit: int = 100):
    """Get logs with optional level filtering"""
    logs = _log_store
    if level and level != 'all':
        logs = [l for l in logs if l.get('level') == level]
    return logs[-limit:]


@app.post("/api/logs")
async def add_log(entry: dict):
    """Add a log entry"""
    import time
    log_entry = {
        "id": f"log_{len(_log_store)}",
        "timestamp": time.strftime("%H:%M:%S"),
        **entry
    }
    _log_store.append(log_entry)
    logger.info(f"[{entry.get('source', 'client')}] {entry.get('message', '')}")
    return {"status": "ok"}


@app.delete("/api/logs")
async def clear_logs():
    """Clear all logs"""
    _log_store.clear()
    return {"status": "cleared"}


@app.get("/")
async def root():
    return {
        "name": "MAS Backend",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check - also verifies Claude Code CLI is available"""
    import subprocess
    import os

    from src.config import get_config

    config = get_config()
    claude_cli = os.path.expanduser(config.claude.cli_path)

    claude_available = False
    try:
        logger.info(f"[health] Checking Claude Code CLI at: {claude_cli}")
        result = subprocess.run(
            [claude_cli, "--version"],
            capture_output=True,
            timeout=5
        )
        claude_available = result.returncode == 0
        logger.info(f"[health] Claude Code CLI available: {claude_available}")
    except Exception as e:
        logger.warning(f"[health] Claude Code CLI check failed: {e}")

    return {
        "status": "healthy",
        "claude_code": "available" if claude_available else "not_found"
    }


if __name__ == "__main__":
    import uvicorn
    from src.config import get_config
    config = get_config()
    uvicorn.run(app, host=config.server.host, port=config.server.port)
