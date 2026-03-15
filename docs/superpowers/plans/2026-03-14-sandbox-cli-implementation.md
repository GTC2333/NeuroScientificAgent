# Sandbox CLI Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Claude CLI 移到沙盒容器中执行，与 SDK 统一运行环境

**Architecture:** 采用主容器 WebSocket 转发到沙盒 WebSocket 的代理模式，通过共享 Volume 实现文件访问

**Tech Stack:** Python, FastAPI, Socket.IO, ptyprocess, Docker

---

## 文件结构

```
scientific_agent/
├── docker/
│   ├── sandbox.Dockerfile              # 修改：添加 CLI 安装
│   ├── sandbox-requirements.txt        # 修改：添加 socketio, ptyprocess
│   └── docker-compose.yml              # 修改：添加共享 Volume
├── sandbox/
│   └── api.py                          # 修改：添加 WebSocket 端点
└── backend/
    └── src/
        └── api/
            └── websocket.py             # 修改：添加代理模式
```

---

## Chunk 1: 修改沙盒依赖和 Dockerfile

### Task 1.1: 修改 sandbox-requirements.txt

**Files:**
- Modify: `scientific_agent/docker/sandbox-requirements.txt`

- [ ] **Step 1: 读取当前 sandbox-requirements.txt 内容**

```bash
cat scientific_agent/docker/sandbox-requirements.txt
```

- [ ] **Step 2: 添加 python-socketio 和 ptyprocess**

```bash
# 在文件末尾添加新依赖
cat >> scientific_agent/docker/sandbox-requirements.txt << 'EOF'
python-socketio>=5.0.0
ptyprocess>=0.7.0
EOF
```

- [ ] **Step 3: 验证文件内容**

```bash
cat scientific_agent/docker/sandbox-requirements.txt
```

预期输出应包含:
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

- [ ] **Step 4: Commit**

```bash
git add scientific_agent/docker/sandbox-requirements.txt
git commit -m "chore: add socketio and ptyprocess to sandbox deps"
```

---

### Task 1.2: 修改 sandbox.Dockerfile

**Files:**
- Modify: `scientific_agent/docker/sandbox.Dockerfile:1-49`

- [ ] **Step 1: 读取当前 sandbox.Dockerfile**

```bash
cat scientific_agent/docker/sandbox.Dockerfile
```

- [ ] **Step 2: 修改 apt-get 安装命令，添加 python3-ptyprocess**

```dockerfile
# 找到这一行:
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git ripgrp \
    && rm -rf /var/lib/apt/lists/*

# 修改为:
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git ripgrep python3-ptyprocess \
    && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 3: 在 apt-get 之后添加 Claude CLI 安装**

```dockerfile
# 在 apt-get 之后添加:
# Install Claude Code CLI
RUN curl -sSfL https://raw.githubusercontent.com/anthropics/claude-code/main/install.sh | sh
```

具体位置: 在 "Install system dependencies" 块之后，"Copy offline pip wheels" 之前

- [ ] **Step 4: 验证 Dockerfile 语法**

```bash
# 检查 Dockerfile 基本语法（不实际构建）
docker build --check -f scientific_agent/docker/sandbox.Dockerfile . 2>&1 || true
```

- [ ] **Step 5: Commit**

```bash
git add scientific_agent/docker/sandbox.Dockerfile
git commit -m "feat(sandbox): install Claude CLI and ptyprocess"
```

---

## Chunk 2: 修改 docker-compose.yml 添加共享 Volume

### Task 2.1: 添加共享 Volume 配置

**Files:**
- Modify: `scientific_agent/docker-compose.yml:1-46`

- [ ] **Step 1: 读取当前 docker-compose.yml**

```bash
cat scientific_agent/docker-compose.yml
```

- [ ] **Step 2: 在 main volumes 中添加 /shared_users 挂载**

找到 volumes 部分，添加:

```yaml
    volumes:
      - ./data:/app/data
      - /var/run/docker.sock:/var/run/docker.sock
      - ${USERS_DIR:-/root/claudeagent/users}:/root/claudeagent/users
      # 新增：共享用户目录给沙盒
      - ${USERS_DIR:-/root/claudeagent/users}:/shared_users:ro
      - ${OFFLINE_DEPS_PATH:-/opt/offline-deps}:/opt/offline-deps:ro
```

- [ ] **Step 3: 验证 YAML 语法**

```bash
python3 -c "import yaml; yaml.safe_load(open('scientific_agent/docker-compose.yml'))"
```

- [ ] **Step 4: Commit**

```bash
git add scientific_agent/docker-compose.yml
git commit -m "feat(docker): add shared volume for sandbox CLI"
```

---

## Chunk 3: 在沙盒 API 中添加 WebSocket 端点

### Task 3.1: 添加 WebSocket Shell 端点到 sandbox/api.py

**Files:**
- Modify: `scientific_agent/sandbox/api.py:1-247`
- Create: `scientific_agent/sandbox/shell_ws.py` (可选，如果代码量大可以拆分)

- [ ] **Step 1: 读取当前 sandbox/api.py**

```bash
cat scientific_agent/sandbox/api.py
```

- [ ] **Step 2: 在文件开头添加 socketio 导入**

在 `import asyncio` 之后添加:

```python
import socketio
import subprocess
import select
import pty
import fcntl
import termios
import struct
```

- [ ] **Step 3: 修改 app 创建方式，使用 socketio**

找到:
```python
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from sandbox.agentic_loop import AgenticLoop

app = FastAPI(title="MAS Sandbox API")
```

修改为:
```python
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import socketio

from sandbox.agentic_loop import AgenticLoop

# 创建 Socket.IO 应用
sio = socketio.AsyncServer(async_mode='asyncio')
app = FastAPI(title="MAS Sandbox API")
app.mount("/", socketio.ASGIApp(sio))
```

- [ ] **Step 4: 在文件末尾添加 ShellConnection 类和 WebSocket 处理**

```python
# ============== Shell WebSocket Handler ==============

WORKSPACE_DIR = os.environ.get("WORKSPACE", "/workspace")
SHARED_USERS_DIR = os.environ.get("SHARED_USERS", "/shared_users")


class ShellConnection:
    """Manage a single shell/PTY connection in sandbox"""

    def __init__(self, sid: str):
        self.sid = sid
        self.master_fd = None
        self.process = None
        self.task = None

    async def handle_init(self, data: dict):
        """Initialize shell process"""
        project_path = data.get("projectPath", "/workspace")
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
            project_path="/workspace",
            session_id=session_id,
            initial_command=initial_command,
            is_plain_shell=is_plain_shell
        )

        # 启动 PTY
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

        # 如果 /workspace 有内容，先备份或清空
        if os.path.exists('/workspace') and os.listdir('/workspace'):
            # 简单处理：假设用户接受覆盖
            import shutil
            backup_dir = f'/workspace.backup'
            if not os.path.exists(backup_dir):
                shutil.move('/workspace', backup_dir)

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

        elif provider == "cursor":
            if session_id:
                return f'cd "{project_path}" && cursor-agent --resume="{session_id}"'
            return f'cd "{project_path}" && cursor-agent'

        elif provider == "codex":
            if session_id:
                return f'cd "{project_path}" && codex resume "{session_id}" || codex'
            return f'cd "{project_path}" && codex'

        elif provider == "gemini":
            if session_id:
                return f'cd "{project_path}" && gemini --resume="{session_id}"'
            return f'cd "{project_path}" && gemini'

        # Default
        if initial_command:
            return f'cd "{project_path}" && {initial_command}'
        return f'cd "{project_path}" && $SHELL'

    async def _read_output(self):
        """Read PTY output and emit to client"""
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
                winsize = struct.pack('HHHH', rows, cols, 0, 0)
                fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
            except Exception as e:
                logger.error(f"[sandbox-shell] Error resizing: {e}")

    async def cleanup(self):
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


# 存储活跃的 shell 连接
shell_connections: Dict[str, ShellConnection] = {}


@sio.event
async def connect(sid, environ):
    """客户端连接"""
    logger.info(f"[sandbox-shell] Client connected: {sid}")


@sio.event
async def disconnect(sid):
    """客户端断开"""
    logger.info(f"[sandbox-shell] Client disconnected: {sid}")
    if sid in shell_connections:
        await shell_connections[sid].cleanup()
        del shell_connections[sid]


@sio.event
async def init(sid, data):
    """处理 init 消息"""
    shell_conn = ShellConnection(sid)
    shell_connections[sid] = shell_conn
    await shell_conn.handle_init(data)


@sio.event
async def input(sid, data):
    """处理 input 消息"""
    if sid in shell_connections:
        await shell_connections[sid].handle_input(data)


@sio.event
async def resize(sid, data):
    """处理 resize 消息"""
    if sid in shell_connections:
        await shell_connections[sid].handle_resize(data)


@sio.event
async def disconnect_shell(sid):
    """处理断开"""
    if sid in shell_connections:
        await shell_connections[sid].cleanup()
        del shell_connections[sid]
```

注意：需要添加 `from typing import Dict` 到导入列表

- [ ] **Step 5: 验证语法**

```bash
python3 -m py_compile scientific_agent/sandbox/api.py
```

- [ ] **Step 6: Commit**

```bash
git add scientific_agent/sandbox/api.py
git commit -m "feat(sandbox): add WebSocket shell endpoint"
```

---

## Chunk 4: 修改主容器 WebSocket 支持代理模式

### Task 4.1: 修改 websocket.py ShellConnection 支持代理模式

**Files:**
- Modify: `scientific_agent/backend/src/api/websocket.py:606-866`

- [ ] **Step 1: 读取 websocket.py 中的 ShellConnection 类**

```bash
sed -n '606,866p' scientific_agent/backend/src/api/websocket.py
```

- [ ] **Step 2: 修改 ShellConnection.__init__ 添加 sandbox_proxy_url 参数**

```python
class ShellConnection:
    """Manage a single shell/PTY connection"""

    def __init__(self, websocket: WebSocket, user_id: str, sandbox_api_url: str = None):
        self.websocket = websocket
        self.user_id = user_id
        self.sandbox_api_url = sandbox_api_url  # 新增
        self.sio_client = None  # 新增
        self.master_fd = None
        self.process = None
        self.task = None
```

- [ ] **Step 3: 修改 handle() 方法支持代理模式**

找到 handle() 方法，修改为:

```python
async def handle(self):
    """Handle shell WebSocket connection"""
    try:
        await self.websocket.accept()
        logger.info(f"[shell] User {self.user_id} connected")

        if self.sandbox_api_url:
            # 代理模式：连接到沙盒
            await self._handle_proxy_mode()
        else:
            # 本地模式（开发用）
            await self._handle_local_mode()

    except WebSocketDisconnect:
        logger.info(f"[shell] User {self.user_id} disconnected")
    except Exception as e:
        logger.error(f"[shell] Error: {e}", exc_info=True)
    finally:
        await self._cleanup_proxy()
```

- [ ] **Step 4: 添加代理模式处理方法**

在 ShellConnection 类中添加:

```python
async def _handle_proxy_mode(self):
    """代理模式：转发到沙盒"""
    import socketio

    self.sio_client = socketio.AsyncClient()

    try:
        # 连接到沙盒 WebSocket
        ws_url = self.sandbox_api_url.replace('http://', '').replace('https://', '')
        await self.sio_client.connect(f"http://{ws_url}/socket.io")

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

async def _cleanup_proxy(self):
    """清理代理连接"""
    if self.sio_client:
        try:
            await self.sio_client.disconnect()
        except:
            pass
        self.sio_client = None
```

- [ ] **Step 5: 重命名原来的 handle() 为 _handle_local_mode()**

将原来的 handle() 方法内容移到 _handle_local_mode() 方法中

- [ ] **Step 6: 修改 shell_websocket_endpoint 获取沙盒 URL 并传递**

找到 shell_websocket_endpoint 函数:

```python
@router.websocket("/shell")
async def shell_websocket_endpoint(websocket: WebSocket, token: str = Query(default="")):
    # ... 认证代码 ...

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
        # 使用本地模式
        shell_conn = ShellConnection(websocket, user_id, None)

    await shell_conn.handle()
```

- [ ] **Step 7: 验证语法**

```bash
python3 -m py_compile scientific_agent/backend/src/api/websocket.py
```

- [ ] **Step 8: Commit**

```bash
git add scientific_agent/backend/src/api/websocket.py
git commit -m "feat(backend): add shell proxy mode to sandbox"
```

---

## Chunk 5: 测试与集成验证

### Task 5.1: 构建镜像测试

**Files:**
- Test: 构建并验证镜像

- [ ] **Step 1: 构建 sandbox 镜像**

```bash
cd scientific_agent/docker
docker build -f sandbox.Dockerfile -t mas-sandbox:test ../.. 2>&1 | tail -20
```

预期: 构建成功，无错误

- [ ] **Step 2: 运行容器测试 CLI 可用性**

```bash
docker run --rm mas-sandbox:test which claude
```

预期输出: `/root/.local/bin/claude` 或类似路径

- [ ] **Step 3: 测试 CLI 版本**

```bash
docker run --rm mas-sandbox:test claude --version
```

预期: 显示版本号

- [ ] **Step 4: Commit 构建相关**

```bash
git tag -a sandbox-cli-v1 -m "sandbox image with CLI support"
```

---

### Task 5.2: 集成测试

- [ ] **Step 1: 使用 docker-compose 启动服务**

```bash
cd scientific_agent
docker-compose up -d --build
```

- [ ] **Step 2: 检查容器状态**

```bash
docker-compose ps
docker logs mas-main 2>&1 | tail -30
```

- [ ] **Step 3: 检查健康检查**

```bash
curl http://localhost:9001/health
```

- [ ] **Step 4: 测试终端 WebSocket 连接**

```bash
# 需要先登录获取 token，然后连接 WebSocket
# 可以使用 websocat 或类似工具测试
```

- [ ] **Step 5: Commit 集成测试结果**

---

## 依赖检查

确保以下命令可用:
- docker
- docker-compose
- python3
- git

---

## 回滚计划

如果出现问题:
1. 回退 websocket.py 中的 ShellConnection 到本地模式
2. 暂时禁用沙盒 CLI 功能
3. 保留 SDK 功能正常
4. 使用 git revert 回退更改

---

> **Plan complete and saved to `docs/superpowers/plans/2026-03-14-sandbox-cli-implementation.md`. Ready to execute?**
