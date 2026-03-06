# Multi-Agent Scientific Operating System (MAS)

A research automation framework built on **Claude Code** with three-layer architecture. Uses Agent Teams to coordinate specialized agents for complex scientific research tasks.

## Architecture
MAS follows a three-layer architecture:
```
┌─────────────────────────────────────────────────┐
│ Layer 1: System (CLAUDE.md)                    │
│   - Project rules                               │
│   - Research protocols                         │
│   - Collaboration guidelines                    │
├─────────────────────────────────────────────────┤
│ Layer 2: Roles (.claude/agents/)               │
│   - principal      (Principal Investigator)    │
│   - theorist       (Hypothesis generation)     │
│   - experimentalist (Experiment design)         │
│   - analyst        (Data analysis)             │
│   - writer         (Scientific writing)         │
├─────────────────────────────────────────────────┤
│ Layer 3: Capabilities (.claude/skills/)         │
│   - literature_review                          │
│   - data_analysis                              │
│   - code_generation                            │
│   - scientific_writing                          │
└─────────────────────────────────────────────────┘
```

## Prerequisites

### Enable Agent Teams (Experimental)

Agent Teams are experimental and require explicit enablement.

**Option 1: Environment Variable**
```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

**Option 2: settings.json** (recommended)
```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

## Quick Start

### Option 1: Web Interface (Recommended)

A web-based chat interface is provided to interact with the MAS system.

#### Prerequisites

- **Python 3.10+**
- **Claude Code CLI** installed at `~/.local/bin/claude`
- **(Optional) Poetry** for dependency management: `pip install poetry`

#### One-Click Startup

```bash
cd /Users/gtc/Learning/NeuroAI/ScientificAgent/claude/research-agent-system
./start.sh
```

This will:
1. Install backend dependencies (if needed)
2. Start the API server on `http://localhost:8000`
3. Open the web interface in your browser

#### Manual Startup

```bash
# Install dependencies
cd backend
poetry install
# or: pip3 install fastapi uvicorn pydantic sse-starlette python-multipart

# Start server
poetry run python -m src.main
# or: python3 -m src.main
```

Then open `frontend/templates/index.html` in your browser.

#### Configuration

The backend is configured to:
- Use Claude Code CLI at `/Users/gtc/.local/bin/claude`
- Read agent definitions from `.claude/agents/`
- Read skill definitions from `.claude/skills/`

To modify these paths, edit `backend/src/services/claude_code.py`.

---

### Option 2: Claude Code CLI Direct

1. **Enable Agent Teams** in your Claude Code settings
2. **Open this project** in Claude Code
3. **Start a research task** using natural language:
   ```
   "Create an agent team to investigate [research topic]. Use principal for coordination, theorist for hypothesis, experimentalist for design, analyst for data, writer for documentation."
   ```

## Project Structure

```
research-agent-system/
├── CLAUDE.md                    # Layer 1 - System rules
│
├── .claude/
│   ├── agents/                  # Layer 2 - Role definitions
│   │   ├── principal.md         # Principal Investigator
│   │   ├── theorist.md          # Hypothesis generation
│   │   ├── experimentalist.md   # Experiment design
│   │   ├── analyst.md           # Data analysis
│   │   └── writer.md            # Scientific writing
│   │
│   ├── skills/                  # Layer 3 - Capabilities
│   │   ├── literature_review/
│   │   ├── data_analysis/
│   │   ├── code_generation/
│   │   └── scientific_writing/
│   │
│   └── prompts/
│       └── orchestrator.md
│
├── start.sh                     # One-click startup script
│
├── frontend/                    # Web interface
│   └── templates/
│       └── index.html           # Chat UI
│
├── backend/                     # FastAPI backend
│   ├── src/
│   │   ├── main.py              # API entry point
│   │   ├── api/                 # API endpoints
│   │   │   ├── chat.py          # Chat endpoint
│   │   │   ├── tasks.py         # Task management
│   │   │   └── skills.py        # Skills listing
│   │   └── services/
│   │       └── claude_code.py   # Claude Code integration
│   └── pyproject.toml           # Poetry dependencies
│
└── README.md
```

## Agent Roles

| Role | Responsibility | When to Use |
|------|----------------|-------------|
| **principal** | Overall coordination, decision making | Need project management, final decisions |
| **theorist** | Hypothesis generation, theoretical framework | Need theory development, literature synthesis |
| **experimentalist** | Experiment design, implementation | Need experimental protocols, prototype code |
| **analyst** | Data analysis, visualization | Need statistical analysis, insights |
| **writer** | Documentation, paper writing | Need reports, papers, documentation |

## Capabilities (Skills)

Each skill is a reusable module that agents can invoke:

- **literature_review**: Academic paper search, filtering, synthesis
- **data_analysis**: Statistical analysis, pattern recognition, visualization
- **code_generation**: Implementation, prototyping, testing
- **scientific_writing**: Paper/report generation, editing, formatting

## Usage Examples

### Literature Review
```
"Use literature_review skill to search for papers on [topic]. Find recent work from top venues."
```

### Research Investigation
```
"Create a team:
- theorist: develop hypothesis about [phenomenon]
- experimentalist: design experiment to test it
- analyst: plan statistical analysis
- writer: prepare methodology section"
```

### Data Analysis
```
"Use data_analysis skill to analyze [dataset]. Generate visualizations and key insights."
```

### Paper Writing
```
"Use scientific_writing skill to write introduction section based on our literature review findings."
```

## Extending the System

### Adding a New Agent Role

1. Create `.claude/agents/<role>.md`
2. Define role: name, description, cognitive style, collaboration rules
3. Use the new role in your prompts

Example:
```yaml
---
name: reviewer
description: Use this agent for paper reviewing
---
# Reviewer
You are an expert peer reviewer...
```

### Adding a New Skill
1. Create `.claude/skills/<skill_name>/SKILL.md`
2. Define:
   - Trigger conditions
   - Workflow steps
   - Output format

## Best Practices

### When to Use Agent Teams

**Good for:**
- Parallel research exploration
- Multi-perspective analysis
- Complex projects with distinct phases
- Peer review with competing hypotheses

**Not recommended for:**
- Simple, quick tasks
- Sequential dependencies
- Single file edits

### Team Size

- **Recommended**: 3-5 teammates
- **Tasks per teammate**: 5-6 for optimal productivity
- **Token cost**: Scales linearly with team size

## Known Limitations

- Agent Teams are experimental
- No session resumption with in-process teammates
- Task status may lag
- Single team per session
- No nested teams

## License

MIT
