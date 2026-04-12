"""Memory routes — remember, recall, forget, browse, stats, bulk export/import.

Feature F3 (Memory Library) adds filtered browsing, type/source/date filtering,
bulk export, and bulk import on top of the original remember/recall/forget.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ome.core import Ome
from ome_server.deps import get_ome

router = APIRouter()


# ── Request / Response models ────────────────────────────────────────

class RememberRequest(BaseModel):
    text: str
    source: str = "app"


class RecallRequest(BaseModel):
    query: str
    top_k: int = 10
    type_filter: Optional[List[str]] = None


class BrowseRequest(BaseModel):
    """Browse memories with filters — for the Memory Library UI."""
    type: Optional[str] = None
    source: Optional[str] = None
    query: Optional[str] = None
    limit: int = 50
    offset: int = 0


class BulkImportItem(BaseModel):
    content: str
    type: str = "fact"
    source: str = "import"


class BulkImportRequest(BaseModel):
    memories: List[BulkImportItem]


class BulkDeleteRequest(BaseModel):
    ids: List[str]


# ── Original routes (unchanged contract) ──────────────────────────────

@router.post("/remember")
async def remember(req: RememberRequest, ome: Ome = Depends(get_ome)) -> dict[str, Any]:
    """Teach your Ome something."""
    return await asyncio.to_thread(ome.remember, req.text, source=req.source)


@router.post("/recall")
async def recall(req: RecallRequest, ome: Ome = Depends(get_ome)):
    """Search your Ome's memories with optional type filtering."""
    results = await asyncio.to_thread(
        ome.recall, req.query, top_k=req.top_k, type_filter=req.type_filter,
    )
    return {"results": results, "count": len(results)}


@router.post("/forget")
async def forget(req: RememberRequest, ome: Ome = Depends(get_ome)) -> dict[str, Any]:
    """Make your Ome forget something."""
    return await asyncio.to_thread(ome.forget, req.text)


# ── F3: Memory Library — Browse, Stats, Bulk ops ──────────────────────

def _browse_sync(ome: Ome, type_filter: Optional[str], source_filter: Optional[str],
                 query: Optional[str], limit: int, offset: int) -> dict:
    """Browse memories with combined filters."""
    store = ome.soul.store

    if query:
        # Text search first, then filter
        raw = store.search_text(query, limit=limit + offset + 50)
    else:
        # List recent, optionally by type
        raw = store.list_recent(limit=limit + offset + 50, mem_type=type_filter)

    # Apply filters
    results = []
    for mem in raw:
        if type_filter and query and mem.type != type_filter:
            continue
        if source_filter and mem.source and source_filter not in mem.source:
            continue
        results.append({
            "id": mem.id,
            "type": mem.type,
            "content": mem.content,
            "source": mem.source,
            "confidence": mem.confidence,
            "created_at": mem.created_at,
            "access_count": mem.access_count,
            "decay_weight": mem.decay_weight,
        })

    total = len(results)
    page = results[offset:offset + limit]
    return {"memories": page, "total": total, "offset": offset, "limit": limit}


def _bulk_import_sync(ome: Ome, items: list[dict]) -> int:
    """Import multiple memories at once."""
    from mindos.store import Memory
    count = 0
    for item in items:
        mem = Memory(
            id="",
            type=item.get("type", "fact"),
            content=item["content"],
            source=item.get("source", "import"),
            confidence=1.0,
        )
        ome.soul.store.add(mem)
        count += 1
    return count


def _bulk_delete_sync(ome: Ome, ids: list[str]) -> int:
    """Delete memories by ID list."""
    store = ome.soul.store
    deleted = 0
    for mem_id in ids:
        mem = store.get(mem_id)
        if mem:
            # Use content prefix for targeted forget
            n = store.forget(mem.content[:80], mem_type=mem.type)
            deleted += n
    return deleted


def _export_sync(ome: Ome, mem_type: Optional[str]) -> list[dict]:
    """Export all memories (optionally filtered by type)."""
    store = ome.soul.store
    mems = store.list_recent(limit=10000, mem_type=mem_type)
    return [
        {
            "id": mem.id,
            "type": mem.type,
            "content": mem.content,
            "source": mem.source,
            "confidence": mem.confidence,
            "created_at": mem.created_at,
        }
        for mem in mems
    ]


@router.post("/memories/browse")
async def browse_memories(req: BrowseRequest, ome: Ome = Depends(get_ome)):
    """Browse memories with type/source/query filters and pagination.

    The Memory Library UI uses this for filtered browsing.
    """
    result = await asyncio.to_thread(
        _browse_sync, ome, req.type, req.source, req.query, req.limit, req.offset,
    )
    return result


@router.get("/memories/stats")
async def memory_stats(ome: Ome = Depends(get_ome)):
    """Memory health dashboard — total, by_type, decay, recent activity."""
    stats = await asyncio.to_thread(ome.memory_stats)
    return stats


@router.get("/memories/types")
async def memory_types(ome: Ome = Depends(get_ome)):
    """List distinct memory types with counts (for filter dropdowns)."""
    stats = await asyncio.to_thread(ome.memory_stats)
    return {"types": stats.get("by_type", {})}


@router.post("/memories/export")
async def export_memories(
    type: Optional[str] = Query(None, description="Filter by memory type"),
    ome: Ome = Depends(get_ome),
):
    """Export all memories as JSON (for backup / migration)."""
    memories = await asyncio.to_thread(_export_sync, ome, type)
    return {"memories": memories, "count": len(memories), "exported_at": time.time()}


@router.post("/memories/import")
async def import_memories(req: BulkImportRequest, ome: Ome = Depends(get_ome)):
    """Bulk import memories from JSON."""
    items = [item.model_dump() for item in req.memories]
    count = await asyncio.to_thread(_bulk_import_sync, ome, items)
    return {"imported": count}


@router.post("/memories/delete-batch")
async def delete_batch(req: BulkDeleteRequest, ome: Ome = Depends(get_ome)):
    """Bulk delete memories by ID list."""
    deleted = await asyncio.to_thread(_bulk_delete_sync, ome, req.ids)
    return {"deleted": deleted}
