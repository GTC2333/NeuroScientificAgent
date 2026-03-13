# Docker Deployment Architecture Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Docker mode fully functional — Nginx serves frontend, single port entry, configurable scripts for build/run/user-create, 1:1 user-sandbox with frontend controls.

**Architecture:** Main container runs Nginx (:80 internal, mapped to configurable host port) serving static frontend + reverse-proxying API/WebSocket to FastAPI (:9000 internal). Each user gets one sandbox container (`mas-sandbox-{username}`) created/rebuilt via frontend buttons. Scripts `build_images.sh`, `run_main.sh`, `create_user.sh` handle ops.

**Tech Stack:** Docker, Nginx, FastAPI, React (existing frontend), docker-py

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `scientific_agent/docker/nginx.conf` | Nginx: static files + API/WS reverse proxy |
| Create | `scientific_agent/docker/sandbox-requirements.txt` | Sandbox Python deps (fixes broken build) |
| Create | `/root/claudeagent/run_main.sh` | Start main container with version tag + env config |
| Modify | `scientific_agent/docker/main.Dockerfile` | Replace nodejs/npm with nginx, change CMD |
| Modify | `scientific_agent/docker-compose.yml` | Use `image:` instead of `build:`, single port |
| Modify | `/root/claudeagent/build_images.sh` | Version tag support, pure `docker build` |
| Modify | `/root/claudeagent/create_user.sh` | Add API register call (directory + account) |
| Modify | `scientific_agent/backend/src/services/sandbox_service.py` | Container name `mas-sandbox-{username}`, add `rebuild_sandbox()` |
| Modify | `scientific_agent/backend/src/api/sandboxes.py` | Add `POST /api/sandboxes/rebuild`, enforce 1:1 |
| Modify | `scientific_agent/backend/src/api/websocket.py:111-122` | Fix `workspace_path` → `workspace_dir` field mismatch |
| Modify | `scientific_agent/Makefile` | Delegate to build_images.sh / run_main.sh |
| Create | `frontend/.../hooks/useSandboxState.ts` | Sandbox status polling + create/rebuild actions |
| Modify | `frontend/.../MainContentHeader.tsx` | Sandbox status badge + create/rebuild buttons |
| Modify | `frontend/.../ChatComposer.tsx` | Disable input when no running sandbox |

---

## Chunk 1: Fix Sandbox Build + Nginx + Dockerfile

### Task 1: Create sandbox-requirements.txt

**Files:**
- Create: `scientific_agent/docker/sandbox-requirements.txt`

- [ ] **Step 1: Create the requirements file**

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.5.0
pyyaml>=6.0
anthropic>=0.25.0
sse-starlette>=2.0.0
```

- [ ] **Step 2: Verify sandbox image builds**

Run: `cd /root/claudeagent/scientific_agent && docker build -t mas-sandbox:test -f docker/sandbox.Dockerfile .`
Expected: Build succeeds (previously failed on missing file)

- [ ] **Step 3: Verify sandbox container starts**

Run: `docker run --rm -d --name test-sandbox -p 19002:9002 -e ANTHROPIC_API_KEY=test mas-sandbox:test && sleep 2 && curl -s http://localhost:19002/health && docker rm -f test-sandbox`
Expected: `{"status":"healthy","service":"sandbox"}`

- [ ] **Step 4: Commit**

```bash
git add scientific_agent/docker/sandbox-requirements.txt
git commit -m "fix: add missing sandbox-requirements.txt for sandbox image build"
```

---

### Task 2: Create Nginx config

**Files:**
- Create: `scientific_agent/docker/nginx.conf`

- [ ] **Step 1: Create nginx.conf**

```nginx
server {
    listen 80;
    server_name _;

    # Frontend static files (SPA)
    location / {
        root /app/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # API reverse proxy
    location /api/ {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket reverse proxy
    location /ws {
        proxy_pass http://127.0.0.1:9000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400s;
    }

    # Shell WebSocket reverse proxy
    location /shell {
        proxy_pass http://127.0.0.1:9000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400s;
    }

    # Health check passthrough
    location /health {
        proxy_pass http://127.0.0.1:9000;
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add scientific_agent/docker/nginx.conf
git commit -m "feat: add nginx config for static files + API/WS reverse proxy"
```

---

### Task 3: Rewrite main.Dockerfile

**Files:**
- Modify: `scientific_agent/docker/main.Dockerfile`

- [ ] **Step 1: Rewrite the Dockerfile**

Replace entire file with:

```dockerfile
# ===========================================
# Main Container Dockerfile
# ===========================================
# Purpose: Nginx (frontend) + FastAPI (backend) + Docker Sandbox Management

# Stage 1: Python builder
FROM python:3.11-slim AS python-builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Stage 2: Node.js builder (produces dist/ only)
FROM node:20-slim AS node-builder

WORKDIR /app/frontend/claudecodeui

COPY frontend/claudecodeui/package*.json ./
RUN npm ci

COPY frontend/claudecodeui/ ./
RUN npm run build


# Stage 3: Production image
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=9000

WORKDIR /app

# Install runtime dependencies (nginx instead of nodejs)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    docker.io \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# Copy Python virtual environment from builder
COPY --from=python-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy built frontend (dist/ only — no node_modules, no server/)
COPY --from=node-builder /app/frontend/claudecodeui/dist ./frontend/dist

# Copy nginx config
COPY docker/nginx.conf /etc/nginx/sites-available/default

# Copy application code
COPY backend/ ./backend/
COPY claude/ ./claude/
COPY config.yaml .
COPY local.yaml.example ./local.yaml

# Expose internal port (Nginx)
EXPOSE 80

# Health check via Nginx → FastAPI
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

# Start nginx + uvicorn
CMD ["sh", "-c", "nginx && cd backend && python -m uvicorn src.main:app --host 0.0.0.0 --port 9000"]
```

Key changes from original:
- Stage 3: `nginx` replaces `nodejs` + `npm`
- Only copies `dist/` (not `node_modules/`, `server/`, `package.json`)
- Copies `dist` to `/app/frontend/dist` (matches nginx.conf root)
- EXPOSE 80 instead of 9000+9001
- CMD: `nginx && uvicorn` instead of `uvicorn & node`

- [ ] **Step 2: Verify main image builds**

Run: `cd /root/claudeagent/scientific_agent && docker build -t mas-main:test -f docker/main.Dockerfile .`
Expected: Build succeeds without nodejs/npm installation

- [ ] **Step 3: Commit**

```bash
git add scientific_agent/docker/main.Dockerfile
git commit -m "feat: replace nodejs with nginx in main container Dockerfile"
```

---

### Task 4: Rewrite docker-compose.yml

**Files:**
- Modify: `scientific_agent/docker-compose.yml`

- [ ] **Step 1: Rewrite docker-compose.yml**

Replace entire file with:

```yaml
version: '3.8'

services:
  main:
    image: ${MAIN_IMAGE:-mas-main:latest}
    container_name: mas-main
    ports:
      - "${FRONTEND_PORT:-9001}:80"
      - "${BACKEND_PORT:-9000}:9000"
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL:-}
      - ANTHROPIC_AUTH_TOKEN=${ANTHROPIC_AUTH_TOKEN:-}
      - CLAUDE_MODEL=${CLAUDE_MODEL:-sonnet}
      - CLAUDE_TIMEOUT=${CLAUDE_TIMEOUT:-300}
      - MAS_SANDBOX_IMAGE=${SANDBOX_IMAGE:-mas-sandbox:latest}
      - MAS_NETWORK=${SANDBOX_NETWORK:-mas-network}
      - MAS_SANDBOX_MEM_LIMIT=${SANDBOX_MEM_LIMIT:-512m}
      - MAS_SANDBOX_CPU_QUOTA=${SANDBOX_CPU_QUOTA:-50000}
      - MAS_SANDBOX_PORT_RANGE_START=${SANDBOX_PORT_RANGE_START:-30000}
      - MAS_SANDBOX_PORT_RANGE_END=${SANDBOX_PORT_RANGE_END:-39999}
    volumes:
      - ./data:/app/data
      - /var/run/docker.sock:/var/run/docker.sock
      - ${USERS_DIR:-/root/claudeagent/users}:/root/claudeagent/users
    networks:
      - mas-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:80/health"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  mas-network:
    driver: bridge
```

Key changes:
- `image:` instead of `build:` (decoupled)
- Port: `${FRONTEND_PORT:-9001}:80` (Nginx)
- All sandbox config via environment variables
- Users directory mounted as volume
- Healthcheck targets Nginx (:80) not FastAPI (:9000)

- [ ] **Step 2: Commit**

```bash
git add scientific_agent/docker-compose.yml
git commit -m "feat: decouple docker-compose from build, use image + env config"
```

---

## Chunk 2: Operations Scripts

### Task 5: Rewrite build_images.sh

**Files:**
- Modify: `/root/claudeagent/build_images.sh`

- [ ] **Step 1: Rewrite build_images.sh**

Replace entire file with:

```bash
#!/bin/bash
# build_images.sh — Build MAS Docker images with optional version tag.
#
# Usage:
#   ./build_images.sh              # build both as :latest
#   ./build_images.sh v1.0         # build both as :v1.0
#   ./build_images.sh sandbox      # sandbox :latest only
#   ./build_images.sh main         # main :latest only
#   ./build_images.sh sandbox v1.0 # sandbox :v1.0 only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/scientific_agent"

# Parse arguments: [target] [tag]
# If only one arg and it starts with 'v' or is 'latest', treat as tag
TARGET="all"
TAG="latest"

if [ $# -eq 1 ]; then
    case "$1" in
        sandbox|main|all) TARGET="$1" ;;
        *)                TAG="$1" ;;
    esac
elif [ $# -ge 2 ]; then
    TARGET="$1"
    TAG="$2"
fi

cd "$PROJECT_DIR"

build_sandbox() {
    echo "=== Building mas-sandbox:${TAG} ==="
    docker build -t "mas-sandbox:${TAG}" -f docker/sandbox.Dockerfile .
    echo "=== Done: mas-sandbox:${TAG} ==="
}

build_main() {
    echo "=== Building mas-main:${TAG} ==="
    docker build -t "mas-main:${TAG}" -f docker/main.Dockerfile .
    echo "=== Done: mas-main:${TAG} ==="
}

case "$TARGET" in
    sandbox) build_sandbox ;;
    main)    build_main ;;
    all)     build_sandbox; build_main ;;
    *)       echo "Usage: $0 [sandbox|main|all] [version-tag]"; exit 1 ;;
esac

echo ""
echo "=== Build Complete ==="
docker images | grep -E "mas-sandbox|mas-main" | head -5
echo ""
echo "Next: ./run_main.sh ${TAG}"
```

- [ ] **Step 2: Verify**

Run: `chmod +x /root/claudeagent/build_images.sh && /root/claudeagent/build_images.sh sandbox test1`
Expected: Builds `mas-sandbox:test1` successfully

- [ ] **Step 3: Commit**

```bash
git add /root/claudeagent/build_images.sh
git commit -m "feat: build_images.sh with version tag support"
```

---

### Task 6: Create run_main.sh

**Files:**
- Create: `/root/claudeagent/run_main.sh`

- [ ] **Step 1: Create run_main.sh**

```bash
#!/bin/bash
# run_main.sh — Start MAS main container with configurable version and parameters.
#
# Usage:
#   ./run_main.sh              # start with :latest
#   ./run_main.sh v1.0         # start with :v1.0
#   FRONTEND_PORT=8080 ./run_main.sh v1.0   # custom port
#
# Environment variables (all optional, defaults shown):
#   MAIN_IMAGE          Override main image (ignores version arg)
#   SANDBOX_IMAGE       Override sandbox image (ignores version arg)
#   FRONTEND_PORT       Host port for web UI (default: 9001)
#   BACKEND_PORT        Host port for API debug access (default: 9000)
#   SANDBOX_NETWORK     Docker network name (default: mas-network)
#   SANDBOX_MEM_LIMIT   Sandbox memory limit (default: 512m)
#   SANDBOX_CPU_QUOTA   Sandbox CPU quota (default: 50000)
#   SANDBOX_PORT_RANGE_START  (default: 30000)
#   SANDBOX_PORT_RANGE_END    (default: 39999)
#   USERS_DIR           User data directory (default: /root/claudeagent/users)
#   ANTHROPIC_API_KEY   Required
#   ANTHROPIC_BASE_URL  Optional
#   ANTHROPIC_AUTH_TOKEN Optional
#   CLAUDE_MODEL        Default model (default: sonnet)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/scientific_agent"

# Version tag from argument
TAG="${1:-latest}"

# Set image names (env var overrides version arg)
export MAIN_IMAGE="${MAIN_IMAGE:-mas-main:${TAG}}"
export SANDBOX_IMAGE="${SANDBOX_IMAGE:-mas-sandbox:${TAG}}"

# Pass through all other env vars with defaults
export FRONTEND_PORT="${FRONTEND_PORT:-9001}"
export BACKEND_PORT="${BACKEND_PORT:-9000}"
export SANDBOX_NETWORK="${SANDBOX_NETWORK:-mas-network}"
export SANDBOX_MEM_LIMIT="${SANDBOX_MEM_LIMIT:-512m}"
export SANDBOX_CPU_QUOTA="${SANDBOX_CPU_QUOTA:-50000}"
export SANDBOX_PORT_RANGE_START="${SANDBOX_PORT_RANGE_START:-30000}"
export SANDBOX_PORT_RANGE_END="${SANDBOX_PORT_RANGE_END:-39999}"
export USERS_DIR="${USERS_DIR:-/root/claudeagent/users}"
export CLAUDE_MODEL="${CLAUDE_MODEL:-sonnet}"

# Ensure users directory exists
mkdir -p "$USERS_DIR/shared/data"

echo "=========================================="
echo "  MAS — Starting Main Container"
echo "=========================================="
echo "  Main image:    $MAIN_IMAGE"
echo "  Sandbox image: $SANDBOX_IMAGE"
echo "  Frontend:      http://localhost:${FRONTEND_PORT}"
echo "  Backend:       http://localhost:${BACKEND_PORT} (debug)"
echo "  Users dir:     $USERS_DIR"
echo "=========================================="

cd "$COMPOSE_DIR"
docker-compose up -d

echo ""
echo "  Waiting for health check..."
for i in $(seq 1 30); do
    if curl -sf "http://localhost:${FRONTEND_PORT}/health" > /dev/null 2>&1; then
        echo "  Healthy! MAS is running at http://localhost:${FRONTEND_PORT}"
        exit 0
    fi
    sleep 1
done

echo "  WARNING: Health check not passing after 30s. Check logs:"
echo "  cd $COMPOSE_DIR && docker-compose logs -f"
```

- [ ] **Step 2: Make executable**

Run: `chmod +x /root/claudeagent/run_main.sh`

- [ ] **Step 3: Commit**

```bash
git add /root/claudeagent/run_main.sh
git commit -m "feat: add run_main.sh with version tag and env config"
```

---

### Task 7: Rewrite create_user.sh

**Files:**
- Modify: `/root/claudeagent/create_user.sh`

- [ ] **Step 1: Rewrite create_user.sh**

Replace entire file with:

```bash
#!/bin/bash
# create_user.sh — Create a MAS user (directory + account).
# Requires main container to be running.
#
# Usage:
#   ./create_user.sh alice mypassword
#   FRONTEND_PORT=8080 ./create_user.sh alice mypassword

set -e

USERNAME="$1"
PASSWORD="$2"
FRONTEND_PORT="${FRONTEND_PORT:-9001}"
BASE_URL="http://localhost:${FRONTEND_PORT}"
USERS_DIR="${USERS_DIR:-/root/claudeagent/users}"

if [ -z "$USERNAME" ] || [ -z "$PASSWORD" ]; then
    echo "Usage: $0 <username> <password>"
    echo ""
    echo "Creates:"
    echo "  1. Directory: ${USERS_DIR}/<username>/{workspaces/default,data}"
    echo "  2. Account:   POST ${BASE_URL}/api/auth/register"
    echo ""
    echo "Requires main container running (./run_main.sh first)"
    exit 1
fi

echo "Creating MAS user: $USERNAME"

# Step 1: Create filesystem directories
echo "  [1/2] Creating directories..."
mkdir -p "${USERS_DIR}/${USERNAME}/workspaces/default"
mkdir -p "${USERS_DIR}/${USERNAME}/data"
chmod -R 755 "${USERS_DIR}/${USERNAME}"
echo "        ${USERS_DIR}/${USERNAME}/workspaces/default/"
echo "        ${USERS_DIR}/${USERNAME}/data/"

# Step 2: Register account via API
echo "  [2/2] Registering account..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/api/auth/register" \
    -H "Content-Type: application/json" \
    -d "{\"username\": \"${USERNAME}\", \"password\": \"${PASSWORD}\"}")

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | head -1)

if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "201" ]; then
    echo "        Account created successfully"
elif echo "$BODY" | grep -q "already exists"; then
    echo "        Account already exists (OK)"
else
    echo "        ERROR: Registration failed (HTTP $HTTP_CODE)"
    echo "        Response: $BODY"
    echo ""
    echo "        Is the main container running? Try: ./run_main.sh"
    exit 1
fi

echo ""
echo "Done! User '$USERNAME' can now login at ${BASE_URL}"
```

- [ ] **Step 2: Verify syntax**

Run: `bash -n /root/claudeagent/create_user.sh`
Expected: No output (syntax OK)

- [ ] **Step 3: Commit**

```bash
git add /root/claudeagent/create_user.sh
git commit -m "feat: create_user.sh creates directory + account in one step"
```

---

### Task 8: Update Makefile

**Files:**
- Modify: `scientific_agent/Makefile`

- [ ] **Step 1: Rewrite Makefile**

Replace entire file with:

```makefile
.PHONY: build build-sandbox build-main up down down-all logs clean rebuild restart

SCRIPT_DIR := $(shell cd .. && pwd)
TAG ?= latest

# Build images (delegates to build_images.sh)
build: build-sandbox build-main

build-sandbox:
	$(SCRIPT_DIR)/build_images.sh sandbox $(TAG)

build-main:
	$(SCRIPT_DIR)/build_images.sh main $(TAG)

# Start main container (delegates to run_main.sh)
up:
	$(SCRIPT_DIR)/run_main.sh $(TAG)

# Stop main container
down:
	docker-compose down

# Stop all (main + sandbox containers)
down-all:
	docker-compose down
	docker ps --filter "name=mas-sandbox-" -q | xargs -r docker rm -f 2>/dev/null || true

# View logs
logs:
	docker-compose logs -f

# Clean up everything
clean:
	docker-compose down -v
	docker ps --filter "name=mas-sandbox-" -q | xargs -r docker rm -f 2>/dev/null || true
	docker system prune -f

# Rebuild and start
rebuild: down build up

# Quick restart
restart: down up
```

- [ ] **Step 2: Commit**

```bash
git add scientific_agent/Makefile
git commit -m "feat: Makefile delegates to build_images.sh and run_main.sh"
```

---

## Chunk 3: Backend — Sandbox Service + API Fixes

### Task 9: Fix websocket.py field name mismatch

**Files:**
- Modify: `scientific_agent/backend/src/api/websocket.py:111-122`

- [ ] **Step 1: Fix find_sandbox_for_project**

In `websocket.py`, change line 116 from:
```python
            if sandbox.get("workspace_path") == project_path or sandbox_id == project_path:
```
to:
```python
            if sandbox.get("workspace_dir") == project_path or sandbox.get("workspace_path") == project_path or sandbox_id == project_path:
```

This adds `workspace_dir` (the field SandboxInfo actually stores) while keeping backward compatibility with `workspace_path` for any old data.

- [ ] **Step 2: Commit**

```bash
git add scientific_agent/backend/src/api/websocket.py
git commit -m "fix: websocket sandbox lookup supports workspace_dir field"
```

---

### Task 10: Update SandboxService for 1:1 user-sandbox

**Files:**
- Modify: `scientific_agent/backend/src/services/sandbox_service.py`

- [ ] **Step 1: Change container naming to use username**

The `create_sandbox` method signature changes — it now needs `username` to name the container. Modify `sandbox_service.py`:

Add a `username` parameter to `create_sandbox` (line 228):

```python
    def create_sandbox(self, sandbox_id: str, user_id: str, name: str, username: str = "") -> SandboxInfo:
```

Change container naming (line 240) from:
```python
        container_name = f"mas-sandbox-{sandbox_id[:8]}"
```
to:
```python
        container_name = f"mas-sandbox-{username}" if username else f"mas-sandbox-{sandbox_id[:8]}"
```

- [ ] **Step 2: Add rebuild_sandbox method**

Add this method after `stop_sandbox` (after line 397):

```python
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
```

- [ ] **Step 3: Add find_by_user method**

Add after `list_sandboxes` (after line 358):

```python
    def find_by_user(self, user_id: str) -> Optional[SandboxInfo]:
        """Find the single sandbox for a user (1:1 model)."""
        sandboxes = _load_sandboxes_json()
        for sid, data in sandboxes.items():
            if data.get("user_id") == user_id:
                return SandboxInfo.from_dict(data)
        return None
```

- [ ] **Step 4: Commit**

```bash
git add scientific_agent/backend/src/services/sandbox_service.py
git commit -m "feat: sandbox service supports username naming + rebuild + find_by_user"
```

---

### Task 11: Update sandboxes.py API for 1:1 + rebuild

**Files:**
- Modify: `scientific_agent/backend/src/api/sandboxes.py`

- [ ] **Step 1: Update create endpoint to enforce 1:1 and pass username**

Replace the `create_sandbox` route (lines 111-135) with:

```python
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
    if info.status == "running" and info.api_url:
        import asyncio
        loop = asyncio.get_event_loop()
        healthy = await loop.run_in_executor(
            None, service.wait_for_healthy, info.api_url, 30
        )
        if not healthy:
            logger.warning("[sandboxes] Container not healthy after 30s: %s", info.container_name)

    logger.info("[sandboxes] Created sandbox for user %s", current_user.username)
    return _to_response(info)
```

- [ ] **Step 2: Add rebuild endpoint**

Add after the `delete_sandbox` route:

```python
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
    if info.status == "running" and info.api_url:
        import asyncio
        loop = asyncio.get_event_loop()
        healthy = await loop.run_in_executor(
            None, service.wait_for_healthy, info.api_url, 30
        )
        if not healthy:
            logger.warning("[sandboxes] Rebuilt container not healthy after 30s: %s", info.container_name)

    logger.info("[sandboxes] Rebuilt sandbox for user %s", current_user.username)
    return _to_response(info)
```

- [ ] **Step 3: Add rebuild to API client**

In `frontend/claudecodeui/src/utils/api.js`, add to the `sandboxes` object (after the `stop` line):

```javascript
  rebuild: () => authenticatedFetch('/api/sandboxes/rebuild', { method: 'POST' }),
```

- [ ] **Step 4: Commit**

```bash
git add scientific_agent/backend/src/api/sandboxes.py
git add scientific_agent/frontend/claudecodeui/src/utils/api.js
git commit -m "feat: enforce 1:1 sandbox + add rebuild endpoint and API client"
```

---

## Chunk 4: Frontend — Sandbox Controls

### Task 12: Create useSandboxState hook

**Files:**
- Create: `scientific_agent/frontend/claudecodeui/src/hooks/useSandboxState.ts`

- [ ] **Step 1: Create the hook**

```typescript
import { useState, useEffect, useCallback } from 'react';
import api from '../utils/api';

export type SandboxStatus = 'none' | 'creating' | 'running' | 'stopped' | 'error' | 'rebuilding';

interface SandboxState {
  status: SandboxStatus;
  sandbox: any | null;
  error: string | null;
}

export function useSandboxState() {
  const [state, setState] = useState<SandboxState>({
    status: 'none',
    sandbox: null,
    error: null,
  });

  const fetchStatus = useCallback(async () => {
    try {
      const sandboxes = await api.sandboxes.list();
      if (sandboxes && sandboxes.length > 0) {
        const sb = sandboxes[0]; // 1:1 model
        setState({
          status: sb.status === 'running' ? 'running' : 'stopped',
          sandbox: sb,
          error: null,
        });
      } else {
        setState({ status: 'none', sandbox: null, error: null });
      }
    } catch (err: any) {
      setState(prev => ({ ...prev, error: err.message }));
    }
  }, []);

  const createSandbox = useCallback(async () => {
    setState(prev => ({ ...prev, status: 'creating', error: null }));
    try {
      const sb = await api.sandboxes.create('default');
      setState({ status: 'running', sandbox: sb, error: null });
    } catch (err: any) {
      setState(prev => ({ ...prev, status: 'error', error: err.message }));
    }
  }, []);

  const rebuildSandbox = useCallback(async () => {
    setState(prev => ({ ...prev, status: 'rebuilding', error: null }));
    try {
      const sb = await api.sandboxes.rebuild();
      setState({ status: 'running', sandbox: sb, error: null });
    } catch (err: any) {
      setState(prev => ({ ...prev, status: 'error', error: err.message }));
    }
  }, []);

  const startSandbox = useCallback(async () => {
    if (!state.sandbox) return;
    try {
      await api.sandboxes.start(state.sandbox.id);
      await fetchStatus();
    } catch (err: any) {
      setState(prev => ({ ...prev, error: err.message }));
    }
  }, [state.sandbox, fetchStatus]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  return {
    ...state,
    createSandbox,
    rebuildSandbox,
    startSandbox,
    refreshStatus: fetchStatus,
  };
}
```

- [ ] **Step 2: Commit**

```bash
git add scientific_agent/frontend/claudecodeui/src/hooks/useSandboxState.ts
git commit -m "feat: add useSandboxState hook for sandbox lifecycle"
```

---

### Task 13: Add Sandbox controls to MainContentHeader

**Files:**
- Modify: `scientific_agent/frontend/claudecodeui/src/components/main-content/view/subcomponents/MainContentHeader.tsx`

- [ ] **Step 1: Add SandboxControls component**

This step depends on the exact current content of `MainContentHeader.tsx`. Read the file first, then add a `<SandboxControls />` component inline or as a separate import.

The component should render:
- When `status === 'none'`: green "Create Sandbox" button
- When `status === 'creating'` or `'rebuilding'`: spinner + "Creating..." / "Rebuilding..."
- When `status === 'running'`: green dot + "Sandbox Running" + "Rebuild" button
- When `status === 'stopped'`: amber dot + "Sandbox Stopped" + "Start" + "Rebuild" buttons
- When `status === 'error'`: red dot + error message + "Retry" button

Place it in the header bar, to the right of the existing tab switcher.

Import and use the `useSandboxState` hook.

- [ ] **Step 2: Disable ChatComposer when no sandbox**

In `ChatComposer.tsx`, find the textarea `disabled` prop (currently `disabled={isLoading}`) and extend it:

```tsx
disabled={isLoading || !hasSandbox}
```

Where `hasSandbox` is passed as a prop or obtained from context. Also add a placeholder message:

```tsx
placeholder={hasSandbox ? "Type a message..." : "Create a sandbox first to start chatting"}
```

- [ ] **Step 3: Verify frontend builds**

Run: `cd /root/claudeagent/scientific_agent/frontend/claudecodeui && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add scientific_agent/frontend/claudecodeui/src/
git commit -m "feat: sandbox status controls in header + disable chat without sandbox"
```

---

## Chunk 5: End-to-End Verification

### Task 14: Build and test full flow

- [ ] **Step 1: Build both images**

Run: `cd /root/claudeagent && ./build_images.sh e2e`
Expected: Both `mas-sandbox:e2e` and `mas-main:e2e` built successfully

- [ ] **Step 2: Start main container**

Run: `cd /root/claudeagent && ./run_main.sh e2e`
Expected: "Healthy! MAS is running at http://localhost:9001"

- [ ] **Step 3: Verify Nginx serves frontend**

Run: `curl -s http://localhost:9001/ | head -5`
Expected: HTML content (the React SPA index.html)

- [ ] **Step 4: Verify API proxy**

Run: `curl -s http://localhost:9001/health`
Expected: `{"status":"healthy",...}`

- [ ] **Step 5: Create user**

Run: `./create_user.sh testuser testpass`
Expected: "Done! User 'testuser' can now login at http://localhost:9001"

- [ ] **Step 6: Test login**

Run: `curl -s -X POST http://localhost:9001/api/auth/login -H "Content-Type: application/json" -d '{"username":"testuser","password":"testpass"}'`
Expected: JSON with `access_token`

- [ ] **Step 7: Test sandbox create**

Run (using token from step 6):
```bash
TOKEN="<token-from-step-6>"
curl -s -X POST http://localhost:9001/api/sandboxes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"default"}'
```
Expected: JSON with sandbox info, `container_name` = `mas-sandbox-testuser`, `status` = `running`

- [ ] **Step 8: Verify sandbox container exists**

Run: `docker ps --filter "name=mas-sandbox-testuser"`
Expected: Container running

- [ ] **Step 9: Test sandbox rebuild**

Run:
```bash
curl -s -X POST http://localhost:9001/api/sandboxes/rebuild \
  -H "Authorization: Bearer $TOKEN"
```
Expected: JSON with new sandbox info, still `container_name` = `mas-sandbox-testuser`

- [ ] **Step 10: Cleanup**

Run: `cd /root/claudeagent/scientific_agent && make down-all && docker rmi mas-main:e2e mas-sandbox:e2e`

- [ ] **Step 11: Final commit**

```bash
git commit --allow-empty -m "test: docker deployment e2e verified"
```
