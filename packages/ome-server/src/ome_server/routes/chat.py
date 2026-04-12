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
    """Stream chat response via SSE with TRUE LLM streaming.

    Event order:
      1. ``meta``  — mood/bond/phase/memories_recalled_count (sent BEFORE the
         LLM is even called, so UI can render an instant first-token placeholder).
      2. ``token`` (many) — raw LLM deltas as they arrive.
      3. ``done``  — final reply + gamification events. The bookkeeping
         (commit, life-state updates, achievements) runs in a background
         thread launched at ``done`` — the stream returns immediately.
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    # Stage 1: prepare (fast, sync) — off the event loop to keep it responsive
    prep = await asyncio.to_thread(ome.chat_stream_prepare, req.message)
    system_prompt = prep["system_prompt"]
    user_message = prep["user_message"]
    meta = prep["meta"]

    async def generate():
        # ── 1. meta event: zero-LLM first-token placeholder ──
        yield f"data: {json.dumps({'type': 'meta', **meta}, ensure_ascii=False)}\n\n"

        # ── 2. token events: TRUE LLM streaming ──
        full_reply_parts: list[str] = []
        queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def _produce():
            try:
                for chunk in ome.stream_tokens(system_prompt, user_message):
                    if chunk:
                        loop.call_soon_threadsafe(queue.put_nowait, chunk)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        producer = asyncio.create_task(asyncio.to_thread(_produce))
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            full_reply_parts.append(chunk)
            yield f"data: {json.dumps({'type': 'token', 'token': chunk}, ensure_ascii=False)}\n\n"
        await producer

        full_reply = "".join(full_reply_parts)

        # ── 3. done event: send ASAP, then fork bookkeeping to background ──
        # Parse reply synchronously (cheap) to strip any <think> block for
        # the client, but leave the heavy commit/life updates for background.
        from ome.engine.conversation_strategy import parse_response

        stripped_reply, _thinking = parse_response(full_reply) if full_reply else ("", None)
        if not stripped_reply:
            stripped_reply = (
                "抱歉，我的大脑暂时连不上了（所有 LLM 都没响应）。"
                "不过我已经记住你说的话了，等恢复后就来找你！"
            )

        done_payload = {
            "type": "done",
            "done": True,
            "full_reply": stripped_reply,
            # Note: mood / bond / level_up / achievements are advisory here
            # — the authoritative values land during the background finalize
            # task. Clients needing post-finalize state should poll /dashboard.
            "mood": meta["mood"],
            "mood_emoji": meta["mood_emoji"],
            "bond_level": meta["bond_level"],
            "streak_days": meta["streak_days"],
        }
        yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"

        # Fire-and-forget finalize (commit + life state) on the thread pool
        async def _finalize_bg():
            try:
                await asyncio.to_thread(
                    ome.chat_stream_finalize, req.message, full_reply,
                )
            except Exception as e:
                import logging
                logging.getLogger("ome_server.chat_stream").warning(
                    "Background finalize failed: %s", e,
                )

        asyncio.create_task(_finalize_bg())

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
