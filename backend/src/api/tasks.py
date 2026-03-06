"""
Tasks API - Manages research tasks and workflows
"""

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

router = APIRouter()


# In-memory task storage (replace with database in production)
tasks_db = {}


class Task(BaseModel):
    id: str
    name: str
    description: str
    agent: str  # principal, theorist, experimentalist, analyst, writer
    status: str = "pending"  # pending, running, completed, failed
    dependencies: List[str] = []
    result: Optional[str] = None
    created_at: str
    updated_at: str


class TaskCreate(BaseModel):
    name: str
    description: str
    agent: str
    dependencies: List[str] = []


class WorkflowCreate(BaseModel):
    name: str
    description: str
    tasks: List[TaskCreate]


@router.get("/tasks")
async def list_tasks(status: Optional[str] = None):
    """List all tasks, optionally filtered by status"""
    tasks_list = list(tasks_db.values())

    if status:
        tasks_list = [t for t in tasks_list if t.status == status]

    return tasks_list


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """Get a specific task by ID"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks_db[task_id]


@router.post("/tasks")
async def create_task(task: TaskCreate):
    """Create a new task"""
    task_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat()

    new_task = Task(
        id=task_id,
        name=task.name,
        description=task.description,
        agent=task.agent,
        dependencies=task.dependencies,
        created_at=now,
        updated_at=now
    )

    tasks_db[task_id] = new_task
    return new_task


@router.post("/tasks/{task_id}/execute")
async def execute_task(task_id: str):
    """Execute a task"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks_db[task_id]

    # Check dependencies
    for dep_id in task.dependencies:
        if dep_id not in tasks_db:
            raise HTTPException(f"Dependency {dep_id} not found")
        if tasks_db[dep_id].status != "completed":
            raise HTTPException(f"Dependency {dep_id} is not completed")

    # Simulate task execution
    task.status = "running"
    task.updated_at = datetime.utcnow().isoformat()

    # In production, this would call Claude Code or the actual agent
    task.result = f"Task {task_id} executed successfully"
    task.status = "completed"
    task.updated_at = datetime.utcnow().isoformat()

    return task


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task"""
    if task_id not in tasks_db:
        raise HTTPException(status_code=404, detail="Task not found")

    task = tasks_db[task_id]
    if task.status not in ["pending", "running"]:
        raise HTTPException(f"Cannot cancel task with status: {task.status}")

    task.status = "failed"
    task.updated_at = datetime.utcnow().isoformat()
    task.result = "Cancelled by user"

    return task


@router.post("/workflows")
async def create_workflow(workflow: WorkflowCreate):
    """Create and execute a workflow with multiple tasks"""
    workflow_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat()

    created_tasks = []

    for task_data in workflow.tasks:
        task_id = str(uuid.uuid4())[:8]
        new_task = Task(
            id=task_id,
            name=task_data.name,
            description=task_data.description,
            agent=task_data.agent,
            dependencies=task_data.dependencies,
            created_at=now,
            updated_at=now
        )
        tasks_db[task_id] = new_task
        created_tasks.append(new_task)

    return {
        "id": workflow_id,
        "name": workflow.name,
        "description": workflow.description,
        "tasks": created_tasks,
        "status": "created"
    }


@router.get("/workflows")
async def list_workflows():
    """List all workflows"""
    # Group tasks by their creation time to form workflows
    return list(tasks_db.values())
