# 网络搜索功能实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 Theorist agent 添加 WebSearch 和 WebFetch 能力，通过 MCP 服务器实现网络搜索功能

**Architecture:** 使用 Claude Code CLI 的 `--mcp-config` 参数加载 MCP 搜索服务器，使 Theorist 能够执行网络搜索和网页抓取

**Tech Stack:**
- Claude Code CLI (已有)
- Tavily MCP Server (tavily-mcp) - 提供免费搜索 API
- Python (backend)

---

### Task 1: 获取 Tavily API Key

**Files:**
- Modify: `local.yaml` (添加 API key 配置)

**Step 1: 注册 Tavily 账号**

打开浏览器访问: https://tavily.com/

注册免费账号，获取 API Key（免费计划有 1000 条/月的配额）

**Step 2: 配置 API Key**

```bash
# 在项目根目录编辑 local.yaml
cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system
```

添加以下内容到 `local.yaml`:
```yaml
tavily:
  api_key: "your-api-key-here"
```

**Step 3: 提交**

```bash
git add local.yaml
git commit -m "feat: add Tavily API key config"
```

---

### Task 2: 安装 Tavily MCP Server

**Files:**
- Modify: `backend/src/config.py` (添加 MCP 配置)

**Step 1: 测试 npx 可用性**

```bash
npx --version
```

Expected: 显示版本号（如 11.9.0）

**Step 2: 测试 MCP 服务器启动**

```bash
npx -y tavily-mcp --help
```

Expected: 显示帮助信息

**Step 3: 配置 MCP 服务器**

编辑 `backend/src/config.py`，添加 MCP 配置类：

```python
@dataclass
class MCPConfig:
    enabled: bool = True
    servers: list = None

    def __post_init__(self):
        if self.servers is None:
            self.servers = []

# 在 Config 类中添加
@dataclass
class Config:
    server: ServerConfig
    claude: ClaudeConfig
    project: ProjectConfig
    workspace: WorkspaceConfig
    mcp: MCPConfig  # 添加这行
```

**Step 4: 提交**

```bash
git add backend/src/config.py
git commit -m "feat: add MCP configuration to config.py"
```

---

### Task 3: 修改 Claude Code Service 支持 MCP

**Files:**
- Modify: `backend/src/services/claude_code.py:97-145`

**Step 1: 读取当前 claude_code.py**

```bash
read -r -n 1 -p "Ready to read claude_code.py"
```

**Step 2: 添加 MCP 配置到 ClaudeCodeService**

在 `ClaudeCodeService.__init__` 方法中添加：

```python
def __init__(self, project_dir: str = None):
    config = get_config()

    # ... existing code ...

    # MCP 配置
    self.mcp_enabled = config.mcp.enabled if hasattr(config, 'mcp') else True
    self.mcp_servers = config.mcp.servers if hasattr(config, 'mcp') else []
```

**Step 3: 构建 MCP 配置 JSON**

添加方法 `_build_mcp_config`:

```python
def _build_mcp_config(self) -> str:
    """构建 MCP 服务器配置 JSON"""
    if not self.mcp_enabled or not self.mcp_servers:
        return None

    # 从 local.yaml 读取 API keys
    settings_env = self._load_settings_env()

    mcp_config = []
    for server in self.mcp_servers:
        if server.get("type") == "tavily":
            api_key = settings_env.get("TAVILY_API_KEY") or server.get("api_key")
            mcp_config.append({
                "name": "tavily",
                "command": "npx",
                "args": ["-y", "tavily-mcp"],
                "env": {
                    "TAVILY_API_KEY": api_key
                }
            })

    return json.dumps(mcp_config) if mcp_config else None
```

**Step 4: 修改 invoke 方法添加 MCP 参数**

在 `invoke` 方法的 cmd 列表中添加：

```python
# 在构建命令后添加 MCP 配置
mcp_config = self._build_mcp_config()
if mcp_config:
    cmd.extend(["--mcp-config", mcp_config])
```

**Step 5: 提交**

```bash
git add backend/src/services/claude_code.py
git commit -m "feat: add MCP support to ClaudeCodeService"
```

---

### Task 4: 配置 Theorist Agent 使用搜索工具

**Files:**
- Modify: `backend/src/services/claude_code.py` (构建系统提示词)

**Step 1: 修改 _build_system_prompt 方法**

更新系统提示词，告知 agent 可用 MCP 工具：

```python
def _build_system_prompt(self, agent_type: str, message: str, skills: List[str] = None) -> str:
    # ... existing code ...

    # MCP 工具上下文
    mcp_tools_context = ""
    if self.mcp_enabled and self.mcp_servers:
        mcp_tools = []
        for server in self.mcp_servers:
            if server.get("type") == "tavily":
                mcp_tools.extend(["tavily_search", "tavily_search_sublinks"])
        if mcp_tools:
            mcp_tools_context = f"\n## Available MCP Tools\nYou have access to: {', '.join(mcp_tools)}"

    system_prompt = f"""...
{mcp_tools_context}
...
"""
```

**Step 2: 提交**

```bash
git add backend/src/services/claude_code.py
git commit -m "feat: add MCP tools to system prompt"
```

---

### Task 5: 更新 local.yaml 配置

**Files:**
- Modify: `local.yaml`

**Step 1: 添加 MCP 服务器配置**

```yaml
mcp:
  enabled: true
  servers:
    - type: tavily
      name: tavily
```

**Step 2: 添加 Tavily API Key（实际值）**

在 `env` 部分或单独配置：

```yaml
env:
  TAVILY_API_KEY: "你的实际API Key"
```

**Step 3: 提交**

```bash
git add local.yaml
git commit -m "feat: add Tavily MCP server configuration"
```

---

### Task 6: 测试搜索功能

**Files:**
- Test: 手动测试

**Step 1: 重启后端服务**

```bash
cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/backend
pkill -f uvicorn || true
source ../venv/bin/activate
uvicorn src.main:app --host 0.0.0.0 --port 9000 &
sleep 3
```

**Step 2: 测试 Theorist 搜索**

```bash
curl -X POST http://localhost:9000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Search for recent papers on neural decoding", "agent": "theorist"}'
```

Expected: 返回搜索结果

**Step 3: 验证日志**

```bash
tail -50 /tmp/backend.log | grep -i mcp
```

Expected: 显示 MCP 配置加载信息

**Step 4: 提交测试结果**

```bash
git log --oneline -1
git status
```

---

### Task 7: 错误处理和文档

**Files:**
- Create: `docs/mcp-setup.md`

**Step 1: 创建文档**

```markdown
# MCP 服务器配置

## Tavily Search

### 获取 API Key
1. 访问 https://tavily.com/
2. 注册免费账号
3. 在 Dashboard 获取 API Key

### 免费配额
- 1000 次搜索/月
- 足够个人研究使用

### 故障排除
- 检查 API Key 是否正确配置
- 查看后端日志中的 MCP 相关错误
- 确认 npx 可用
```

**Step 2: 提交**

```bash
git add docs/mcp-setup.md
git commit -m "docs: add MCP setup guide"
```

---

## 总结

完成此计划后，Theorist agent 将能够：
1. 使用 Tavily Search 进行网络搜索
2. 获取学术论文和研究资料
3. 执行文献调研任务

预计任务数: 7
