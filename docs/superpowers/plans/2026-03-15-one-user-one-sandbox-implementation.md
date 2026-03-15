# 1用户1沙盒 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现每个用户一个沙盒容器的架构，支持 SDK(对话) 和 CLI(终端)

**Architecture:** 双容器架构 - 主容器(Frontend+Backend) + 用户沙盒容器(SDK+CLI)，首次登录时自动创建沙盒

**Tech Stack:** Python, FastAPI, Socket.IO, Docker, WebSocket

---

## 文件结构

```
scientific_agent/
├── backend/
│   └── src/
│       ├── api/
│       │   ├── sandboxes.py      # 修改: 适配1用户1沙盒
│       │   ├── auth.py           # 修改: 登录时自动创建沙盒
│       │   └── websocket.py      # 修改: Shell转发到沙盒
│       └── services/
│           └── sandbox_service.py  # 修改: 创建以用户命名的沙盒
├── sandbox/
│   └── api.py                    # 修改: 添加WebSocket Shell
├── docker/
│   ├── sandbox.Dockerfile         # 修改: 安装CLI+WebSocket依赖
│   ├── sandbox-requirements.txt  # 修改: 添加socketio,ptyprocess
│   └── compose.yml              # 新增: 沙盒网络配置
└── user_management.sh            # 可选: 更新用户管理
```

---

## Chunk 1: 沙盒服务修改 - 适配1用户1沙盒

### Task 1.1: 修改 sandbox_service.py - 以用户名命名沙盒

**Files:**
- Modify: `scientific_agent/backend/src/services/sandbox_service.py`

- [ ] **Step 1: 读取当前 sandbox_service.py**

```bash
head -100 scientific_agent/backend/src/services/sandbox_service.py
```

- [ ] **Step 2: 找到 create_sandbox 方法，修改容器命名为 sandbox-{username}**

```python
# 找到 create_sandbox 方法（约第228行）
# 修改容器命名逻辑:
container_name = f"sandbox-{username}"  # 原来是 sandbox-{sandbox_id[:8]}
```

- [ ] **Step 3: 添加用户目录挂载配置**

```python
# 在 _build_volumes 方法中，修改为挂载用户目录
def _build_volumes(self, workspace_dir: str, data_dir: str) -> dict:
    """Build volume mounts for sandbox container"""
    user_home = os.path.dirname(os.path.dirname(workspace_dir))  # /root/claudeagent/users/{username}

    return {
        f"{user_home}/workspaces": {"bind": "/workspace/workspaces", "mode": "rw"},
        f"{user_home}/data": {"bind": "/workspace/data", "mode": "rw"},
        f"{user_home}/.claude": {"bind": "/workspace/.claude", "mode": "ro"},
        f"{user_home}/settings": {"bind": "/workspace/settings", "mode": "rw"},
    }
```

- [ ] **Step 4: 验证语法**

```bash
python3 -m py_compile scientific_agent/backend/src/services/sandbox_service.py
```

- [ ] **Step 5: Commit**

```bash
git add scientific_agent/backend/src/services/sandbox_service.py
git commit -m "feat(sandbox): name container by username, add multi-dir mounts"
```

---

### Task 1.2: 修改 sandboxes.py API - 返回用户沙盒

**Files:**
- Modify: `scientific_agent/backend/src/api/sandboxes.py:1-250`

- [ ] **Step 1: 读取当前 sandboxes.py**

```bash
head -50 scientific_agent/backend/src/api/sandboxes.py
```

- [ ] **Step 2: 添加根据用户名查询沙盒的方法**

```python
# 在文件末尾添加:

@router.get("/sandboxes/by-username/{username}", response_model=SandboxResponse)
async def get_sandbox_by_username(username: str, current_user: UserResponse = Depends(get_current_user)):
    """Get sandbox by username"""
    sandboxes = load_sandboxes()

    for sandbox_id, sandbox in sandboxes.items():
        if sandbox.get("username") == username:
            return _to_response(SandboxInfo.from_dict(sandbox))

    raise HTTPException(status_code=404, detail="Sandbox not found")
```

- [ ] **Step 3: 添加创建用户沙盒的便捷方法**

```python
@router.post("/sandboxes/create-for-user", response_model=SandboxResponse)
async def create_sandbox_for_current_user(current_user: UserResponse = Depends(get_current_user)):
    """Create sandbox for current user (called on first login)"""
    from src.services.sandbox_service import get_sandbox_service

    service = get_sandbox_service()

    # 检查是否已存在
    sandboxes = load_sandboxes()
    for sb in sandboxes.values():
        if sb.get("user_id") == current_user.id:
            return _to_response(SandboxInfo.from_dict(sb))

    # 创建沙盒
    info = service.create_sandbox(
        sandbox_id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=current_user.username,  # 使用用户名
        username=current_user.username
    )

    return _to_response(info)
```

- [ ] **Step 4: 验证语法**

```bash
python3 -m py_compile scientific_agent/backend/src/api/sandboxes.py
```

- [ ] **Step 5: Commit**

```bash
git add scientific_agent/backend/src/api/sandboxes.py
git commit -m "feat(sandbox): add username-based sandbox lookup"
```

---

## Chunk 2: 登录时自动创建沙盒

### Task 2.1: 修改 auth.py - 登录成功后自动创建沙盒

**Files:**
- Modify: `scientific_agent/backend/src/api/auth.py:1-100`

- [ ] **Step 1: 读取 auth.py 中的 login 函数**

```bash
grep -n "def login" scientific_agent/backend/src/api/auth.py
```

- [ ] **Step 2: 在 login 函数中，认证成功后添加沙盒检查/创建逻辑**

```python
# 找到 login 成功的返回前，添加:

# 检查并创建用户沙盒
from src.api.sandboxes import load_sandboxes

sandboxes = load_sandboxes()
user_sandbox = None
for sb in sandboxes.values():
    if sb.get("user_id") == user["id"]:
        user_sandbox = sb
        break

if not user_sandbox:
    # 自动创建沙盒
    from src.services.sandbox_service import get_sandbox_service
    service = get_sandbox_service()
    info = service.create_sandbox(
        sandbox_id=str(uuid.uuid4()),
        user_id=user["id"],
        name=user["username"],
        username=user["username"]
    )
    user_sandbox = info.to_dict()
    logger.info(f"Auto-created sandbox for user: {user['username']}")
```

- [ ] **Step 3: 修改 login 返回值，包含沙盒信息**

```python
# 在返回中添加 sandbox 字段
return {
    "token": token,
    "user": user,
    "sandbox": user_sandbox  # 新增
}
```

- [ ] **Step 4: 验证语法**

```bash
python3 -m py_compile scientific_agent/backend/src/api/auth.py
```

- [ ] **Step 5: Commit**

```bash
git add scientific_agent/backend/src/api/auth.py
git commit -m "feat(auth): auto-create sandbox on first login"
```

---

## Chunk 3: 沙盒端 WebSocket Shell

### Task 3.1: 修改 sandbox/api.py - 添加 WebSocket Shell 端点

**Files:**
- Modify: `scientific_agent/sandbox/api.py:1-250`

- [ ] **Step 1: 读取当前 sandbox/api.py**

```bash
head -30 scientific_agent/sandbox/api.py
```

- [ ] **Step 2: 添加 WebSocket 和 socketio 导入**

```python
# 在文件开头添加:
import socketio
import pty
import fcntl
import termios
import struct
import select
from typing import Dict
```

- [ ] **Step 3: 创建 Socket.IO 应用**

```python
# 在 app = FastAPI 之后添加:
sio = socketio.AsyncServer(async_mode='asyncio')
app.mount("/", socketio.ASGIApp(sio))
```

- [ ] **Step 4: 在文件末尾添加 ShellConnection 类**

```python
# ============== Shell WebSocket Handler ==============

shell_connections: Dict[str, dict] = {}


class ShellConnection:
    def __init__(self, sid: str):
        self.sid = sid
        self.master_fd = None
        self.process = None

    async def handle_init(self, data: dict):
        project_path = data.get("projectPath", "/workspace")
        session_id = data.get("sessionId")
        provider = data.get("provider", "plain-shell")
        cols = data.get("cols", 80)
        rows = data.get("rows", 24)
        is_plain_shell = data.get("isPlainShell", False)

        # 构建命令
        if is_plain_shell:
            cmd = f'cd "{project_path}" && $SHELL'
        elif provider == "claude":
            if session_id:
                cmd = f'cd "{project_path}" && claude --resume {session_id}'
            else:
                cmd = f'cd "{project_path}" && claude'
        else:
            cmd = f'cd "{project_path}" && $SHELL'

        # 启动 PTY
        self.master_fd, slave_fd = pty.openpty()

        winsize = struct.pack('HHHH', rows, cols, 0, 0)
        fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

        self.process = subprocess.Popen(
            cmd, shell=True,
            stdin=slave_fd, stdout=slave_fd, stderr=slave_fd,
            cwd=project_path, start_new_session=True
        )
        os.close(slave_fd)

        # 启动输出读取
        asyncio.create_task(self.read_output())

    async def read_output(self):
        while True:
            ready, _, _ = select.select([self.master_fd], [], [], 0.1)
            if ready:
                data = os.read(self.master_fd, 4096)
                if data:
                    await sio.emit('output', {"type": "output", "data": data.decode()}, room=self.sid)
            if self.process.poll() is not None:
                break
            await asyncio.sleep(0.01)

    async def handle_input(self, data: dict):
        if self.master_fd:
            os.write(self.master_fd, data.get("data", "").encode())

    async def handle_resize(self, data: dict):
        if self.master_fd:
            cols = data.get("cols", 80)
            rows = data.get("rows", 24)
            winsize = struct.pack('HHHH', rows, cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)


@sio.event
async def connect(sid, environ):
    logger.info(f"[sandbox-shell] Client connected: {sid}")


@sio.event
async def disconnect(sid):
    if sid in shell_connections:
        del shell_connections[sid]


@sio.event
async def init(sid, data):
    shell_conn = ShellConnection(sid)
    shell_connections[sid] = shell_conn
    await shell_conn.handle_init(data)


@sio.event
async def input(sid, data):
    if sid in shell_connections:
        await shell_connections[sid].handle_input(data)


@sio.event
async def resize(sid, data):
    if sid in shell_connections:
        await shell_connections[sid].handle_resize(data)
```

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

## Chunk 4: 主容器 Shell 转发

### Task 4.1: 修改 websocket.py - Shell 转发到沙盒

**Files:**
- Modify: `scientific_agent/backend/src/api/websocket.py:850-950`

- [ ] **Step 1: 读取 ShellConnection 类和 shell_websocket_endpoint**

```bash
sed -n '850,950p' scientific_agent/backend/src/api/websocket.py
```

- [ ] **Step 2: 修改 ShellConnection.__init__ 添加 sandbox_url 参数**

```python
class ShellConnection:
    def __init__(self, websocket, user_id, sandbox_url=None):
        self.websocket = websocket
        self.user_id = user_id
        self.sandbox_url = sandbox_url  # 新增
        self.sio_client = None  # 新增
        # ... 现有代码
```

- [ ] **Step 3: 修改 handle 方法支持代理模式**

```python
async def handle(self):
    if self.sandbox_url:
        await self._handle_proxy_mode()
    else:
        await self._handle_local_mode()
```

- [ ] **Step 4: 添加代理模式处理方法**

```python
async def _handle_proxy_mode(self):
    import socketio
    self.sio_client = socketio.AsyncClient()

    ws_url = self.sandbox_url.replace('http://', '').replace('https://', '')
    await self.sio_client.connect(f"http://{ws_url}/socket.io")

    init_sent = False
    while True:
        data = await self.websocket.receive_text()
        msg = json.loads(data)

        if msg["type"] == "init":
            await self.sio_client.emit("init", msg)
            init_sent = True
        elif msg["type"] == "input" and init_sent:
            await self.sio_client.emit("input", msg)
        elif msg["type"] == "resize" and init_sent:
            await self.sio_client.emit("resize", msg)
        elif msg["type"] == "disconnect":
            if init_sent:
                await self.sio_client.emit("disconnect_shell")
            break

async def _proxy_receive(self):
    @self.sio_client.on('output')
    async def on_output(data):
        await self.websocket.send_json(data)

    await asyncio.sleep(3600)
```

- [ ] **Step 5: 修改 shell_websocket_endpoint 获取沙盒 URL**

```python
@router.websocket("/shell")
async def shell_websocket_endpoint(websocket: WebSocket, token: str = Query(default="")):
    user = authenticate_ws_token(token)
    if not user:
        await websocket.accept()
        await websocket.send_json({"type": "error", "error": "Unauthorized"})
        await websocket.close()
        return

    # 查找用户的沙盒
    sandboxes = load_sandboxes()
    sandbox_url = None
    for sb in sandboxes.values():
        if sb.get("user_id") == user["id"]:
            sandbox_url = sb.get("api_url")
            break

    shell_conn = ShellConnection(websocket, user["id"], sandbox_url)
    await shell_conn.handle()
```

- [ ] **Step 6: 验证语法**

```bash
python3 -m py_compile scientific_agent/backend/src/api/websocket.py
```

- [ ] **Step 7: Commit**

```bash
git add scientific_agent/backend/src/api/websocket.py
git commit -m "feat(websocket): add shell proxy to sandbox"
```

---

## Chunk 5: Docker 配置

### Task 5.1: 修改 sandbox-requirements.txt - 添加依赖

**Files:**
- Modify: `scientific_agent/docker/sandbox-requirements.txt`

- [ ] **Step 1: 读取当前依赖**

```bash
cat scientific_agent/docker/sandbox-requirements.txt
```

- [ ] **Step 2: 添加 WebSocket 相关依赖**

```bash
echo "python-socketio>=5.0.0" >> scientific_agent/docker/sandbox-requirements.txt
echo "ptyprocess>=0.7.0" >> scientific_agent/docker/sandbox-requirements.txt
```

- [ ] **Step 3: Commit**

```bash
git add scientific_agent/docker/sandbox-requirements.txt
git commit -m "chore: add socketio and ptyprocess to sandbox deps"
```

---

### Task 5.2: 修改 sandbox.Dockerfile - 安装 CLI

**Files:**
- Modify: `scientific_agent/docker/sandbox.Dockerfile`

- [ ] **Step 1: 读取当前 Dockerfile**

```bash
head -30 scientific_agent/docker/sandbox.Dockerfile
```

- [ ] **Step 2: 添加 Claude CLI 安装**

```dockerfile
# 在 apt-get install 之后添加:
RUN curl -sSfL https://raw.githubusercontent.com/anthropics/claude-code/main/install.sh | sh
```

- [ ] **Step 3: Commit**

```bash
git add scientific_agent/docker/sandbox.Dockerfile
git commit -m "feat(sandbox): install Claude CLI"
```

---

### Task 5.3: 创建沙盒网络配置

**Files:**
- Create: `scientific_agent/docker/sandbox-network.yml`

- [ ] **Step 1: 创建网络配置**

```yaml
# scientific_agent/docker/sandbox-network.yml
# 用于动态创建用户沙盒的网络配置

networks:
  mas-network:
    name: mas-network
    driver: bridge
```

- [ ] **Step 2: Commit**

```bash
git add scientific_agent/docker/sandbox-network.yml
git commit -m "feat(docker): add sandbox network config"
```

---

## Chunk 6: 测试

### Task 6.1: 单元测试

- [ ] **Step 1: 测试沙盒服务创建**

```bash
# 测试创建以用户名命名的沙盒
python3 -c "
from backend.src.services.sandbox_service import get_sandbox_service
service = get_sandbox_service()
info = service.create_sandbox('test-id', 'user-test', 'testuser', 'testuser')
print(f'Container: {info.container_name}')
assert info.container_name == 'sandbox-testuser'
"
```

- [ ] **Step 2: 测试 API 端点**

```bash
# 启动服务并测试
cd scientific_agent
python3 -m uvicorn backend.src.main:app --port 9000 &
sleep 3

# 测试沙盒创建
curl -X POST http://localhost:9000/api/sandboxes/create-for-user \
  -H "Authorization: Bearer <token>"

# 测试 Shell 端点
# (需要 WebSocket 客户端测试)
```

- [ ] **Step 3: Commit 测试**

```bash
git add tests/
git commit -m "test: add sandbox tests"
```

---

## 依赖检查

确保以下命令可用:
- docker
- docker-compose
- python3
- git
- curl

---

## 回滚计划

如果出现问题:
1. 回退 websocket.py 移除代理模式
2. 禁用 auth.py 中的自动创建沙盒
3. 使用 git revert 回退更改

---

## 相关文件列表

| 文件 | 状态 | 说明 |
|------|------|------|
| backend/src/services/sandbox_service.py | 修改 | 以用户名命名，多目录挂载 |
| backend/src/api/sandboxes.py | 修改 | 添加用户名查询API |
| backend/src/api/auth.py | 修改 | 登录时自动创建沙盒 |
| backend/src/api/websocket.py | 修改 | Shell转发到沙盒 |
| sandbox/api.py | 修改 | 添加WebSocket Shell |
| docker/sandbox-requirements.txt | 修改 | 添加socketio, ptyprocess |
| docker/sandbox.Dockerfile | 修改 | 安装CLI |
| docker/sandbox-network.yml | 新建 | 网络配置 |

---

> **Plan complete and saved to `docs/superpowers/plans/2026-03-15-one-user-one-sandbox-implementation.md`. Ready to execute?**
