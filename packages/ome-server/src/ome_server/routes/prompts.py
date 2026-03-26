"""Prompt generation routes — personalized conversation starters via LLM."""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ome.core import Ome
from ome_server.deps import get_ome

router = APIRouter()


class PromptRequest(BaseModel):
    count: int = 3
    context: str = ""


@router.post("/prompts/generate")
async def generate_prompts(req: PromptRequest, ome: Ome = Depends(get_ome)):
    """Generate personalized conversation starters using LLM + memory."""
    prompts = await asyncio.to_thread(
        ome.generate_prompts, req.count, req.context
    )
    return {
        "prompts": prompts,
        "mood": ome.emotion.mood,
        "mood_emoji": ome.emotion.mood_emoji(),
        "bond_level": ome.bond.level,
    }


@router.get("/greeting")
async def get_greeting(ome: Ome = Depends(get_ome)):
    """Generate a personalized LLM-powered greeting."""
    greeting = await asyncio.to_thread(ome.generate_greeting)
    return {
        "greeting": greeting,
        "mood": ome.emotion.mood,
        "mood_emoji": ome.emotion.mood_emoji(),
    }
