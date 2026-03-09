# Docker 镜像隔离架构实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 MAS 系统构建为两个 Docker 镜像（主容器 + 沙盒容器），支持通过 Docker Compose 快速部署

**Architecture:**
- **主容器 (main)**: FastAPI backend + React frontend，负责用户会话管理、前端服务、与沙盒通信
- **沙盒容器 (sandbox)**: 隔离执行环境，运行 Claude Code CLI，支持 Agent Teams
- **通信方式**: HTTP REST API
- **容器生命周期**: 按会话创建，会话结束时销毁

**Tech Stack:**
- 主容器: Python 3.11 + Node.js 20 + FastAPI + React + Vite
- 沙盒容器: Python 3.11 + Claude Code CLI + Docker SDK
- 编排: Docker Compose

---

## 任务总览

| 任务 | 描述 | 预计步骤 |
|------|------|----------|
| Task 1 | 创建项目 .dockerignore 文件 | 3 |
| Task 2 | 创建主容器 Dockerfile | 5 |
| Task 3 | 创建沙盒容器 Dockerfile | 5 |
| Task 4 | 创建 docker-compose.yml | 4 |
| Task 5 | 创建环境变量配置文件 | 3 |
| Task 6 | 验证镜像构建 | 3 |
| Task 7 | 测试容器间通信 | 3 |

---

## Task 1: 创建项目 .dockerignore 文件

**Files:**
- Create: `/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/.dockerignore`

**Step 1: 创建 .dockerignore**

```gitignore
# Git
.git
.gitignore

# Python
__pycache__
*.pyc
*.pyo
*.pyd
.Python
venv/
.venv/
*.egg-info/
dist/
build/

# Node.js
node_modules/
npm-debug.log
yarn-error.log

# IDE
.vscode/
.idea/
*.swp
*.swo

# Docker
Dockerfile
docker-compose*.yml

# Documentation
docs/plans/
*.md

# OS
.DS_Store
Thumbs.db

# Project specific
temp_workspace/
data/
*.log
```

**Step 2: 验证文件创建**

Run: `cat /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/.dockerignore`
Expected: 显示上述内容

**Step 3: Commit**

```bash
git add .dockerignore
git commit -m "feat: add .dockerignore for container builds"
```

---

## Task 2: 创建主容器 Dockerfile

**Files:**
- Create: `/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/docker/main.Dockerfile`

**Step 1: 创建 backend 依赖文件**

**Files:**
- Create: `/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/docker/requirements.txt`

```text
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.5.0
pyyaml>=6.0
requests>=2.31.0
sse-starlette>=2.0.0
python-multipart>=0.0.6
docker>=6.1.0
```

**Step 2: 创建主容器 Dockerfile**

**Files:**
- Create: `/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/docker/main.Dockerfile`

```dockerfile
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
```

**Step 3: 验证文件创建**

Run: `cat /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/docker/main.Dockerfile | head -30`
Expected: 显示 Dockerfile 前 30 行

**Step 4: 创建 .dockerignore 子目录配置**

**Files:**
- Create: `/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/docker/main.dockerignore`

```gitignore
# Ignore everything
*

# But not these
!backend/
!frontend/
!.claude/
!config.yaml
!local.yaml.example
!start.sh
```

**Step 5: Commit**

```bash
git add docker/main.Dockerfile docker/main.dockerignore docker/requirements.txt
git commit -m "feat: add main container Dockerfile"
```

---

## Task 3: 创建沙盒容器 Dockerfile

**Files:**
- Create: `/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/docker/sandbox.Dockerfile`

**Step 1: 创建沙盒 Dockerfile**

```dockerfile
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

# Create workspace directory
RUN mkdir -p /workspace

# Expose API port (for sandbox API server)
EXPOSE 9002

# Entry point
ENTRYPOINT ["/entrypoint.sh"]
```

**Step 2: 创建沙盒入口脚本**

**Files:**
- Create: `/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/docker/sandbox-entrypoint.sh`

```bash
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
```

**Step 3: 创建沙盒 API 模块**

**Files:**
- Create: `/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/sandbox/api.py`

```python
"""
Sandbox API - Provides HTTP interface for Claude Code execution
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import subprocess
import json
import logging

app = FastAPI(title="MAS Sandbox API")
logger = logging.getLogger("sandbox")

class ClaudeRequest(BaseModel):
    message: str
    agent_type: str = "principal"
    model: Optional[str] = None
    session_id: Optional[str] = None
    skills: Optional[List[str]] = None

class ClaudeResponse(BaseModel):
    response: str
    agent_type: str
    session_id: Optional[str] = None

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "sandbox"}

@app.post("/execute", response_model=ClaudeResponse)
async def execute_claude(request: ClaudeRequest):
    """Execute Claude Code CLI with given prompt"""
    try:
        # Build command
        cmd = [
            "claude",
            "-p",
            "--print",
            "--dangerously-skip-permissions",
            "--output-format", "text",
            "--add-dir", "/app/.claude",
            "--model", request.model or "claude-sonnet-4-20250514",
        ]

        if request.session_id:
            cmd.extend(["--session-id", request.session_id])

        # Add system prompt with agent type
        system_prompt = f"""You are running in MAS Sandbox as {request.agent_type.upper()} agent.

Your role is defined in /app/.claude/agents/{request.agent_type}.md
Use skills from /app/.claude/skills/ when appropriate.

Respond now:"""

        cmd.extend(["--system-prompt", system_prompt])
        cmd.append(request.message)

        # Execute
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd="/workspace"
        )

        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=result.stderr)

        return ClaudeResponse(
            response=result.stdout,
            agent_type=request.agent_type,
            session_id=request.session_id
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Execution timeout")
    except Exception as e:
        logger.error(f"Sandbox execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def get_status():
    """Get sandbox status"""
    return {
        "status": "ready",
        "claude_version": subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True
        ).stdout.strip()
    }
```

**Step 4: 创建沙盒 .dockerignore**

**Files:**
- Create: `/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/docker/sandbox.dockerignore`

```gitignore
# Ignore everything
*

# But not these
!backend/src/services/
!.claude/
!config.yaml
!sandbox/
!docker/requirements.txt
```

**Step 5: Commit**

```bash
git add docker/sandbox.Dockerfile docker/sandbox-entrypoint.sh docker/sandbox.dockerignore sandbox/api.py
git commit -m "feat: add sandbox container Dockerfile and API"
```

---

## Task 4: 创建 docker-compose.yml

**Files:**
- Create: `/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/docker-compose.yml`

**Step 1: 创建 docker-compose.yml**

```yaml
version: '3.8'

services:
  # Main Container - Backend + Frontend
  main:
    build:
      context: .
      dockerfile: docker/main.Dockerfile
    container_name: mas-main
    ports:
      - "9000:9000"  # Backend API
      - "9001:9001"  # Frontend UI
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL:-}
      - SANDBOX_API_URL=http://sandbox:9002
      - CLAUDE_MODEL=${CLAUDE_MODEL:-claude-sonnet-4-20250514}
      - CLAUDE_TIMEOUT=${CLAUDE_TIMEOUT:-300}
    volumes:
      - ./temp_workspace:/app/temp_workspace
      - ./data:/app/data
    depends_on:
      sandbox:
        condition: service_healthy
    networks:
      - mas-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # Sandbox Container - Isolated Claude Code execution
  sandbox:
    build:
      context: .
      dockerfile: docker/sandbox.Dockerfile
    container_name: mas-sandbox
    ports:
      - "9002:9002"  # Sandbox API
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - WORKSPACE=/workspace
    volumes:
      - sandbox-workspace:/workspace
    networks:
      - mas-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9002/health"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  mas-network:
    driver: bridge

volumes:
  sandbox-workspace:
    driver: local
```

**Step 2: 创建 .env.example**

**Files:**
- Create: `/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/.env.example`

```bash
# Required
ANTHROPIC_API_KEY=your-api-key-here

# Optional - Defaults shown
ANTHROPIC_BASE_URL=
CLAUDE_MODEL=claude-sonnet-4-20250514
CLAUDE_TIMEOUT=300
```

**Step 3: 创建 Makefile 简化操作**

**Files:**
- Create: `/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/Makefile`

```makefile
.PHONY: build up down logs clean

# Build images
build:
	docker-compose build

# Start containers
up:
	docker-compose up -d

# Stop containers
down:
	docker-compose down

# View logs
logs:
	docker-compose logs -f

# View sandbox logs
logs-sandbox:
	docker-compose logs -f sandbox

# View main logs
logs-main:
	docker-compose logs -f main

# Clean up
clean:
	docker-compose down -v
	docker system prune -f

# Rebuild and start
rebuild: down build up

# Quick restart
restart: down up
```

**Step 4: Commit**

```bash
git add docker-compose.yml .env.example Makefile
git commit -m "feat: add docker-compose and deployment config"
```

---

## Task 5: 创建环境变量配置文件

**Files:**
- Create: `/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/docker/env.production`

**Step 1: 创建生产环境配置**

```yaml
# Local development override
project:
  name: "MAS"
  claude_dir: "/app/.claude"

workspace:
  temp_dir: "temp_workspace"

claude:
  cli_path: "/usr/local/bin/claude"
  model: "claude-sonnet-4-20250514"
  timeout: 300

# Sandbox configuration
sandbox:
  enabled: true
  api_url: "http://sandbox:9002"
  workspace: "/workspace"

# MCP configuration (optional)
mcp:
  enabled: true
  servers:
    - type: "tavily"
      name: "tavily"
```

**Step 2: 更新 backend/src/config.py 支持环境变量**

**Files:**
- Modify: `/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/backend/src/config.py`

需要添加以下配置项：
```python
class SandboxConfig:
    enabled: bool = True
    api_url: str = "http://sandbox:9002"
    workspace: str = "/workspace"
```

**Step 3: Commit**

```bash
git add docker/env.production
git commit -m "feat: add production environment config"
```

---

## Task 6: 验证镜像构建

**Step 1: 构建镜像**

Run: `docker-compose build`
Expected: 成功构建两个镜像，无错误

**Step 2: 检查镜像**

Run: `docker images | grep mas-`
Expected:
```
mas-main      latest    xxx    size
mas-sandbox   latest    xxx    size
```

**Step 3: Commit**

```bash
git commit -m "chore: verify docker images build successfully"
```

---

## Task 7: 测试容器间通信

**Step 1: 启动容器**

Run: `docker-compose up -d`
Expected: 两个容器启动成功

**Step 2: 检查健康状态**

Run: `docker-compose ps`
Expected: 两个容器状态为 healthy

**Step 3: 测试 API**

Run: `curl http://localhost:9000/health`
Expected: `{"status":"healthy"}`

Run: `curl http://localhost:9002/status`
Expected: `{"status":"ready","claude_version":"..."}`

---

## 部署使用指南

### 快速启动

```bash
# 1. 复制环境变量
cp .env.example .env
# 编辑 .env 添加 ANTHROPIC_API_KEY

# 2. 启动服务
make up

# 3. 访问
# Frontend: http://localhost:9001
# Backend API: http://localhost:9000
```

### 常用命令

```bash
# 查看日志
make logs

# 停止服务
make down

# 重新构建
make rebuild
```

---

## 计划完成

**Plan complete and saved to `docs/plans/2026-03-09-docker-isolation-implementation-plan.md`.**

Two execution options:

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
