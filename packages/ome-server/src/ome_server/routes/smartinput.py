"""Smart Input route — AI-powered structured extraction from natural language.

Exposes ome.smart_extract() which parses contacts, tasks, and notes from free text.
Feature D2 in Ome365.
"""

from __future__ import annotations

import asyncio
from typing import Any, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ome.core import Ome
from ome_server.deps import get_ome

router = APIRouter()


class SmartInputRequest(BaseModel):
    text: str


class ExtractedContact(BaseModel):
    name: str
    info: str = ""


class ExtractedTask(BaseModel):
    title: str
    due: str = ""
    priority: str = "medium"


class ExtractedNote(BaseModel):
    content: str


class SmartInputResponse(BaseModel):
    contacts: List[ExtractedContact]
    tasks: List[ExtractedTask]
    notes: List[ExtractedNote]
    raw_facts: List[str]


@router.post("/smart-input", response_model=SmartInputResponse)
async def smart_input(req: SmartInputRequest, ome: Ome = Depends(get_ome)) -> dict[str, Any]:
    """Extract structured data (contacts, tasks, notes) from natural language text.

    Uses LLM when available, falls back to regex extraction.
    Also commits the input to Ome's memory.
    """
    result = await asyncio.to_thread(ome.smart_extract, req.text)
    return result
