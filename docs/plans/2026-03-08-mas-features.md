# MAS Features Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** 实现两个功能：1) Skills热插拔 - 用户可在会话前/中动态选择skills; 2) Global Memory - 修复Claude Code session-id问题实现会话记忆

**Architecture:**
- Skills热插拔：后端添加skills选择API + 前端Zustand状态管理 + UI组件
- Global Memory：ChatRequest添加session_id字段 → 传递给Claude Code CLI --session-id参数

**Tech Stack:** Python/FastAPI (后端), React/TypeScript/Zustand (前端), Claude Code CLI

---

## Task 1: Global Memory - Add session_id to ChatRequest

**Files:**
- Modify: `backend/src/api/chat.py:26-30` (ChatRequest model)
- Modify: `backend/src/api/chat.py:48-82` (chat endpoint)
- Modify: `backend/src/api/chat.py:85-107` (chat_stream endpoint)
- Modify: `backend/src/services/claude_code.py:90-172` (invoke and invoke_streaming methods)

**Step 1: Add session_id field to ChatRequest**

```python
# In backend/src/api/chat.py, modify ChatRequest class:
class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Message]] = None
    agent_type: Optional[str] = None
    session_id: Optional[str] = None  # ADD THIS LINE
```

**Step 2: Pass session_id to Claude Code service in chat endpoint**

```python
# In backend/src/api/chat.py, modify chat() function:
response_text = claude_service.invoke(
    message=request.message,
    agent_type=agent_type,
    session_id=request.session_id  # ADD THIS LINE
)
```

**Step 3: Pass session_id to Claude Code service in chat_stream endpoint**

```python
# In backend/src/api/chat.py, modify chat_stream():
for chunk in claude_service.invoke_streaming(
    message=request.message,
    agent_type=agent_type,
    session_id=request.session_id  # ADD THIS LINE
):
```

**Step 4: Add session_id parameter to ClaudeCodeService.invoke()**

```python
# In backend/src/services/claude_code.py, modify invoke() method signature and body:
def invoke(self, message: str, agent_type: str = "principal",
           model: str = None, session_id: str = None) -> str:  # ADD session_id parameter

    # In the cmd building section, add session_id flag:
    cmd = [
        self.claude_cli,
        "-p",
        "--print",
        "--output-format", "text",
        "--add-dir", str(self.claude_dir),
        "--setting-sources", "project",
        "--model", model,
        "--system-prompt", system_prompt,
    ]

    # ADD THIS: Add session_id to command if provided
    if session_id:
        cmd.extend(["--session-id", session_id])

    cmd.append(message)  # This should be last
```

**Step 5: Add session_id parameter to ClaudeCodeService.invoke_streaming()**

```python
# In backend/src/services/claude_code.py, modify invoke_streaming():
def invoke_streaming(self, message: str, agent_type: str = "principal",
                      model: str = None, session_id: str = None) -> Generator[str, None, None]:

    # Add session_id to cmd:
    if session_id:
        cmd.extend(["--session-id", session_id])
```

**Step 6: Test the changes**

```bash
cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/backend
python -c "
from src.api.chat import ChatRequest
req = ChatRequest(message='test', session_id='test-123')
print(f'session_id: {req.session_id}')
print('ChatRequest with session_id: OK')
"
```

**Step 7: Test Claude Code service**

```bash
cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/backend
python -c "
from src.services.claude_code import ClaudeCodeService
svc = ClaudeCodeService()
result = svc.invoke('Say hello', session_id='test-session-001')
print(f'Result: {result[:100]}...')
"
```

---

## Task 2: Skills Hot-swap - Backend API

**Files:**
- Modify: `backend/src/api/skills.py` (add select endpoint)
- Modify: `backend/src/api/chat.py` (pass selected skills to Claude Code)

**Step 1: Add SkillsSelectRequest model and endpoint**

```python
# Add to backend/src/api/skills.py:
from typing import List, Optional
from pydantic import BaseModel

class SkillsSelectRequest(BaseModel):
    session_id: str
    selected_skills: List[str]

# Add new endpoint after existing skills endpoints:
@router.post("/skills/select")
async def select_skills(request: SkillsSelectRequest):
    """Select skills for a session"""
    # Store selected skills in memory (in production, use database)
    if not hasattr(select_skills, 'session_skills'):
        select_skills.session_skills = {}

    select_skills.session_skills[request.session_id] = request.selected_skills
    return {"status": "ok", "selected_skills": request.selected_skills}

@router.get("/skills/selected/{session_id}")
async def get_selected_skills(session_id: str):
    """Get selected skills for a session"""
    if not hasattr(select_skills, 'session_skills'):
        return {"selected_skills": []}
    return {"selected_skills": select_skills.session_skills.get(session_id, [])}
```

**Step 2: Modify chat.py to pass skills to Claude Code**

```python
# Modify ChatRequest to include skills:
class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Message]] = None
    agent_type: Optional[str] = None
    session_id: Optional[str] = None
    selected_skills: Optional[List[str]] = None  # ADD THIS

# Modify invoke call to pass skills:
response_text = claude_service.invoke(
    message=request.message,
    agent_type=agent_type,
    session_id=request.session_id,
    skills=request.selected_skills  # ADD THIS
)
```

**Step 3: Modify ClaudeCodeService to use skills in system prompt**

```python
# In backend/src/services/claude_code.py, modify _build_system_prompt:
def _build_system_prompt(self, agent_type: str, message: str, skills: List[str] = None) -> str:
    agent_def = self._load_agent_prompt(agent_type)

    skills_context = ""
    if skills:
        skills_list = ", ".join(skills)
        skills_context = f"\n## Active Skills\nYou have access to the following skills: {skills_list}"

    system_prompt = f"""You are running in the Multi-Agent Scientific (MAS) Operating System.
Your role is: {agent_type.upper()}

{agent_def}

## Current Task
User message: {message}
{skills_context}

## Instructions
1. Respond as the {agent_type} agent following its defined cognitive style
2. Use the skills available in {self.claude_dir}/skills/ when appropriate
3. If you need to perform actions, you may use available tools
4. Write any outputs to the file system in appropriate directories

Respond now as the {agent_type} agent:"""

    return system_prompt
```

**Step 4: Update invoke and invoke_streaming to pass skills**

```python
# Modify invoke() signature and call:
def invoke(self, message: str, agent_type: str = "principal",
           model: str = None, session_id: str = None,
           skills: List[str] = None) -> str:

    system_prompt = self._build_system_prompt(agent_type, message, skills)
    # ... rest of method
```

**Step 5: Test skills API**

```bash
cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/backend

# Test skills list
curl http://localhost:9000/skills | head -50

# Test skills selection
curl -X POST http://localhost:9000/skills/select \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-123", "selected_skills": ["literature_review", "data_analysis"]}'
```

---

## Task 3: Frontend - Add session_id and skills state

**Files:**
- Modify: `frontend/src/store/useStore.ts` (add session_id and activeSkills)
- Test: `frontend/src/components/SessionCreationPanel.tsx` (existing)
- Test: `frontend/src/components/ChatPanel.tsx` (existing)

**Step 1: Add session_id and activeSkills to Zustand store**

```typescript
// In frontend/src/store/useStore.ts, add to interface and state:
interface AppState {
  // ... existing fields
  sessionId: string | null;
  activeSkills: string[];
  // ... existing methods
  setSessionId: (id: string) => void;
  setActiveSkills: (skills: string[]) => void;
  addActiveSkill: (skill: string) => void;
  removeActiveSkill: (skill: string) => void;
}

// In the store implementation:
setSessionId: (id) => set({ sessionId: id }),
setActiveSkills: (skills) => set({ activeSkills: skills }),
addActiveSkill: (skill) => set((state) => ({
  activeSkills: [...state.activeSkills, skill]
})),
removeActiveSkill: (skill) => set((state) => ({
  activeSkills: state.activeSkills.filter(s => s !== skill)
})),
```

**Step 2: Generate session_id on session creation**

```typescript
// In SessionCreationPanel or useStore, generate UUID:
const generateSessionId = () => {
  return 'session-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
};

// When creating new session:
const newSessionId = generateSessionId();
setSessionId(newSessionId);
```

**Step 3: Update ChatPanel to pass session_id and skills**

```typescript
// In frontend/src/api/chat.ts or equivalent:
const sendMessage = async (message: string, sessionId: string, skills: string[]) => {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      session_id: sessionId,
      selected_skills: skills,
      agent_type: 'principal'
    })
  });
  return response.json();
};
```

---

## Task 4: Frontend - Skills Selector UI

**Files:**
- Modify: `frontend/src/components/SessionCreationPanel.tsx` (add skills multi-select)
- Modify: `frontend/src/components/ChatPanel.tsx` (add skills quick bar)

**Step 1: Add skills multi-select to SessionCreationPanel**

```tsx
// In SessionCreationPanel.tsx:
import { useState, useEffect } from 'react';
import { useStore } from '../store/useStore';

export function SessionCreationPanel() {
  const [availableSkills, setAvailableSkills] = useState<string[]>([]);
  const { activeSkills, setActiveSkills } = useStore();

  useEffect(() => {
    fetch('/api/skills')
      .then(res => res.json())
      .then(data => setAvailableSkills(data.map((s: any) => s.name)));
  }, []);

  const toggleSkill = (skill: string) => {
    if (activeSkills.includes(skill)) {
      setActiveSkills(activeSkills.filter(s => s !== skill));
    } else {
      setActiveSkills([...activeSkills, skill]);
    }
  };

  return (
    <div className="skills-selector">
      <h3>Select Skills</h3>
      <div className="skills-list">
        {availableSkills.map(skill => (
          <label key={skill}>
            <input
              type="checkbox"
              checked={activeSkills.includes(skill)}
              onChange={() => toggleSkill(skill)}
            />
            {skill}
          </label>
        ))}
      </div>
    </div>
  );
}
```

**Step 2: Add skills quick bar to ChatPanel**

```tsx
// In ChatPanel.tsx:
import { useStore } from '../store/useStore';

export function ChatPanel() {
  const { activeSkills, removeActiveSkill, addActiveSkill } = useStore();

  return (
    <div className="chat-panel">
      {/* Skills quick bar */}
      {activeSkills.length > 0 && (
        <div className="skills-bar">
          {activeSkills.map(skill => (
            <span key={skill} className="skill-tag">
              {skill}
              <button onClick={() => removeActiveSkill(skill)}>×</button>
            </span>
          ))}
        </div>
      )}
      {/* ... chat input and messages */}
    </div>
  );
}
```

**Step 3: Test frontend**

```bash
cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/frontend
npm run dev
# Open http://localhost:9001
# Test: Create new session, select skills, send message
```

---

## Task 5: Integration Testing

**Files:**
- Test end-to-end flow

**Step 1: Start backend and frontend**

```bash
# Terminal 1: Backend
cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/backend
./start.sh

# Terminal 2: Frontend
cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system/frontend
npm run dev
```

**Step 2: Test Global Memory**

```bash
# In browser or via curl:
# 1. Send first message with session_id
curl -X POST http://localhost:9000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "My name is Zhang San", "session_id": "test-session-001"}'

# 2. Send second message with same session_id
curl -X POST http://localhost:9000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is my name?", "session_id": "test-session-001"}'

# Expected: Claude Code should remember "Zhang San" from previous message
```

**Step 3: Test Skills Hot-swap**

```bash
# 1. Select skills for session
curl -X POST http://localhost:9000/skills/select \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-session-002", "selected_skills": ["literature_review"]}'

# 2. Send message with selected skills
curl -X POST http://localhost:9000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Find papers about transformers", "session_id": "test-session-002", "selected_skills": ["literature_review"]}'

# Expected: Response should use literature_review skill
```

---

## Summary

| Task | Description | Files to Modify |
|------|-------------|-----------------|
| 1 | Global Memory - Add session_id | chat.py, claude_code.py |
| 2 | Skills Hot-swap - Backend API | skills.py, chat.py, claude_code.py |
| 3 | Frontend - State management | useStore.ts |
| 4 | Frontend - UI components | SessionCreationPanel.tsx, ChatPanel.tsx |
| 5 | Integration testing | - |

**Total estimated tasks: 5 major tasks with ~20 steps**
