# ===========================================
# Sandbox Container Dockerfile
# ===========================================
# Purpose: Isolated execution environment with SDK agentic loop

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    WORKSPACE=/workspace

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    grep \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY docker/sandbox-requirements.txt .
RUN pip install --no-cache-dir -r sandbox-requirements.txt

# Copy sandbox code and claude config
COPY sandbox/ ./sandbox/
COPY claude/ ./claude/

# Create workspace directory
RUN mkdir -p /workspace

# Expose API port
EXPOSE 9002

# Start sandbox API
CMD ["python", "-m", "uvicorn", "sandbox.api:app", "--host", "0.0.0.0", "--port", "9002"]
