"""
Multi-Agent Scientific Operating System - Backend
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api import chat, tasks, skills

app = FastAPI(
    title="MAS API",
    description="Multi-Agent Scientific Operating System Backend",
    version="0.1.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(tasks.router, prefix="/api", tags=["Tasks"])
app.include_router(skills.router, prefix="/api", tags=["Skills"])


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
        result = subprocess.run(
            [claude_cli, "--version"],
            capture_output=True,
            timeout=5
        )
        claude_available = result.returncode == 0
    except Exception:
        pass

    return {
        "status": "healthy",
        "claude_code": "available" if claude_available else "not_found"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
