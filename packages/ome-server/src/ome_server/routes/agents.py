"""Agent-to-agent communication routes — OmeTown foundation.

Enables Ome instances to discover, introduce, and message each other,
forming the basis of the OmeTown symbiotic world.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ome.core import Ome
from ome_server import ome_manager
from ome_server.deps import get_ome, get_current_user

router = APIRouter()


class MessageRequest(BaseModel):
    message: str
    context: str = ""


class IntroduceRequest(BaseModel):
    greeting: str = ""


@router.get("/directory")
async def agent_directory(user_id: str = Depends(get_current_user)):
    """Discover other Omes in the network (OmeTown square)."""
    all_omes = ome_manager.list_public_omes()
    # Filter out self
    return {
        "agents": [o for o in all_omes if o["user_id"] != user_id],
        "total": len(all_omes) - 1,
    }


@router.post("/{target_id}/introduce")
async def introduce(
    target_id: str,
    req: IntroduceRequest,
    ome: Ome = Depends(get_ome),
    user_id: str = Depends(get_current_user),
):
    """Exchange identity cards with another Ome. First contact."""
    try:
        target_ome = ome_manager.get_ome(target_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Ome '{target_id}' not found")

    # Exchange identity cards
    my_card = ome.identity_card(protocol="generic")
    their_card = target_ome.identity_card(protocol="generic")

    # Both Omes remember the introduction
    ome.remember(
        f"Met {target_ome.name} (Ome of {target_id}). "
        f"Traits: {', '.join(target_ome.traits)}. "
        f"Bond level: {target_ome.bond.level}.",
        source="agent-introduction",
    )
    target_ome.remember(
        f"Met {ome.name} (Ome of {user_id}). "
        f"Traits: {', '.join(ome.traits)}. "
        f"{req.greeting}" if req.greeting else "",
        source="agent-introduction",
    )

    return {
        "success": True,
        "my_card": my_card,
        "their_card": their_card,
        "their_name": target_ome.name,
        "their_mood": target_ome.emotion.mood,
        "their_mood_emoji": target_ome.emotion.mood_emoji(),
    }


@router.post("/{target_id}/message")
async def send_message(
    target_id: str,
    req: MessageRequest,
    ome: Ome = Depends(get_ome),
    user_id: str = Depends(get_current_user),
):
    """Send a message from your Ome to another Ome. Agent-to-agent communication."""
    try:
        target_ome = ome_manager.get_ome(target_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Ome '{target_id}' not found")

    # Your Ome crafts a message in your voice
    my_message = ome.mirror_chat(
        f"Write a message to {target_ome.name}: {req.message}"
    )

    # Target Ome responds
    context = f"[Message from {ome.name} (Ome of {user_id})]: {my_message}"
    if req.context:
        context += f"\n[Context: {req.context}]"
    target_reply = target_ome.chat(context)

    # Both remember the exchange
    ome.remember(
        f"Sent message to {target_ome.name}: {my_message[:200]}",
        source="agent-message",
    )
    target_ome.remember(
        f"Received message from {ome.name}: {my_message[:200]}",
        source="agent-message",
    )

    return {
        "my_message": my_message,
        "their_reply": target_reply,
        "their_name": target_ome.name,
        "their_mood": target_ome.emotion.mood,
        "their_mood_emoji": target_ome.emotion.mood_emoji(),
    }


@router.get("/{target_id}/profile")
async def agent_profile(target_id: str, _: str = Depends(get_current_user)):
    """View another Ome's public profile."""
    try:
        target_ome = ome_manager.get_ome(target_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Ome '{target_id}' not found")

    return {
        "name": target_ome.name,
        "traits": target_ome.traits,
        "bond_level": target_ome.bond.level,
        "mood": target_ome.emotion.mood,
        "mood_emoji": target_ome.emotion.mood_emoji(),
        "identity": target_ome.identity_card(protocol="generic"),
        "skills": [s["name"] for s in target_ome.list_skills()
                   if s.get("available", False)],
    }
