# ===========================================
# Sandbox Container Dockerfile
# ===========================================
# Purpose: Isolated execution environment with SDK agentic loop
#
# Offline build: 支持两种离线依赖来源:
#   1. docker/offline-deps/ (构建时 COPY 进镜像)
#   2. /opt/offline-deps/ (运行时通过 volume 挂载)

FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    WORKSPACE=/workspace

WORKDIR /app

# Install system dependencies (one-shot: update + install)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Copy offline pip wheels (if available)
COPY docker/offline-deps/pip-wheels/sandbox/ /tmp/pip-wheels/

# Install Python dependencies (offline-first)
COPY docker/sandbox-requirements.txt .
RUN if [ -d /tmp/pip-wheels ] && ls /tmp/pip-wheels/*.whl 1>/dev/null 2>&1; then \
        pip install --no-cache-dir --no-index --find-links /tmp/pip-wheels -r sandbox-requirements.txt; \
    else \
        pip install --no-cache-dir -r sandbox-requirements.txt; \
    fi && \
    rm -rf /tmp/pip-wheels

# Copy sandbox code and claude config
COPY sandbox/ ./sandbox/
COPY claude/ ./claude/

# Create workspace directory
RUN mkdir -p /workspace

# Expose API port
EXPOSE 9002

# Start sandbox API
CMD ["python", "-m", "uvicorn", "sandbox.api:app", "--host", "0.0.0.0", "--port", "9002"]
