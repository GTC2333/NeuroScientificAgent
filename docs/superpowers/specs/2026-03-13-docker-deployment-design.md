# Docker 部署架构设计

## Context

MAS 系统已有 Docker 沙盒隔离实现（SandboxService、sandbox 容器），但存在以下问题：
1. `sandbox-requirements.txt` 缺失，sandbox 镜像构建失败
2. 前端由 Node.js Express 服务，需要 nodejs runtime 在容器内
3. 对外暴露 :9000 + :9001 两个端口，不统一
4. 镜像构建和容器运行耦合在 docker-compose 中
5. `create_user.sh` 只建目录，auth.py 只建账户，两者独立
6. 用户可创建多个 sandbox，但实际需求是 1:1

## Decisions

| # | 决策项 | 选择 |
|---|--------|------|
| 1 | 重复代码清理 | 不清理，先让 Docker 模式跑通 |
| 2 | 前端服务方式 | Nginx 服务静态文件 + 反代 API |
| 3 | 对外端口 | `${FRONTEND_PORT:-9001}`，可配置 |
| 4 | 用户管理 | 管理员脚本一键创建（目录 + 账户） |
| 5 | 用户-Sandbox 关系 | 1:1，容器名 `mas-sandbox-{username}` |
| 6 | Sandbox 创建方式 | 前端按钮手动创建/重建，非懒创建 |
| 7 | 镜像构建 vs 运行 | 解耦：`build_images.sh` 构建，`run_main.sh` 运行 |
| 8 | 版本管理 | 统一版本号参数：`./build_images.sh v1.0` + `./run_main.sh v1.0` |

## Architecture

```
                    ┌─── 主容器 (mas-main) ─────────────────────┐
                    │                                           │
用户 A ─┐           │  Nginx (:80 内部)                         │
        ├─ :9001 ──▶│    ├─ /*        → dist/ (静态文件)         │
用户 B ─┘           │    ├─ /api/*    → FastAPI :9000            │
                    │    ├─ /ws       → FastAPI :9000 (WS)      │
                    │    └─ /shell    → FastAPI :9000 (WS)      │
                    │                                           │
                    │  FastAPI (:9000, 仅内部)                   │
                    │    ├─ auth (JWT 登录)                      │
                    │    ├─ SandboxService (Docker socket)       │
                    │    └─ WebSocket → httpx SSE 代理            │
                    └───────────────────────────────────────────┘
                                    │ Docker socket
                    ┌───────────────┼───────────────┐
                    ▼                               ▼
            ┌─ sandbox-alice ──┐       ┌─ sandbox-bob ──┐
            │ api.py :9002     │       │ api.py :9002    │
            │ agentic_loop.py  │       │ agentic_loop.py │
            │ /workspace (rw)  │       │ /workspace (rw) │
            └──────────────────┘       └─────────────────┘
```

## Configurable Parameters

All via environment variables with defaults:

```bash
# run_main.sh 支持的配置
MAIN_IMAGE=mas-main:latest           # 主容器镜像（被版本号参数覆盖）
SANDBOX_IMAGE=mas-sandbox:latest     # 沙盒镜像（被版本号参数覆盖）
FRONTEND_PORT=9001                   # 对外端口
BACKEND_PORT=9000                    # 内部 FastAPI 端口
SANDBOX_NETWORK=mas-network
SANDBOX_MEM_LIMIT=512m
SANDBOX_CPU_QUOTA=50000
SANDBOX_PORT_RANGE_START=30000
SANDBOX_PORT_RANGE_END=39999
ANTHROPIC_API_KEY=
ANTHROPIC_BASE_URL=
ANTHROPIC_AUTH_TOKEN=
CLAUDE_MODEL=sonnet
```

## User Management

`create_user.sh` 一步完成目录 + 账户：

```bash
./create_user.sh alice mypassword
# 1. mkdir -p /root/claudeagent/users/alice/{workspaces/default,data}
# 2. curl POST /api/auth/register {username, password}
```

Requires main container running.

## Sandbox Lifecycle

1:1 user-sandbox. Frontend buttons control lifecycle:

- 未创建 → 「创建 Sandbox」 → `POST /api/sandboxes/create`
- 运行中 → 「重建 Sandbox」 → `POST /api/sandboxes/rebuild`
- 已停止 → 「启动」 + 「重建」

Container name: `mas-sandbox-{username}`.
Workspace files preserved on rebuild (only container recreated).
No messaging allowed without running sandbox.

## Nginx Config

```nginx
server {
    listen 80;
    location / {
        root /app/frontend/dist;
        try_files $uri $uri/ /index.html;
    }
    location /api/ {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    location /ws {
        proxy_pass http://127.0.0.1:9000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400s;
    }
    location /shell {
        proxy_pass http://127.0.0.1:9000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400s;
    }
    location /health {
        proxy_pass http://127.0.0.1:9000;
    }
}
```

## File Changes

### New Files

| File | Purpose |
|------|---------|
| `docker/nginx.conf` | Nginx config |
| `docker/sandbox-requirements.txt` | Sandbox Python deps (fixes build) |
| `/root/claudeagent/run_main.sh` | Start main container with version |

### Modified Files

| File | Change |
|------|--------|
| `docker/main.Dockerfile` | Remove nodejs/npm, add nginx, change CMD |
| `docker-compose.yml` | Remove `build:`, use `image:`, port mapping |
| `/root/claudeagent/build_images.sh` | Version tag support, pure `docker build` |
| `/root/claudeagent/create_user.sh` | Add API register call |
| `backend/src/api/sandboxes.py` | Add `POST /api/sandboxes/rebuild` |
| `backend/src/services/sandbox_service.py` | Container name `mas-sandbox-{username}`, add `rebuild_sandbox()` |
| `Makefile` | Delegate to build_images.sh / run_main.sh |
| Frontend component(s) | Sandbox status + create/rebuild buttons |

### Unchanged

All sandbox/* files, claude_code.py, claude_sdk.py, backend/tools.py, sandbox.Dockerfile (only needs the new requirements file).

## Operation Flow

```bash
./build_images.sh v1.0              # Step 1: Build images
./run_main.sh v1.0                  # Step 2: Start main container
./create_user.sh alice mypassword   # Step 3: Create user
# Browser: http://host:9001 → login → create sandbox → use
```
