# ===========================================
# Main Container Dockerfile
# ===========================================
# Purpose: Backend API + Frontend UI (Nginx) + Docker Sandbox Management
#
# Offline build: 支持两种离线依赖来源:
#   1. docker/offline-deps/ (构建时 COPY 进镜像)
#   2. /opt/offline-deps/ (运行时通过 volume 挂载)
#
# 运行 docker/download_deps.sh 预下载依赖到 docker/offline-deps/

# Stage 1: Python builder
FROM python:3.12-slim AS python-builder

WORKDIR /app

# Create virtual environment (no need for gcc in Stage 1)
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy offline pip wheels (if available)
COPY docker/offline-deps/pip-wheels/main/ /tmp/pip-wheels/
COPY docker/requirements.txt .

# Offline-first: try local wheels, fallback to network
RUN if [ -d /tmp/pip-wheels ] && ls /tmp/pip-wheels/*.whl 1>/dev/null 2>&1; then \
        pip install --no-cache-dir --no-index --find-links /tmp/pip-wheels -r requirements.txt; \
    else \
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
        tar xzf /tmp/npm-cache/node_modules.tar.gz; \
    else \
        npm ci; \
    fi && \
    rm -rf /tmp/npm-cache

# Copy frontend source and build
COPY frontend/claudecodeui/ ./
RUN npm run build


# Stage 3: Production image (Nginx + FastAPI)
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=9000

WORKDIR /app

# Install runtime dependencies (one-shot: update + install)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx curl docker.io \
    && rm -rf /var/lib/apt/lists/*

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
