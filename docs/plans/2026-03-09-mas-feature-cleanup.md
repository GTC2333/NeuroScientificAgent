# MAS 功能精简与 Claude Code 集成计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 移除与 Claude Code 功能重复的部分，确保两者正确互补，更新 DESIGN.md

**Architecture:** 分析功能重叠，将冗余组件简化为提示信息，保留 MAS 特有功能（ResearchState、可视化、工作流）

**Tech Stack:** React + TypeScript (前端), FastAPI (后端), Claude Code CLI

---

## 任务概览

| 任务 | 内容 | 状态 |
|------|------|------|
| Task 1 | 分析文档化 - 记录功能重叠分析 | - |
| Task 2 | 简化 FilesTab - 改为提示信息 | - |
| Task 3 | 简化 LogsTab - 保留业务日志 | - |
| Task 4 | 标记 Files API 为废弃 | - |
| Task 5 | 更新 DESIGN.md | - |

---

### Task 1: 分析文档化

**Files:**
- Create: `docs/analysis/claude-code-capability-analysis.md`

**Step 1: 创建分析文档**

```markdown
# Claude Code 与 MAS 功能重叠分析

## Claude Code 原生能力

| 能力 | 工具/参数 | 说明 |
|------|----------|------|
| 文件操作 | Read, Glob, Grep, Edit, Write | 完整文件系统访问 |
| 日志输出 | console, --verbose | 内置控制台 + 调试模式 |
| 子 Agent 调度 | Task 工具 | 多 Agent 协作 |
| 会话记忆 | --session-id | 跨对话上下文保持 |
| Skills 系统 | CLI Skills | 技能热插拔 |
| 搜索能力 | WebSearch, WebFetch | 网络搜索 |
| MCP 支持 | --mcp-config | 外部工具集成 |

## MAS 设计功能

| 功能 | 与 Claude Code 关系 | 建议 |
|------|-------------------|------|
| FilesTab 文件浏览器 | 冗余 - Claude Code 已有 | 简化 |
| LogsTab 日志查看 | 部分冗余 - Claude Code 有更完整日志 | 简化 |
| Task API | 冗余 - Task 工具已实现 | 标记废弃 |
| Files API | 冗余 - Claude Code 已有 | 标记废弃 |
| Session 持久化 | 互补 - 需要前端配合 | 保持 |
| Skills 选择 | 互补 - 需要前端配合 | 保持 |
| ResearchState | 独有 - 科学流程管理 | 保持 |
| 多 Agent 可视化 | 独有 - UI 展示 | 保持 |
```

**Step 2: 创建目录并保存文件**

```bash
mkdir -p /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/docs/analysis
```

Run: 创建分析文档

Expected: 文件创建成功

**Step 3: Commit**

```bash
cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system
git add docs/analysis/claude-code-capability-analysis.md
git commit -m "docs: add Claude Code capability analysis"
```

---

### Task 2: 简化 FilesTab

**Files:**
- Modify: `frontend/src/components/tabs/FilesTab.tsx`

**Step 1: 读取当前 FilesTab**

Run: `cat frontend/src/components/tabs/FilesTab.tsx`

Expected: 当前 FilesTab 内容

**Step 2: 替换为简化版本**

```tsx
import { useState } from 'react';

export function FilesTab() {
  return (
    <div className="p-4">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
        <h3 className="font-medium text-blue-800 mb-2">文件操作</h3>
        <p className="text-sm text-blue-700">
          文件操作已集成到 Claude Code 工具中。
        </p>
        <ul className="text-sm text-blue-600 mt-2 space-y-1">
          <li>• <code>Read</code> - 读取文件内容</li>
          <li>• <code>Glob</code> - 搜索文件</li>
          <li>• <code>Grep</code> - 文件内容搜索</li>
          <li>• <code>Edit</code> - 编辑文件</li>
          <li>• <code>Write</code> - 写入文件</li>
        </ul>
      </div>
      <p className="text-xs text-gray-500">
        请在聊天窗口中使用以上工具进行文件操作。
      </p>
    </div>
  );
}
```

**Step 3: 更新 InspectorPanel 移除 FilesTab**

Run: 检查 InspectorPanel.tsx 是否需要更新

Expected: FilesTab 仍然存在但显示简化内容

**Step 4: Commit**

```bash
git add frontend/src/components/tabs/FilesTab.tsx
git commit -m "refactor: simplify FilesTab to use Claude Code tools"
```

---

### Task 3: 简化 LogsTab

**Files:**
- Modify: `frontend/src/components/tabs/LogsTab.tsx`

**Step 1: 读取当前 LogsTab**

Run: `cat frontend/src/components/tabs/LogsTab.tsx`

Expected: 当前 LogsTab 内容

**Step 2: 简化 LogsTab - 保留业务日志**

```tsx
import { useState, useRef, useEffect, useCallback } from 'react';
import { api, LogEntry, LogLevel } from '../../services/api';

export function LogsTab() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filter, setFilter] = useState<LogLevel | 'all'>('all');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const refreshIntervalRef = useRef<number | null>(null);

  const fetchLogs = useCallback(async () => {
    const level = filter === 'all' ? undefined : filter;
    const fetchedLogs = await api.getLogs(level, 50); // 限制50条
    setLogs(fetchedLogs);
  }, [filter]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  useEffect(() => {
    if (autoRefresh) {
      refreshIntervalRef.current = window.setInterval(fetchLogs, 3000);
    }
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [autoRefresh, fetchLogs]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const handleClear = async () => {
    await api.clearLogs();
    setLogs([]);
  };

  const levelColors: Record<LogLevel, string> = {
    info: 'text-blue-600',
    warn: 'text-yellow-600',
    error: 'text-red-600',
    all: 'text-gray-600',
  };

  const filteredLogs = filter === 'all' ? logs : logs.filter(l => l.level === filter);

  return (
    <div className="flex flex-col h-full">
      {/* 简化的 Controls */}
      <div className="flex gap-2 mb-2 items-center flex-wrap">
        {(['all', 'info', 'warn', 'error'] as const).map((level) => (
          <button
            key={level}
            onClick={() => setFilter(level)}
            className={`px-2 py-1 text-xs rounded ${
              filter === level ? 'bg-gray-800 text-white' : 'bg-gray-100 text-gray-600'
            }`}
          >
            {level}
          </button>
        ))}
        <button
          onClick={() => setAutoRefresh(!autoRefresh)}
          className={`px-2 py-1 text-xs rounded ml-auto ${
            autoRefresh ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
          }`}
        >
          {autoRefresh ? 'Auto' : 'Paused'}
        </button>
      </div>

      {/* 说明 */}
      <div className="text-xs text-gray-500 mb-2 bg-gray-50 p-2 rounded">
        显示 MAS 业务日志。Claude Code 日志请使用终端查看。
      </div>

      {/* Log entries */}
      <div className="flex-1 overflow-auto font-mono text-xs space-y-1">
        {filteredLogs.length === 0 ? (
          <div className="text-gray-400 text-center py-4">No logs yet</div>
        ) : (
          filteredLogs.map((log) => (
            <div key={log.id} className="flex gap-2">
              <span className="text-gray-400">{log.timestamp}</span>
              <span className={`font-medium ${levelColors[log.level]}`}>[{log.level.toUpperCase()}]</span>
              {log.source && <span className="text-gray-500">[{log.source}]</span>}
              <span className="text-gray-700">{log.message}</span>
            </div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add frontend/src/components/tabs/LogsTab.tsx
git commit -m "refactor: simplify LogsTab to show only business logs"
```

---

### Task 4: 标记 Files API 为废弃

**Files:**
- Modify: `backend/src/api/files.py`

**Step 1: 添加废弃注释**

在 `backend/src/api/files.py` 文件顶部添加废弃说明：

```python
# backend/src/api/files.py
"""
DEPRECATED: 此 API 已废弃，请使用 Claude Code 工具进行文件操作。
- Read: 读取文件
- Glob: 搜索文件
- Grep: 内容搜索
- Edit: 编辑文件
- Write: 写入文件

保留此 API 仅用于向后兼容。
"""
from fastapi import APIRouter, HTTPException, Deprecated
from pydantic import BaseModel
from typing import List, Optional
from src.services.file_manager import list_files, read_file, write_file, upload_file

router = APIRouter()

# 在每个路由上添加 @Deprecated 装饰器
@router.get("/files")
@Deprecated("使用 Claude Code 文件工具代替")
async def list_files_api(path: str = ""):
    ...
```

**Step 2: Commit**

```bash
git add backend/src/api/files.py
git commit -m "deprecate: mark Files API as deprecated"
```

---

### Task 5: 更新 DESIGN.md

**Files:**
- Modify: `DESIGN.md`

**Step 1: 添加功能分析章节**

在 DESIGN.md 末尾添加：

```markdown
---

## Claude Code 集成分析

### 功能重叠

| MAS 设计 | Claude Code 能力 | 处理方式 |
|---------|-----------------|---------|
| FilesTab | Read/Glob/Grep/Edit/Write | ✅ 已简化 - 显示工具提示 |
| LogsTab | console + --verbose | ✅ 已简化 - 只显示业务日志 |
| Task API | Task 工具 | ✅ 标记废弃 |
| Files API | Read/Edit/Write | ✅ 标记废弃 |
| Session 持久化 | --session-id | ✅ 已集成 |
| Skills 选择 | CLI Skills | ✅ 已集成 |

### 保持的独有功能

- ResearchState 管理（科学研究流程）
- 多 Agent 状态可视化（UI 展示）
- Session UI 管理（前端交互）
- Lead Agent 协调（人机接口）
```

**Step 2: 更新 UI 组件状态表**

更新现有状态表，将 FilesTab 和 LogsTab 状态改为简化版本：

```markdown
### UI 组件
| 模块 | 功能 | 状态 |
|------|------|------|
| Sidebar | 会话列表、搜索、新建 | ✅ |
| SessionCreationPanel | Agent 配置、模板选择 | ✅ |
| ChatPanel | 消息渲染、用户输入 | ✅ |
| InspectorPanel | Graph/Agents/Files/Logs | ✅ (Files/Logs 已简化) |
| FilesTab | 文件操作提示 | ✅ (简化 - 使用 Claude Code 工具) |
| LogsTab | 业务日志查看 | ✅ (简化 - 只显示业务日志) |
| Logging System | 前后端日志、错误处理 | ✅ |
| Backend API | 基础 chat/tasks 接口 | ✅ (Files API 标记废弃) |
```

**Step 3: Commit**

```bash
git add DESIGN.md
git commit -m "docs: update DESIGN.md with Claude Code integration analysis"
```

---

## 执行顺序

1. Task 1: 创建分析文档
2. Task 2: 简化 FilesTab
3. Task 3: 简化 LogsTab
4. Task 4: 标记 Files API 废弃
5. Task 5: 更新 DESIGN.md

**Plan complete and saved to `docs/plans/2026-03-09-mas-feature-cleanup.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
