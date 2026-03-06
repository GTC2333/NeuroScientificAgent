# Multi-Agent Scientific Operating System (MAS)

This is a research automation framework built on Claude Code with **Agent Teams enabled**.
It coordinates multiple specialized agents to complete complex scientific research tasks under strict reproducibility and modularity constraints.

---

# System Overview

MAS follows a three-layer architecture:

```
Layer 1 - System Constitution      (CLAUDE.md)
Layer 2 - Agent Roles              (.claude/agents/)
Layer 3 - Capability Modules       (.claude/skills/)
```

The system MUST operate as a multi-agent team.
Single-agent monolithic execution of complex research tasks is prohibited.

---

# Mandatory MAS Initialization Protocol

When a research task is detected:

1. Initialize an Agent Team.
2. Assign a **Principal Investigator (PI)** as team lead.
3. Instantiate required specialized agents.
4. Load skills and role definitions.
5. Build task dependency graph before execution begins.

No research workflow may execute before team initialization is complete.

---

# Core Principles

## 1. Structured Task Decomposition

All research tasks MUST be decomposed into atomic subtasks with:

* Defined inputs
* Defined outputs
* Explicit dependencies
* Structured output schema (JSON or YAML)

No task may execute without a declared dependency graph.

---

## 2. Role Specialization and Isolation

Each agent has a strictly defined responsibility scope:

* **Principal Investigator (PI)**
  Overall coordination, validation of hypotheses, conflict resolution.

* **Theorist**
  Hypothesis generation, theoretical modeling.

* **Experimentalist**
  Experiment design, implementation, execution control.

* **Analyst**
  Data analysis, visualization, statistical validation.

* **Writer**
  Documentation, reporting, paper drafting.

### Role Isolation Policy

* Agents may not override responsibilities of other roles.
* Agents may not directly edit other agents’ outputs.
* All cross-role information exchange must occur via:

  * File system artifacts
  * Orchestrator-mediated messages

---

## 3. Capability Modularity

Skills are reusable capability modules.

Agents invoke skills; agents do not perform unstructured free-form execution.

Example skills:

* `literature_review`
* `data_analysis`
* `code_generation`
* `scientific_writing`

Skill outputs MUST:

* Follow declared schema
* Be written to file
* Avoid conversational-only output

---

## 4. File-System-as-Memory Principle

The file system is the only persistent memory layer.

All intermediate artifacts MUST be written to disk:

* Research notes → `research/`
* Experiments → `experiments/<id>/`
* Analysis → `analysis/`
* System state → `.claude/state/`

Long-term reasoning must not rely on conversation context.

---

## 5. Workflow Orchestration

The orchestrator manages execution using dependency graphs.

### Execution Steps

1. Parse workflow definition (`src/task_graph.yaml`)
2. Validate schema
3. Build dependency graph
4. Perform topological sort
5. Execute tasks respecting dependencies
6. Parallel execution ONLY for dependency-independent tasks

---

## 6. Execution Constraints

### Concurrency

* No uncontrolled parallel experiment execution.
* Maximum parallel experiments must be explicitly configured.

### Code Structure

* Code must be modular.
* All logic must not reside in a single file.
* Each experiment must have its own directory.

### Reproducibility Requirements

Each experiment MUST generate:

* `config.yaml`
* `environment.yaml`
* `results.json`
* `log.txt`
* Random seed specification
* Git commit hash

If any artifact is missing, the task is considered failed.

---

# Agent Instantiation Rules

At system start:

1. Read agent definitions from `.claude/agents/*.md`
2. Load skill modules from `.claude/skills/*/SKILL.md`
3. Load workflow definition from `src/task_graph.yaml`
4. Initialize Agent Team
5. Spawn agents according to task graph requirements

Agents are instantiated only when needed.

---

# Collaboration Protocol

## Inter-Agent Communication

* All messages flow through the orchestrator.
* No direct uncontrolled communication.
* Persistent state stored in `.claude/state/`.

## Result Propagation

* Task outputs are written to disk.
* Downstream tasks read from file artifacts.
* Dependency edges determine data flow.

---

## Conflict Resolution

* PI has final authority.
* Analyst validates empirical claims.
* Theorist validates theoretical claims.
* Writer cannot modify experimental conclusions.

---

# Error Recovery Protocol

If a task fails:

1. Mark task as failed.
2. Generate structured failure report.
3. Spawn debugging subtask.
4. Patch must be reviewed by PI before re-execution.

Automatic blind retry is prohibited.

---

# Workflow Execution Model

### Task States

```
pending -> running -> completed
                \-> failed
```

### Execution Order

1. Load workflow definition
2. Validate schema
3. Build dependency graph
4. Execute in topological order
5. Persist results
6. Validate completion criteria

---

# Starting the System

```bash
pip install -r requirements.txt
python -m src.server
```

Or:

```bash
python -c "from src.orchestrator import Orchestrator; o = Orchestrator()"
```

Agent Teams must be enabled before startup.

---

# Extending the System

## Adding a New Agent Role

1. Create `.claude/agents/<role>.md`
2. Define scope and responsibility boundaries
3. Associate allowed skills
4. Update orchestrator logic if required

---

## Adding a New Skill

1. Create `.claude/skills/<skill_name>/SKILL.md`
2. Define trigger conditions
3. Define structured output schema
4. Specify file output destination

---

# Research Protocol Compliance

All research conducted through MAS must:

1. Document sources
2. Acknowledge limitations
3. Log parameters and seeds
4. Preserve reproducibility artifacts
5. Follow ethical research guidelines

---

# System Philosophy

MAS is not a conversational assistant.

It is a structured scientific operating system designed for:

* Modularity
* Reproducibility
* Role specialization
* Controlled execution
* Auditability

All design decisions must preserve these properties.
