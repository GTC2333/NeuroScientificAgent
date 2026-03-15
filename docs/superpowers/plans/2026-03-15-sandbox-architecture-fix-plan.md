# 执行计划：1-User-1-Sandbox 架构完善

## 背景

在检查当前代码后，发现以下问题需要修复：

### 已发现的问题

| 编号 | 问题 | 严重程度 | 位置 |
|------|------|----------|------|
| A | Volume 挂载不符合方案A设计 | 高 | sandbox_service.py:204-217 |
| B | 缺少 sessions 目录创建 | 中 | sandbox_service.py:163-181 |
| C | API URL 使用错误 (api_url vs host_api_url) | 高 | websocket.py, sandboxes.py |
| D | Local Mode 需要添加注释 | 低 | websocket.py |

---

## 执行计划

### 第一阶段：Volume 挂载修复 (问题A)

#### 1.1 修改 `_ensure_user_dirs` 方法
**文件**: `backend/src/services/sandbox_service.py`
**修改内容**:
- 添加 `sessions_dir` 目录创建
- 确保目录结构符合方案A设计

```python
# 新增 sessions 目录
sessions_dir = base / user_id / "sessions"
sessions_dir.mkdir(parents=True, exist_ok=True)
```

#### 1.2 修改 `_build_volumes` 方法
**文件**: `backend/src/services/sandbox_service.py`
**修改内容**:
- 改为分别挂载各个目录
- 使用正确的挂载路径和权限

```python
def _build_volumes(self, workspace_dir: str, data_dir: str) -> dict:
    user_home = os.path.dirname(os.path.dirname(workspace_dir))

    volumes = {
        workspace_dir: {"bind": "/workspace", "mode": "rw"},
        data_dir: {"bind": "/data", "mode": "ro"},
        f"{user_home}/.claude": {"bind": "/app/claude", "mode": "rw"},
        f"{user_home}/sessions": {"bind": "/sessions", "mode": "rw"},
    }

    # Also mount shared data as read-only if exists
    shared = Path(self.config.shared_data_dir)
    if shared.exists():
        volumes[str(shared)] = {"bind": "/shared", "mode": "ro"}
    return volumes
```

**注意**: 需要更新 `create_sandbox` 方法，传入正确的 `user_home` 参数

---

### 第二阶段：API URL 修复 (问题C)

#### 2.1 修改 Chat 代理模式的 URL 获取
**文件**: `backend/src/api/websocket.py`
**位置**: `handle_claude_command` 函数，约第274行
**修改内容**:
```python
# 修改前
sandbox_api_url = sandbox_data.get("api_url")

# 修改后
sandbox_api_url = sandbox_data.get("host_api_url")
```

#### 2.2 修改 Shell 代理模式的 URL 获取
**文件**: `backend/src/api/websocket.py`
**位置**: `shell_websocket_endpoint` 函数，约第965行
**修改内容**:
```python
# 修改前
sandbox_api_url = user_sandbox.get("api_url")

# 修改后
sandbox_api_url = user_sandbox.get("host_api_url")
```

#### 2.3 修改健康检查的 URL
**文件**: `backend/src/api/sandboxes.py`
**位置**: 两处，约第134行和第213行
**修改内容**:
```python
# 修改前
healthy = await loop.run_in_executor(
    None, service.wait_for_healthy, info.api_url, 30
)

# 修改后
healthy = await loop.run_in_executor(
    None, service.wait_for_healthy, info.host_api_url, 30
)
```

---

### 第三阶段：Local Mode 注释 (问题D)

#### 3.1 为 Chat 的 Local Mode 添加注释
**文件**: `backend/src/api/websocket.py`
**位置**: `handle_claude_command` 函数的 Local Mode 部分
**添加内容**:
```python
# ===== LOCAL MODE: Fallback to local execution (dev mode, not recommended for production) =====
# NOTE: This path is only used when:
# 1. No sandbox is configured for the user
# 2. Docker/HTTPX is not available in the main container
# For production, always ensure sandbox is running and use Proxy Mode above
logger.warning("[ws] Local mode: executing via ClaudeSDKService (NOT RECOMMENDED FOR PRODUCTION)")
```

#### 3.2 为 Shell 的 Local Mode 添加注释
**文件**: `backend/src/api/websocket.py`
**位置**: `_handle_local_mode` 方法
**添加内容**:
```python
async def _handle_local_mode(self):
    """Local mode: run shell directly in main container (dev mode only)
    WARNING: This is not recommended for production. Use proxy mode to sandbox.
    """
    # ... existing code
```

---

## 执行顺序

1. **第一阶段** (问题A + B)
   - 修改 `_ensure_user_dirs` - 添加 sessions 目录
   - 修改 `_build_volumes` - 改为方案A的分别挂载

2. **第二阶段** (问题C)
   - 修改 websocket.py 的 Chat 代理
   - 修改 websocket.py 的 Shell 代理
   - 修改 sandboxes.py 的健康检查

3. **第三阶段** (问题D)
   - 为 Local Mode 添加注释

---

## 预期结果

修复完成后：
- Volume 挂载更安全，只暴露必要的目录
- 会话数据保存在用户目录下
- 主容器正确使用 host_api_url 连接 sandbox
- Local Mode 代码有明确注释，避免误用

---

## 风险与回滚

- **风险**: Volume 挂载修改可能影响现有用户数据
- **缓解**: 修改仅影响新创建的沙盒，不影响已存在的
- **回滚**: 如果出现问题，可以快速回滚到之前版本
