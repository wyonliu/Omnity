"""Skill routes — list and execute skills."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
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
    try:
        result = await asyncio.to_thread(ome.use_skill, skill_name, **req.kwargs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"技能执行失败: {e}")
    return {
        "success": result.success,
        "output": result.output,
        "output_type": result.output_type,
        "needs_approval": result.needs_approval,
        "metadata": result.metadata,
    }
