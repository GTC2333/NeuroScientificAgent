#!/bin/bash

# MAS - Multi-Agent Scientific Operating System
# One-click startup script

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_FILE="$SCRIPT_DIR/frontend/templates/index.html"
PORT=8000

echo "=========================================="
echo "  MAS - Starting Multi-Agent System"
echo "=========================================="

# Check if backend dependencies are installed
if [ ! -d "$BACKEND_DIR/venv" ] && [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo "[1/4] Setting up Python environment..."

    # Try poetry first, fall back to pip
    if command -v poetry &> /dev/null; then
        cd "$BACKEND_DIR"
        poetry install
        POETRY_RUN="poetry run"
    else
        cd "$BACKEND_DIR"
        pip3 install -q fastapi uvicorn pydantic sse-starlette python-multipart
        POETRY_RUN=""
    fi

    if [ $? -ne 0 ]; then
        echo "Error: Failed to install dependencies"
        exit 1
    fi
fi

# Determine how to run Python
if command -v poetry &> /dev/null; then
    cd "$BACKEND_DIR"
    POETRY_RUN="poetry run"
else
    POETRY_RUN="python3"
fi

# Kill existing server on port 8000
if lsof -Pi :$PORT -sTCP:LISTEN -t &> /dev/null; then
    echo "[2/4] Killing existing server on port $PORT..."
    lsof -Pi :$PORT -sTCP:LISTEN -t | xargs kill -9 2>/dev/null
fi

# Start backend server
echo "[3/4] Starting backend server on port $PORT..."
cd "$BACKEND_DIR"
$POETRY_RUN python -m src.main &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Check if backend started successfully
if ! curl -s http://localhost:$PORT/health &> /dev/null; then
    echo "Error: Backend failed to start"
    exit 1
fi

echo "[4/4] Opening frontend..."
# Open frontend in default browser
if command -v open &> /dev/null; then
    open "file://$FRONTEND_FILE"
elif command -v xdg-open &> /dev/null; then
    xdg-open "file://$FRONTEND_FILE"
else
    echo "Please open: file://$FRONTEND_FILE"
fi

echo ""
echo "=========================================="
echo "  MAS is running!"
echo "=========================================="
echo "  Backend: http://localhost:$PORT"
echo "  Frontend: $FRONTEND_FILE"
echo ""
echo "  Press Ctrl+C to stop"
echo "=========================================="

# Wait for interrupt
trap "kill $BACKEND_PID 2>/dev/null; exit" INT TERM

wait $BACKEND_PID
