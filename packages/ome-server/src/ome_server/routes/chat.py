"""Chat routes — main conversation + mirror + calibrate + SSE streaming."""

from __future__ import annotations

import asyncio
import json
from typing import Any

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


class CalibrateRequest(BaseModel):
    message: str
    response: str
    feedback: str


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, ome: Ome = Depends(get_ome)):
    """Chat with your Ome. Auto-remembers everything."""
    reply = ome.chat(req.message)
    return ChatResponse(
        reply=reply,
        mood=ome.emotion.mood,
        mood_emoji=ome.emotion.mood_emoji(),
        bond_level=ome.bond.level,
        streak_days=ome.bond.streak_days,
    )


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest, ome: Ome = Depends(get_ome)):
    """Stream chat response via SSE. Token-by-token delivery."""
    reply = ome.chat(req.message)

    async def generate():
        # Stream tokens (simulate word-by-word for non-streaming LLMs)
        words = reply.split()
        for i, word in enumerate(words):
            token = word if i == 0 else " " + word
            data = json.dumps({"token": token}, ensure_ascii=False)
            yield f"data: {data}\n\n"
            await asyncio.sleep(0.03)  # 30ms per word for natural feel

        # Final event with metadata
        done = json.dumps({
            "done": True,
            "full_reply": reply,
            "mood": ome.emotion.mood,
            "mood_emoji": ome.emotion.mood_emoji(),
            "bond_level": ome.bond.level,
            "streak_days": ome.bond.streak_days,
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
    reply = ome.mirror_chat(req.message)
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
    result = ome.calibrate(req.message, req.response, req.feedback)
    return result


@router.get("/events")
async def check_events(ome: Ome = Depends(get_ome)):
    """Check proactive events (morning greeting, streak reminder, etc.)."""
    events = ome.check_events()
    return [
        {
            "event_name": e.event_name,
            "message": e.message,
            "needs_approval": e.needs_approval,
        }
        for e in events
    ]
