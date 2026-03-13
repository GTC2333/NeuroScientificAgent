# ===========================================
# Sandbox Container Dockerfile
# ===========================================
# Purpose: Isolated execution environment with SDK agentic loop
#
# Offline build: 如果 docker/offline-deps/ 下有预下载的依赖，
# 优先使用离线安装。运行 docker/download_deps.sh 预下载。

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    WORKSPACE=/workspace

WORKDIR /app

# Copy offline apt repo (if available)
COPY docker/offline-deps/apt-repo/ /tmp/apt-repo/

# Install system dependencies (offline-first)
RUN set -eux; \
    if [ -f /tmp/apt-repo/Packages ]; then \
        echo "[OFFLINE] Using local APT repo..." && \
        echo "deb [trusted=yes] file:/tmp/apt-repo ./" > /etc/apt/sources.list.d/local.list && \
        apt-get update && \
        apt-get install -y --no-install-recommends curl git ripgrep 2>/dev/null || \
        (rm -f /etc/apt/sources.list.d/local.list && apt-get update && \
         apt-get install -y --no-install-recommends curl git ripgrep); \
    else \
        echo "[ONLINE] Installing from remote repos..." && \
        apt-get update && \
        apt-get install -y --no-install-recommends curl git ripgrep; \
    fi && \
    rm -rf /var/lib/apt/lists/* /tmp/apt-repo

# Copy offline pip wheels (if available)
COPY docker/offline-deps/pip-wheels/sandbox/ /tmp/pip-wheels/

# Install Python dependencies (offline-first)
COPY docker/sandbox-requirements.txt .
RUN if ls /tmp/pip-wheels/*.whl 1>/dev/null 2>&1; then \
        echo "[OFFLINE] Installing from local pip wheels..." && \
        pip install --no-cache-dir --no-index --find-links /tmp/pip-wheels -r sandbox-requirements.txt; \
    else \
        echo "[ONLINE] Installing from PyPI..." && \
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
