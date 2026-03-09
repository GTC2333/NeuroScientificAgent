# MAS 系统功能增强实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** 完善 MAS 系统的前端 UI/UX、会话持久化、后端 API 扩展和错误处理监控能力

**Architecture:**
- 前端: React + Zustand + React Router (已有基础架构)
- 后端: FastAPI + Python (已有基础架构)
- 持久化: localStorage (前端) + JSON 文件 (后端)

**Tech Stack:**
- React 18 + TypeScript
- Zustand (状态管理)
- React Router (路由)
- Tailwind CSS (样式)
- FastAPI (后端)
- Python JSON 文件存储

---

## 功能概览

### 1. 前端 UI/UX 增强
- 添加 Settings 和 Help 标签页
- 会话历史侧边栏列表
- 文件上传组件

### 2. 会话持久化
- 前端: 已有 localStorage 持久化 (Zustand persist)
- 后端: 添加会话存储 API，支持服务器端保存和恢复

### 3. 后端 API 扩展
- 文件操作 API (上传/下载/列表)
- 任务管理 API
- 会话管理 API
- 系统健康检查增强

### 4. 错误处理与监控
- 前端: Error Boundary + 通知组件
- 后端: 增强日志 + 错误处理中间件

---

## 任务列表

### Task 1: 添加前端 Settings 和 Help 标签页

**Files:**
- Modify: `frontend/src/components/InspectorPanel.tsx`
- Create: `frontend/src/components/tabs/SettingsTab.tsx`
- Create: `frontend/src/components/tabs/HelpTab.tsx`

**Step 1: 创建 SettingsTab.tsx**

```tsx
// frontend/src/components/tabs/SettingsTab.tsx
import { useState } from 'react';

export function SettingsTab() {
  const [apiEndpoint, setApiEndpoint] = useState('http://localhost:9000');
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [autoSave, setAutoSave] = useState(true);

  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-gray-800">Settings</h3>

      <div className="space-y-3">
        <div>
          <label className="block text-sm font-medium text-gray-700">API Endpoint</label>
          <input
            type="text"
            value={apiEndpoint}
            onChange={(e) => setApiEndpoint(e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Theme</label>
          <select
            value={theme}
            onChange={(e) => setTheme(e.target.value as 'light' | 'dark')}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm"
          >
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </div>

        <div className="flex items-center">
          <input
            id="auto-save"
            type="checkbox"
            checked={autoSave}
            onChange={(e) => setAutoSave(e.target.checked)}
            className="h-4 w-4 rounded border-gray-300 text-blue-600"
          />
          <label htmlFor="auto-save" className="ml-2 block text-sm text-gray-700">
            Auto-save sessions
          </label>
        </div>
      </div>
    </div>
  );
}
```

**Step 2: 创建 HelpTab.tsx**

```tsx
// frontend/src/components/tabs/HelpTab.tsx
export function HelpTab() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-gray-800">Help</h3>

      <div className="space-y-3 text-sm">
        <div>
          <h4 className="font-medium text-gray-700">Quick Start</h4>
          <p className="text-gray-600 mt-1">
            Create a new session, select agents and skills, then start chatting.
          </p>
        </div>

        <div>
          <h4 className="font-medium text-gray-700">Agent Roles</h4>
          <ul className="list-disc list-inside text-gray-600 mt-1 space-y-1">
            <li><strong>Principal:</strong> Project coordination</li>
            <li><strong>Theorist:</strong> Hypothesis generation</li>
            <li><strong>Experimentalist:</strong> Experiment design</li>
            <li><strong>Analyst:</strong> Data analysis</li>
            <li><strong>Writer:</strong> Documentation</li>
          </ul>
        </div>

        <div>
          <h4 className="font-medium text-gray-700">Keyboard Shortcuts</h4>
          <ul className="list-disc list-inside text-gray-600 mt-1 space-y-1">
            <li><kbd>Ctrl</kbd> + <kbd>Enter</kbd>: Send message</li>
            <li><kbd>Ctrl</kbd> + <kbd>N</kbd>: New session</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
```

**Step 3: 修改 InspectorPanel.tsx 添加新标签页**

```tsx
// frontend/src/components/InspectorPanel.tsx
import { SettingsTab } from './tabs/SettingsTab';
import { HelpTab } from './tabs/HelpTab';

type Tab = 'graph' | 'agents' | 'files' | 'logs' | 'settings' | 'help';

const tabs: { id: Tab; label: string }[] = [
  { id: 'graph', label: 'Graph' },
  { id: 'agents', label: 'Agents' },
  { id: 'files', label: 'Files' },
  { id: 'logs', label: 'Logs' },
  { id: 'settings', label: 'Settings' },
  { id: 'help', label: 'Help' },
];

// 在 render 部分添加:
{activeTab === 'settings' && <SettingsTab />}
{activeTab === 'help' && <HelpTab />}
```

**Step 4: 测试**

Run: `cd frontend && npm run dev`
Expected: 可以在 InspectorPanel 中看到 Settings 和 Help 标签页

---

### Task 2: 会话历史侧边栏列表

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`

**Step 1: 修改 Sidebar.tsx**

```tsx
// frontend/src/components/Sidebar.tsx
import { useStore, SessionStore } from '../store/useStore';
import { useNavigate, useParams } from 'react-router-dom';

export function Sidebar() {
  const sessions = useStore((state: SessionStore) => state.sessions);
  const currentSessionId = useStore((state: SessionStore) => state.currentSessionId);
  const createSession = useStore((state: SessionStore) => state.createSession);
  const deleteSession = useStore((state: SessionStore) => state.deleteSession);
  const navigate = useNavigate();
  const { sessionId } = useParams();

  const handleNewSession = () => {
    const id = createSession('New Session', ['principal'], []);
    navigate(`/${id}`);
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="w-64 bg-gray-100 border-r border-gray-200 flex flex-col">
      <div className="p-4">
        <button
          onClick={handleNewSession}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors"
        >
          + New Session
        </button>
      </div>

      <div className="flex-1 overflow-auto">
        <div className="px-4 py-2">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Sessions ({sessions.length})
          </h3>
        </div>

        <div className="space-y-1 px-2">
          {sessions.map((session) => (
            <div
              key={session.id}
              className={`group flex items-center justify-between p-2 rounded-lg cursor-pointer ${
                session.id === currentSessionId
                  ? 'bg-blue-100 text-blue-800'
                  : 'hover:bg-gray-200 text-gray-700'
              }`}
              onClick={() => navigate(`/${session.id}`)}
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{session.title}</p>
                <p className="text-xs text-gray-500">{formatDate(session.updatedAt)}</p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  deleteSession(session.id);
                  if (session.id === currentSessionId) {
                    navigate('/');
                  }
                }}
                className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-100 rounded text-red-600"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
```

**Step 2: 测试**

Expected: 侧边栏显示所有会话列表，点击可切换会话，hover 显示删除按钮

---

### Task 3: 后端会话持久化 API

**Files:**
- Create: `backend/src/api/sessions.py`
- Create: `backend/src/services/session_store.py`
- Modify: `backend/src/main.py` (注册路由)

**Step 1: 创建 session_store.py**

```python
# backend/src/services/session_store.py
import json
import os
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

SESSIONS_DIR = Path(__file__).parent.parent.parent.parent / "data" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

def _get_session_file(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"

def save_session(session_id: str, data: Dict) -> bool:
    """Save session to file"""
    try:
        file_path = _get_session_file(session_id)
        data['saved_at'] = datetime.now().isoformat()
        file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return True
    except Exception as e:
        print(f"Failed to save session: {e}")
        return False

def load_session(session_id: str) -> Optional[Dict]:
    """Load session from file"""
    try:
        file_path = _get_session_file(session_id)
        if file_path.exists():
            return json.loads(file_path.read_text())
        return None
    except Exception as e:
        print(f"Failed to load session: {e}")
        return None

def list_sessions() -> List[Dict]:
    """List all saved sessions"""
    sessions = []
    for file_path in SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(file_path.read_text())
            sessions.append({
                'id': data.get('id'),
                'title': data.get('title'),
                'createdAt': data.get('createdAt'),
                'updatedAt': data.get('updatedAt'),
                'saved_at': data.get('saved_at'),
            })
        except Exception:
            continue
    return sorted(sessions, key=lambda x: x.get('updatedAt', ''), reverse=True)

def delete_session(session_id: str) -> bool:
    """Delete session file"""
    try:
        file_path = _get_session_file(session_id)
        if file_path.exists():
            file_path.unlink()
        return True
    except Exception as e:
        print(f"Failed to delete session: {e}")
        return False
```

**Step 2: 创建 sessions.py API**

```python
# backend/src/api/sessions.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from src.services.session_store import save_session, load_session, list_sessions, delete_session

router = APIRouter()

class SessionSaveRequest(BaseModel):
    session_id: str
    title: str
    agents: List[str]
    skills: List[str]
    messages: List[Dict[str, Any]]
    createdAt: str
    updatedAt: str

class SessionResponse(BaseModel):
    success: bool
    session_id: Optional[str] = None

@router.post("/sessions")
async def save_session_endpoint(request: SessionSaveRequest):
    """Save session to backend"""
    data = request.dict()
    success = save_session(request.session_id, data)
    return SessionResponse(success=success, session_id=request.session_id if success else None)

@router.get("/sessions")
async def list_sessions_endpoint():
    """List all saved sessions"""
    sessions = list_sessions()
    return {"sessions": sessions}

@router.get("/sessions/{session_id}")
async def get_session_endpoint(session_id: str):
    """Get a specific session"""
    session = load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.delete("/sessions/{session_id}")
async def delete_session_endpoint(session_id: str):
    """Delete a session"""
    success = delete_session(session_id)
    return SessionResponse(success=success)
```

**Step 3: 注册路由**

```python
# backend/src/main.py
from src.api import sessions  # 添加这行

app.include_router(sessions.router)  # 添加这行
```

**Step 4: 测试**

Run: `curl http://localhost:9000/sessions`
Expected: 返回会话列表

---

### Task 4: 文件操作 API

**Files:**
- Create: `backend/src/api/files.py`
- Create: `backend/src/services/file_manager.py`

**Step 1: 创建 file_manager.py**

```python
# backend/src/services/file_manager.py
import os
import shutil
from pathlib import Path
from typing import List, Dict
import base64

WORKSPACE_DIR = Path(__file__).parent.parent.parent.parent / "temp_workspace"
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

def list_files(path: str = "") -> List[Dict]:
    """List files in workspace"""
    target_dir = WORKSPACE_DIR / path if path else WORKSPACE_DIR
    if not target_dir.exists():
        return []

    files = []
    for item in target_dir.iterdir():
        files.append({
            "name": item.name,
            "type": "directory" if item.is_dir() else "file",
            "size": item.stat().st_size if item.is_file() else 0,
            "modified": item.stat().st_mtime,
        })
    return sorted(files, key=lambda x: (x["type"], x["name"]))

def read_file(path: str) -> str:
    """Read file content"""
    file_path = WORKSPACE_DIR / path
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return file_path.read_text(encoding='utf-8')

def write_file(path: str, content: str) -> bool:
    """Write file content"""
    try:
        file_path = WORKSPACE_DIR / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding='utf-8')
        return True
    except Exception as e:
        print(f"Failed to write file: {e}")
        return False

def upload_file(path: str, content: str) -> bool:
    """Upload file (content base64 encoded)"""
    try:
        file_path = WORKSPACE_DIR / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        data = base64.b64decode(content)
        file_path.write_bytes(data)
        return True
    except Exception as e:
        print(f"Failed to upload file: {e}")
        return False
```

**Step 2: 创建 files.py API**

```python
# backend/src/api/files.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from src.services.file_manager import list_files, read_file, write_file, upload_file

router = APIRouter()

class FileWriteRequest(BaseModel):
    path: str
    content: str

class FileUploadRequest(BaseModel):
    path: str
    content: str  # base64 encoded

@router.get("/files")
async def list_files_api(path: str = ""):
    """List files in workspace"""
    files = list_files(path)
    return {"files": files, "path": path}

@router.get("/files/{path:path}")
async def read_file_api(path: str):
    """Read file content"""
    try:
        content = read_file(path)
        return {"path": path, "content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")

@router.post("/files")
async def write_file_api(request: FileWriteRequest):
    """Write file content"""
    success = write_file(request.path, request.content)
    return {"success": success, "path": request.path}

@router.post("/files/upload")
async def upload_file_api(request: FileUploadRequest):
    """Upload file"""
    success = upload_file(request.path, request.content)
    return {"success": success, "path": request.path}
```

**Step 3: 注册路由**

```python
# backend/src/main.py
from src.api import files

app.include_router(files.router)
```

**Step 4: 测试**

Run: `curl http://localhost:9000/files`
Expected: 返回文件列表

---

### Task 5: 前端错误边界与通知组件

**Files:**
- Create: `frontend/src/components/ErrorBoundary.tsx`
- Create: `frontend/src/components/Notification.tsx`
- Modify: `frontend/src/main.tsx`

**Step 1: 创建 ErrorBoundary.tsx**

```tsx
// frontend/src/components/ErrorBoundary.tsx
import { Component, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <h3 className="text-red-800 font-semibold">Something went wrong</h3>
          <p className="text-red-600 text-sm mt-2">
            {this.state.error?.message || 'An unexpected error occurred'}
          </p>
          <button
            onClick={() => this.setState({ hasError: false })}
            className="mt-3 px-3 py-1 bg-red-100 text-red-700 rounded hover:bg-red-200"
          >
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
```

**Step 2: 创建 Notification.tsx**

```tsx
// frontend/src/components/Notification.tsx
import { useState, useEffect } from 'react';

export type NotificationType = 'success' | 'error' | 'warning' | 'info';

interface Notification {
  id: string;
  type: NotificationType;
  message: string;
}

let notificationCallback: ((notification: Omit<Notification, 'id'>) => void) | null = null;

export function showNotification(type: NotificationType, message: string) {
  if (notificationCallback) {
    notificationCallback({ type, message });
  }
}

export function NotificationContainer() {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  useEffect(() => {
    notificationCallback = (notification) => {
      const id = Math.random().toString(36).substr(2, 9);
      setNotifications((prev) => [...prev, { ...notification, id }]);

      // Auto dismiss after 5 seconds
      setTimeout(() => {
        setNotifications((prev) => prev.filter((n) => n.id !== id));
      }, 5000);
    };

    return () => {
      notificationCallback = null;
    };
  }, []);

  const getStyles = (type: NotificationType) => {
    switch (type) {
      case 'success': return 'bg-green-50 border-green-200 text-green-800';
      case 'error': return 'bg-red-50 border-red-200 text-red-800';
      case 'warning': return 'bg-yellow-50 border-yellow-200 text-yellow-800';
      case 'info': return 'bg-blue-50 border-blue-200 text-blue-800';
    }
  };

  if (notifications.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2">
      {notifications.map((notification) => (
        <div
          key={notification.id}
          className={`px-4 py-3 rounded-lg border shadow-lg ${getStyles(notification.type)}`}
        >
          <p className="text-sm">{notification.message}</p>
        </div>
      ))}
    </div>
  );
}
```

**Step 3: 修改 main.tsx 添加 ErrorBoundary**

```tsx
// frontend/src/main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { ErrorBoundary } from './components/ErrorBoundary';
import { NotificationContainer } from './components/Notification';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <App />
        <NotificationContainer />
      </BrowserRouter>
    </ErrorBoundary>
  </React.StrictMode>
);
```

**Step 4: 测试**

Expected: 组件出错时显示错误边界 UI，正常操作时显示通知

---

### Task 6: 后端增强日志与错误处理

**Files:**
- Modify: `backend/src/main.py`
- Modify: `backend/src/services/claude_code.py`

**Step 1: 添加错误处理中间件**

```python
# backend/src/main.py
import logging
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 添加错误处理中间件
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": str(exc),
            "type": type(exc).__name__,
            "path": str(request.url)
        }
    )
```

**Step 2: 增强 Claude Code 服务的日志**

```python
# backend/src/services/claude_code.py
# 在 invoke 方法中添加更详细的日志
def invoke(self, message: str, agent_type: str = "principal",
           model: str = None, session_id: str = None,
           skills: List[str] = None) -> str:
    """Invoke Claude Code CLI and return response"""
    logger.info(f"[ClaudeCode] ===== INVOCATION START =====")
    logger.info(f"[ClaudeCode] Agent: {agent_type}, Model: {model}, Session: {session_id}")
    logger.info(f"[ClaudeCode] Skills: {skills}")
    logger.info(f"[ClaudeCode] Message: {message[:200]}...")

    # ... 原有代码 ...

    if result.returncode != 0:
        logger.error(f"[ClaudeCode] ===== INVOCATION FAILED =====")
        logger.error(f"[ClaudeCode] Error: {result.stderr[:500] if result.stderr else 'Unknown'}")
        # 记录完整错误用于调试
        logger.error(f"[ClaudeCode] Full stderr: {result.stderr}")
    else:
        logger.info(f"[ClaudeCode] ===== INVOCATION SUCCESS =====")
        logger.info(f"[ClaudeCode] Response length: {len(result.stdout)}")

    return result.stdout.strip() if result.returncode == 0 else f"Error: {result.stderr}"
```

**Step 3: 测试**

Run: `curl http://localhost:9000/nonexistent`
Expected: 返回格式化的错误 JSON

---

### Task 7: 任务管理 API 增强

**Files:**
- Modify: `backend/src/api/tasks.py`

**Step 1: 扩展 tasks.py**

```python
# backend/src/api/tasks.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Task(BaseModel):
    id: str
    name: str
    description: str
    agent: str
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = []
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str

# In-memory task storage (replace with DB in production)
tasks_db: dict[str, Task] = {}

@router.get("/tasks")
async def list_tasks():
    """List all tasks"""
    return {"tasks": list(tasks_db.values())}

@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get a specific task"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks_db[task_id]

@router.post("/tasks")
async def create_task(task: Task):
    """Create a new task"""
    tasks_db[task.id] = task
    return task

@router.patch("/tasks/{task_id}")
async def update_task(task_id: str, status: TaskStatus, result: Optional[str] = None, error: Optional[str] = None):
    """Update task status"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks_db[task_id]
    task.status = status
    task.updated_at = datetime.now().isoformat()
    if result:
        task.result = result
    if error:
        task.error = error

    return task

@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a task"""
    if task_id in tasks_db:
        del tasks_db[task_id]
    return {"success": True}
```

**Step 2: 测试**

Run: `curl http://localhost:9000/tasks`
Expected: 返回任务列表

---

### Task 8: 端到端集成测试

**Step 1: 测试完整流程**

```bash
# 1. 启动后端
cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system
./start.sh &

# 2. 测试 API 端点
curl http://localhost:9000/sessions
curl http://localhost:9000/files
curl http://localhost:9000/tasks
curl http://localhost:9000/health

# 3. 测试前端
# 打开 http://localhost:9001
# - 创建新会话
# - 检查侧边栏会话列表
# - 打开 Settings 和 Help 标签页
```

**Step 2: 验证功能**

- [ ] Settings 标签页显示并可修改配置
- [ ] Help 标签页显示帮助信息
- [ ] 侧边栏显示所有会话
- [ ] 可以创建、删除会话
- [ ] API 返回正确的 JSON
- [ ] 错误边界捕获异常并显示友好 UI

---

## 执行顺序

1. **Task 1** (Settings/Help 标签页) - 前端基础 UI
2. **Task 2** (会话历史列表) - 前端交互
3. **Task 3** (会话持久化 API) - 后端基础
4. **Task 4** (文件操作 API) - 后端扩展
5. **Task 5** (错误边界) - 前端稳定性
6. **Task 6** (后端日志) - 后端稳定性
7. **Task 7** (任务管理 API) - 后端扩展
8. **Task 8** (端到端测试) - 验证

---

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 本地存储空间不足 | 定期清理旧会话 |
| API 响应慢 | 添加超时和缓存 |
| 前端错误影响体验 | Error Boundary 隔离 |
| 文件上传安全 | 限制文件类型和大小 |
