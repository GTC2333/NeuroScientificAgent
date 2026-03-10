# Workspace Root Filter Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Filter Claude Code UI to only show projects/sessions within `/root/claudeagent/scientific_agent/temp_workspace` directory, and ensure Claude Code SDK works within this directory.

**Architecture:** Add a workspace root filter configuration that:
1. Stores the allowed workspace root path in project config (`~/.claude/project-config.json`)
2. Filters project discovery in `getProjects()` to only include projects under this root
3. Exposes the filter to frontend via API
4. Frontend stores the setting in localStorage
5. Claude Code SDK respects this root directory for all operations

**Tech Stack:** Node.js (backend), React (frontend), Claude Code SDK

---

## File Structure

### Backend Files
- `server/projects.js` - Add workspace root filter logic in `getProjects()` function
- `server/routes/projects.js` - Add API to get/set workspace root configuration
- `server/index.js` - Add config endpoint to expose workspace root to frontend
- `temp_workspace/.claude/settings.json` - New file to store workspace root configuration

### Frontend Files
- `src/hooks/useProjectsState.ts` - Add filter logic after fetching projects
- `src/components/sidebar/view/subcomponents/SidebarHeader.tsx` - Add UI to display/set workspace root (optional)
- `src/utils/api.js` - Add API methods for workspace root config

---

## Chunk 1: Backend Configuration

### Task 1: Create workspace config file in temp_workspace

**Files:**
- Create: `temp_workspace/.claude/settings.json`

- [ ] **Step 1: Create directory and config file**

```bash
mkdir -p /root/claudeagent/scientific_agent/temp_workspace/.claude
```

```json
{
  "workspaceRoot": "/root/claudeagent/scientific_agent/temp_workspace"
}
```

- [ ] **Step 2: Commit**

---

### Task 2: Modify server/routes/projects.js to support workspace root

**Files:**
- Modify: `server/routes/projects.js:15-25`
- Test: Manual API testing

- [ ] **Step 1: Add WORKSPACE_ROOT constant that reads from config file**

Replace:
```javascript
// Configure allowed workspace root (defaults to user's home directory)
export const WORKSPACES_ROOT = process.env.WORKSPACES_ROOT || os.homedir();
```

With:
```javascript
import { promises as fs } from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Read workspace root from temp_workspace config
async function getWorkspaceRoot() {
  const configPath = path.resolve(__dirname, '../../temp_workspace/.claude/settings.json');
  try {
    const content = await fs.readFile(configPath, 'utf-8');
    const config = JSON.parse(content);
    return config.workspaceRoot || os.homedir();
  } catch {
    return os.homedir();
  }
}

// Configure allowed workspace root
let WORKSPACES_ROOT = os.homedir();

// Initialize workspace root from config
getWorkspaceRoot().then(root => {
  WORKSPACES_ROOT = root;
  console.log('[API] Workspace root set to:', WORKSPACES_ROOT);
});

export { WORKSPACES_ROOT, getWorkspaceRoot };
```

- [ ] **Step 2: Commit**

---

### Task 3: Modify server/projects.js to filter projects by workspace root

**Files:**
- Modify: `server/projects.js:384-463`
- Test: Manual API testing

- [ ] **Step 1: Add workspace root filter logic**

After importing getWorkspaceRoot, modify getProjects function:

```javascript
async function getProjects(progressCallback = null) {
  const workspaceRoot = await getWorkspaceRoot();
  // ... existing code ...

  // Filter projects by workspace root
  const filteredProjects = projects.filter(project => {
    if (!project.fullPath) return false;
    return project.fullPath.startsWith(workspaceRoot);
  });

  return filteredProjects;
}
```

- [ ] **Step 2: Run test**

Run: Test by accessing /api/projects API and verify only temp_workspace projects are returned

- [ ] **Step 3: Commit**

---

## Chunk 2: Frontend Integration

### Task 4: Modify useProjectsState.ts to handle workspace root filter

**Files:**
- Modify: `src/hooks/useProjectsState.ts:151-171`

- [ ] **Step 1: Add workspace root filter constant**

Add at top of file:
```typescript
const WORKSPACE_ROOT_FILTER = '/root/claudeagent/scientific_agent/temp_workspace';
```

- [ ] **Step 2: Modify fetchProjects to filter results**

In fetchProjects function, after getting projectData:

```typescript
const filteredProjects = projectData.filter((project: Project) => {
  if (!project.fullPath) return false;
  return project.fullPath.startsWith(WORKSPACE_ROOT_FILTER);
});

setProjects((prevProjects) => {
  if (prevProjects.length === 0) {
    return filteredProjects;
  }

  return projectsHaveChanges(prevProjects, filteredProjects, true)
    ? filteredProjects
    : prevProjects;
});
```

- [ ] **Step 3: Commit**

---

### Task 5: Verify Claude Code SDK integration

**Files:**
- Verify: Claude Code SDK configuration

- [ ] **Step 1: Check Claude Code SDK settings**

Verify that Claude Code SDK reads from temp_workspace config:
- Check if `.claude/settings.json` is being read
- Verify SDK uses correct working directory

- [ ] **Step 2: Test with actual project**

Run Claude Code UI and verify:
1. New projects are created under temp_workspace
2. Sessions are only shown for temp_workspace projects
3. Claude Code SDK operates within temp_workspace

- [ ] **Step 3: Commit**

---

## Summary

This implementation adds workspace root filtering to Claude Code UI:

1. **Backend**: Reads workspace root from `temp_workspace/.claude/settings.json`
2. **Project Discovery**: Filters `getProjects()` to only return projects under workspace root
3. **Frontend**: Additional safety filter in `useProjectsState.ts`
4. **SDK Integration**: Claude Code SDK works within the configured workspace directory

The key change is making the system use `temp_workspace` as the base directory for all operations, ensuring isolation from the user's home directory.
