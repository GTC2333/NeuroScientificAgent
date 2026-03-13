# MAS Dev + Docker Compose Deployment (Minimal) — Design

**Status:** Proposed (user-approved direction: Option A)

## Goal

- **Development:** One-click local startup via `scientific_agent/start.sh` (Poetry backend + Vite claudecodeui).
- **Production / scalable single-host deployment:** Two Docker images orchestrated by **Docker Compose**, with the **frontend served as a static site**, and API requests routed consistently under `/api`.

## Non-Goals (for this design)

- Kubernetes manifests/Helm.
- Multi-node service discovery, autoscaling.
- Changing MAS core architecture or agent workflows.

## Constraints / Existing Repo Reality

- Backend is a FastAPI app run via Uvicorn (Poetry-managed).
- Frontend is `frontend/claudecodeui` (Vite in dev).
- Existing design docs already describe a **Main vs Sandbox** container split; this design keeps that split and makes the *production entrypoint* minimal.

## Minimal Production Architecture

### Components

1) **web (Nginx)** — *public entrypoint*
- Serves **static frontend assets** at `/`.
- Reverse-proxies:
  - `/api/*` → `backend:9000`
  - `/ws` and `/shell` (if used) → `backend:9000` (with websocket upgrade)

2) **backend (FastAPI/Uvicorn)**
- Exposes API under `/api/*` and health under `/health`.
- Calls **sandbox** over the internal docker network when it needs to execute Claude Code CLI.

3) **sandbox (Claude Code CLI execution environment)**
- Runs Claude Code CLI + skills/agents execution.
- Receives execution requests from backend over internal network.

### Networking

- Public ports: **80/443 on web only**.
- Internal ports:
  - backend: **9000**
  - sandbox: **9002** (or existing port used by sandbox API)
- Internal docker network (compose default or explicit `mas-network`).

### API & URL invariants (for long-term flexibility)

- Browser always uses:
  - Frontend: `/`
  - Backend API: `/api/*`
- This invariant allows later changes without touching frontend code:
  - Replace Nginx with backend static hosting
  - Move backend to a different port
  - Add auth, rate limit, WAF at the edge

## Development Architecture (kept as-is)

- `start.sh` runs:
  - backend: `poetry run uvicorn ... --port 9000`
  - frontend: `vite --host --port 5173` (proxy `/api` to `http://localhost:9000` via Vite config)

## Configuration & Secrets Model

- Use environment variables for provider credentials (no secrets baked into images):
  - `ANTHROPIC_BASE_URL`
  - `ANTHROPIC_AUTH_TOKEN` (or `ANTHROPIC_API_KEY` depending on gateway)
  - `ANTHROPIC_MODEL`
- Compose loads these from:
  - `.env` for local compose dev
  - `docker/env.production` (or equivalent) for production

## Extensibility / Future Modifications (explicitly supported)

- **Static hosting switch:**
  - Default: Nginx serves static assets.
  - Future option: backend serves the same built assets (remove web container).
- **Scaling sandbox:**
  - Sandbox can be scaled independently (within compose constraints) by adding replicas behind a simple internal router (future).
- **CI/CD ready:**
  - Images are clearly separated; adding build pipelines does not change runtime topology.

## Verification Criteria

Production/compose run is considered healthy if:
- `GET /health` returns `status: healthy`.
- Browser loads `/` successfully.
- Browser API calls to `/api/*` succeed via Nginx reverse proxy.

---

## Notes

This document intentionally stays minimal and focuses on stable boundaries (URLs, container responsibilities) to maximize later changeability.
