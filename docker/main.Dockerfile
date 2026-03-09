# ===========================================
# Main Container Dockerfile
# ===========================================
# Purpose: Backend API + Frontend UI + Sandbox Communication

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

# Install Python dependencies
COPY docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# Stage 2: Node.js builder
FROM node:20-slim AS node-builder

WORKDIR /app

# Install frontend dependencies
COPY frontend/package*.json ./
RUN npm ci --only=production


# Stage 3: Production image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    PORT=9000 \
    FRONTEND_PORT=9001

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python virtual environment from builder
COPY --from=python-builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy built node_modules
COPY --from=node-builder /app/node_modules ./frontend/node_modules

# Copy application code
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY .claude/ ./.claude/
COPY config.yaml .
COPY local.yaml.example ./local.yaml
COPY start.sh .

# Expose ports
EXPOSE 9000 9001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9000/health || exit 1

# Start command
CMD ["sh", "-c", "cd backend && python -m uvicorn src.main:app --host 0.0.0.0 --port 9000 & cd frontend && npm run dev -- --host 0.0.0.0 --port 9001 && wait"]
