# MCP Configuration Hang Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 MCP 配置导致的 CLI 挂起问题，使系统能正常运行 Claude Code 并支持多智能体协作

**Architecture:** 问题根因是 `npx -y tavily-mcp` 进程启动后阻塞了 stdio 通信。修复方案采用"快速修复+长期方案"策略：
1. 快速修复：禁用 MCP 或添加超时控制
2. 根因修复：改进 MCP 配置加载逻辑

**Tech Stack:** Python (FastAPI), Claude Code CLI, MCP (Model Context Protocol), Tavily

---

## 问题分析

### 当前症状
- 启用 MCP 配置时：`claude -p --mcp-config xxx "Hello"` 挂起 120 秒超时
- 禁用 MCP 配置时：CLI 正常工作，返回响应
- 直接运行 `npx -y tavily-mcp` 测试

### 根因
MCP 服务器 (`npx -y tavily-mcp`) 启动后阻塞了 stdio 通信管道，导致 Claude Code CLI 无法正常读取响应。

---

## Task 1: 验证问题 - 测试 MCP 直接运行

**Files:**
- Test: `/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/temp_workspace/mcp_config.json`

**Step 1: 检查当前 MCP 配置文件内容**

Run: `cat /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/temp_workspace/mcp_config.json`

Expected: JSON 格式的 MCP 服务器配置

**Step 2: 直接测试 npx tavily-mcp 是否能启动**

Run: `timeout 10 npx -y tavily-mcp --help 2>&1 || echo "Command timed out or failed"`

Expected: 输出帮助信息或超时错误

**Step 3: 测试 stdio 通信是否正常**

Run: `echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | timeout 5 npx -y tavily-mcp 2>&1 | head -20`

Expected: JSON-RPC 响应或超时

**Step 4: 记录测试结果**

将结果写入笔记，总结 MCP 是否可用

---

## Task 2: 快速修复 - 禁用 MCP 或添加超时

**Files:**
- Modify: `/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/local.yaml:20-25`
- Test: API 调用测试

**Step 1: 临时禁用 MCP（快速验证）**

Edit `local.yaml`:
```yaml
mcp:
  enabled: false  # 临时禁用，验证系统基本功能
  servers: []
```

**Step 2: 测试 API 是否正常工作**

Run:
```bash
curl -X POST http://localhost:9000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello", "agent_type": "principal"}'
```

Expected: 正常返回响应（无超时）

**Step 3: 验证完成后恢复 MCP 配置**

Edit `local.yaml`:
```yaml
mcp:
  enabled: true
  servers:
    - type: tavily
      name: tavily
```

---

## Task 3: 根因修复 - 改进 MCP 处理逻辑

**Files:**
- Modify: `/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/backend/src/services/claude_code.py:94-129`
- Test: API 调用测试

**Step 1: 添加 MCP 启动超时检测**

在 `_build_mcp_config` 方法中添加：
```python
def _test_mcp_server(self, server_config: dict) -> bool:
    """Test if MCP server can start and respond"""
    import subprocess
    import time

    try:
        cmd = [server_config["command"]] + server_config["args"]
        env = os.environ.copy()
        env.update(server_config.get("env", {}))

        # Start process with stdio
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env
        )

        # Try to initialize
        init_msg = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n'
        try:
            stdout, stderr = proc.communicate(
                input=init_msg.encode(),
                timeout=5
            )
            proc.kill()
            return True
        except subprocess.TimeoutExpired:
            proc.kill()
            return False
    except Exception as e:
        logger.warning(f"[ClaudeCode] MCP server test failed: {e}")
        return False
```

**Step 2: 修改 `_build_mcp_config` 添加降级逻辑**

在构建 MCP 配置后，测试每个服务器是否可用：
```python
def _build_mcp_config(self) -> str:
    """Build MCP server configuration and save to file, return file path"""
    if not self.mcp_enabled or not self.mcp_servers:
        logger.info("[ClaudeCode] MCP disabled or no servers configured")
        return None

    # ... 现有构建逻辑 ...

    if mcp_config:
        # 测试每个 MCP 服务器是否可用
        working_servers = []
        for server in mcp_config:
            if self._test_mcp_server(server):
                working_servers.append(server)
                logger.info(f"[ClaudeCode] MCP server {server['name']} is working")
            else:
                logger.warning(f"[ClaudeCode] MCP server {server['name']} failed test, skipping")

        if not working_servers:
            logger.warning("[ClaudeCode] No working MCP servers, disabling MCP")
            return None

        # 只写入可用的服务器配置
        config_json = json.dumps(working_servers)
        # ... 写入文件 ...
```

**Step 3: 测试修复后的效果**

Run:
```bash
curl -X POST http://localhost:9000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is machine learning?", "agent_type": "principal"}'
```

Expected:
- 如果 MCP 不可用：返回正常响应（使用内置能力）
- 如果 MCP 可用：返回带搜索结果的响应

---

## Task 4: 验证多智能体协作

**Files:**
- Test: API 调用测试
- Modify (optional): `/Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/backend/src/api/chat.py`

**Step 1: 测试 Agent 角色切换**

Run:
```bash
# Test Theorist
curl -X POST http://localhost:9000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Explain the hypothesis of artificial general intelligence", "agent_type": "theorist"}'

# Test Writer
curl -X POST http://localhost:9000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Write a short paragraph about AI", "agent_type": "writer"}'
```

Expected: 不同 Agent 返回符合角色设定的响应

**Step 2: 测试 Session 持久化**

Run:
```bash
SESSION_ID="test-session-$(date +%s)"

# First message
curl -X POST http://localhost:9000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Remember this: My favorite number is 42\", \"agent_type\": \"principal\", \"session_id\": \"$SESSION_ID\"}"

# Second message (should remember)
curl -X POST http://localhost:9000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"What is my favorite number?\", \"agent_type\": \"principal\", \"session_id\": \"$SESSION_ID\"}"
```

Expected: 第二次响应提到数字 42

---

## Task 5: 提交更改

**Step 1: 检查更改**

Run: `git status`

**Step 2: 提交修复**

Run:
```bash
git add backend/src/services/claude_code.py local.yaml
git commit -m "fix: handle MCP server unavailability gracefully

- Add MCP server health check before using
- Fallback to non-MCP mode if servers unavailable
- Improve error handling for subprocess communication

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## 预期结果

1. ✅ MCP 不可用时系统仍能正常运行
2. ✅ MCP 可用时正常提供搜索能力
3. ✅ Agent 角色切换正常工作
4. ✅ Session 持久化正常工作
