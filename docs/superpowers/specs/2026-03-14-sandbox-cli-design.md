# SPEC: 沙盒容器集成 Claude CLI

> 日期: 2026-03-14
> 状态: Approved
> 目标: 将 Claude CLI 移到沙盒容器中执行，与 SDK 统一运行环境

---

## 1. 背景

当前架构中：
- **对话页面**: 使用 SDK，在沙盒容器中执行
- **终端页面**: 使用 CLI，在主容器中执行

目标：将 CLI 也移到沙盒容器中，实现统一的隔离执行环境。

---

## 2. 架构设计

### 2.1 最终架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           主容器 (Main Container)                        │
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────────┐  │
│  │   Frontend │  │   Backend   │  │     Shell WebSocket Handler    │  │
│  │   (React)  │  │  (FastAPI)  │  │   (ShellConnection 代理模式)   │  │
│  │   :9001    │  │   :9000     │  │        /shell 端点             │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────────────┘  │
│         │                │                     │                     │
│         │        ┌──────┴──────┐               │ httpx 转发         │
│         │        │   WebSocket │◄──────────────┘                     │
│         │        │   Router    │                                     │
│         │        └──────┬──────┘                                     │
│         │               │                                            │
│         │        ┌──────┴──────┐   ┌──────────────────────────┐    │
│         │        │  httpx / SSE │──►│  沙盒容器 API (SDK)      │    │
│         │        └──────────────┘   │  /execute/stream         │    │
│         │                          └──────────────────────────┘    │
│         │                                                              │
│         │        ┌──────────────────────────────────────────────┐    │
│         └────────►  Docker Manager (docker-py)                   │    │
│                  │  • 创建/删除沙盒容器                           │    │
│                  │  • 端口分配                                    │    │
│                  │  • 健康检查                                     │    │
│                  └──────────────────────────────────────────────┘    │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Volumes                                                           │ │
│  │  • /root/claudeagent/users ──共享──► /shared_users (ro)           │ │
│  │  • /var/run/docker.sock                                           │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ Docker Network + Volume
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         沙盒容器 (Sandbox Container)                    │
│                                                                          │
│  ┌─────────────────────────┐  ┌─────────────────────────────────────┐  │
│  │     Sandbox API          │  │     Shell WebSocket Endpoint        │  │
│  │  • /execute (SDK)       │  │  • /ws/shell                       │  │
│  │  • /execute/stream      │  │  • ShellConnection                  │  │
│  │  • /workspace/files     │  │  • PTY + CLI                       │  │
│  └─────────────────────────┘  └─────────────────────────────────────┘  │
│                                    │                                     │
│                                    ▼                                     │
│                          ┌────────────────────────┐                     │
│                          │   Claude CLI           │                     │
│                          │  • claude             │                     │
│                          │  • --resume session   │                     │
│                          │  • 工作目录: /workspace│                     │
│                          └────────────────────────┘                     │
│                                                                          │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │  Volumes                                                           │ │
│  │  • /shared_users ──映射──► /workspace (符号链接)                  │ │
│  │    user_123/workspace_A/ ──► /workspace                          │ │
│  │                                                                      │ │
│  │  • mas-workspace-{id} (Docker volume) - SDK 临时文件              │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流

```
前端 WebSocket (init)
        │
        ▼
主容器 /shell 端点
        │
        ▼
ShellConnection.handle_init()
        │
        ├─ 检查 sandbox_api_url
        │
        ▼
httpx.WebSocket连接 ──────────────► 沙盒 /ws/shell
   │                                           │
   │  init/input/resize/disconnect              │
   │                                           ▼
   │                                    ShellConnection.handle_init()
   │                                           │
   │                                           ▼
   │                                    subprocess.Popen('claude')
   │                                           │  PTY
   │                                           ▼
   ◄─────────────────────────────────── output (转发)
        │
        ▼
主容器 WebSocket.send_json() ──► 前端
```

---

## 3. 技术方案

### 3.1 共享 Volume 配置

```yaml
# docker-compose.yml

services:
  main:
    volumes:
      - ${USERS_DIR:-/root/claudeagent/users}:/root/claudeagent/users
      - ${USERS_DIR:-/root/claudeagent/users}:/shared_users:ro   # 新增

  sandbox:
    volumes:
      - ${USERS_DIR:-/root/claudeagent/users}:/shared_users:ro   # 新增
      - sandbox-workspace:/workspace                              # 沙盒工作目录
```

### 3.2 路径映射规则

```
/shared_users/{user_id}/{workspace_name}/  →  /workspace/

示例:
/shared_users/user_123/workspace_A/         →  /workspace/
  ├── src/
  ├── .claude/
  │   └── sessions/                         ← CLI session 状态
  └── package.json
```

### 3.3 沙盒启动时的符号链接

```python
# sandbox/api.py - ShellConnection 初始化时

async def init_shell(workspace_name: str, user_id: str):
    """初始化 shell 工作目录"""

    # 创建符号链接：/workspace -> /shared_users/{user_id}/{workspace}
    user_workspace = f"/shared_users/{user_id}/{workspace_name}"

    if not os.path.exists('/workspace'):
        os.makedirs('/workspace')

    # 如果 /workspace 不是符号链接，则创建
    if not os.path.islink('/workspace'):
        if os.path.exists('/workspace') and os.listdir('/workspace'):
            # /workspace 有内容，备份或合并（暂不处理）
            pass
        else:
            # 创建符号链接
            if os.path.islink('/workspace'):
                os.unlink('/workspace')
            os.symlink(user_workspace, '/workspace')

    return '/workspace'
```

### 3.4 消息协议（保持不变）

| 消息类型 | 方向 | 格式 |
|---------|------|------|
| init | 前端 → 主容器 → 沙盒 | `{"type": "init", "projectPath": "", "provider": "claude", "sessionId": "", "cols": 80, "rows": 24}` |
| input | 前端 → 主容器 → 沙盒 | `{"type": "input", "data": "..."}` |
| resize | 前端 → 主容器 → 沙盒 | `{"type": "resize", "cols": 80, "rows": 24}` |
| disconnect | 前端 → 主容器 → 沙盒 | `{"type": "disconnect"}` |
| output | 沙盒 → 主容器 → 前端 | `{"type": "output", "data": "..."}` |
| error | 沙盒 → 主容器 → 前端 | `{"type": "error", "error": "..."}` |

---

## 4. 文件修改清单

### 4.1 docker/sandbox.Dockerfile

```dockerfile
# ===========================================
# Sandbox Container Dockerfile
# ===========================================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    WORKSPACE=/workspace

WORKDIR /app

# 安装系统依赖（包括 Claude CLI）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git ripgrep python3-ptyprocess \
    && rm -rf /var/lib/apt/lists/*

# 安装 Claude Code CLI
RUN curl -sSfL https://raw.githubusercontent.com/anthropics/claude-code/main/install.sh | sh

# 复制离线 pip wheels (if available)
COPY docker/offline-deps/pip-wheels/sandbox/ /tmp/pip-wheels/

# 安装 Python 依赖（offline-first）
COPY docker/sandbox-requirements.txt .
RUN if [ -d /tmp/pip-wheels ] && ls /tmp/pip-wheels/*.whl 1>/dev/null 2>&1; then \
        pip install --no-cache-dir --no-index --find-links /tmp/pip-wheels -r sandbox-requirements.txt; \
    else \
        pip install --no-cache-dir -r sandbox-requirements.txt; \
    fi && \
    rm -rf /tmp/pip-wheels

# 复制沙盒代码和 claude 配置
COPY sandbox/ ./sandbox/
COPY claude/ ./claude/

# 创建 workspace 目录
RUN mkdir -p /workspace

# 创建共享目录挂载点
RUN mkdir -p /shared_users

# 暴露端口
EXPOSE 9002

# 启动沙盒 API (HTTP + WebSocket)
CMD ["python", "-m", "uvicorn", "sandbox.api:app", "--host", "0.0.0.0", "--port", "9002"]
```

### 4.2 docker/sandbox-requirements.txt

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.5.0
pyyaml>=6.0
anthropic>=0.25.0
sse-starlette>=2.0.0
python-socketio>=5.0.0
ptyprocess>=0.7.0
```

### 4.3 sandbox/api.py (新增部分)

```python
"""
Sandbox API - HTTP interface for sandbox containers.
扩展支持 WebSocket Shell 端点
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import socketio

from sandbox.agentic_loop import AgenticLoop

# ============== WebSocket Server ==============

# 创建 Socket.IO 服务器
sio = AsyncServer(async_mode='asyncio')
app = FastAPI(socketio_path="/ws/socket.io")

# 挂载 Socket.IO
sio = socketio.AsyncServer(async_mode='asyncio')
app.mount("/", socketio.ASGIApp(sio))

logger = logging.getLogger("Sandbox.WS")

WORKSPACE_DIR = os.environ.get("WORKSPACE", "/workspace")
SHARED_USERS_DIR = os.environ.get("SHARED_USERS", "/shared_users")


class ShellConnection:
    """Manage a single shell/PTY connection in sandbox"""

    def __init__(self, sid: str, workspace: str):
        self.sid = sid
        self.workspace = workspace
        self.master_fd = None
        self.process = None
        self.task = None

    async def handle_init(self, data: dict):
        """Initialize shell process"""
        project_path = data.get("projectPath", "")
        session_id = data.get("sessionId")
        provider = data.get("provider", "plain-shell")
        cols = data.get("cols", 80)
        rows = data.get("rows", 24)
        initial_command = data.get("initialCommand")
        is_plain_shell = data.get("isPlainShell", False)

        logger.info(f"[sandbox-shell] Init: project={project_path}, provider={provider}")

        # 建立符号链接
        await self._setup_workspace(project_path)

        # 构建 shell 命令
        shell_command = self._build_command(
            provider=provider,
            project_path="/workspace",  # 使用符号链接后的路径
            session_id=session_id,
            initial_command=initial_command,
            is_plain_shell=is_plain_shell
        )

        # 启动 PTY
        import pty
        import fcntl
        import termios
        import struct

        self.master_fd, slave_fd = pty.openpty()

        # 设置终端大小
        winsize = struct.pack('HHHH', rows, cols, 0, 0)
        fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

        # 启动进程
        self.process = subprocess.Popen(
            shell_command,
            shell=True,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd="/workspace",
            start_new_session=True,
            env={**os.environ, "TERM": "xterm-256color"}
        )

        os.close(slave_fd)

        # 启动输出读取任务
        self.task = asyncio.create_task(self._read_output())

        logger.info(f"[sandbox-shell] Shell started with PID: {self.process.pid}")

    async def _setup_workspace(self, project_path: str):
        """建立工作目录符号链接"""
        # project_path 格式: /shared_users/user_123/workspace_A

        if os.path.islink('/workspace'):
            os.unlink('/workspace')

        # 创建符号链接
        os.symlink(project_path, '/workspace')
        logger.info(f"[sandbox-shell] Linked /workspace -> {project_path}")

    def _build_command(self, provider: str, project_path: str, session_id: Optional[str],
                      initial_command: Optional[str], is_plain_shell: bool) -> str:
        """Build shell command"""
        if is_plain_shell:
            if initial_command:
                return f'cd "{project_path}" && {initial_command}'
            return f'cd "{project_path}" && $SHELL'

        if provider == "claude" or provider == "anthropic":
            if session_id:
                return f'cd "{project_path}" && claude --resume {session_id} || claude'
            return f'cd "{project_path}" && claude'

        # ... 其他 provider

        return f'cd "{project_path}" && $SHELL'

    async def _read_output(self):
        """Read PTY output and emit to client"""
        import select
        try:
            while True:
                if self.master_fd is None:
                    break

                ready, _, _ = select.select([self.master_fd], [], [], 0.1)

                if ready:
                    try:
                        data = os.read(self.master_fd, 4096)
                        if data:
                            await sio.emit('output', {
                                "type": "output",
                                "data": data.decode("utf-8", errors="replace")
                            }, room=self.sid)
                    except OSError:
                        break

                if self.process and self.process.poll() is not None:
                    exit_code = self.process.returncode
                    await sio.emit('output', {
                        "type": "output",
                        "data": f"\r\nProcess exited with code {exit_code}\r\n"
                    }, room=self.sid)
                    break

                await asyncio.sleep(0.01)

        except Exception as e:
            logger.error(f"[sandbox-shell] Error reading output: {e}")
        finally:
            await self._cleanup()

    async def handle_input(self, data: dict):
        """Forward input to PTY"""
        input_data = data.get("data", "")
        if self.master_fd and input_data:
            try:
                os.write(self.master_fd, input_data.encode("utf-8"))
            except OSError as e:
                logger.error(f"[sandbox-shell] Error writing input: {e}")

    async def handle_resize(self, data: dict):
        """Handle terminal resize"""
        if self.master_fd:
            cols = data.get("cols", 80)
            rows = data.get("rows", 24)
            try:
                import fcntl
                import termios
                import struct
                winsize = struct.pack('HHHH', rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
            except Exception as e:
                logger.error(f"[sandbox-shell] Error resizing: {e}")

    async def _cleanup(self):
        """Clean up resources"""
        if self.master_fd:
            try:
                os.close(self.master_fd)
            except:
                pass
            self.master_fd = None

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=2)
            except:
                try:
                    self.process.kill()
                except:
                    pass
            self.process = None


# ============== Socket.IO 事件处理 ==============

@sio.event
async def connect(sid, environ):
    """客户端连接"""
    logger.info(f"[sandbox-shell] Client connected: {sid}")
    # 可在此验证 API key
    # api_key = environ.get('HTTP_X_SANDBOX_API_KEY')


@sio.event
async def disconnect(sid):
    """客户端断开"""
    logger.info(f"[sandbox-shell] Client disconnected: {sid}")


@sio.event
async def init(sid, data):
    """处理 init 消息"""
    shell_conn = ShellConnection(sid, data.get("projectPath", "/workspace"))
    # 存储连接（可以用字典）
    await shell_conn.handle_init(data)


@sio.event
async def input(sid, data):
    """处理 input 消息"""
    # 从字典中获取 ShellConnection
    await shell_conn.handle_input(data)


@sio.event
async def resize(sid, data):
    """处理 resize 消息"""
    await shell_conn.handle_resize(data)


@sio.event
async def disconnect_shell(sid):
    """处理断开"""
    await shell_conn._cleanup()
```

### 4.4 backend/src/api/websocket.py (修改部分)

```python
class ShellConnection:
    """Manage a single shell/PTY connection - 支持代理模式"""

    def __init__(self, websocket: WebSocket, user_id: str, sandbox_api_url: str = None):
        self.websocket = websocket
        self.user_id = user_id
        self.sandbox_api_url = sandbox_api_url  # 新增：沙盒 API URL
        self.sio_client = None  # 新增：Socket.IO 客户端
        self.master_fd = None
        self.process = None
        self.task = None

    async def handle(self):
        """Handle shell WebSocket connection"""
        try:
            await self.websocket.accept()
            logger.info(f"[shell] User {self.user_id} connected")

            if self.sandbox_api_url:
                # ===== 代理模式：连接到沙盒 =====
                await self._handle_proxy_mode()
            else:
                # ===== 本地模式（开发用）=====
                await self._handle_local_mode()

        except WebSocketDisconnect:
            logger.info(f"[shell] User {self.user_id} disconnected")
        except Exception as e:
            logger.error(f"[shell] Error: {e}", exc_info=True)
        finally:
            await self._cleanup_proxy()

    async def _handle_proxy_mode(self):
        """代理模式：转发到沙盒"""
        import socketio

        self.sio_client = socketio.AsyncClient()

        try:
            # 连接到沙盒 WebSocket
            ws_url = self.sandbox_api_url.replace('http://', '').replace('https://', '')
            await self.sio_client.connect(f"http://{ws_url}/ws/socket.io")

            logger.info(f"[shell] Connected to sandbox: {self.sandbox_api_url}")

            # 创建转发任务
            receive_task = asyncio.create_task(self._proxy_receive())
            init_sent = False

            while True:
                data = await self.websocket.receive_text()
                try:
                    message = json.loads(data)
                except json.JSONDecodeError:
                    continue

                msg_type = message.get("type", "")

                if msg_type == "init":
                    # 第一次：转发到沙盒
                    await self.sio_client.emit('init', message)
                    init_sent = True
                elif msg_type == "input":
                    if init_sent:
                        await self.sio_client.emit('input', message)
                elif msg_type == "resize":
                    if init_sent:
                        await self.sio_client.emit('resize', message)
                elif msg_type == "disconnect":
                    if init_sent:
                        await self.sio_client.emit('disconnect_shell')
                    break

            receive_task.cancel()

        except Exception as e:
            logger.error(f"[shell] Proxy error: {e}")
            await self.websocket.send_json({
                "type": "error",
                "error": f"Proxy error: {str(e)}"
            })
        finally:
            await self._cleanup_proxy()

    async def _proxy_receive(self):
        """接收沙盒返回并转发到前端"""
        @self.sio_client.on('output')
        async def on_output(data):
            await self.websocket.send_json(data)

        @self.sio_client.on('error')
        async def on_error(data):
            await self.websocket.send_json({
                "type": "error",
                "error": data.get('error', 'Unknown error')
            })

        # 保持连接
        await asyncio.sleep(3600)


# 修改 shell_websocket_endpoint
@router.websocket("/shell")
async def shell_websocket_endpoint(websocket: WebSocket, token: str = Query(default="")):
    """Shell WebSocket endpoint - 支持代理模式"""
    # 认证
    user = authenticate_ws_token(token)
    if not user:
        await websocket.accept()
        await websocket.send_json({"type": "error", "error": "Unauthorized"})
        await websocket.close(code=4001, reason="Unauthorized")
        return

    user_id = user["id"]

    # 检查用户是否有沙盒
    sandboxes = load_sandboxes()
    user_sandbox = None
    for sandbox_id, sandbox in sandboxes.items():
        if sandbox.get("user_id") == user_id and sandbox.get("status") == "running":
            user_sandbox = sandbox
            break

    if user_sandbox:
        # 使用代理模式
        sandbox_api_url = user_sandbox.get("api_url")
        shell_conn = ShellConnection(websocket, user_id, sandbox_api_url)
    else:
        # 使用本地模式（开发用）
        shell_conn = ShellConnection(websocket, user_id, sandbox_api_url=None)

    await shell_conn.handle()
```

### 4.5 docker-compose.yml (修改部分)

```yaml
services:
  main:
    image: ${MAIN_IMAGE:-mas-main:latest}
    container_name: mas-main
    ports:
      - "${FRONTEND_PORT:-9001}:80"
    environment:
      # ... 现有环境变量
    volumes:
      - ./data:/app/data
      - /var/run/docker.sock:/var/run/docker.sock
      - ${USERS_DIR:-/root/claudeagent/users}:/root/claudeagent/users
      # 新增：共享用户目录给沙盒
      - ${USERS_DIR:-/root/claudeagent/users}:/shared_users:ro
      # 新增：离线依赖
      - ${OFFLINE_DEPS_PATH:-/opt/offline-deps}:/opt/offline-deps:ro
    networks:
      - mas-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:80/health"]
      interval: 30s
      timeout: 10s
      start_period: 10s
      retries: 3

networks:
  mas-network:
    name: mas-network
    driver: bridge
```

---

## 5. 认证与安全

### 5.1 认证流程

```
前端 WebSocket 握手
        │
        ▼
主容器 /shell?token=JWT
        │
        ▼
验证 JWT → 获取 user_id
        │
        ▼
查询 sandboxes.json → 获取 user 的沙盒 api_url
        │
        ▼
如果沙盒存在:
  • 携带 API key 连接到沙盒 WebSocket
  • 或在 init 消息中传递
如果沙盒不存在:
  • 回退到本地模式（开发用）
```

### 5.2 API Key 传递

```python
# 主容器 -> 沙盒

# 方案 1: 通过 init 消息
await sio_client.emit('init', {
    "type": "init",
    "projectPath": "/shared_users/user_123/workspace_A",
    "provider": "claude",
    "api_key": sandbox_api_key,  # 新增
    ...
})

# 方案 2: 通过 WebSocket 连接参数
await sio_client.connect(
    f"http://{ws_url}/ws/socket.io",
    headers={"X-Sandbox-API-Key": sandbox_api_key}
)
```

---

## 6. 错误处理

### 6.1 沙盒不可用

| 错误场景 | 处理方式 |
|---------|---------|
| 沙盒未运行 | 回退到本地模式，提示用户 |
| 沙盒 WebSocket 连接失败 | 返回错误给前端，提示重试 |
| 沙盒进程启动失败 | 发送 error 消息给前端 |

### 6.2 路径问题

| 错误场景 | 处理方式 |
|---------|---------|
| /shared_users/{user_id}/{workspace} 不存在 | 返回错误 "项目不存在" |
| 符号链接创建失败 | 返回错误，提示检查权限 |

---

## 7. 测试计划

### 7.1 单元测试

| 测试项 | 验证内容 |
|--------|---------|
| ShellConnection._build_command() | 生成的命令格式正确 |
| 路径映射逻辑 | /shared_users → /workspace 正确 |
| 消息转发 | init/input/resize 正确转发 |

### 7.2 集成测试

| 测试项 | 验证内容 |
|--------|---------|
| 主容器 → 沙盒 WebSocket 连接 | 连接建立成功 |
| 终端输入输出 | input → 沙盒 → output 完整流程 |
| CLI 会话恢复 | --resume session_id 生效 |
| 文件同步 | 主容器创建文件，沙盒可见 |

---

## 8. 回滚计划

如果出现问题：
1. 回退 websocket.py 中的 ShellConnection 到本地模式
2. 暂时禁用沙盒 CLI 功能
3. 保留 SDK 功能正常

---

## 9. 依赖项汇总

| 依赖 | 版本 | 用途 |
|------|------|------|
| python-socketio | >=5.0.0 | WebSocket 通信 |
| ptyprocess | >=0.7.0 | PTY 管理 |
| Claude CLI | latest | 代码执行 |

---

## 10. 相关文件列表

| 文件 | 状态 | 说明 |
|------|------|------|
| docker/sandbox.Dockerfile | 修改 | 添加 CLI 安装 |
| docker/sandbox-requirements.txt | 修改 | 添加 socketio, ptyprocess |
| sandbox/api.py | 修改 | 添加 WebSocket 端点 |
| backend/src/api/websocket.py | 修改 | 添加代理模式 |
| docker-compose.yml | 修改 | 添加共享 Volume |

---

## 11. 实施顺序

1. **Phase 1**: 修改 sandbox.Dockerfile + requirements.txt
2. **Phase 2**: 实现 sandbox/api.py WebSocket 端点
3. **Phase 3**: 修改 docker-compose.yml 添加 Volume
4. **Phase 4**: 修改 websocket.py 代理模式
5. **Phase 5**: 测试与调试

---

> **批准**: 用户已批准此设计
> **日期**: 2026-03-14
