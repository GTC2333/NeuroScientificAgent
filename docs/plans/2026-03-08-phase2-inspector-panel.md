# Phase 2: Inspector Panel Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现 Inspector Panel，包含 Graph/Agents/Files/Logs 四个标签页，用于实时监控 Research Agent 的工作状态。

**Architecture:**
- 在 ChatWindow 右侧添加可折叠的 Inspector Panel
- 使用 React Flow 实现工作流可视化
- 通过 SSE 或轮询获取后端实时数据
- Tab 切换展示不同维度的监控信息

**Tech Stack:**
- React 18 + TypeScript + Vite
- React Flow (@xyflow/react) - 工作流可视化
- Tailwind CSS
- SSE (Server-Sent Events) - 实时日志

---

## Task 1: 创建 Inspector Panel 基础组件

**Files:**
- Create: `frontend/src/components/InspectorPanel.tsx`
- Modify: `frontend/src/App.tsx:18-24`

**Step 1: 创建 InspectorPanel.tsx 组件**

```tsx
import { useState } from 'react';

type Tab = 'graph' | 'agents' | 'files' | 'logs';

export function InspectorPanel() {
  const [activeTab, setActiveTab] = useState<Tab>('graph');
  const [isCollapsed, setIsCollapsed] = useState(false);

  const tabs: { id: Tab; label: string }[] = [
    { id: 'graph', label: 'Graph' },
    { id: 'agents', label: 'Agents' },
    { id: 'files', label: 'Files' },
    { id: 'logs', label: 'Logs' },
  ];

  if (isCollapsed) {
    return (
      <button
        onClick={() => setIsCollapsed(false)}
        className="w-10 bg-gray-100 border-l border-gray-200 flex flex-col items-center py-4 gap-2"
      >
        <span className="text-xs text-gray-500 rotate-90">Inspector</span>
      </button>
    );
  }

  return (
    <div className="w-80 bg-white border-l border-gray-200 flex flex-col">
      <div className="flex border-b border-gray-200">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 py-2 text-sm font-medium ${
              activeTab === tab.id
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
        <button
          onClick={() => setIsCollapsed(true)}
          className="px-2 text-gray-400 hover:text-gray-600"
        >
          ×
        </button>
      </div>
      <div className="flex-1 overflow-auto p-4">
        {/* Tab content will be added in subsequent tasks */}
        <div className="text-gray-400 text-sm">{tab.label} content</div>
      </div>
    </div>
  );
}
```

**Step 2: 修改 App.tsx 集成 InspectorPanel**

在 ChatWindow 右侧添加 InspectorPanel：

```tsx
import { InspectorPanel } from './components/InspectorPanel';

// 在 return 中修改:
<main className="flex-1 flex">
  {currentSessionId ? (
    <div className="flex-1 flex">
      <ChatWindow />
      <InspectorPanel />
    </div>
  ) : (
    <SessionCreationPanel />
  )}
</main>
```

**Step 3: 验证组件渲染**

Run: `npm run dev`
Expected: 在 ChatWindow 右侧看到 Inspector Panel，包含四个 Tab

**Step 4: Commit**

```bash
git add frontend/src/components/InspectorPanel.tsx frontend/src/App.tsx
git commit -m "feat: add InspectorPanel base component with tabs"
```

---

## Task 2: 实现 Graph Tab - 工作流可视化

**Files:**
- Modify: `frontend/src/components/InspectorPanel.tsx`

**Step 1: 安装 React Flow**

Run: `npm install @xyflow/react`

**Step 2: 更新 InspectorPanel 添加 Graph Tab 内容**

```tsx
import { ReactFlow, Background, Controls, useNodesState, useEdgesState } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

// 添加示例节点数据
const initialNodes = [
  { id: '1', position: { x: 250, y: 0 }, data: { label: 'Principal' }, type: 'input' },
  { id: '2', position: { x: 100, y: 100 }, data: { label: 'Theorist' } },
  { id: '3', position: { x: 250, y: 100 }, data: { label: 'Experimentalist' } },
  { id: '4', position: { x: 400, y: 100 }, data: { label: 'Analyst' } },
  { id: '5', position: { x: 250, y: 200 }, data: { label: 'Writer' }, type: 'output' },
];

const initialEdges = [
  { id: 'e1-2', source: '1', target: '2' },
  { id: 'e1-3', source: '1', target: '3' },
  { id: 'e1-4', source: '1', target: '4' },
  { id: 'e2-5', source: '2', target: '5' },
  { id: 'e3-5', source: '3', target: '5' },
  { id: 'e4-5', source: '4', target: '5' },
];

// 在 GraphTab 组件中:
export function GraphTab() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  return (
    <div className="h-64">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
```

**Step 3: 在 InspectorPanel 中使用 GraphTab**

```tsx
import { GraphTab } from './tabs/GraphTab';

// 在 tabs 内容区:
{activeTab === 'graph' && <GraphTab />}
```

**Step 4: 验证 Graph 渲染**

Run: `npm run dev`
Expected: 看到 Agent 工作流图，包含 Principal → Theorist/Experimentalist/Analyst → Writer

**Step 5: Commit**

```bash
git add frontend/src/components/InspectorPanel.tsx
git commit -m "feat: add Graph tab with React Flow visualization"
```

---

## Task 3: 实现 Agents Tab - 实时 Agent 状态

**Files:**
- Create: `frontend/src/components/tabs/AgentsTab.tsx`
- Modify: `frontend/src/components/InspectorPanel.tsx`

**Step 1: 创建 AgentsTab.tsx**

```tsx
import { useState, useEffect } from 'react';
import { api } from '../../services/api';
import type { Agent } from '../../types';

interface AgentStatus {
  type: string;
  name: string;
  status: 'idle' | 'active' | 'thinking';
  currentTask?: string;
}

export function AgentsTab() {
  const [agents, setAgents] = useState<AgentStatus[]>([
    { type: 'principal', name: 'Principal', status: 'idle' },
    { type: 'theorist', name: 'Theorist', status: 'idle' },
    { type: 'experimentalist', name: 'Experimentalist', status: 'idle' },
    { type: 'analyst', name: 'Analyst', status: 'idle' },
    { type: 'writer', name: 'Writer', status: 'idle' },
  ]);

  const statusColors = {
    idle: 'bg-gray-100 text-gray-600',
    active: 'bg-green-100 text-green-700',
    thinking: 'bg-blue-100 text-blue-700',
  };

  return (
    <div className="space-y-2">
      {agents.map((agent) => (
        <div
          key={agent.type}
          className="p-3 bg-gray-50 rounded-lg flex items-center justify-between"
        >
          <div>
            <div className="font-medium text-gray-900">{agent.name}</div>
            {agent.currentTask && (
              <div className="text-xs text-gray-500">{agent.currentTask}</div>
            )}
          </div>
          <span className={`px-2 py-1 rounded text-xs font-medium ${statusColors[agent.status]}`}>
            {agent.status}
          </span>
        </div>
      ))}
    </div>
  );
}
```

**Step 2: 集成到 InspectorPanel**

```tsx
import { AgentsTab } from './tabs/AgentsTab';

// 在 tabs 内容区添加:
{activeTab === 'agents' && <AgentsTab />}
```

**Step 3: 验证 Agents Tab**

Run: `npm run dev`
Expected: 看到 5 个 Agent 的状态列表

**Step 4: Commit**

```bash
git add frontend/src/components/tabs/AgentsTab.tsx frontend/src/components/InspectorPanel.tsx
git commit -m "feat: add Agents tab showing agent status"
```

---

## Task 4: 实现 Files Tab - 文件浏览器

**Files:**
- Create: `frontend/src/components/tabs/FilesTab.tsx`
- Modify: `frontend/src/components/InspectorPanel.tsx`

**Step 1: 创建 FilesTab.tsx**

```tsx
import { useState } from 'react';

interface FileItem {
  name: string;
  type: 'file' | 'folder';
  size?: number;
  modified?: string;
}

export function FilesTab() {
  const [files] = useState<FileItem[]>([
    { name: 'research/', type: 'folder' },
    { name: 'experiments/', type: 'folder' },
    { name: 'analysis/', type: 'folder' },
    { name: 'config.yaml', type: 'file', size: 1024, modified: '2024-01-15' },
    { name: 'results.json', type: 'file', size: 2048, modified: '2024-01-15' },
  ]);
  const [currentPath, setCurrentPath] = useState<string[]>([]);

  const getIcon = (type: string) => {
    return type === 'folder' ? '📁' : '📄';
  };

  return (
    <div className="space-y-2">
      {/* Breadcrumb */}
      <div className="text-xs text-gray-500 flex gap-1">
        <button onClick={() => setCurrentPath([])} className="hover:text-blue-600">
          root
        </button>
        {currentPath.map((segment, i) => (
          <span key={i}>
            /<button onClick={() => setCurrentPath(currentPath.slice(0, i + 1))} className="hover:text-blue-600">{segment}</button>
          </span>
        ))}
      </div>

      {/* File list */}
      <div className="space-y-1">
        {files.map((file) => (
          <div
            key={file.name}
            className="flex items-center gap-2 p-2 hover:bg-gray-100 rounded cursor-pointer"
          >
            <span>{getIcon(file.type)}</span>
            <span className="flex-1 text-sm text-gray-700">{file.name}</span>
            {file.size && <span className="text-xs text-gray-400">{file.size}B</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
```

**Step 2: 集成到 InspectorPanel**

```tsx
import { FilesTab } from './tabs/FilesTab';

// 在 tabs 内容区添加:
{activeTab === 'files' && <FilesTab />}
```

**Step 3: 验证 Files Tab**

Run: `npm run dev`
Expected: 看到文件/文件夹列表

**Step 4: Commit**

```bash
git add frontend/src/components/tabs/FilesTab.tsx frontend/src/components/InspectorPanel.tsx
git commit -m "feat: add Files tab with file browser"
```

---

## Task 5: 实现 Logs Tab - 执行日志

**Files:**
- Create: `frontend/src/components/tabs/LogsTab.tsx`
- Modify: `frontend/src/components/InspectorPanel.tsx`

**Step 1: 创建 LogsTab.tsx**

```tsx
import { useState, useRef, useEffect } from 'react';

interface LogEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'warn' | 'error';
  message: string;
  source?: string;
}

export function LogsTab() {
  const [logs, setLogs] = useState<LogEntry[]>([
    { id: '1', timestamp: '10:30:15', level: 'info', message: 'Session started', source: 'system' },
    { id: '2', timestamp: '10:30:16', level: 'info', message: 'Principal agent initialized', source: 'principal' },
    { id: '3', timestamp: '10:30:18', level: 'info', message: 'Task: literature review', source: 'principal' },
  ]);
  const [filter, setFilter] = useState<'all' | 'info' | 'warn' | 'error'>('all');
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const levelColors = {
    info: 'text-blue-600',
    warn: 'text-yellow-600',
    error: 'text-red-600',
  };

  const filteredLogs = filter === 'all' ? logs : logs.filter(l => l.level === filter);

  return (
    <div className="flex flex-col h-full">
      {/* Filter buttons */}
      <div className="flex gap-2 mb-2">
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
      </div>

      {/* Log entries */}
      <div className="flex-1 overflow-auto font-mono text-xs space-y-1">
        {filteredLogs.map((log) => (
          <div key={log.id} className="flex gap-2">
            <span className="text-gray-400">{log.timestamp}</span>
            <span className={`font-medium ${levelColors[log.level]}`}>[{log.level.toUpperCase()}]</span>
            {log.source && <span className="text-gray-500">[{log.source}]</span>}
            <span className="text-gray-700">{log.message}</span>
          </div>
        ))}
        <div ref={logsEndRef} />
      </div>
    </div>
  );
}
```

**Step 2: 集成到 InspectorPanel**

```tsx
import { LogsTab } from './tabs/LogsTab';

// 在 tabs 内容区添加:
{activeTab === 'logs' && <LogsTab />}
```

**Step 3: 验证 Logs Tab**

Run: `npm run dev`
Expected: 看到日志列表，支持过滤

**Step 4: Commit**

```bash
git add frontend/src/components/tabs/LogsTab.tsx frontend/src/components/InspectorPanel.tsx
git commit -m "feat: add Logs tab with filtering"
```

---

## Task 6: 添加后端 API 支持 (可选 - 后续迭代)

**Files:**
- Create: `backend/src/api/files.py`
- Create: `backend/src/api/logs.py`

**说明:** 当前使用模拟数据，后续迭代可添加真实 API:
- `GET /api/files` - 获取项目文件列表
- `GET /api/logs` - 获取执行日志

---

## 总结

完成 Phase 2 后，Inspector Panel 将提供:

1. **Graph Tab** - 使用 React Flow 可视化 Agent 工作流
2. **Agents Tab** - 显示 5 个 Agent 的实时状态
3. **Files Tab** - 项目文件浏览器
4. **Logs Tab** - 执行日志查看器 (支持过滤)

**Estimated Total Tasks:** 6 tasks
**Estimated Time:** 30-45 minutes
