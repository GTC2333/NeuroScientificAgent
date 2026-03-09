# Frontend-Backend Integration Design

## Project Overview

- **Project**: MAS (Multi-Agent Scientific Operating System) Frontend
- **Date**: 2026-03-06
- **Goal**: Build React frontend that connects to existing FastAPI backend, enabling users to interact with Claude Code agents

## Architecture

```
┌─────────────────────┐     ┌─────────────────────┐
│   React Frontend   │────▶│   FastAPI Backend   │
│   (localhost:3000)  │◀────│   (localhost:8000)  │
└─────────────────────┘     └─────────────────────┘
                                    │
                                    ▼
                            ┌─────────────────────┐
                            │   Claude Code CLI   │
                            │  (temp_workspace/)   │
                            └─────────────────────┘
```

## Tech Stack

- **Frontend**: React 18 + TypeScript + Vite
- **Styling**: Tailwind CSS
- **State Management**: React Context + useReducer
- **HTTP Client**: Axios
- **Backend**: FastAPI (existing)

## Components

### 1. Frontend Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── ChatWindow.tsx      # Main chat interface
│   │   ├── MessageList.tsx     # Message display
│   │   ├── MessageInput.tsx    # Input field
│   │   ├── AgentSelector.tsx    # Agent type selection
│   │   ├── Sidebar.tsx         # Agents & Skills list
│   │   ├── TaskPanel.tsx       # Task management
│   │   └── Header.tsx          # App header
│   ├── hooks/
│   │   ├── useChat.ts          # Chat API hook
│   │   ├── useAgents.ts        # Agents API hook
│   │   ├── useSkills.ts        # Skills API hook
│   │   └── useTasks.ts         # Tasks API hook
│   ├── services/
│   │   └── api.ts              # Axios API client
│   ├── context/
│   │   └── ChatContext.tsx     # Chat state management
│   ├── types/
│   │   └── index.ts            # TypeScript interfaces
.tsx
││   ├── App   └── main.tsx
├── index.html
├── tailwind.config.js
├── vite.config.ts
└── package.json
```

### 2. Backend Enhancements

- **CORS**: Already configured for localhost:3000
- **New Endpoints**:
  - `POST /api/chat` - Send message (existing)
  - `POST /api/chat/stream` - Streaming response (existing)
  - `GET /api/agents` - List agents (existing)
  - `GET /api/skills` - List skills (existing)
  - `GET /api/tasks` - List tasks (existing)
  - `GET /health` - Health check (existing)

### 3. Temporary Workspace

```
research-agent-system/
├── temp_workspace/              # Claude Code working directory
│   ├── .claude -> ../.claude   # Symlink to config
│   ├── work/                    # User files
│   └── logs/                    # Execution logs
└── temp_workspace.env           # Environment file
```

## API Contract

### Chat Request
```typescript
interface ChatRequest {
  message: string;
  agent_type: 'principal' | 'theorist' | 'experimentalist' | 'analyst' | 'writer';
  history?: Message[];
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
}
```

### Chat Response
```typescript
interface ChatResponse {
  reply: string;
  agent_type: string;
  task_id?: string;
}
```

### Streaming Response
```typescript
// Server-Sent Events
data: {"text": "partial content"}
data: {"done": true}
```

## Implementation Steps

1. **Setup React project** with Vite + TypeScript + Tailwind
2. **Create API service** with Axios
3. **Build UI components** (Header, Sidebar, Chat)
4. **Implement chat functionality** with streaming support
5. **Add task management** panel
6. **Create temp_workspace** directory with symlink
7. **Update backend** to use temp_workspace for Claude Code execution

## Environment Variables

```env
# Frontend (.env)
VITE_API_BASE=http://localhost:8000/api

# Backend (local.yaml or config.yaml)
claude:
  cli_path: "~/.local/bin/claude"
  model: "sonnet"
  timeout: 120

project:
  root_dir: "./temp_workspace"
  claude_dir: "./.claude"
```

## Acceptance Criteria

1. ✅ Frontend runs on http://localhost:3000
2. ✅ Backend runs on http://localhost:8000
3. ✅ User can select different agent types
4. ✅ Chat messages are sent to backend and responses displayed
5. ✅ Streaming responses work correctly
6. ✅ Claude Code operates in temp_workspace directory
7. ✅ All 5 agent types are accessible
8. ✅ Skills and tasks are displayed in sidebar
