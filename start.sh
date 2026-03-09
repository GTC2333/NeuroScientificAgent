#!/bin/bash

# MAS - Multi-Agent Scientific Operating System
# One-click startup script

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_FILE="$SCRIPT_DIR/frontend/templates/index.html"
PORT=9000

echo "=========================================="
echo "  MAS - Starting Multi-Agent System"
echo "=========================================="

# Check for existing venv in project root
VENV_DIR="$SCRIPT_DIR/venv"

# Setup Python environment
if [ -d "$VENV_DIR" ]; then
    echo "[1/4] Using existing Python virtual environment..."
    PYTHON_CMD="$VENV_DIR/bin/python"
    PIP_CMD="$VENV_DIR/bin/pip"
else
    echo "[1/4] Setting up Python virtual environment..."

    # Create venv if it doesn't exist
    python3 -m venv "$VENV_DIR"
    PYTHON_CMD="$VENV_DIR/bin/python"
    PIP_CMD="$VENV_DIR/bin/pip"

    # Install dependencies
    $PIP_CMD install -q fastapi uvicorn pydantic sse-starlette python-multipart pyyaml

    if [ $? -ne 0 ]; then
        echo "Error: Failed to install dependencies"
        exit 1
    fi
fi

# Kill existing servers
if lsof -Pi :$PORT -sTCP:LISTEN -t &> /dev/null; then
    echo "[2/4] Killing existing server on port $PORT..."
    lsof -Pi :$PORT -sTCP:LISTEN -t | xargs kill -9 2>/dev/null
fi
if lsof -Pi :9001 -sTCP:LISTEN -t &> /dev/null; then
    echo "[2/4] Killing existing server on port 9001..."
    lsof -Pi :9001 -sTCP:LISTEN -t | xargs kill -9 2>/dev/null
fi

# Start backend server
echo "[3/4] Starting backend server on port $PORT..."
cd "$BACKEND_DIR"
$PYTHON_CMD -m uvicorn src.main:app --host 0.0.0.0 --port $PORT &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Check if backend started successfully
if ! curl -s http://localhost:$PORT/health &> /dev/null; then
    echo "Error: Backend failed to start"
    exit 1
fi

echo "[4/4] Starting frontend dev server..."

# Start frontend with npm
cd "$SCRIPT_DIR/frontend"
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi
npm run dev &
FRONTEND_PID=$!

# Wait for frontend to start
sleep 5

# Open frontend in default browser
if command -v open &> /dev/null; then
    open "http://localhost:9001"
elif command -v xdg-open &> /dev/null; then
    xdg-open "http://localhost:9001"
fi

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
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

wait
