"""
Skills API - Lists available research skills/capabilities
"""

import os
from pathlib import Path
from typing import List, Dict
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

# Path to skills directory in the parent project
SKILLS_DIR = Path(__file__).parent.parent.parent.parent / ".claude" / "skills"


class Skill(BaseModel):
    name: str
    description: str
    category: str
    path: str


@router.get("/skills", response_model=List[Skill])
async def list_skills():
    """List all available skills"""
    skills = []

    if SKILLS_DIR.exists():
        for skill_path in SKILLS_DIR.iterdir():
            if skill_path.is_dir():
                skill_file = skill_path / "SKILL.md"
                description = "No description available"

                if skill_file.exists():
                    try:
                        content = skill_file.read_text()
                        # Extract first paragraph as description
                        lines = content.strip().split("\n")
                        description = lines[0] if lines else description
                    except Exception:
                        pass

                # Determine category from path
                category = skill_path.name.split("-")[0] if "-" in skill_path.name else "general"

                skills.append(Skill(
                    name=skill_path.name,
                    description=description,
                    category=category,
                    path=str(skill_path)
                ))

    return skills


@router.get("/skills/{skill_name}")
async def get_skill(skill_name: str):
    """Get detailed information about a specific skill"""
    skill_path = SKILLS_DIR / skill_name

    if not skill_path.exists():
        return {"error": "Skill not found"}

    skill_file = skill_path / "SKILL.md"
    references_dir = skill_path / "references"

    result = {
        "name": skill_name,
        "path": str(skill_path),
        "files": []
    }

    # List all files in skill directory
    if skill_path.exists():
        for f in skill_path.rglob("*"):
            if f.is_file():
                result["files"].append(str(f.relative_to(skill_path)))

    # Read SKILL.md if exists
    if skill_file.exists():
        result["content"] = skill_file.read_text()[:1000]  # First 1000 chars

    return result


@router.get("/agents")
async def list_agents():
    """List all available agent types"""
    agents = [
        {
            "type": "principal",
            "name": "Principal Investigator",
            "description": "Overall coordination, hypothesis validation, and team leadership"
        },
        {
            "type": "theorist",
            "name": "Theorist",
            "description": "Hypothesis generation and theoretical framework development"
        },
        {
            "type": "experimentalist",
            "name": "Experimentalist",
            "description": "Experiment design, implementation, and execution"
        },
        {
            "type": "analyst",
            "name": "Analyst",
            "description": "Data analysis, visualization, and statistical validation"
        },
        {
            "type": "writer",
            "name": "Writer",
            "description": "Documentation, reporting, and paper drafting"
        }
    ]
    return agents
