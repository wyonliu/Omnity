"""Life routes — dashboard, status, identity, autonomy."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ome.core import Ome
from ome_server.deps import get_ome

router = APIRouter()


@router.get("/dashboard")
async def dashboard(ome: Ome = Depends(get_ome)) -> dict[str, Any]:
    """Full life dashboard: bond, achievements, skills, streak, emotion, highlights."""
    return ome.life_dashboard()


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
