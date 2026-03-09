# Agent Functionality Testing Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Test and verify that each agent (Theorist, Experimentalist, Analyst, Writer) can perform their expected functions through the Claude Code CLI integration.

**Architecture:** The system invokes Claude Code CLI as a subprocess with agent definitions and skills. The key question is whether the tools specified in agent definitions (WebSearch, WebFetch, Bash) actually work with Claude Code CLI.

**Tech Stack:** FastAPI (backend), Claude Code CLI, Python subprocess

---

## Current System State

- **Backend**: FastAPI server on port 9000
- **Integration**: `ClaudeCodeService` invokes CLI with agent definitions
- **Agent Tools**: Defined in `.claude/agents/*.md`
- **Issue**: Tools like `WebSearch`, `WebFetch` are NOT built into Claude Code CLI

---

## Testing Strategy

We need to test from bottom up:
1. Backend can start
2. Claude Code CLI can be invoked
3. Individual tool capabilities work
4. Agent-specific functions work

---

### Task 1: Verify Backend Starts and Health Check

**Files:**
- Modify: `backend/src/config.py:23` (verify CLI path)
- Test: `backend/src/main.py`

**Step 1: Start the backend server**

Run:
```bash
cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system
source venv/bin/activate
python -m uvicorn src.main:app --host 0.0.0.0 --port 9000 &
```
Expected: Server starts on port 9000

**Step 2: Test health endpoint**

Run:
```bash
curl http://localhost:9000/health
```
Expected: JSON with `"status": "healthy"` and Claude Code availability

**Step 3: Commit**

```bash
git add backend/src/config.py
git commit -m "test: verify backend starts and health check passes"
```

---

### Task 2: Test Claude Code CLI Invocation

**Files:**
- Test: `backend/src/services/claude_code.py`

**Step 1: Test direct CLI invocation**

Run:
```bash
cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system
claude -p --print "Hello, respond with exactly 'OK' if you receive this"
```
Expected: "OK" response

**Step 2: Test via backend API**

Run:
```bash
curl -X POST http://localhost:9000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Say 'TEST_OK' if you receive this", "agent_type": "principal"}'
```
Expected: JSON with `"reply"` containing "TEST_OK"

**Step 3: Commit**

```bash
git add backend/src/services/claude_code.py
git commit -m "test: verify Claude Code CLI invocation works"
```

---

### Task 3: Test Theorist - Web Search Capability

**Files:**
- Test: `/api/chat` endpoint with `agent_type: "theorist"`

**Step 1: Test if WebSearch tool works**

Run:
```bash
curl -X POST http://localhost:9000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Search for recent papers on neural decoding in 2024", "agent_type": "theorist"}'
```
Expected: List of papers with titles, authors, venues

**Step 2: Analyze the response**

If response contains actual paper titles → WebSearch works
If response says "I don't have access to web search" → WebSearch NOT available

**Step 3: Document findings**

Add to response analysis in plan results

**Step 4: Commit**

```bash
git commit -m "test: verify Theorist web search capability"
```

---

### Task 4: Test Experimentalist - Code Execution

**Files:**
- Test: `/api/chat` endpoint with `agent_type": "experimentalist"`

**Step 1: Test if Bash tool works**

Run:
```bash
curl -X POST http://localhost:9000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Write a simple Python script that prints \"Hello from Experimentalist\" and save it to /tmp/test_script.py, then execute it", "agent_type": "experimentalist"}'
```
Expected: Script created and executed, output shows "Hello from Experimentalist"

**Step 2: Verify the file was created**

Run:
```bash
cat /tmp/test_script.py
```
Expected: Python script content

**Step 3: Commit**

```bash
git commit -m "test: verify Experimentalist code execution capability"
```

---

### Task 5: Test Analyst - Data Analysis

**Files:**
- Test: `/api/chat` endpoint with `agent_type": "analyst"`

**Step 1: Test analyst data analysis**

Run:
```bash
curl -X POST http://localhost:9000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Create a simple CSV file with 3 rows of sample data (name, score), then calculate the average score using Python", "agent_type": "analyst"}'
```
Expected: CSV created, average calculated

**Step 2: Verify the CSV was created**

Run:
```bash
cat /tmp/*.csv 2>/dev/null || ls -la /tmp/*.csv
```
Expected: CSV file exists with data

**Step 3: Commit**

```bash
git commit -m "test: verify Analyst data analysis capability"
```

---

### Task 6: Test Writer - Document Generation

**Files:**
- Test: `/api/chat` endpoint with `agent_type": "writer"`

**Step 1: Test writer document creation**

Run:
```bash
curl -X POST http://localhost:9000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Write a brief research summary about AI in neuroscience and save it to /tmp/research_summary.md", "agent_type": "writer"}'
```
Expected: Markdown document created

**Step 2: Verify the file was created**

Run:
```bash
cat /tmp/research_summary.md
```
Expected: Markdown content

**Step 3: Commit**

```bash
git commit -m "test: verify Writer document generation capability"
```

---

### Task 7: Test Skills Invocation

**Files:**
- Test: `/api/chat` endpoint with `selected_skills`

**Step 1: Test with literature_review skill**

Run:
```bash
curl -X POST http://localhost:9000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Find 3 papers on working memory training", "agent_type": "theorist", "selected_skills": ["literature-review"]}'
```
Expected: Literature review output

**Step 2: Test with code_generation skill**

Run:
```bash
curl -X POST http://localhost:9000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Generate a Python function to calculate factorial", "agent_type": "experimentalist", "selected_skills": ["code-generation"]}'
```
Expected: Code generated with proper structure

**Step 3: Commit**

```bash
git commit -m "test: verify skills invocation works"
```

---

## Test Results Summary

After completing all tasks, document:

| Agent | Function | Expected | Actual Result | Status |
|-------|----------|----------|---------------|--------|
| Theorist | Web Search | Papers found | ? | PENDING |
| Experimentalist | Code Execution | Script runs | ? | PENDING |
| Analyst | Data Analysis | CSV + stats | ? | PENDING |
| Writer | Document Creation | Markdown file | ? | PENDING |
| All | Skills | Proper output | ? | PENDING |

---

## Next Steps Based on Results

1. **If tools don't work**: Configure MCP servers for WebSearch/WebFetch
2. **If CLI fails**: Debug subprocess invocation
3. **If skills don't load**: Check skill loading logic
