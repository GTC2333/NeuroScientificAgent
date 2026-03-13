#!/bin/bash

# MAS - Multi-Agent Scientific Operating System
# One-click startup script
# Supports two modes:
#   - Local mode (default): runs backend + frontend directly
#   - Docker mode: set MAS_SANDBOX_IMAGE to enable Docker sandbox containers

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
PORT=9000

echo "=========================================="
echo "  MAS - Starting Multi-Agent System"
echo "=========================================="

# Check for Docker sandbox mode
if [ -n "$MAS_SANDBOX_IMAGE" ]; then
    echo "  Docker sandbox mode enabled"
    echo "  Sandbox image: $MAS_SANDBOX_IMAGE"
    echo "=========================================="
fi

# Poetry-based backend env (single source of truth)
if ! command -v poetry &> /dev/null; then
    echo "Error: poetry not found in PATH"
    exit 1
fi

echo "[1/4] Installing backend dependencies (Poetry)..."
cd "$BACKEND_DIR"
poetry install --no-root

# Kill existing servers
if lsof -Pi :$PORT -sTCP:LISTEN -t &> /dev/null; then
    echo "[2/4] Killing existing server on port $PORT..."
    lsof -Pi :$PORT -sTCP:LISTEN -t | xargs kill -9 2>/dev/null
fi
if lsof -Pi :9001 -sTCP:LISTEN -t &> /dev/null; then
    echo "[2/4] Killing existing server on port 9001..."
    lsof -Pi :9001 -sTCP:LISTEN -t | xargs kill -9 2>/dev/null
fi
if lsof -Pi :3001 -sTCP:LISTEN -t &> /dev/null; then
    echo "[2/4] Killing existing server on port 3001 (Express)..."
    lsof -Pi :3001 -sTCP:LISTEN -t | xargs kill -9 2>/dev/null
fi
if lsof -Pi :5173 -sTCP:LISTEN -t &> /dev/null; then
    echo "[2/4] Killing existing server on port 5173 (Vite)..."
    lsof -Pi :5173 -sTCP:LISTEN -t | xargs kill -9 2>/dev/null
fi

# Start backend server (Poetry)
echo "[3/4] Starting backend server on port $PORT (Poetry)..."
cd "$BACKEND_DIR"
# Load Minimax-compatible env from local Claude settings if present
if [ -f "$SCRIPT_DIR/.claude/settings.local.json" ]; then
    export ANTHROPIC_BASE_URL="$(python3 -c 'import json;print(json.load(open("/root/claudeagent/scientific_agent/.claude/settings.local.json"))['"'"'env'"'"'].get("ANTHROPIC_BASE_URL", ""))')"
    export ANTHROPIC_AUTH_TOKEN="$(python3 -c 'import json;print(json.load(open("/root/claudeagent/scientific_agent/.claude/settings.local.json"))['"'"'env'"'"'].get("ANTHROPIC_AUTH_TOKEN", ""))')"
    export ANTHROPIC_MODEL="$(python3 -c 'import json;print(json.load(open("/root/claudeagent/scientific_agent/.claude/settings.local.json"))['"'"'env'"'"'].get("ANTHROPIC_MODEL", ""))')"
fi
poetry run uvicorn src.main:app --host 0.0.0.0 --port $PORT &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Check if backend started successfully
if ! curl -s http://localhost:$PORT/health &> /dev/null; then
    echo "Error: Backend failed to start"
    exit 1
fi

# Start frontend (Express server + Vite dev server)
echo "[4/4] Starting claudecodeui..."

CLAUDECODEUI_DIR="$SCRIPT_DIR/frontend/claudecodeui"
cd "$CLAUDECODEUI_DIR"

# In this environment proxy vars may break npm registry access
export HTTP_PROXY=
export HTTPS_PROXY=
export ALL_PROXY=
export NO_PROXY=

# Configure Vite proxy target
export MAS_BACKEND_URL="http://localhost:$PORT"

# Skip authentication (Platform mode)
export VITE_IS_PLATFORM=true

# Ensure Vite dev server listens on port 9001 (overrides .env default of 5173)
export VITE_PORT=9001

if [ ! -d "node_modules" ]; then
    echo "Installing claudecodeui dependencies..."
    npm install
fi

# Use npm run dev to start both Express server and Vite dev server
# concurrently will run "node server/index.js" and "vite --host" together
echo "Starting claudecodeui (Express + Vite)..."
npx npm run dev &

echo ""
echo "=========================================="
echo "  MAS is running!"
echo "=========================================="
echo "  Backend: http://localhost:$PORT"
echo "  Frontend: http://localhost:9001"
echo ""
echo "  Press Ctrl+C to stop"
echo "=========================================="

# Wait for interrupt
trap "kill $BACKEND_PID 2>/dev/null; exit" INT TERM

wait $BACKEND_PID
