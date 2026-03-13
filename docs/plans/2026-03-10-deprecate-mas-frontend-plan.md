# Deprecate mas-frontend (keep claudecodeui) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move the legacy `mas-frontend` app out of `scientific_agent/frontend/` into `scientific_agent/deprecated/mas-frontend/` while keeping `scientific_agent/start.sh` fully functional (still serving `frontend/claudecodeui` on port 9001).

**Architecture:** Keep `frontend/claudecodeui/**` in place as the active UI used by `start.sh`. Deprecate everything else currently living directly under `frontend/` (the Vite+TS `mas-frontend` app and `frontend/templates`) by moving it under `deprecated/mas-frontend/`. Do not modify docker files in this change; explicitly accept that docker builds relying on `frontend/package.json` will break until a later, user-approved docker refactor.

**Tech Stack:** Bash (mv/mkdir), FastAPI/Uvicorn (health check), Vite (claudecodeui dev server), Poetry.

---

### Task 1: Preflight inventory (confirm exactly what will move)

**Files:**
- Inspect: `scientific_agent/frontend/` (directory listing)
- Inspect: `scientific_agent/frontend/claudecodeui/` (confirm it remains)
- Inspect: `scientific_agent/start.sh`

**Step 1: List current frontend directory**

Run:
```bash
ls -la scientific_agent/frontend
```
Expected:
- `claudecodeui/` exists
- legacy files exist: `src/`, `package.json`, `vite.config.ts`, `templates/`, etc.

**Step 2: Confirm claudecodeui is present and will NOT be moved**

Run:
```bash
ls -la scientific_agent/frontend/claudecodeui | head
```
Expected: directory contents print; no errors.

**Step 3: Confirm start.sh uses claudecodeui and contains the legacy FRONTEND_FILE variable**

Run:
```bash
sed -n '1,120p' scientific_agent/start.sh
```
Expected:
- `CLAUDECODEUI_DIR="$SCRIPT_DIR/frontend/claudecodeui"`
- legacy unused variable: `FRONTEND_FILE="$SCRIPT_DIR/frontend/templates/index.html"`

---

### Task 2: Create deprecated target directory

**Files:**
- Create: `scientific_agent/deprecated/mas-frontend/` (directory)

**Step 1: Create directory**

Run:
```bash
mkdir -p scientific_agent/deprecated/mas-frontend
```
Expected: directory created; no output.

**Step 2: Sanity check directory exists**

Run:
```bash
ls -la scientific_agent/deprecated
```
Expected: shows `mas-frontend/`.

---

### Task 3: Move mas-frontend files into deprecated (excluding claudecodeui)

**Files:**
- Move (from): `scientific_agent/frontend/*` (excluding `claudecodeui/`)
- Move (to): `scientific_agent/deprecated/mas-frontend/*`

**Step 1: Move directories and files**

Run each command and verify success after each group:

```bash
# Move the legacy Vite+TS app
mv scientific_agent/frontend/src scientific_agent/deprecated/mas-frontend/

# Move configuration and package manifests
mv scientific_agent/frontend/index.html scientific_agent/deprecated/mas-frontend/
mv scientific_agent/frontend/package.json scientific_agent/deprecated/mas-frontend/
mv scientific_agent/frontend/package-lock.json scientific_agent/deprecated/mas-frontend/
mv scientific_agent/frontend/vite.config.ts scientific_agent/deprecated/mas-frontend/
mv scientific_agent/frontend/tsconfig.json scientific_agent/deprecated/mas-frontend/
mv scientific_agent/frontend/tsconfig.node.json scientific_agent/deprecated/mas-frontend/
mv scientific_agent/frontend/tailwind.config.js scientific_agent/deprecated/mas-frontend/
mv scientific_agent/frontend/postcss.config.js scientific_agent/deprecated/mas-frontend/

# Move legacy static templates UI
mv scientific_agent/frontend/templates scientific_agent/deprecated/mas-frontend/
```

Expected:
- All `mv` commands succeed.
- `scientific_agent/frontend/` still contains `claudecodeui/`.

**Step 2: Verify only claudecodeui remains under frontend**

Run:
```bash
ls -la scientific_agent/frontend
```
Expected:
- `claudecodeui/` remains
- The moved items are gone

**Step 3: Verify deprecated folder now contains the moved app**

Run:
```bash
ls -la scientific_agent/deprecated/mas-frontend
```
Expected:
- `src/` present
- `package.json`, `vite.config.ts`, `templates/`, etc.

---

### Task 4: Clean legacy variable in start.sh (no behavior change)

**Files:**
- Modify: `scientific_agent/start.sh` (remove unused `FRONTEND_FILE=...frontend/templates/index.html`)

**Step 1: Remove the legacy variable line**

Edit `scientific_agent/start.sh` to delete this line:
```bash
FRONTEND_FILE="$SCRIPT_DIR/frontend/templates/index.html"
```

Expected:
- No other references exist; removing it should not affect behavior.

**Step 2: Quick grep to ensure no remaining references**

Run:
```bash
grep -n "FRONTEND_FILE" -n scientific_agent/start.sh || true
```
Expected: no output.

---

### Task 5: Verify start.sh still works (backend health + frontend reachable)

**Files:**
- None

**Step 1: Start system**

Run:
```bash
./scientific_agent/start.sh
```
Expected:
- Backend starts on `:9000`
- Vite dev server starts on `:9001` from `frontend/claudecodeui`

**Step 2: Verify backend health**

In another terminal:
```bash
curl -sS http://localhost:9000/health
```
Expected: JSON with `status: healthy`.

**Step 3: Verify frontend is reachable**

In another terminal:
```bash
curl -I http://localhost:9001/
```
Expected: `HTTP/1.1 200` and `Content-Type: text/html`.

**Step 4: Verify frontend proxy to backend**

In another terminal:
```bash
curl -sS http://localhost:9001/api/health || true
```
Expected:
- Either 200 with JSON, or (if Vite proxy config differs) a clear error indicating proxy mismatch.

---

## Rollback (if anything goes wrong)

**Rollback A: Move mas-frontend back into place**

Run:
```bash
mv scientific_agent/deprecated/mas-frontend/* scientific_agent/frontend/
```
Then verify:
```bash
ls -la scientific_agent/frontend
```

**Rollback B: Restore the FRONTEND_FILE line in start.sh**

Re-add:
```bash
FRONTEND_FILE="$SCRIPT_DIR/frontend/templates/index.html"
```
near the top where it originally was.

---

## Execution Handoff

Plan complete and saved to `scientific_agent/docs/plans/2026-03-10-deprecate-mas-frontend-plan.md`.

Two execution options:

1. **Subagent-Driven (this session)** — I dispatch a fresh subagent per task, review between tasks.
2. **Parallel Session (separate)** — Open a new session using **superpowers:executing-plans** and run tasks in batches with checkpoints.

Which approach do you prefer?
