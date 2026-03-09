# ===========================================
# Sandbox Container Dockerfile
# ===========================================
# Purpose: Isolated execution environment for Claude Code CLI

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    wget \
    build-essential \
    # For Claude Code CLI
    sudo \
    jq \
    # For potential Node.js tools
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Claude Code CLI (stable version)
RUN curl -fsSL https://raw.githubusercontent.com/anthropics/claude-code/main/install.sh | sh

# Verify Claude Code installation
RUN claude --version

# Copy sandbox-specific files
COPY docker/sandbox-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy .claude directory and sandbox API
COPY .claude/ ./.claude/
COPY sandbox/ ./sandbox/
COPY config.yaml .

# Create workspace directory
RUN mkdir -p /workspace

# Expose API port (for sandbox API server)
EXPOSE 9002

# Entry point
ENTRYPOINT ["/entrypoint.sh"]
