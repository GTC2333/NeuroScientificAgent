"""
Sandbox API - Provides HTTP interface for Claude Code execution
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import subprocess
import json
import logging
import os
from pathlib import Path

app = FastAPI(title="MAS Sandbox API")
logger = logging.getLogger("sandbox")

# Workspace directory
WORKSPACE_DIR = os.environ.get("WORKSPACE", "/workspace")
CLAUDE_DIR = "/app/.claude"


class ClaudeRequest(BaseModel):
    message: str
    agent_type: str = "principal"
    model: Optional[str] = None
    session_id: Optional[str] = None
    skills: Optional[List[str]] = None


class ClaudeResponse(BaseModel):
    response: str
    agent_type: str
    session_id: Optional[str] = None


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "sandbox"}


@app.get("/status")
async def get_status():
    """Get sandbox status"""
    try:
        claude_version = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10
        ).stdout.strip()
    except Exception:
        claude_version = "unknown"

    return {
        "status": "ready",
        "claude_version": claude_version,
        "workspace": WORKSPACE_DIR
    }


@app.post("/execute", response_model=ClaudeResponse)
async def execute_claude(request: ClaudeRequest):
    """Execute Claude Code CLI with given prompt"""
    try:
        # Build command
        model = request.model or "claude-sonnet-4-20250514"

        cmd = [
            "claude",
            "-p",
            "--print",
            "--dangerously-skip-permissions",
            "--output-format", "text",
            "--add-dir", CLAUDE_DIR,
            "--model", model,
        ]

        if request.session_id:
            cmd.extend(["--session-id", request.session_id])

        # Build system prompt with agent type
        agent_def = ""
        agent_file = Path(CLAUDE_DIR) / "agents" / f"{request.agent_type}.md"
        if agent_file.exists():
            agent_def = agent_file.read_text()

        # Build skills context
        skills_context = ""
        if request.skills:
            skills_list = ", ".join(request.skills)
            skills_context = f"\n## Active Skills\nYou have access to: {skills_list}"

        system_prompt = f"""You are running in MAS Sandbox as {request.agent_type.upper()} agent.

{agent_def}

## Current Task
User message: {request.message}
{skills_context}

## Instructions
1. Respond as the {request.agent_type} agent following its defined cognitive style
2. Use the skills available in {CLAUDE_DIR}/skills/ when appropriate
3. Write any outputs to the workspace directory

Respond now:"""

        cmd.extend(["--system-prompt", system_prompt])
        cmd.append(request.message)

        logger.info(f"[Sandbox] Executing: {' '.join(cmd[:10])}...")

        # Execute
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=WORKSPACE_DIR,
            env=os.environ.copy()
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            logger.error(f"[Sandbox] Execution failed: {error_msg[:500]}")
            raise HTTPException(status_code=500, detail=error_msg)

        return ClaudeResponse(
            response=result.stdout,
            agent_type=request.agent_type,
            session_id=request.session_id
        )

    except subprocess.TimeoutExpired:
        logger.error("[Sandbox] Execution timeout")
        raise HTTPException(status_code=504, detail="Execution timeout (>300s)")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Sandbox execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workspace/files")
async def list_workspace_files():
    """List files in workspace directory"""
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
                    "modified": item.stat().st_mtime
                })

        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workspace/files/{path:path}")
async def get_workspace_file(path: str):
    """Get file content from workspace"""
    try:
        file_path = Path(WORKSPACE_DIR) / path
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")

        content = file_path.read_text(encoding='utf-8')
        return {
            "path": path,
            "content": content,
            "size": file_path.stat().st_size
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
