#!/usr/bin/env python3
"""Ome + FastAPI — all 7 endpoints for a full AI twin backend.

Usage:
    pip install "omnity-ome[all]" fastapi uvicorn
    export DEEPSEEK_API_KEY="sk-..."
    uvicorn server_integration:app --reload
"""

from fastapi import FastAPI
from pydantic import BaseModel
from ome import Ome

app = FastAPI(title="Ome Twin API")
twin = Ome.load("~/.ome/server-demo")


class ChatRequest(BaseModel):
    message: str


class TextRequest(BaseModel):
    text: str


# 1. Chat with rich context
@app.post("/api/ai")
async def chat(req: ChatRequest):
    return twin.chat_rich(req.message)


# 2. Life dashboard (bond, emotion, achievements, skills)
@app.get("/api/growth")
async def growth():
    return twin.life_dashboard()


# 3. Record an interaction event
@app.post("/api/growth/interact")
async def interact():
    twin.soul.commit("interaction", "api_interaction", {})
    return {"ok": True}


# 4. Trigger personality evolution
@app.post("/api/growth/evolve")
async def evolve():
    return twin.evolve()


# 5. Search memories
@app.get("/api/memories")
async def search_memories(q: str = "", limit: int = 10):
    memories = twin.recall(q, limit=limit) if q else []
    return [{"category": m.category, "content": m.content,
             "importance": m.importance} for m in memories]


# 6. Teach a new memory
@app.post("/api/memories")
async def add_memory(req: TextRequest):
    twin.remember(req.text)
    return {"ok": True}


# 7. Smart extraction (contacts, tasks, notes)
@app.post("/api/ai/smart-input")
async def smart_input(req: TextRequest):
    return twin.smart_extract(req.text)


# 8. Proactive events check
@app.get("/api/proactive")
async def proactive():
    events = twin.check_events()
    return [{"name": e.event_name, "message": e.message} for e in events]
