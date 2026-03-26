"""Memory routes — remember, recall, forget."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ome.core import Ome
from ome_server.deps import get_ome

router = APIRouter()


class RememberRequest(BaseModel):
    text: str
    source: str = "app"


class RecallRequest(BaseModel):
    query: str
    top_k: int = 10


@router.post("/remember")
async def remember(req: RememberRequest, ome: Ome = Depends(get_ome)) -> dict[str, Any]:
    """Teach your Ome something."""
    return await asyncio.to_thread(ome.remember, req.text, source=req.source)


@router.post("/recall")
async def recall(req: RecallRequest, ome: Ome = Depends(get_ome)):
    """Search your Ome's memories."""
    results = await asyncio.to_thread(ome.recall, req.query, top_k=req.top_k)
    return {"results": results, "count": len(results)}


@router.post("/forget")
async def forget(req: RememberRequest, ome: Ome = Depends(get_ome)) -> dict[str, Any]:
    """Make your Ome forget something."""
    return await asyncio.to_thread(ome.forget, req.text)
