#!/bin/bash
set -e

echo "=========================================="
echo "  MAS Sandbox Container"
echo "=========================================="
echo "  Claude Code CLI: $(claude --version)"
echo "  Workspace: /workspace"
echo "=========================================="

# Start sandbox API server in background
echo "Starting sandbox API server..."
cd /app
python -m uvicorn sandbox.api:app --host 0.0.0.0 --port 9002 &
API_PID=$!

# Wait for API to be ready
sleep 2

# Health check
if curl -f http://localhost:9002/health &>/dev/null; then
    echo "Sandbox API ready at http://localhost:9002"
else
    echo "Warning: Sandbox API health check failed"
fi

# Keep container running
echo "Sandbox ready. Press Ctrl+C to stop."
wait $API_PID
