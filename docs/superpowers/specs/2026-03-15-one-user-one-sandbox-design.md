# SPEC: 1用户1沙盒 - 双容器架构

> 日期: 2026-03-15
> 状态: Draft
> 目标: 每个用户一个沙盒容器，支持 SDK(对话) 和 CLI(终端)

---

## 1. 背景

当前架构问题：
- feat 分支没有终端功能（WebSocket Shell）
- 没有沙盒到用户的映射
- 用户和沙盒是分离的

目标架构：
- 1用户 = 1沙盒容器
- 首次登录时自动创建沙盒
- 同时支持 SDK（对话）和 CLI（终端）

---

## 2. 架构设计

### 2.1 最终架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         主容器 (Main Container)                          │
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────────┐ │
│  │   Frontend │  │   Backend   │  │     Shell WebSocket Handler      │ │
│  │   :9001    │  │   :9000     │  │   /shell → 沙盒 WebSocket 转发   │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────────────┘ │
│         │                │                      │                         │
│         │        ┌──────┴──────┐              │                         │
│         │        │ 用户管理     │              │                         │
│         │        │ + 沙盒映射  │◄─────────────┘                         │
│         │        └──────────────┘                                        │
│         │                │                                               │
│         │        ┌──────┴──────┐                                        │
│         │        │ httpx       │                                        │
│         │        │             │                                        │
│         │        │ • POST /execute → 沙盒 HTTP                         │
│         │        │ • WS /shell → 沙盒 WebSocket                        │
│         │        └──────────────┘                                        │
│         │                                                                   │
└───────────────────────────────────────────────────────────────────────────┘
          │
          │ Docker Network (mas-network)
          │
┌─────────▼───────────────────────────────────────────────────────────────┐
│  沙盒容器 1: sandbox-alice                                               │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  :9002 (仅内部网络可访问)                                         │   │
│  │                                                                   │   │
│  │  HTTP 端点:                                                      │   │
│  │  • POST /execute          → SDK 执行 (对话)                      │   │
│  │  • POST /execute/stream   → SDK 流式响应                         │   │
│  │                                                                   │   │
│  │  WebSocket 端点:                                                  │   │
│  │  • /ws/socket.io         → Shell (CLI)                         │   │
│  │                                                                   │   │
│  │  Claude: SDK + CLI                                               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  Volume 映射:                                                          │
│  /root/claudeagent/users/alice/ → /workspace/                          │
│    ├── workspaces/default/                                             │
│    ├── data/                                                         │
│    ├── .claude/                                                     │
│    └── settings/                                                     │
└───────────────────────────────────────────────────────────────────────┘

┌─────────▼───────────────────────────────────────────────────────────────┐
│  沙盒容器 2: sandbox-bob                                                │
│  ...                                                                   │
└───────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流

#### 对话流程 (SDK)
```
前端 POST /api/chat
        │
        ▼
主容器 Backend
        │
        ▼ 查找用户的沙盒 URL
查询 sandboxes.json
        │
        ▼ POST http://sandbox-{username}:9002/execute
        │
        ▼
沙盒容器 (SDK)
        │
        ▼ HTTP Response
主容器 → 前端
```

#### 终端流程 (CLI)
```
前端 WebSocket /shell?token=JWT
        │
        ▼
主容器 ShellConnection
        │
        ▼ 查找用户的沙盒 URL
查询 sandboxes.json
        │
        ▼ WebSocket ws://sandbox-{username}:9002/socket.io
        │
        ▼
沙盒容器 ShellConnection
        │
        ▼ PTY → Claude CLI
输出 ──► 沙盒 WebSocket ──► 主容器 ──► 前端
```

---

## 3. 数据模型

### 3.1 用户模型 (backend/data/users.json)

```json
{
  "alice": {
    "id": "user-alice-id",
    "username": "alice",
    "password_hash": "...",
    "created_at": "2026-03-15T10:00:00Z"
  }
}
```

### 3.2 沙盒模型 (backend/data/sandboxes.json)

```json
{
  "sandbox-alice": {
    "id": "sandbox-alice",
    "user_id": "user-alice-id",
    "username": "alice",
    "container_name": "sandbox-alice",
    "api_url": "http://sandbox-alice:9002",
    "ws_url": "http://sandbox-alice:9002",
    "status": "running",
    "workspace_dir": "/workspace",
    "created_at": "2026-03-15T10:05:00Z"
  }
}
```

### 3.3 用户目录结构

```
/root/claudeagent/users/{username}/
├── workspaces/
│   └── default/           → /workspace/workspaces/default
├── data/                  → /workspace/data
├── .claude/                → /workspace/.claude
│   ├── CLAUDE.md
│   ├── agents/
│   └── skills/
└── settings/              → /workspace/settings
```

---

## 4. 文件修改清单

### 4.1 新增文件

| 文件 | 说明 |
|------|------|
| `backend/src/api/sandboxes.py` | 沙盒 CRUD API |
| `backend/src/services/sandbox_manager.py` | 沙盒容器管理 |

### 4.2 修改文件

| 文件 | 修改内容 |
|------|---------|
| `backend/src/api/websocket.py` | 添加 Shell 转发到沙盒 |
| `backend/src/api/auth.py` | 登录时自动创建沙盒 |
| `sandbox/api.py` | 添加 WebSocket Shell 端点 |
| `docker/sandbox.Dockerfile` | 安装 CLI + WebSocket 依赖 |
| `docker-compose.yml` | 添加沙盒网络配置 |
| `user_management.sh` | 更新用户管理（可选） |

### 4.3 需要安装的依赖

#### sandbox-requirements.txt
```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.5.0
pyyaml>=6.0
anthropic>=0.25.0
sse-starlette>=2.0.0
python-socketio>=5.0.0     # 新增: WebSocket
ptyprocess>=0.7.0            # 新增: PTY
```

---

## 5. API 设计

### 5.1 沙盒管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/sandboxes | 创建沙盒 (为当前用户) |
| GET | /api/sandboxes | 列出当前用户的沙盒 |
| GET | /api/sandboxes/{username} | 获取指定用户的沙盒 |
| DELETE | /api/sandboxes/{username} | 删除沙盒 |

### 5.2 认证时自动创建沙盒

```python
# backend/src/api/auth.py - login 成功后

@app.post("/api/auth/login")
async def login(request: LoginRequest):
    # ... 现有登录逻辑 ...

    # 新增: 检查用户沙盒是否存在，不存在则创建
    sandboxes = load_sandboxes()
    user_sandbox = None
    for sb in sandboxes.values():
        if sb.get("username") == username:
            user_sandbox = sb
            break

    if not user_sandbox:
        # 自动创建沙盒
        user_sandbox = create_sandbox_for_user(username, user_id)
        logger.info(f"Auto-created sandbox for user: {username}")

    return {"token": token, "user": user, "sandbox": user_sandbox}
```

---

## 6. WebSocket Shell 转发实现

### 6.1 主容器 ShellConnection (修改)

```python
# backend/src/api/websocket.py

class ShellConnection:
    def __init__(self, websocket, user_id, sandbox_url=None):
        self.websocket = websocket
        self.user_id = user_id
        self.sandbox_url = sandbox_url  # e.g., http://sandbox-alice:9002
        self.sio_client = None

    async def handle(self):
        if self.sandbox_url:
            # 代理模式: 转发到沙盒
            await self._handle_proxy_mode()
        else:
            # 本地模式 (开发用)
            await self._handle_local_mode()

    async def _handle_proxy_mode(self):
        import socketio
        self.sio_client = socketio.AsyncClient()

        # 连接到沙盒 WebSocket
        ws_url = self.sandbox_url.replace('http://', '').replace('https://', '')
        await self.sio_client.connect(f"http://{ws_url}/socket.io")

        # 转发消息
        while True:
            data = await self.websocket.receive_text()
            message = json.loads(data)

            if message["type"] == "init":
                await self.sio_client.emit("init", message)
            elif message["type"] == "input":
                await self.sio_client.emit("input", message)
            elif message["type"] == "resize":
                await self.sio_client.emit("resize", message)
            elif message["type"] == "disconnect":
                await self.sio_client.emit("disconnect_shell")
                break
```

### 6.2 沙盒 ShellConnection (新增)

```python
# sandbox/api.py

@sio.event
async def init(sid, data):
    """初始化 Shell"""
    project_path = data.get("projectPath", "/workspace")
    provider = data.get("provider", "plain-shell")
    session_id = data.get("sessionId")

    # 建立工作目录符号链接
    await setup_workspace_symlinks(project_path)

    # 启动 PTY + CLI
    shell_command = build_shell_command(provider, "/workspace", session_id)

    master_fd, slave_fd = pty.openpty()
    process = subprocess.Popen(
        shell_command,
        shell=True,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd="/workspace",
        start_new_session=True,
    )

    # 启动输出读取任务
    asyncio.create_task(read_output(master_fd, sid))

@sio.event
async def input(sid, data):
    """转发输入到 PTY"""
    # os.write(master_fd, data["data"].encode())

@sio.event
async def resize(sid, data):
    """调整终端大小"""
    # fcntl.ioctl(master_fd, TIOCSWINSZ, ...)
```

---

## 7. Docker 配置

### 7.1 docker-compose.yml

```yaml
services:
  main:
    image: ${MAIN_IMAGE:-mas-main:latest}
    container_name: mas-main
    ports:
      - "9000:9000"   # Backend
      - "9001:9001"   # Frontend
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL:-}
      - CLAUDE_MODEL=${CLAUDE_MODEL:-claude-sonnet-4-20250514}
      # 新增: 沙盒网络配置
      - SANDBOX_NETWORK=mas-network
      - SANDBOX_BASE_NAME=sandbox-
    volumes:
      - ./data:/app/data
      - ./users:/root/claudeagent/users  # 用户目录
    networks:
      - mas-network
    depends_on:
      - sandbox  # 等待沙盒网络就绪 (可选)

networks:
  mas-network:
    driver: bridge
```

### 7.2 沙盒动态启动

由于需要为每个用户动态创建沙盒容器，不使用 docker-compose 的静态服务，而是使用管理脚本：

```bash
# 启动用户沙盒
docker run -d \
  --name sandbox-${username} \
  --network mas-network \
  -v /root/claudeagent/users/${username}:/workspace \
  -e ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY} \
  -e WORKSPACE=/workspace \
  mas-sandbox:latest
```

---

## 8. 工作目录映射

### 8.1 符号链接方案

在沙盒启动时：

```python
# sandbox/api.py - 启动时执行

async def setup_workspace_symlinks(user_home: str):
    """建立工作目录符号链接"""

    # user_home = "/root/claudeagent/users/alice"

    # 确保 /workspace 存在
    os.makedirs("/workspace", exist_ok=True)

    # 建立子目录映射
    mappings = {
        "workspaces": "/workspace/workspaces",
        "data": "/workspace/data",
        ".claude": "/workspace/.claude",
        "settings": "/workspace/settings",
    }

    for src_name, target in mappings.items():
        src_path = os.path.join(user_home, src_name)

        # 如果源目录存在
        if os.path.exists(src_path):
            os.makedirs(target, exist_ok=True)

            # 创建符号链接
            # 方式 A: 符号链接
            # ln -sf {src_path} {target}

            # 方式 B: 绑定挂载 (需要更多权限)
            # mount --bind {src_path} {target}
```

### 8.2 直接挂载方案 (推荐)

更简单的方式是在启动沙盒时直接挂载：

```bash
docker run -d \
  --name sandbox-${username} \
  --network mas-network \
  -v /root/claudeagent/users/${username}/workspaces:/workspace/workspaces \
  -v /root/claudeagent/users/${username}/data:/workspace/data \
  -v /root/claudeagent/users/${username}/.claude:/workspace/.claude \
  -v /root/claudeagent/users/${username}/settings:/workspace/settings \
  mas-sandbox:latest
```

---

## 9. 错误处理

### 9.1 沙盒不可用

| 场景 | 处理 |
|------|------|
| 用户登录时沙盒创建失败 | 返回错误，提示稍后重试 |
| WebSocket 连接沙盒失败 | 返回错误到前端，显示"沙盒不可用" |
| 沙盒进程崩溃 | 自动重启或标记为不可用 |

### 9.2 路径问题

| 场景 | 处理 |
|------|------|
| 用户目录不存在 | 自动创建 |
| 符号链接失败 | 记录警告，使用原始目录 |

---

## 10. 安全性

### 10.1 网络隔离

- 沙盒容器只在 `mas-network` 内可访问
- 不暴露到宿主机网络

### 10.2 API Key

- 沙盒通过环境变量获取 `ANTHROPIC_API_KEY`
- 不需要额外的认证

---

## 11. 实施顺序

### Phase 1: 沙盒管理 API
- [ ] 创建 `backend/src/api/sandboxes.py`
- [ ] 创建 `backend/src/services/sandbox_manager.py`
- [ ] 测试沙盒创建/删除

### Phase 2: 登录时自动创建沙盒
- [ ] 修改 `backend/src/api/auth.py`
- [ ] 登录成功后自动创建沙盒

### Phase 3: WebSocket Shell
- [ ] 在 `sandbox/api.py` 添加 WebSocket 端点
- [ ] 实现 ShellConnection

### Phase 4: 主容器转发
- [ ] 修改 `backend/src/api/websocket.py`
- [ ] 实现代理转发

### Phase 5: Docker 配置
- [ ] 更新 `docker-compose.yml`
- [ ] 创建沙盒启动脚本

### Phase 6: 测试
- [ ] 单元测试
- [ ] 集成测试

---

## 12. 回滚计划

如果出现问题：
1. 回退到不支持沙盒的版本
2. 使用静态沙盒服务
3. 暂时禁用终端功能，保留对话功能

---

> **Draft - 待批准后实施**
