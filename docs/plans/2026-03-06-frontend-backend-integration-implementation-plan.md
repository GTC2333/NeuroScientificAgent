# Frontend-Backend Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build React frontend that connects to FastAPI backend, enabling users to interact with Claude Code agents through a temp_workspace directory.

**Architecture:** React SPA (Vite + TypeScript + Tailwind) on port 3000 connects to FastAPI on port 8000 via CORS. Claude Code operates in temp_workspace/ directory.

**Tech Stack:** React 18, TypeScript, Vite, Tailwind CSS, Axios, FastAPI

---

## Phase 1: Project Setup

### Task 1: Create React project with Vite

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`

**Step 1: Write package.json**

```json
{
  "name": "mas-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.16",
    "postcss": "^8.4.32",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0"
  }
}
```

**Step 2: Write vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

**Step 3: Write tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

**Step 4: Write tsconfig.node.json**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

**Step 5: Write tailwind.config.js**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

**Step 6: Write postcss.config.js**

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

**Step 7: Write index.html**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>MAS - Research Agent System</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

**Step 8: Commit**

```bash
cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/frontend
git add package.json vite.config.ts tsconfig.json tsconfig.node.json tailwind.config.js postcss.config.js index.html
git commit -m "feat: scaffold React project with Vite + TypeScript + Tailwind"
```

---

### Task 2: Install dependencies

**Step 1: Install npm packages**

Run: `cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/frontend && npm install`

Expected: Dependencies installed successfully

**Step 2: Commit**

```bash
git add package-lock.json
git commit -m "chore: install npm dependencies"
```

---

## Phase 2: Core Types and API

### Task 3: Create TypeScript types

**Files:**
- Create: `frontend/src/types/index.ts`

**Step 1: Write types/index.ts**

```typescript
export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
}

export interface ChatRequest {
  message: string;
  agent_type: AgentType;
  history?: Message[];
}

export interface ChatResponse {
  reply: string;
  agent_type: string;
  task_id?: string;
}

export type AgentType = 'principal' | 'theorist' | 'experimentalist' | 'analyst' | 'writer';

export interface Agent {
  type: AgentType;
  name: string;
  description: string;
}

export interface Skill {
  name: string;
  description: string;
  category: string;
  path: string;
}

export interface Task {
  id: string;
  name: string;
  description: string;
  agent: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  dependencies: string[];
  result?: string;
  created_at: string;
  updated_at: string;
}
```

**Step 2: Commit**

```bash
git add src/types/index.ts
git commit -m "feat: add TypeScript interfaces"
```

---

### Task 4: Create API service

**Files:**
- Create: `frontend/src/services/api.ts`

**Step 1: Write services/api.ts**

```typescript
import axios from 'axios';
import type { ChatRequest, ChatResponse, Agent, Skill, Task } from '../types';

const API_BASE = '/api';

export const api = {
  // Chat
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await axios.post<ChatResponse>(`${API_BASE}/chat`, request);
    return response.data;
  },

  async *streamMessage(request: ChatRequest): AsyncGenerator<string> {
    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });

    const reader = response.body?.getReader();
    if (!reader) return;

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.text) yield data.text;
            if (data.done) return;
          } catch {
            // Skip invalid JSON
          }
        }
      }
    }
  },

  // Agents
  async getAgents(): Promise<Agent[]> {
    const response = await axios.get<Agent[]>(`${API_BASE}/agents`);
    return response.data;
  },

  // Skills
  async getSkills(): Promise<Skill[]> {
    const response = await axios.get<Skill[]>(`${API_BASE}/skills`);
    return response.data;
  },

  // Tasks
  async getTasks(status?: string): Promise<Task[]> {
    const url = status ? `${API_BASE}/tasks?status=${status}` : `${API_BASE}/tasks`;
    const response = await axios.get<Task[]>(url);
    return response.data;
  },

  async createTask(task: { name: string; description: string; agent: string }): Promise<Task> {
    const response = await axios.post<Task>(`${API_BASE}/tasks`, task);
    return response.data;
  },
};
```

**Step 2: Commit**

```bash
git add src/services/api.ts
git commit -m "feat: add API service with axios"
```

---

## Phase 3: React Components

### Task 5: Create main entry files

**Files:**
- Create: `frontend/src/index.css`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`

**Step 1: Write index.css**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
```

**Step 2: Write main.tsx**

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

**Step 3: Write App.tsx (minimal placeholder)**

```typescript
function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <h1 className="text-2xl font-bold p-4">MAS - Loading...</h1>
    </div>
  )
}

export default App
```

**Step 4: Commit**

```bash
git add src/index.css src/main.tsx src/App.tsx
git commit -m "feat: add main entry files"
```

---

### Task 6: Create Header component

**Files:**
- Create: `frontend/src/components/Header.tsx`

**Step 1: Write Header.tsx**

```typescript
import type { AgentType } from '../types';

interface HeaderProps {
  currentAgent: AgentType;
  onAgentChange: (agent: AgentType) => void;
}

const agents: { type: AgentType; label: string }[] = [
  { type: 'principal', label: 'PI' },
  { type: 'theorist', label: 'Theorist' },
  { type: 'experimentalist', label: 'Experimentalist' },
  { type: 'analyst', label: 'Analyst' },
  { type: 'writer', label: 'Writer' },
];

export function Header({ currentAgent, onAgentChange }: HeaderProps) {
  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="text-2xl">🔬</span>
        <h1 className="text-xl font-semibold text-gray-900">MAS - Research Agent</h1>
      </div>

      <div className="flex gap-2">
        {agents.map((agent) => (
          <button
            key={agent.type}
            onClick={() => onAgentChange(agent.type)}
            className={`px-3 py-1.5 text-sm rounded-md border transition-colors ${
              currentAgent === agent.type
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white text-gray-700 border-gray-200 hover:border-blue-400'
            }`}
          >
            {agent.label}
          </button>
        ))}
      </div>
    </header>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/Header.tsx
git commit -m "feat: add Header component with agent selector"
```

---

### Task 7: Create Sidebar component

**Files:**
- Create: `frontend/src/components/Sidebar.tsx`

**Step 1: Write Sidebar.tsx**

```typescript
import { useEffect, useState } from 'react';
import { api } from '../services/api';
import type { Agent, Skill } from '../types';

export function Sidebar() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [agentsData, skillsData] = await Promise.all([
          api.getAgents(),
          api.getSkills(),
        ]);
        setAgents(agentsData);
        setSkills(skillsData.slice(0, 5));
      } catch (err) {
        console.error('Failed to load sidebar data:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <aside className="w-72 bg-white border-r border-gray-200 p-4">
        <div className="text-gray-500">Loading...</div>
      </aside>
    );
  }

  return (
    <aside className="w-72 bg-white border-r border-gray-200 p-4 overflow-y-auto">
      <section className="mb-6">
        <h3 className="text-xs font-semibold text-gray-500 uppercase mb-3">Available Agents</h3>
        <div className="space-y-2">
          {agents.map((agent) => (
            <div key={agent.type} className="p-3 border border-gray-200 rounded-lg hover:border-blue-400 cursor-pointer">
              <h4 className="font-medium text-sm text-gray-900">{agent.name}</h4>
              <p className="text-xs text-gray-500 mt-1">{agent.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h3 className="text-xs font-semibold text-gray-500 uppercase mb-3">Available Skills</h3>
        <div className="space-y-2">
          {skills.map((skill) => (
            <div key={skill.name} className="p-3 border border-gray-200 rounded-lg hover:border-blue-400 cursor-pointer">
              <h4 className="font-medium text-sm text-gray-900">{skill.name}</h4>
              <p className="text-xs text-gray-500 mt-1">{skill.description}</p>
            </div>
          ))}
        </div>
      </section>
    </aside>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/Sidebar.tsx
git commit -m "feat: add Sidebar component with agents and skills"
```

---

### Task 8: Create MessageList component

**Files:**
- Create: `frontend/src/components/MessageList.tsx`

**Step 1: Write MessageList.tsx**

```typescript
import { useEffect, useRef } from 'react';
import type { Message } from '../types';

interface MessageListProps {
  messages: Message[];
}

export function MessageList({ messages }: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    containerRef.current?.scrollTo(0, containerRef.current.scrollHeight);
  }, [messages]);

  return (
    <div ref={containerRef} className="flex-1 overflow-y-auto p-6 space-y-4">
      {messages.length === 0 && (
        <div className="text-center text-gray-500 py-8">
          Start a conversation with the research agent...
        </div>
      )}

      {messages.map((message, index) => (
        <div
          key={index}
          className={`max-w-[70%] p-4 rounded-xl ${
            message.role === 'user'
              ? 'ml-auto bg-blue-600 text-white'
              : 'mr-auto bg-white border border-gray-200'
          }`}
        >
          <div className="text-xs opacity-70 mb-1">
            {message.role === 'user' ? 'You' : 'Assistant'}
          </div>
          <div className="whitespace-pre-wrap">{message.content}</div>
        </div>
      ))}
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/MessageList.tsx
git commit -m "feat: add MessageList component"
```

---

### Task 9: Create MessageInput component

**Files:**
- Create: `frontend/src/components/MessageInput.tsx`

**Step 1: Write MessageInput.tsx**

```typescript
import { useState, useRef } from 'react';

interface MessageInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function MessageInput({ onSend, disabled }: MessageInputProps) {
  const [text, setText] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || disabled) return;
    onSend(text.trim());
    setText('');
    inputRef.current?.focus();
  };

  return (
    <form onSubmit={handleSubmit} className="p-4 bg-white border-t border-gray-200 flex gap-3">
      <input
        ref={inputRef}
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type your research request..."
        disabled={disabled}
        className="flex-1 px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-500 disabled:bg-gray-100"
      />
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className="px-6 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
      >
        Send
      </button>
    </form>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/MessageInput.tsx
git commit -m "feat: add MessageInput component"
```

---

### Task 10: Create TaskPanel component

**Files:**
- Create: `frontend/src/components/TaskPanel.tsx`

**Step 1: Write TaskPanel.tsx**

```typescript
import { useEffect, useState } from 'react';
import { api } from '../services/api';
import type { Task } from '../types';

export function TaskPanel() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await api.getTasks('running');
        setTasks(data);
      } catch (err) {
        console.error('Failed to load tasks:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const statusColors = {
    pending: 'bg-gray-100 text-gray-600',
    running: 'bg-yellow-100 text-yellow-700',
    completed: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
  };

  if (loading) {
    return (
      <aside className="w-80 bg-white border-l border-gray-200 p-4">
        <div className="text-gray-500">Loading...</div>
      </aside>
    );
  }

  return (
    <aside className="w-80 bg-white border-l border-gray-200 p-4 overflow-y-auto">
      <h3 className="text-xs font-semibold text-gray-500 uppercase mb-3">Active Tasks</h3>

      {tasks.length === 0 ? (
        <div className="text-gray-500 text-sm">No active tasks</div>
      ) : (
        <div className="space-y-3">
          {tasks.map((task) => (
            <div key={task.id} className="p-3 border border-gray-200 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-sm">{task.name}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${statusColors[task.status]}`}>
                  {task.status}
                </span>
              </div>
              <div className="text-xs text-gray-500">
                Agent: {task.agent}
              </div>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/TaskPanel.tsx
git commit -m "feat: add TaskPanel component"
```

---

### Task 11: Create ChatWindow component

**Files:**
- Create: `frontend/src/components/ChatWindow.tsx`

**Step 1: Write ChatWindow.tsx**

```typescript
import { useState, useCallback } from 'react';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { api } from '../services/api';
import type { Message, AgentType } from '../types';

interface ChatWindowProps {
  agentType: AgentType;
}

export function ChatWindow({ agentType }: ChatWindowProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Welcome to the Multi-Agent Scientific Operating System. I\'m the Principal Investigator agent. How can I assist with your research today?',
    },
  ]);
  const [loading, setLoading] = useState(false);

  const handleSend = useCallback(async (text: string) => {
    const userMessage: Message = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const response = await api.sendMessage({
        message: text,
        agent_type: agentType,
      });

      const assistantMessage: Message = { role: 'assistant', content: response.reply };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Error: Could not connect to backend. Please ensure the backend is running on port 8000.',
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  }, [agentType]);

  return (
    <div className="flex-1 flex flex-col bg-gray-50">
      <MessageList messages={messages} />
      <MessageInput onSend={handleSend} disabled={loading} />
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add src/components/ChatWindow.tsx
git commit -m "feat: add ChatWindow component"
```

---

### Task 12: Update App.tsx with full layout

**Files:**
- Modify: `frontend/src/App.tsx`

**Step 1: Write App.tsx**

```typescript
import { useState } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { ChatWindow } from './components/ChatWindow';
import { TaskPanel } from './components/TaskPanel';
import type { AgentType } from './types';

function App() {
  const [currentAgent, setCurrentAgent] = useState<AgentType>('principal');

  return (
    <div className="h-screen flex flex-col">
      <Header currentAgent={currentAgent} onAgentChange={setCurrentAgent} />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar />

        <ChatWindow agentType={currentAgent} />

        <TaskPanel />
      </div>
    </div>
  );
}

export default App;
```

**Step 2: Commit**

```bash
git add src/App.tsx
git commit -m "feat: wire up all components in App"
```

---

### Task 13: Test frontend build

**Step 1: Run TypeScript check**

Run: `cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/frontend && npx tsc --noEmit`

Expected: No errors

**Step 2: Build project**

Run: `cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/frontend && npm run build`

Expected: Build successful

**Step 3: Commit**

```bash
git add .
git commit -m "feat: complete frontend components"
```

---

## Phase 4: Backend Integration

### Task 14: Create temp_workspace directory

**Files:**
- Create: `frontend/temp_workspace/`
- Create: `frontend/temp_workspace/.claude` (symlink)
- Create: `frontend/temp_workspace/work/`
- Create: `frontend/temp_workspace/logs/`

**Step 1: Create directories**

```bash
cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system
mkdir -p temp_workspace/work temp_workspace/logs
ln -s ../.claude temp_workspace/.claude
ls -la temp_workspace/
```

Expected: Symlink created successfully

**Step 2: Write .gitignore for temp_workspace**

```bash
echo -e "work/\nlogs/\n!.gitkeep" > temp_workspace/.gitignore
touch temp_workspace/work/.gitkeep
touch temp_workspace/logs/.gitignore
```

**Step 3: Commit**

```bash
git add temp_workspace/
git commit -m "feat: create temp_workspace directory with symlink"
```

---

### Task 15: Update backend config to use temp_workspace

**Files:**
- Modify: `backend/src/config.py:20-32`
- Modify: `backend/src/services/claude_code.py:23-31`

**Step 1: Read current config**

Run: `cat /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/config.yaml`

**Step 2: Modify config.py to support temp_workspace**

In `backend/src/config.py`, add a new dataclass:

```python
@dataclass
class WorkspaceConfig:
    temp_dir: str = "temp_workspace"
    work_dir: str = "temp_workspace/work"
    logs_dir: str = "temp_workspace/logs"
```

Add to Config:
```python
@dataclass
class Config:
    server: ServerConfig
    claude: ClaudeConfig
    project: ProjectConfig
    workspace: WorkspaceConfig  # Add this
```

**Step 3: Modify claude_code.py to use temp_workspace**

In `backend/src/services/claude_code.py`, update the `__init__`:

```python
def __init__(self, project_dir: str = None):
    config = get_config()

    # Use temp_workspace as default project directory
    project_root = Path(__file__).parent.parent.parent.parent
    default_workspace = project_root / config.workspace.temp_dir

    self.project_dir = project_dir or str(default_workspace)
    self.claude_dir = Path(config.project.claude_dir).resolve()
    self.claude_cli = os.path.expanduser(config.claude.cli_path)
    self.timeout = config.claude.timeout
    self.default_model = config.claude.model
```

**Step 4: Commit**

```bash
git add backend/src/config.py backend/src/services/claude_code.py
git commit -m "feat: update backend to use temp_workspace"
```

---

## Phase 5: Integration Testing

### Task 16: Start and test the full system

**Step 1: Start backend**

Run: `cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/backend && python -m src.main &`

Expected: Backend running on port 8000

**Step 2: Start frontend**

Run: `cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/frontend && npm run dev &`

Expected: Frontend running on port 3000

**Step 3: Test health endpoint**

Run: `curl http://localhost:8000/health`

Expected: `{"status":"healthy","claude_code":"available"}`

**Step 4: Test chat endpoint**

Run: `curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{"message":"Hello","agent_type":"principal"}'`

Expected: JSON response with reply

**Step 5: Test frontend**

Open: http://localhost:3000

Expected: Page loads with agent selector, sidebar, chat window

**Step 6: Commit**

```bash
git commit -m "test: integration test complete"
```

---

## Summary

- **Phase 1**: Project setup (2 tasks)
- **Phase 2**: Types and API (2 tasks)
- **Phase 3**: React components (9 tasks)
- **Phase 4**: Backend integration (2 tasks)
- **Phase 5**: Testing (1 task)

**Total: 16 tasks**

---

## Execution Choice

**Plan complete and saved to `docs/plans/2026-03-06-frontend-backend-integration-design.md`. Two execution options:**

1. **Subagent-Driven** - I dispatch fresh subagent per task, review between tasks, fast iteration
2. **Parallel Session** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
