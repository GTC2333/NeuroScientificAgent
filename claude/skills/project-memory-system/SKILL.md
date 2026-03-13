---
name: project-memory-system
description: Use when starting a new project, onboarding to a codebase, or when the project lacks structured CLAUDE.md / DESIGN.md / MEMORY.md for cross-session continuity
---

# Project Memory System

## Overview

One-shot initializer for a three-file project memory system. Generates CLAUDE.md (rules), DESIGN.md (architecture), MEMORY.md (experience log) with all maintenance rules embedded in the files themselves. After initialization, this skill is never needed again — Claude follows the rules via CLAUDE.md auto-loading.

## When to Use

- Starting a new project that needs cross-session continuity
- Onboarding to a codebase with no CLAUDE.md / DESIGN.md / MEMORY.md
- User asks to "set up project docs", "initialize Claude for this project"

**When NOT to use:**
- Project already has CLAUDE.md + DESIGN.md + MEMORY.md
- Updating existing docs (use `claude-md-management:revise-claude-md`)

## Initialization Workflow

### Step 1: Scan the Project

Before creating any files:

1. Read existing README, docs/, package.json, pyproject.toml, or similar
2. Identify: tech stack, directory structure, entry points, key patterns
3. Check for existing `.claude/` directory or `CLAUDE.md`
4. Detect project type (see Project Type Detection below)
5. Ask user to confirm findings and any preferences

### Step 2: Detect Project Type → Choose DESIGN.md Modules

Scan the project and select which optional DESIGN.md modules to include:

| Signal | Project Type | Optional Modules to Add |
|--------|-------------|------------------------|
| `routes/`, `api/`, REST/GraphQL endpoints | Web API | API Design table |
| `src/components/`, `.tsx`, `package.json` with React/Vue/Svelte | Frontend | Components table |
| `setup.py`, `Cargo.toml`, `package.json` (lib) | Library | Public API table |
| `Dockerfile`, `docker-compose`, `k8s/` | Infrastructure | Services table |
| `experiments/`, `.ipynb`, research papers | Research | Experiments table |
| CLI entry point, `argparse`, `click`, `commander` | CLI Tool | Commands table |

Multiple types may overlap. Include all matching modules.

### Step 3: Create CLAUDE.md

**Location:** Project root (`./CLAUDE.md`)

Generate from this template, filling in all project-specific info from Step 1:

```markdown
# CLAUDE.md

## Every Session

1. Read in order: `CLAUDE.md` → `DESIGN.md` → `MEMORY.md`
2. Before architecture/feature changes: re-read relevant `DESIGN.md` sections
3. End of session: append to `MEMORY.md`

## Change Control

| File | Rule |
|------|------|
| CLAUDE.md | Constitution-level. User approval required. Show exact diff. |
| DESIGN.md | Propose first (use template at top of DESIGN.md). User approval required. |
| MEMORY.md | Append-only. May fix factual errors with explanation. |

## Re-Read Triggers

Re-read `DESIGN.md` when:
- Requirements change
- Approach fails verification
- Discovered overlap with existing patterns

## Project

- **Tech stack:** {FILLED}
- **Entry point:** {FILLED}

| Directory | Purpose |
|-----------|---------|
| {FILLED} | {FILLED} |

| Command | Purpose |
|---------|---------|
| {FILLED} | {FILLED} |
```

**Customization:** Append any project-specific rules the user mentions (port constraints, naming conventions, forbidden patterns, etc.) as additional sections.

### Step 4: Create DESIGN.md

**Location:** Project root (`./DESIGN.md`)

#### Core (always included):

```markdown
# DESIGN.md

> **Change rule:** propose first, get user approval, then apply.
>
> ```
> ## Proposal: <Title>
> ### Context
> ### Proposed change
> ### Rationale
> ### Impact / risks
> ```

## Status: ✅ Implemented · 🔄 Planned · 💡 Proposed

## Architecture

{ASCII diagram of the system — MUST be filled, not left as placeholder}

## Components

| Component | Status | Description |
|-----------|--------|-------------|
| {FILLED} | {STATUS} | {FILLED} |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| {FILLED} | {FILLED} |

## Status Overview

| Module | Status | Notes |
|--------|--------|-------|
| {FILLED} | {STATUS} | {FILLED} |
```

#### Optional modules (append based on Step 2 detection):

**Web API:**
```markdown
## API Design

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| {FILLED} | {FILLED} | {FILLED} | {STATUS} |
```

**Frontend:**
```markdown
## Components

| Component | Path | Description | Status |
|-----------|------|-------------|--------|
| {FILLED} | {FILLED} | {FILLED} | {STATUS} |
```

**Library:**
```markdown
## Public API

| Export | Description | Status |
|--------|-------------|--------|
| {FILLED} | {FILLED} | {STATUS} |
```

**CLI Tool:**
```markdown
## Commands

| Command | Description | Status |
|---------|-------------|--------|
| {FILLED} | {FILLED} | {STATUS} |
```

**Research:**
```markdown
## Experiments

| ID | Hypothesis | Status | Results |
|----|-----------|--------|---------|
| {FILLED} | {FILLED} | {STATUS} | {FILLED} |
```

**Infrastructure:**
```markdown
## Services

| Service | Port | Description | Status |
|---------|------|-------------|--------|
| {FILLED} | {FILLED} | {FILLED} | {STATUS} |
```

### Step 5: Create MEMORY.md

**Location:** Project root (`./MEMORY.md`)

```markdown
# MEMORY.md

> **Format:** `## YYYY-MM-DD — What was done` + one-line summary. Reusable lessons go under Lessons.

## Log

## {TODAY} — Project initialized
Set up CLAUDE.md, DESIGN.md, MEMORY.md. Tech stack: {STACK}.

---

## Lessons

(Reusable lessons, pitfalls, decisions that apply across sessions)
```

### Step 6: Verify

After creating all three files:

1. Confirm CLAUDE.md has no `<placeholder>` or `{UNFILLED}` left
2. Confirm DESIGN.md architecture diagram is filled (not placeholder)
3. Confirm MEMORY.md has today's date and correct tech stack
4. Present a summary to user for final review

## Key Rules

- **Fill, don't placeholder.** Every `{FILLED}` must be replaced with real project info from Step 1. If info is unknown, ask the user — never leave placeholders.
- **Templates stay in this skill only.** The generated CLAUDE.md contains rules, not templates. DESIGN.md and MEMORY.md contain their own compact format hints at the top.
- **One-shot.** After initialization, this skill is done. All maintenance rules live in the generated files.
