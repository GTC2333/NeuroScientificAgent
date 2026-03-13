# ===========================================
# Main Container Dockerfile
# ===========================================
# Purpose: Backend API + Frontend UI (Nginx) + Docker Sandbox Management
#
# Offline build: 如果 docker/offline-deps/ 下有预下载的依赖，
# 优先使用离线安装，跳过网络下载，大幅加速构建。
# 运行 docker/download_deps.sh 预下载依赖。

# Stage 1: Python builder
FROM python:3.11-slim AS python-builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy offline pip wheels (if available)
COPY docker/offline-deps/pip-wheels/main/ /tmp/pip-wheels/
COPY docker/requirements.txt .

# Offline-first: try local wheels, fallback to network
RUN if ls /tmp/pip-wheels/*.whl 1>/dev/null 2>&1; then \
        echo "[OFFLINE] Installing from local pip wheels..." && \
        pip install --no-cache-dir --no-index --find-links /tmp/pip-wheels -r requirements.txt; \
    else \
        echo "[ONLINE] No local wheels found, installing from PyPI..." && \
        pip install --no-cache-dir -r requirements.txt; \
    fi && \
    rm -rf /tmp/pip-wheels


# Stage 2: Node.js builder
FROM node:20-slim AS node-builder

WORKDIR /app/frontend/claudecodeui

# Copy offline npm cache (if available)
COPY docker/offline-deps/npm-cache/ /tmp/npm-cache/

# Install frontend dependencies (offline-first)
COPY frontend/claudecodeui/package*.json ./
RUN if [ -f /tmp/npm-cache/node_modules.tar.gz ]; then \
        echo "[OFFLINE] Extracting cached node_modules..." && \
        tar xzf /tmp/npm-cache/node_modules.tar.gz && \
        npm install 2>/dev/null || true; \
    else \
        echo "[ONLINE] Running npm ci..." && \
        npm ci; \
    fi && \
    rm -rf /tmp/npm-cache

# Copy frontend source and build
COPY frontend/claudecodeui/ ./
RUN npm run build


# Stage 3: Production image (Nginx + FastAPI)
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=9000

WORKDIR /app

# Copy offline apt repo (if available)
COPY docker/offline-deps/apt-repo/ /tmp/apt-repo/

# Install runtime dependencies (offline-first for apt)
RUN set -eux; \
    if [ -f /tmp/apt-repo/Packages ]; then \
        echo "[OFFLINE] Using local APT repo..." && \
        echo "deb [trusted=yes] file:/tmp/apt-repo ./" > /etc/apt/sources.list.d/local.list && \
        apt-get update && \
        apt-get install -y --no-install-recommends nginx curl docker.io 2>/dev/null || \
        (rm -f /etc/apt/sources.list.d/local.list && apt-get update && \
         apt-get install -y --no-install-recommends nginx curl docker.io); \
    else \
        echo "[ONLINE] Installing from remote repos..." && \
        apt-get update && \
        apt-get install -y --no-install-recommends nginx curl docker.io; \
    fi && \
    rm -rf /var/lib/apt/lists/* /tmp/apt-repo

# Copy Python virtual environment from builder
COPY --from=python-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy Nginx config
COPY docker/nginx.conf /etc/nginx/sites-available/default

# Copy built frontend static files (only dist/, no node/express needed)
COPY --from=node-builder /app/frontend/claudecodeui/dist ./frontend/dist

# Copy application code
COPY backend/ ./backend/
COPY claude/ ./claude/
COPY config.yaml .
COPY local.yaml.example ./local.yaml

# Expose single port (Nginx serves both static + API proxy)
EXPOSE 80

# Health check via Nginx → FastAPI
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:80/health || exit 1

# Start nginx + uvicorn
CMD ["sh", "-c", "nginx && cd backend && python -m uvicorn src.main:app --host 0.0.0.0 --port 9000"]
