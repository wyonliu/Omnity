"""Chat routes — main conversation + mirror + calibrate + SSE streaming."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ome.core import Ome
from ome_server.deps import get_ome
from ome_server import ome_manager

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    mood: str
    mood_emoji: str
    bond_level: int
    streak_days: int
    # Gamification events — populated when something happens
    level_up: Optional[Dict[str, Any]] = None
    achievements: Optional[List[Dict[str, Any]]] = None
    daily_challenge: Optional[Dict[str, Any]] = None


class CalibrateRequest(BaseModel):
    message: str
    response: str
    feedback: str


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, ome: Ome = Depends(get_ome)):
    """Chat with your Ome. Auto-remembers everything."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    old_level = ome.bond.level
    old_achievements = set(ome.achievements.unlocked.keys())

    reply = await asyncio.to_thread(ome.chat, req.message)

    # Detect level-up
    level_up = None
    if ome.bond.level > old_level:
        from ome.life.bond import BOND_LEVELS
        lvl_info = BOND_LEVELS[ome.bond.level]
        level_up = {
            "level": ome.bond.level,
            "name": lvl_info["name"],
            "unlocks": lvl_info["unlocks"],
        }

    # Detect new achievements
    new_achs = set(ome.achievements.unlocked.keys()) - old_achievements
    achievements = None
    if new_achs:
        achievements = [
            a for a in ome.achievements.unlocked_list()
            if a["id"] in new_achs
        ]

    # Daily challenge progress
    daily_challenge = ome.get_daily_challenge()

    return ChatResponse(
        reply=reply,
        mood=ome.emotion.mood,
        mood_emoji=ome.emotion.mood_emoji(),
        bond_level=ome.bond.level,
        streak_days=ome.bond.streak_days,
        level_up=level_up,
        achievements=achievements,
        daily_challenge=daily_challenge,
    )


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, ome: Ome = Depends(get_ome)):
    """Stream chat response via SSE. Token-by-token delivery."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    old_level = ome.bond.level
    old_achievements = set(ome.achievements.unlocked.keys())

    reply = await asyncio.to_thread(ome.chat, req.message)

    # Detect events
    level_up = None
    if ome.bond.level > old_level:
        from ome.life.bond import BOND_LEVELS
        lvl_info = BOND_LEVELS[ome.bond.level]
        level_up = {"level": ome.bond.level, "name": lvl_info["name"], "unlocks": lvl_info["unlocks"]}

    new_achs = set(ome.achievements.unlocked.keys()) - old_achievements
    achievements = [a for a in ome.achievements.unlocked_list() if a["id"] in new_achs] if new_achs else None

    async def generate():
        # Character-based chunking — works for Chinese (no word boundaries)
        # Send 2-4 chars at a time for natural streaming feel
        chunk_size = 3
        for i in range(0, len(reply), chunk_size):
            token = reply[i:i + chunk_size]
            data = json.dumps({"token": token}, ensure_ascii=False)
            yield f"data: {data}\n\n"
            await asyncio.sleep(0.03)

        # Generate follow-up suggestions (lightweight LLM call)
        try:
            follow_ups = await asyncio.to_thread(
                ome.suggest_follow_ups, req.message, reply, 3
            )
        except Exception:
            follow_ups = []

        done = json.dumps({
            "done": True,
            "full_reply": reply,
            "mood": ome.emotion.mood,
            "mood_emoji": ome.emotion.mood_emoji(),
            "bond_level": ome.bond.level,
            "streak_days": ome.bond.streak_days,
            "level_up": level_up,
            "achievements": achievements,
            "daily_challenge": ome.get_daily_challenge(),
            "suggested_follow_ups": follow_ups,
        }, ensure_ascii=False)
        yield f"data: {done}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/mirror", response_model=ChatResponse)
async def mirror(req: ChatRequest, ome: Ome = Depends(get_ome)):
    """Mirror chat — Ome responds in YOUR voice."""
    reply = await asyncio.to_thread(ome.mirror_chat, req.message)
    return ChatResponse(
        reply=reply,
        mood=ome.emotion.mood,
        mood_emoji=ome.emotion.mood_emoji(),
        bond_level=ome.bond.level,
        streak_days=ome.bond.streak_days,
    )


@router.post("/calibrate")
async def calibrate(req: CalibrateRequest, ome: Ome = Depends(get_ome)):
    """Give feedback on mirror_chat to improve persona accuracy."""
    result = await asyncio.to_thread(ome.calibrate, req.message, req.response, req.feedback)
    return result


@router.get("/events")
async def check_events(ome: Ome = Depends(get_ome)):
    """Check proactive events (morning greeting, streak reminder, etc.)."""
    events = await asyncio.to_thread(ome.check_events)
    return [
        {
            "event_name": e.event_name,
            "message": e.message,
            "needs_approval": e.needs_approval,
        }
        for e in events
    ]
