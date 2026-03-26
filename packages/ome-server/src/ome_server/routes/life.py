"""Life routes — dashboard, status, identity, autonomy, soul card."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from ome.core import Ome
from ome_server.deps import get_ome

router = APIRouter()


@router.get("/dashboard")
async def dashboard(ome: Ome = Depends(get_ome)) -> dict[str, Any]:
    """Full life dashboard: bond, achievements, skills, streak, emotion, highlights."""
    return await asyncio.to_thread(ome.life_dashboard)


@router.get("/status")
async def status(ome: Ome = Depends(get_ome)) -> dict[str, Any]:
    """Ome status: memory stats, soul age, version."""
    return ome.status()


@router.get("/identity")
async def identity(protocol: str = "generic", ome: Ome = Depends(get_ome)) -> dict[str, Any]:
    """Cross-ecosystem identity card."""
    return ome.identity_card(protocol=protocol)


@router.get("/daily-challenge")
async def daily_challenge(ome: Ome = Depends(get_ome)) -> dict[str, Any]:
    """Today's daily challenge with progress."""
    return ome.get_daily_challenge()


@router.get("/soul-card")
async def soul_card(ome: Ome = Depends(get_ome)) -> dict[str, Any]:
    """Get Soul Card data (JSON). Use /soul-card/image for the rendered PNG."""
    if not ome.soul_card_ready():
        return {"ready": False, "conversations_needed": 10 - ome.bond.total_interactions}
    card = await asyncio.to_thread(ome.soul_card)
    return {"ready": True, **card.to_dict()}


@router.get("/soul-card/image")
async def soul_card_image(ome: Ome = Depends(get_ome)):
    """Get Soul Card as a rendered PNG image."""
    if not ome.soul_card_ready():
        raise HTTPException(status_code=400, detail="需要至少10次对话才能生成灵魂卡片")
    png_bytes = await asyncio.to_thread(ome.soul_card_image)
    return Response(content=png_bytes, media_type="image/png")


@router.get("/profile")
async def profile(ome: Ome = Depends(get_ome)):
    """User profile summary for the app."""
    return {
        "name": ome.name,
        "traits": ome.traits,
        "bond": ome.bond.current_level_info(),
        "streak": {
            "current": ome.bond.streak_days,
            "max": ome.bond.max_streak,
        },
        "emotion": ome.emotion.to_dict(),
        "autonomy": {
            "state": ome.autonomy.state.value,
            "level": ome.autonomy.autonomy_level.name.lower(),
        },
        "total_memories": ome.soul.status().get("memory", {}).get("total", 0),
        "achievements_count": f"{ome.achievements.unlocked_count()}/{ome.achievements.total_count()}",
        "daily_challenge": ome.get_daily_challenge(),
    }
