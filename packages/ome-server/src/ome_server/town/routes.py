"""OmeTown API routes — town state, NPC chat, scenario progress."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ome_server.town.simulation import get_simulation

log = logging.getLogger("ome_server.town.routes")

router = APIRouter(prefix="/api/town", tags=["town"])


# ── Models ─────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    npc_id: str
    message: str

class AccuseRequest(BaseModel):
    suspect_id: str


# ── Routes ─────────────────────────────────────────────────────────

@router.get("/state")
async def get_town_state():
    """Get full town state: NPC positions, activities, scenario progress."""
    sim = get_simulation()
    return sim.get_state()


@router.post("/chat")
async def chat_with_npc(req: ChatRequest):
    """Chat with an NPC. Returns their response powered by real Ome brain."""
    sim = get_simulation()
    result = await sim.npc_chat(req.npc_id, req.message)
    return result


@router.post("/chat/stream")
async def chat_with_npc_stream(req: ChatRequest):
    """SSE streaming chat with an NPC."""
    sim = get_simulation()

    async def event_stream():
        async for chunk in sim.npc_chat_stream(req.npc_id, req.message):
            yield f"data: {json.dumps({'token': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/accuse")
async def accuse_suspect(req: AccuseRequest):
    """Accuse a suspect of the theft. Returns whether correct."""
    sim = get_simulation()
    return sim.accuse(req.suspect_id)


@router.get("/scenario")
async def get_scenario():
    """Get scenario description and current progress."""
    sim = get_simulation()
    state = sim.get_state()
    return state["scenario"]


@router.get("/clues")
async def get_discovered_clues():
    """Get list of clues the player has discovered."""
    sim = get_simulation()
    from ome_server.town.scenario import EVIDENCE_CHAIN
    discovered = []
    for ev in EVIDENCE_CHAIN:
        if ev["clue"] in sim.player_discovered_clues:
            discovered.append({
                "clue": ev["clue"],
                "source": ev["source"],
                "description": ev["description"],
            })
    return {
        "discovered": discovered,
        "total": len(EVIDENCE_CHAIN),
        "complete": sim.scenario_complete,
    }
