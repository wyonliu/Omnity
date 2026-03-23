"""Skill routes — list and execute skills."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ome.core import Ome
from ome_server.deps import get_ome

router = APIRouter()


class SkillRequest(BaseModel):
    kwargs: dict[str, Any] = {}


@router.get("/skills")
async def list_skills(ome: Ome = Depends(get_ome)):
    """List all available skills with their status."""
    return ome.list_skills()


@router.post("/skills/{skill_name}")
async def use_skill(skill_name: str, req: SkillRequest, ome: Ome = Depends(get_ome)):
    """Execute a skill by name."""
    result = ome.use_skill(skill_name, **req.kwargs)
    return {
        "success": result.success,
        "output": result.output,
        "output_type": result.output_type,
        "needs_approval": result.needs_approval,
        "metadata": result.metadata,
    }
