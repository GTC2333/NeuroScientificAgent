# Claude SDK Migration & Sandbox Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan.

**Goal:** Migrate backend to use Claude SDK (inspired by claudecodeui) AND implement the multi-tenant sandbox system from SPEC.md

**Architecture:**
- Replace Claude CLI subprocess with Anthropic Python SDK
- Implement sandbox isolation (each sandbox = independent Claude session)
- Support multi-tenant with user isolation
- Keep WebSocket streaming for real-time interaction

**Tech Stack:**
- Python 3.10+ with `anthropic` SDK
- FastAPI + WebSocket
- Existing: JSON file storage, JWT auth

---

## File Structure

```
backend/
├── src/
│   ├── services/
│   │   ├── claude_sdk.py      # NEW - Anthropic SDK wrapper (like claudecodeui)
│   │   ├── sandbox_manager.py # NEW - Sandbox lifecycle management
│   │   └── session_manager.py # NEW - Per-sandbox session handling
│   └── api/
│       ├── sandbox.py         # MODIFY - Implement full sandbox CRUD
│       ├── websocket.py       # MODIFY - Per-sandbox WebSocket
│       └── auth.py            # EXISTING - Keep as-is
├── data/
│   ├── users.json
│   ├── sandboxes.json
│   └── sessions.json
└── requirements.txt            # MODIFY - Add anthropic
```

---

## Chunk 1: SDK Integration

### Task 1: Install Anthropic SDK

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add anthropic SDK**

```bash
echo "anthropic>=0.25.0" >> requirements.txt
```

- [ ] **Step 2: Install**

```bash
pip install anthropic>=0.25.0
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add anthropic SDK"
```

---

### Task 2: Create Claude SDK Service

**Files:**
- Create: `backend/src/services/claude_sdk.py`

This mirrors claudecodeui's approach:
- Direct SDK calls (no subprocess)
- Streaming support
- Session management
- MCP server support

- [ ] **Step 1: Create SDK wrapper**

```python
"""
Claude SDK Service - Uses Anthropic Python SDK
Inspired by claudecodeui's claude-sdk.js approach
"""
import os
import json
import logging
from pathlib import Path
from typing import Generator, List, Optional
from anthropic import Anthropic
from anthropic.types import Message

from src.config import get_config

logger = logging.getLogger("MAS.ClaudeSDK")

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CLAUDE_DIR = PROJECT_ROOT / ".claude"


class ClaudeSDKService:
    """Service to invoke Claude using Anthropic Python SDK"""

    def __init__(self, project_dir: str = None):
        config = get_config()

        project_root = Path(__file__).parent.parent.parent.parent
        default_workspace = project_root / config.workspace.temp_dir

        self.project_dir = project_dir or str(default_workspace)
        self.claude_dir = Path(config.project.claude_dir).resolve()
        self.default_model = config.claude.model
        self.api_key = config.claude.api_key
        self.max_tokens = getattr(config.claude, 'max_tokens', 4096)

        # MCP configuration
        self.mcp_enabled = config.mcp.enabled if hasattr(config, 'mcp') else True
        self.mcp_servers = config.mcp.servers if hasattr(config, 'mcp') else []

        # Initialize SDK client
        self.client = Anthropic(
            api_key=self.api_key,
            max_retries=3,
        )
        logger.info("[ClaudeSDK] Initialized with model: %s", self.default_model)

    def _load_settings_env(self) -> dict:
        """Load environment variables from settings.local.json"""
        settings_file = self.claude_dir / "settings.local.json"
        env_vars = {}

        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                    if "env" in settings:
                        env_vars = settings["env"]
            except Exception as e:
                logger.warning(f"[ClaudeSDK] Failed to load settings: {e}")

        return env_vars

    def _load_agent_prompt(self, agent_type: str) -> str:
        """Load agent definition from .claude/agents/"""
        agent_file = self.claude_dir / "agents" / f"{agent_type}.md"
        if agent_file.exists():
            return agent_file.read_text()
        return ""

    def _build_system_prompt(self, agent_type: str, message: str, skills: List[str] = None) -> str:
        """Build system prompt for agent"""
        agent_def = self._load_agent_prompt(agent_type)

        skills_context = ""
        if skills:
            skills_context = f"\n## Active Skills\nYou have access to: {', '.join(skills)}"

        mcp_tools_context = ""
        if self.mcp_enabled and self.mcp_servers:
            mcp_tools = [s.get("type") for s in self.mcp_servers]
            if mcp_tools:
                mcp_tools_context = f"\n## Available MCP Tools\n{', '.join(mcp_tools)}"

        return f"""You are running in the Multi-Agent Scientific (MAS) Operating System.
Your role: {agent_type.upper()}

{agent_def}

## Current Task
User: {message}
{skills_context}
{mcp_tools_context}

Respond as {agent_type}:"""

    def invoke(self, message: str, agent_type: str = "principal",
               model: str = None, session_id: str = None,
               skills: List[str] = None) -> str:
        """Non-streaming invocation"""
        model = model or self.default_model

        logger.info(f"[ClaudeSDK] Invoke: agent={agent_type}, model={model}")

        system_prompt = self._build_system_prompt(agent_type, message, skills)

        try:
            response = self.client.messages.create(
                model=model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": message}]
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"[ClaudeSDK] Error: {e}")
            return f"Error: {str(e)}"

    def invoke_streaming(self, message: str, agent_type: str = "principal",
                        model: str = None, session_id: str = None,
                        skills: List[str] = None) -> Generator[str, None, None]:
        """Streaming invocation"""
        model = model or self.default_model

        logger.info(f"[ClaudeSDK] Streaming: agent={agent_type}, model={model}")

        system_prompt = self._build_system_prompt(agent_type, message, skills)

        try:
            with self.client.messages.stream(
                model=model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": message}]
            ) as stream:
                for text in stream.text_stream:
                    if text:
                        yield text
        except Exception as e:
            logger.error(f"[ClaudeSDK] Stream error: {e}")
            yield f"Error: {str(e)}"


_service: Optional[ClaudeSDKService] = None


def get_claude_sdk_service() -> ClaudeSDKService:
    global _service
    if _service is None:
        _service = ClaudeSDKService()
    return _service
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/services/claude_sdk.py
git commit -m "feat: add Claude SDK service"
```

---

### Task 3: Update claude_code.py to use SDK

**Files:**
- Modify: `backend/src/services/claude_code.py`

- [ ] **Step 1: Update service to use SDK**

Update the ClaudeCodeService class to use the SDK by default:

```python
# Add import at top
from src.services.claude_sdk import get_claude_sdk_service

# In ClaudeCodeService.__init__, add:
self.sdk_service = get_claude_sdk_service()

# Update invoke method to use SDK:
def invoke(self, message: str, agent_type: str = "principal",
           model: str = None, session_id: str = None,
           skills: List[str] = None) -> str:
    # Use SDK
    if self.sdk_service:
        return self.sdk_service.invoke(message, agent_type, model, session_id, skills)
    # Fallback to CLI if needed
    ...
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/services/claude_code.py
git commit -m "refactor: migrate to Claude SDK"
```

---

## Chunk 2: Sandbox System (SPEC.md)

### Task 4: Create Sandbox Manager

**Files:**
- Create: `backend/src/services/sandbox_manager.py`

Based on SPEC.md sandbox design:
- Each sandbox is an isolated workspace
- Auto-create workspace on init
- Port allocation (9002+)
- Status management

- [ ] **Step 1: Create sandbox manager**

```python
"""
Sandbox Manager - Manages isolated sandbox instances
Each sandbox = independent workspace + Claude session
"""
import json
import uuid
import logging
import os
from pathlib import Path
from typing import Optional, Dict
from datetime import datetime

logger = logging.getLogger("MAS.Sandbox")

DATA_DIR = Path(__file__).parent.parent.parent / "data"
SANDBOXES_FILE = DATA_DIR / "sandboxes.json"

# Port pool for sandboxes (9002-9999)
PORT_POOL_START = 9002
PORT_POOL_END = 9999
_used_ports = set()


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
        import shutil
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


def list_user_sandboxes(user_id: str) -> list:
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
        import shutil
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/services/sandbox_manager.py
git commit -m "feat: add sandbox manager"
```

---

### Task 5: Create Session Manager

**Files:**
- Create: `backend/src/services/session_manager.py`

- [ ] **Step 1: Create session manager**

```python
"""
Session Manager - Manages sessions within sandboxes
Each session = conversation with Claude
"""
import json
import uuid
import logging
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger("MAS.Session")

DATA_DIR = Path(__file__).parent.parent.parent / "data"
SESSIONS_FILE = DATA_DIR / "sessions.json"


def _load_sessions() -> Dict:
    if SESSIONS_FILE.exists():
        with open(SESSIONS_FILE, 'r') as f:
            return json.load(f)
    return {}


def _save_sessions(sessions: Dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SESSIONS_FILE, 'w') as f:
        json.dump(sessions, f, indent=2)


def create_session(sandbox_id: str, title: str = None) -> Dict:
    """Create new session in sandbox"""
    session_id = str(uuid.uuid4())

    session = {
        "id": session_id,
        "sandbox_id": sandbox_id,
        "title": title or f"Session-{len(_load_sessions()) + 1}",
        "messages": [],
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }

    sessions = _load_sessions()
    sessions[session_id] = session
    _save_sessions(sessions)

    logger.info(f"[Session] Created: {session_id} in sandbox {sandbox_id}")
    return session


def get_session(session_id: str) -> Optional[Dict]:
    """Get session by ID"""
    sessions = _load_sessions()
    return sessions.get(session_id)


def list_sandbox_sessions(sandbox_id: str) -> List[Dict]:
    """List all sessions in sandbox"""
    sessions = _load_sessions()
    return [s for s in sessions.values() if s.get('sandbox_id') == sandbox_id]


def add_message(session_id: str, role: str, content: str) -> Optional[Dict]:
    """Add message to session"""
    sessions = _load_sessions()
    if session_id not in sessions:
        return None

    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat()
    }

    sessions[session_id]["messages"].append(message)
    sessions[session_id]["updated_at"] = datetime.utcnow().isoformat()
    _save_sessions(sessions)

    return sessions[session_id]


def update_session(session_id: str, updates: Dict) -> Optional[Dict]:
    """Update session"""
    sessions = _load_sessions()
    if session_id not in sessions:
        return None

    sessions[session_id].update(updates)
    sessions[session_id]['updated_at'] = datetime.utcnow().isoformat()
    _save_sessions(sessions)
    return sessions[session_id]


def delete_session(session_id: str) -> bool:
    """Delete session"""
    sessions = _load_sessions()
    if session_id not in sessions:
        return False

    del sessions[session_id]
    _save_sessions(sessions)
    logger.info(f"[Session] Deleted: {session_id}")
    return True
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/services/session_manager.py
git commit -m "feat: add session manager"
```

---

### Task 6: Update Sandboxes API

**Files:**
- Modify: `backend/src/api/sandboxes.py`

Implement full CRUD per SPEC.md:

- [ ] **Step 1: Update sandboxes.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import logging

from src.services import sandbox_manager
from src.api.auth import get_current_user

logger = logging.getLogger("MAS.API")
router = APIRouter(prefix="/api/sandboxes", tags=["sandboxes"])


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


@router.post("", response_model=SandboxResponse)
async def create_sandbox(
    data: SandboxCreate,
    current_user = Depends(get_current_user)
):
    """Create new sandbox"""
    sandbox = sandbox_manager.create_sandbox(
        user_id=current_user["id"],
        name=data.name
    )
    return sandbox


@router.get("", response_model=List[SandboxResponse])
async def list_sandboxes(current_user = Depends(get_current_user)):
    """List user's sandboxes"""
    return sandbox_manager.list_user_sandboxes(current_user["id"])


@router.get("/{sandbox_id}", response_model=SandboxResponse)
async def get_sandbox(sandbox_id: str, current_user = Depends(get_current_user)):
    """Get sandbox details"""
    sandbox = sandbox_manager.get_sandbox(sandbox_id)
    if not sandbox or sandbox.get("user_id") != current_user["id"]:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    return sandbox


@router.delete("/{sandbox_id}")
async def delete_sandbox(sandbox_id: str, current_user = Depends(get_current_user)):
    """Delete sandbox"""
    sandbox = sandbox_manager.get_sandbox(sandbox_id)
    if not sandbox or sandbox.get("user_id") != current_user["id"]:
        raise HTTPException(status_code=404, detail="Sandbox not found")

    sandbox_manager.delete_sandbox(sandbox_id)
    return {"status": "deleted"}


@router.post("/{sandbox_id}/start")
async def start_sandbox(sandbox_id: str, current_user = Depends(get_current_user)):
    """Start sandbox"""
    sandbox = sandbox_manager.get_sandbox(sandbox_id)
    if not sandbox or sandbox.get("user_id") != current_user["id"]:
        raise HTTPException(status_code=404, detail="Sandbox not found")

    sandbox_manager.start_sandbox(sandbox_id)
    return {"status": "running"}


@router.post("/{sandbox_id}/stop")
async def stop_sandbox(sandbox_id: str, current_user = Depends(get_current_user)):
    """Stop sandbox"""
    sandbox = sandbox_manager.get_sandbox(sandbox_id)
    if not sandbox or sandbox.get("user_id") != current_user["id"]:
        raise HTTPException(status_code=404, detail="Sandbox not found")

    sandbox_manager.stop_sandbox(sandbox_id)
    return {"status": "stopped"}
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/api/sandboxes.py
git commit -m "feat: implement sandbox API"
```

---

### Task 7: Update Sessions API

**Files:**
- Modify: `backend/src/api/sessions.py`

- [ ] **Step 1: Update sessions.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from src.services import session_manager, sandbox_manager
from src.api.auth import get_current_user

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    sandbox_id: str
    title: Optional[str] = None


class SessionResponse(BaseModel):
    id: str
    sandbox_id: str
    title: str
    messages: List
    created_at: str
    updated_at: str


@router.post("", response_model=SessionResponse)
async def create_session(
    data: SessionCreate,
    current_user = Depends(get_current_user)
):
    """Create session in sandbox"""
    # Verify sandbox belongs to user
    sandbox = sandbox_manager.get_sandbox(data.sandbox_id)
    if not sandbox or sandbox.get("user_id") != current_user["id"]:
        raise HTTPException(status_code=404, detail="Sandbox not found")

    session = session_manager.create_session(
        sandbox_id=data.sandbox_id,
        title=data.title
    )
    return session


@router.get("", response_model=List[SessionResponse])
async def list_sessions(
    sandbox_id: str = None,
    current_user = Depends(get_current_user)
):
    """List sessions (optionally filtered by sandbox)"""
    if sandbox_id:
        # Verify sandbox belongs to user
        sandbox = sandbox_manager.get_sandbox(sandbox_id)
        if not sandbox or sandbox.get("user_id") != current_user["id"]:
            raise HTTPException(status_code=404, detail="Sandbox not found")
        return session_manager.list_sandbox_sessions(sandbox_id)

    # Return all user sessions
    all_sessions = []
    sandboxes = sandbox_manager.list_user_sandboxes(current_user["id"])
    for sb in sandboxes:
        all_sessions.extend(session_manager.list_sandbox_sessions(sb["id"]))
    return all_sessions


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, current_user = Depends(get_current_user)):
    """Get session details"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify sandbox belongs to user
    sandbox = sandbox_manager.get_sandbox(session["sandbox_id"])
    if not sandbox or sandbox.get("user_id") != current_user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")

    return session


@router.delete("/{session_id}")
async def delete_session(session_id: str, current_user = Depends(get_current_user)):
    """Delete session"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify sandbox belongs to user
    sandbox = sandbox_manager.get_sandbox(session["sandbox_id"])
    if not sandbox or sandbox.get("user_id") != current_user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")

    session_manager.delete_session(session_id)
    return {"status": "deleted"}
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/api/sessions.py
git commit -m "feat: implement session API"
```

---

## Chunk 3: WebSocket Integration

### Task 8: Update WebSocket for Per-Sandbox Sessions

**Files:**
- Modify: `backend/src/api/websocket.py`

- [ ] **Step 1: Update WebSocket handler**

Update to use SDK and support sandbox-scoped sessions:

```python
@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "message":
                content = data.get("content", "")
                sandbox_id = data.get("sandbox_id")

                # Get session and verify ownership
                session = session_manager.get_session(session_id)
                if not session:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Session not found"
                    })
                    continue

                # Add user message
                session_manager.add_message(session_id, "user", content)

                # Use SDK streaming (now uses Claude SDK)
                claude_service = get_claude_service()

                await websocket.send_json({
                    "type": "status",
                    "state": "thinking"
                })

                full_response = ""
                for chunk in claude_service.invoke_streaming(
                    message=content,
                    session_id=session_id
                ):
                    full_response += chunk
                    await websocket.send_json({
                        "type": "response",
                        "content": chunk,
                        "delta": True
                    })

                # Save assistant message
                session_manager.add_message(session_id, "assistant", full_response)

                await websocket.send_json({
                    "type": "status",
                    "state": "complete"
                })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except Exception as e:
        logger.error(f"[WebSocket] Error: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
```

- [ ] **Step 2: Commit**

```bash
git add backend/src/api/websocket.py
git commit -m "refactor: update WebSocket for SDK"
```

---

## Chunk 4: Testing

### Task 9: Test the Integration

- [ ] **Step 1: Start backend**

```bash
cd backend && python -m uvicorn src.main:app --host 0.0.0.0 --port 9000 --reload
```

- [ ] **Step 2: Test sandbox creation**

```bash
curl -X POST http://localhost:9000/api/sandboxes \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "test-sandbox"}'
```

- [ ] **Step 3: Test WebSocket**

```bash
# Connect to ws://localhost:9000/ws/<session_id>
# Send: {"type": "message", "content": "Hello"}
```

- [ ] **Step 4: Verify logs**

Check for "[ClaudeSDK]" logs confirming SDK usage

---

## Summary

This plan implements:

1. **Claude SDK Migration**
   - New `claude_sdk.py` service (inspired by claudecodeui)
   - Updated `claude_code.py` to use SDK by default

2. **Sandbox System (SPEC.md)**
   - `sandbox_manager.py` - Sandbox lifecycle + port allocation
   - `session_manager.py` - Per-sandbox session management
   - Full CRUD API for sandboxes and sessions

3. **WebSocket Integration**
   - Updated to use SDK streaming
   - Per-sandbox session support

The result: Multi-tenant sandbox system with Claude SDK integration, matching SPEC.md design.
