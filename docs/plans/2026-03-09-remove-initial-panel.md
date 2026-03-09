# Remove Initial Research Goal Panel Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Remove the initial research goal input panel and auto-generated welcome message, so users start with a clean chat interface.

**Architecture:** Simplify the session creation flow by using default values and removing the welcome message auto-insertion.

**Tech Stack:** React + TypeScript, Zustand, React Router

---

### Task 1: Add default session creation to store

**Files:**
- Modify: `frontend/src/store/useStore.ts:19` - Add new createSessionWithDefaults method
- Modify: `frontend/src/store/useStore.ts:33-50` - Update createSession to have optional parameters

**Step 1: Add optional parameters with defaults to createSession**

```typescript
// Change line 19 from:
createSession: (title: string, agents: AgentType[], skills: string[]) => string;

// To:
createSession: (title: string, agents?: AgentType[], skills?: string[]) => string;
```

**Step 2: Update createSession implementation with default values**

```typescript
// Change lines 33-50 to:
createSession: (title, agents = ['principal'], skills = []) => {
  const id = generateUUID();
  const now = new Date().toISOString();
  const newSession: Session = {
    id,
    title: title || 'New Research',
    agents,
    skills,
    messages: [],
    createdAt: now,
    updatedAt: now,
  };
  set((state) => ({
    sessions: [newSession, ...state.sessions],
    currentSessionId: id,
  }));
  return id;
},
```

**Step 3: Commit**

```bash
git add frontend/src/store/useStore.ts
git commit -m "feat: add optional params with defaults to createSession"
```

---

### Task 2: Modify Sidebar to create session with defaults

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx:13-16` - Update handleNewSession

**Step 1: Update handleNewSession to create session with defaults**

```typescript
// Change lines 13-16 from:
const handleNewSession = () => {
  setCurrentSession(null);
  navigate('/');
};

// To:
const handleNewSession = () => {
  const newSessionId = createSession('New Research', ['principal'], []);
  navigate(`/${newSessionId}`);
};
```

**Step 2: Add createSession to imports if not present**

```typescript
// Already imported in line 8: const createSession = useStore((state: SessionStore) => state.createSession);
```

**Step 3: Commit**

```bash
git add frontend/src/components/Sidebar.tsx
git commit -m "feat: create session with defaults on New Session click"
```

---

### Task 3: Remove welcome message from ChatWindow

**Files:**
- Modify: `frontend/src/components/ChatWindow.tsx:72-85` - Remove the useEffect that adds welcome message

**Step 1: Remove the useEffect that auto-adds welcome message**

Delete lines 72-85 (the entire useEffect block):

```typescript
// Show welcome message if no messages
useEffect(() => {
  if (currentSession && messages.length === 0) {
    const skillsText = currentSession.skills.length > 0
      ? `\n\nUsing skills: ${currentSession.skills.join(', ')}`
      : '';
    const welcomeMessage: Message = {
      role: 'assistant',
      content: `Welcome to this research session!\n\nI'm coordinating ${currentSession.agents.join(', ')} agents to work on: **${currentSession.title}**${skillsText}\n\nWhat would you like to investigate?`,
      timestamp: new Date().toISOString(),
    };
    addMessage(currentSessionId!, welcomeMessage);
  }
}, [currentSessionId]);
```

**Step 2: Clean up unused imports**

```typescript
// Remove Message from import if only used for welcome message
// Check if Message is still needed for:
// - userMessage (line 21) - YES
// - assistantMessage (line 51) - YES
// - errorMsg (line 43) - YES
// - errorMessage (line 61) - YES
// Message type is still needed, keep it
```

**Step 3: Commit**

```bash
git add frontend/src/components/ChatWindow.tsx
git commit -m "feat: remove auto-generated welcome message"
```

---

### Task 4: Remove SessionCreationPanel (optional cleanup)

**Files:**
- Delete: `frontend/src/components/SessionCreationPanel.tsx`
- Modify: `frontend/src/App.tsx` - Remove SessionCreationPanel import and route

**Step 1: Check App.tsx for SessionCreationPanel usage**

```bash
grep -n "SessionCreationPanel" frontend/src/App.tsx
```

**Step 2: Read relevant section of App.tsx**

```bash
sed -n '50,70p' frontend/src/App.tsx
```

**Step 3: Modify App.tsx to remove SessionCreationPanel**

```typescript
// Remove import line:
// import { SessionCreationPanel } from './components/SessionCreationPanel';

// Change route from:
<Route path="/" element={<SessionCreationPanel />} />

// To redirect to first session or show empty state:
<Route path="/" element={<Navigate to={sessions.length > 0 ? `/${sessions[0].id}` : "/"} replace />} />
```

Or simply:

```typescript
<Route path="/" element={<div className="flex-1 flex items-center justify-center"><p className="text-gray-500">Select or create a session to start</p></div>} />
```

**Step 4: Delete SessionCreationPanel.tsx**

```bash
rm frontend/src/components/SessionCreationPanel.tsx
```

**Step 5: Commit**

```bash
git add frontend/src/App.tsx
git rm frontend/src/components/SessionCreationPanel.tsx
git commit -m "refactor: remove SessionCreationPanel component"
```

---

## Summary

| Task | Description |
|------|-------------|
| 1 | Add optional parameters with defaults to createSession |
| 2 | Update Sidebar to create session with defaults |
| 3 | Remove welcome message auto-insertion |
| 4 | Remove SessionCreationPanel (optional cleanup) |
