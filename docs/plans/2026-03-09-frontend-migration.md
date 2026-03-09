# Frontend Migration to claudecodeui Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 MAS 系统的前端替换为 claudecodeui，同时保留现有的后端服务和 agent 逻辑

**Architecture:**
- 保留现有 FastAPI 后端 (`backend/src/api/*`)
- 将 claudecodeui 作为新的前端基础
- 新增 MAS 专用组件：技能选择面板、Agent 角色切换、研究任务面板
- 通过 API 集成现有后端服务

**Tech Stack:**
- 前端: React (JavaScript) + Tailwind CSS + Vite
- 后端: FastAPI (保留)
- 通信: REST API + WebSocket

---

## 前置条件

确保后端服务正在运行:
```bash
cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system
./start.sh
```

---

### Task 1: 克隆并设置 claudecodeui

**Files:**
- Create: `frontend/claudecodeui/` (从 `/tmp/claudecodeui` 复制)

**Step 1: 复制 claudecodeui 到项目**

```bash
cp -r /tmp/claudecodeui /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/frontend/claudecodeui
```

**Step 2: 安装依赖**

```bash
cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/frontend/claudecodeui
npm install
```

**Step 3: 验证开发服务器启动**

```bash
npm run dev
# 预期: http://localhost:3001 可访问
```

**Step 4: Commit**

```bash
git add frontend/claudecodeui/
git commit -m "feat: add claudecodeui as new frontend base"
```

---

### Task 2: 配置代理连接 MAS 后端

**Files:**
- Modify: `frontend/claudecodeui/vite.config.js`

**Step 1: 添加 API 代理配置**

修改 `frontend/claudecodeui/vite.config.js`:

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3001,
    proxy: {
      '/api': {
        target: 'http://localhost:9000',
        changeOrigin: true,
      },
    },
  },
})
```

**Step 2: 验证代理工作**

```bash
# 启动后端 (如果未运行)
cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system && ./start.sh

# 启动前端
cd frontend/claudecodeui && npm run dev

# 测试 API
curl http://localhost:3001/api/agents
# 预期: 返回 agent 列表
```

**Step 3: Commit**

```bash
git add frontend/claudecodeui/vite.config.js
git commit -f eixt: "feat: add API proxy to MAS backend"
```

---

### Task 3: 创建 MAS API 服务层

**Files:**
- Create: `frontend/claudecodeui/src/services/mas-api.js`

**Step 1: 创建 API 服务**

```javascript
// src/services/mas-api.js
const API_BASE = '/api';

export const masApi = {
  // Chat with agents
  async sendMessage(message, agentType = 'principal', sessionId = null, skills = []) {
    const response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        agent_type: agentType,
        session_id: sessionId,
        selected_skills: skills,
      }),
    });
    return response.json();
  },

  // Get available agents
  async getAgents() {
    const response = await fetch(`${API_BASE}/agents`);
    return response.json();
  },

  // Get available skills
  async getSkills() {
    const response = await fetch(`${API_BASE}/skills`);
    return response.json();
  },

  // Get tasks
  async getTasks(status) {
    const url = status ? `${API_BASE}/tasks?status=${status}` : `${API_BASE}/tasks`;
    const response = await fetch(url);
    return response.json();
  },

  // Create task
  async createTask(name, description, agent) {
    const response = await fetch(`${API_BASE}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description, agent }),
    });
    return response.json();
  },
};
```

**Step 2: Commit**

```bash
git add frontend/claudecodeui/src/services/mas-api.js
git commit -m "feat: add MAS API service layer"
```

---

### Task 4: 创建 MAS 聊天组件

**Files:**
- Create: `frontend/claudecodeui/src/components/mas-chat/MasChat.jsx`

**Step 1: 创建 MAS 专用聊天组件**

```jsx
// src/components/mas-chat/MasChat.jsx
import { useState, useEffect, useRef } from 'react';
import { masApi } from '../../services/mas-api';

const AGENT_ROLES = [
  { id: 'principal', name: 'Principal Investigator', icon: '👑' },
  { id: 'theorist', name: 'Theorist', icon: '📚' },
  { id: 'experimentalist', name: 'Experimentalist', icon: '🔬' },
  { id: 'analyst', name: 'Analyst', icon: '📊' },
  { id: 'writer', name: 'Writer', icon: '✍️' },
];

export function MasChat({ sessionId }) {
  const [message, setMessage] = useState('');
  const [agentType, setAgentType] = useState('principal');
  const [selectedSkills, setSelectedSkills] = useState([]);
  const [skills, setSkills] = useState([]);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    masApi.getSkills().then(setSkills);
  }, []);

  const sendMessage = async () => {
    if (!message.trim() || loading) return;

    const userMsg = { role: 'user', content: message };
    setMessages(prev => [...prev, userMsg]);
    setMessage('');
    setLoading(true);

    try {
      const response = await masApi.sendMessage(message, agentType, sessionId, selectedSkills);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.reply,
        agent: response.agent_type,
      }]);
    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'error',
        content: `Error: ${error.message}`,
      }]);
    } finally {
      setLoading(false);
    }
  };

  const toggleSkill = (skillId) => {
    setSelectedSkills(prev =>
      prev.includes(skillId)
        ? prev.filter(s => s !== skillId)
        : [...prev, skillId]
    );
  };

  return (
    <div className="flex flex-col h-full">
      {/* Agent Selection */}
      <div className="flex gap-2 p-4 border-b border-gray-700">
        {AGENT_ROLES.map(agent => (
          <button
            key={agent.id}
            onClick={() => setAgentType(agent.id)}
            className={`px-3 py-1 rounded-lg text-sm ${
              agentType === agent.id
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            {agent.icon} {agent.name}
          </button>
        ))}
      </div>

      {/* Skills Selection */}
      {skills.length > 0 && (
        <div className="flex gap-2 p-2 border-b border-gray-700 flex-wrap">
          {skills.map(skill => (
            <button
              key={skill.id || skill.name}
              onClick={() => toggleSkill(skill.id || skill.name)}
              className={`px-2 py-1 rounded text-xs ${
                selectedSkills.includes(skill.id || skill.name)
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {skill.name}
            </button>
          ))}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[70%] rounded-lg p-3 ${
              msg.role === 'user'
                ? 'bg-blue-600 text-white'
                : msg.role === 'error'
                ? 'bg-red-600 text-white'
                : 'bg-gray-700 text-gray-100'
            }`}>
              {msg.agent && <span className="text-xs opacity-75">[{msg.agent}] </span>}
              {msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-700 rounded-lg p-3">
              <span className="animate-pulse">Thinking...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-700">
        <div className="flex gap-2">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
            placeholder="Ask the research team..."
            className="flex-1 bg-gray-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={sendMessage}
            disabled={loading || !message.trim()}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-lg px-4 py-2"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
```

**Step 2: 创建组件索引**

```jsx
// src/components/mas-chat/index.js
export { MasChat } from './MasChat';
```

**Step 3: Commit**

```bash
git add frontend/claudecodeui/src/components/mas-chat/
git commit -m "feat: add MAS chat component with agent selection"
```

---

### Task 5: 集成 MasChat 到主应用

**Files:**
- Modify: `frontend/claudecodeui/src/App.jsx`

**Step 1: 修改 App.jsx 添加 MAS 聊天面板**

```jsx
// src/App.jsx - 关键修改
import { MasChat } from './components/mas-chat';

function App() {
  // ... existing state ...

  const [showMasChat, setShowMasChat] = useState(false);

  return (
    <div className={`app ${isFullScreen ? 'fullscreen' : ''}`}>
      {/* ... existing layout ... */}

      {/* MAS Chat Panel - 可以作为侧边栏或独立面板 */}
      {showMasChat && (
        <div className="mas-chat-panel" style={{ width: '400px', borderLeft: '1px solid #374151' }}>
          <MasChat sessionId={sessionId} />
        </div>
      )}
    </div>
  );
}
```

**Step 2: 添加切换按钮到侧边栏**

在侧边栏添加一个按钮来切换 MAS 聊天面板:

```jsx
// 在侧边栏组件中添加
<button
  onClick={() => setShowMasChat(!showMasChat)}
  className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-700"
>
  <span>🔬</span>
  <span>MAS Research</span>
</button>
```

**Step 3: 测试集成**

```bash
# 重启前端
cd frontend/claudecodeui && npm run dev

# 验证:
# 1. 访问 http://localhost:3001
# 2. 点击 MAS Research 按钮
# 3. 选择 Agent 角色 (Principal, Theorist, etc.)
# 4. 发送消息测试 API 调用
```

**Step 4: Commit**

```bash
git add frontend/claudecodeui/src/App.jsx
git commit -m "feat: integrate MasChat component into main app"
```

---

### Task 6: 添加任务面板 (可选扩展)

**Files:**
- Create: `frontend/claudecodeui/src/components/mas-tasks/MasTaskPanel.jsx`

**Step 1: 创建任务面板组件**

```jsx
// src/components/mas-tasks/MasTaskPanel.jsx
import { useState, useEffect } from 'react';
import { masApi } from '../../services/mas-api';

export function MasTaskPanel() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);

  const loadTasks = async () => {
    setLoading(true);
    const data = await masApi.getTasks();
    setTasks(data);
    setLoading(false);
  };

  useEffect(() => {
    loadTasks();
    // 定期刷新
    const interval = setInterval(loadTasks, 5000);
    return () => clearInterval(interval);
  }, []);

  const createTask = async () => {
    const name = prompt('Task name:');
    if (!name) return;
    const description = prompt('Description:');
    const agent = prompt('Agent (principal/theorist/experimentalist/analyst/writer):') || 'principal';

    await masApi.createTask(name, description, agent);
    loadTasks();
  };

  return (
    <div className="p-4">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold">Research Tasks</h2>
        <button
          onClick={createTask}
          className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded"
        >
          + New Task
        </button>
      </div>

      {loading ? (
        <p>Loading...</p>
      ) : tasks.length === 0 ? (
        <p className="text-gray-500">No tasks yet</p>
      ) : (
        <ul className="space-y-2">
          {tasks.map(task => (
            <li key={task.id} className="bg-gray-700 rounded-lg p-3">
              <div className="font-medium">{task.name}</div>
              <div className="text-sm text-gray-400">{task.description}</div>
              <div className="flex gap-2 mt-2">
                <span className="text-xs bg-gray-600 px-2 py-1 rounded">{task.agent}</span>
                <span className={`text-xs px-2 py-1 rounded ${
                  task.status === 'completed' ? 'bg-green-600' :
                  task.status === 'failed' ? 'bg-red-600' : 'bg-yellow-600'
                }`}>
                  {task.status}
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

**Step 2: 集成到 App**

在 App.jsx 中添加任务面板的切换和显示。

**Step 3: Commit**

```bash
git add frontend/claudecodeui/src/components/mas-tasks/
git commit -m "feat: add MAS task panel"
```

---

### Task 7: 清理旧前端 (可选)

**Files:**
- Delete: `frontend/src/`
- Delete: `frontend/index.html`
- Delete: `frontend/package.json`

**Step 1: 确认新前端工作正常后再删除旧代码**

```bash
# 验证新前端完全可用后再执行
rm -rf frontend/src/ frontend/index.html frontend/package.json
```

**Step 2: Commit**

```bash
git add -A
git commit -m "refactor: remove old frontend, use claudecodeui"
```

---

## 验证清单

完成所有任务后验证:

- [ ] `http://localhost:3001` 可访问
- [ ] 侧边栏有 MAS Research 按钮
- [ ] 点击后显示 Agent 选择 (Principal, Theorist, etc.)
- [ ] 选择技能后发送消息到 `/api/chat`
- [ ] 后端返回正确的 agent 响应
- [ ] 响应式设计在移动端正常

---

## 后续扩展

1. **文件浏览器集成**: 使用现有的 `file-tree` 组件显示研究文件
2. **Terminal 集成**: 添加研究任务执行终端
3. **Git 面板**: 显示实验代码的版本历史
4. **会话管理**: 保存和恢复研究会话

---

## 回滚计划

如果出现问题:
```bash
# 恢复旧前端
git checkout HEAD~1 -- frontend/
```
