# MAS Dev + Docker Compose Deployment (Minimal) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep `start.sh` as the fastest dev workflow, and add/align a minimal production-ready Docker Compose topology where the frontend is served as a static site behind Nginx and API traffic is routed under `/api`.

**Architecture:** Production uses three services: `web` (Nginx) as the only public entrypoint, `backend` (FastAPI/Uvicorn), and `sandbox` (Claude Code execution). Stable invariants: browser uses `/` and `/api/*` only.

**Tech Stack:** Docker, Docker Compose, Nginx, FastAPI/Uvicorn, Poetry, Vite (dev), Node.js.

---

## Preflight (do once)

### Task 0: Inventory existing docker assets

**Files:**
- Inspect: `scientific_agent/docker-compose.yml`
- Inspect: `scientific_agent/docker/main.Dockerfile`
- Inspect: `scientific_agent/docker/sandbox.Dockerfile`
- Inspect: `scientific_agent/docker/env.production`
- Inspect: `scientific_agent/.env.example`
- Inspect: `scientific_agent/frontend/claudecodeui/vite.config.js`
- Inspect: `scientific_agent/backend/src/main.py`

**Step 1: List docker-related files**

Run:
```bash
ls -la scientific_agent/docker scientific_agent/docker-compose.yml || true
```
Expected: see existing Dockerfiles/compose.

**Step 2: Read compose & Dockerfiles to confirm current ports and services**

Run:
```bash
sed -n '1,240p' scientific_agent/docker-compose.yml
sed -n '1,240p' scientific_agent/docker/main.Dockerfile
sed -n '1,240p' scientific_agent/docker/sandbox.Dockerfile
```
Expected: understand current topology before changing anything.

---

## Implementation

### Task 1: Define production static frontend build output

**Files:**
- Inspect: `scientific_agent/frontend/claudecodeui/package.json`
- Inspect: `scientific_agent/frontend/claudecodeui/vite.config.js`

**Step 1: Identify build command and output directory**

Run:
```bash
cat scientific_agent/frontend/claudecodeui/package.json
```
Expected: find `build` script (typically `vite build`) and confirm output directory (typically `dist/`).

**Step 2: Verify Vite build output location**

Run:
```bash
cat scientific_agent/frontend/claudecodeui/vite.config.js
```
Expected: confirm default `dist/` or configured `build.outDir`.

**Step 3: Run a local build to confirm it produces static assets**

Run:
```bash
cd scientific_agent/frontend/claudecodeui
npm ci
npm run build
ls -la dist || ls -la build || true
```
Expected: a directory containing `index.html` and assets.

---

### Task 2: Add minimal Nginx config for `/` + `/api` routing

**Files:**
- Create: `scientific_agent/docker/nginx/default.conf`

**Step 1: Create the Nginx config file**

Create `scientific_agent/docker/nginx/default.conf` with this content:
```nginx
server {
  listen 80;

  root /usr/share/nginx/html;
  index index.html;

  # Serve SPA
  location / {
    try_files $uri $uri/ /index.html;
  }

  # API reverse proxy
  location /api/ {
    proxy_pass http://backend:9000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
  }

  # Optional websockets
  location /ws {
    proxy_pass http://backend:9000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
  }

  location /shell {
    proxy_pass http://backend:9000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
  }
}
```

**Step 2: Sanity check config format**

Run:
```bash
nginx -t -c /etc/nginx/nginx.conf || true
```
Expected: you may need a container to truly validate; this step is informational.

---

### Task 3: Build a minimal `web` image that serves built frontend

**Files:**
- Create: `scientific_agent/docker/web.Dockerfile`

**Step 1: Create Dockerfile (multi-stage: build frontend then serve via nginx)**

Create `scientific_agent/docker/web.Dockerfile`:
```dockerfile
# Build frontend
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/claudecodeui/package*.json ./
RUN npm ci
COPY frontend/claudecodeui/ ./
RUN npm run build

# Serve via nginx
FROM nginx:1.27-alpine
COPY docker/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist/ /usr/share/nginx/html/
```

**Step 2: Build the image**

Run:
```bash
docker build -f scientific_agent/docker/web.Dockerfile -t mas-web:local scientific_agent
```
Expected: build succeeds and includes static assets.

---

### Task 4: Align docker-compose.yml to the minimal production topology

**Files:**
- Modify: `scientific_agent/docker-compose.yml`

**Step 1: Update compose to include `web`, `backend`, `sandbox`**

Target shape (exact edits depend on existing file contents):
- `web`:
  - builds `docker/web.Dockerfile`
  - exposes `80:80`
  - depends_on backend
- `backend`:
  - builds existing `docker/main.Dockerfile` (or adjust if needed)
  - exposes only internal `9000`
  - env_file: `.env` or `docker/env.production`
  - depends_on sandbox
- `sandbox`:
  - builds existing `docker/sandbox.Dockerfile`
  - exposes only internal `9002`
  - env_file: same env file

**Step 2: Validate compose config**

Run:
```bash
docker compose -f scientific_agent/docker-compose.yml config
```
Expected: prints fully resolved config; no errors.

---

### Task 5: Production smoke test via compose

**Files:**
- None

**Step 1: Start stack**

Run:
```bash
docker compose -f scientific_agent/docker-compose.yml up -d --build
```
Expected: services start.

**Step 2: Verify health**

Run:
```bash
curl -sS http://localhost/health
curl -sS http://localhost/api/health || true
```
Expected:
- If `/health` is served by backend behind proxy, ensure routing is correct.
- If health is only on backend root, consider proxying `/health` as well (design choice).

**Step 3: Verify static UI loads**

Run:
```bash
curl -I http://localhost/
```
Expected: 200 with `text/html`.

**Step 4: Verify `/api/*` reverse proxy**

Run:
```bash
curl -sS http://localhost/api/logs || true
```
Expected: a JSON response (depends on API availability).

---

### Task 6: Keep dev workflow intact (start.sh remains fastest)

**Files:**
- Inspect: `scientific_agent/start.sh`

**Step 1: Verify dev startup still works**

Run:
```bash
./scientific_agent/start.sh
```
Expected:
- backend on 9000
- Vite on 5173

**Step 2: Verify Vite proxies `/api` to backend**

Run:
```bash
curl -sS http://localhost:5173/api/health || true
```
Expected: successful proxying (or adjust to the correct health path).

---

## Documentation / Operator Notes

- Update `.env.example` to list required `ANTHROPIC_*` variables used by your provider.
- Document two workflows:
  - Dev: `./start.sh`
  - Prod: `docker compose up -d --build`

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-03-09-mas-dev-docker-compose-implementation-plan.md`.

Two execution options:

1. **Subagent-Driven (this session)** — I dispatch a fresh subagent per task and review between tasks.
2. **Parallel Session (separate)** — Open a new session using **superpowers:executing-plans** and run tasks in batches with checkpoints.

Which approach do you prefer?
