"""Contacts routes — CRUD for personal contacts stored as Mindos memories.

Feature E1 in Ome365. Contacts are stored as type="contact" memories in Mindos,
with structured JSON in the content field. This keeps them searchable via FTS5
and subject to the same decay/sync lifecycle as all other memories.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ome.core import Ome
from ome_server.deps import get_ome

router = APIRouter()


# ── Models ──────────────────────────────────────────────────────────

class ContactCreate(BaseModel):
    name: str
    phone: str = ""
    email: str = ""
    relationship: str = ""
    notes: str = ""
    tags: List[str] = []


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    relationship: Optional[str] = None
    notes: Optional[str] = None
    tags: Optional[List[str]] = None


class ContactOut(BaseModel):
    id: str
    name: str
    phone: str = ""
    email: str = ""
    relationship: str = ""
    notes: str = ""
    tags: List[str] = []
    created_at: Optional[float] = None


# ── Helpers ─────────────────────────────────────────────────────────

def _contact_to_content(data: dict) -> str:
    """Serialize contact dict to a searchable string + JSON block.

    Format: "Contact: Name — phone, email, relationship\\n{json}"
    The first line is FTS5-friendly; the JSON block preserves structured data.
    """
    parts = [f"Contact: {data['name']}"]
    if data.get("phone"):
        parts.append(data["phone"])
    if data.get("email"):
        parts.append(data["email"])
    if data.get("relationship"):
        parts.append(data["relationship"])
    header = " — ".join(parts)
    payload = json.dumps(data, ensure_ascii=False)
    return f"{header}\n{payload}"


def _content_to_contact(mem_id: str, content: str, created_at: float = 0) -> dict:
    """Parse a contact memory back into structured data."""
    lines = content.split("\n", 1)
    if len(lines) >= 2:
        try:
            data = json.loads(lines[1])
            data["id"] = mem_id
            data["created_at"] = created_at
            return data
        except json.JSONDecodeError:
            pass
    # Fallback: just the header line
    return {"id": mem_id, "name": content, "created_at": created_at}


def _list_contacts_sync(ome: Ome) -> list[dict]:
    """List all contact memories."""
    store = ome.soul.store
    mems = store.list_recent(limit=500, mem_type="contact")
    contacts = []
    for mem in mems:
        c = _content_to_contact(mem.id, mem.content, mem.created_at)
        contacts.append(c)
    # Sort by name
    contacts.sort(key=lambda c: c.get("name", ""))
    return contacts


def _get_contact_sync(ome: Ome, contact_id: str) -> dict:
    """Get a single contact by memory ID."""
    store = ome.soul.store
    mem = store.get(contact_id)
    if not mem or mem.type != "contact":
        return {}
    return _content_to_contact(mem.id, mem.content, mem.created_at)


def _create_contact_sync(ome: Ome, data: dict) -> dict:
    """Create a new contact memory."""
    from mindos.store import Memory
    content = _contact_to_content(data)
    mem = Memory(
        id="",
        type="contact",
        content=content,
        source="contacts",
        confidence=1.0,
    )
    ome.soul.store.add(mem)
    # Find the just-added memory by searching
    results = ome.soul.store.search_text(f"Contact: {data['name']}", limit=1)
    if results:
        return _content_to_contact(results[0].id, results[0].content, results[0].created_at)
    return {**data, "id": "unknown"}


def _update_contact_sync(ome: Ome, contact_id: str, updates: dict) -> dict:
    """Update a contact by deleting and re-creating with merged data."""
    store = ome.soul.store
    mem = store.get(contact_id)
    if not mem or mem.type != "contact":
        return {}
    existing = _content_to_contact(mem.id, mem.content, mem.created_at)
    # Merge updates (only non-None fields)
    for k, v in updates.items():
        if v is not None:
            existing[k] = v
    # Remove old
    store.forget(mem.content[:50], mem_type="contact")
    # Re-create
    from mindos.store import Memory
    content = _contact_to_content(existing)
    new_mem = Memory(
        id="",
        type="contact",
        content=content,
        source="contacts",
        confidence=1.0,
    )
    store.add(new_mem)
    results = store.search_text(f"Contact: {existing['name']}", limit=1)
    if results:
        return _content_to_contact(results[0].id, results[0].content, results[0].created_at)
    return existing


def _delete_contact_sync(ome: Ome, contact_id: str) -> bool:
    """Delete a contact memory."""
    store = ome.soul.store
    mem = store.get(contact_id)
    if not mem or mem.type != "contact":
        return False
    # Use the first 80 chars of content as pattern for targeted deletion
    deleted = store.forget(mem.content[:80], mem_type="contact")
    return deleted > 0


def _search_contacts_sync(ome: Ome, query: str) -> list[dict]:
    """Search contacts by name/phone/email/notes."""
    store = ome.soul.store
    # Search then filter to contact type
    results = store.search_text(query, limit=50)
    contacts = []
    for mem in results:
        if mem.type == "contact":
            contacts.append(_content_to_contact(mem.id, mem.content, mem.created_at))
    return contacts


# ── Routes ──────────────────────────────────────────────────────────

@router.get("")
async def list_contacts(ome: Ome = Depends(get_ome)) -> dict[str, Any]:
    """List all contacts."""
    contacts = await asyncio.to_thread(_list_contacts_sync, ome)
    return {"contacts": contacts, "count": len(contacts)}


@router.post("")
async def create_contact(req: ContactCreate, ome: Ome = Depends(get_ome)) -> dict[str, Any]:
    """Create a new contact."""
    data = req.model_dump()
    contact = await asyncio.to_thread(_create_contact_sync, ome, data)
    return {"contact": contact}


@router.get("/search")
async def search_contacts(q: str, ome: Ome = Depends(get_ome)) -> dict[str, Any]:
    """Search contacts by name, phone, email, or notes."""
    contacts = await asyncio.to_thread(_search_contacts_sync, ome, q)
    return {"contacts": contacts, "count": len(contacts)}


@router.get("/{contact_id}")
async def get_contact(contact_id: str, ome: Ome = Depends(get_ome)) -> dict[str, Any]:
    """Get a single contact by ID."""
    contact = await asyncio.to_thread(_get_contact_sync, ome, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"contact": contact}


@router.put("/{contact_id}")
async def update_contact(contact_id: str, req: ContactUpdate,
                         ome: Ome = Depends(get_ome)) -> dict[str, Any]:
    """Update a contact."""
    updates = req.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    contact = await asyncio.to_thread(_update_contact_sync, ome, contact_id, updates)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"contact": contact}


@router.delete("/{contact_id}")
async def delete_contact(contact_id: str, ome: Ome = Depends(get_ome)) -> dict[str, Any]:
    """Delete a contact."""
    deleted = await asyncio.to_thread(_delete_contact_sync, ome, contact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"status": "deleted"}
