"""Anonymous session routes — zero-registration first chat."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from ome_server import ome_manager

router = APIRouter()


class AnonChatRequest(BaseModel):
    message: str


class AnonChatResponse(BaseModel):
    reply: str
    mood: str
    mood_emoji: str
    message_count: int
    session_id: str


@router.post("/session")
async def create_session():
    """Create a new anonymous session. No auth needed."""
    session_id = ome_manager.create_anon_session()
    return {"session_id": session_id}


@router.post("/chat", response_model=AnonChatResponse)
async def anon_chat(
    req: AnonChatRequest,
    x_session_id: str = Header(..., alias="X-Session-ID"),
):
    """Chat without registering. Pass X-Session-ID header."""
    try:
        result = ome_manager.anon_chat(x_session_id, req.message)
        return AnonChatResponse(**result)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found or expired")
