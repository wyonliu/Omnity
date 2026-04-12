"""Map & Checklist routes — spatial data + task management.

Feature C7 in Ome365. Provides:
  - GET /map             — full map state (grid, walkability, NPCs, landmarks)
  - GET /map/npcs        — NPC positions and activities
  - GET /map/path        — A* pathfinding between two points
  - CRUD /checklists/*   — task checklists stored as Mindos memories
"""

from __future__ import annotations

import asyncio
import heapq
import json
import time
import uuid
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ome.core import Ome
from ome_server.deps import get_ome
from ome_server.town.simulation import (
    get_simulation, is_walkable, _GROUND_TILE_AT, _WALKABLE_GROUND,
)

router = APIRouter()


# ══════════════════════════════════════════════════════════════════════
#  MAP — Spatial data from OmeTown
# ══════════════════════════════════════════════════════════════════════

GRID_SIZE = 18


def _build_walkability_grid() -> list[list[bool]]:
    """Build 18×18 walkability matrix."""
    grid = []
    for row in range(GRID_SIZE):
        grid.append([is_walkable(col, row) for col in range(GRID_SIZE)])
    return grid


def _get_landmarks() -> list[dict]:
    """Extract notable landmarks from the tile map."""
    landmarks = []
    for (col, row), tile in _GROUND_TILE_AT.items():
        if tile == "fountain":
            landmarks.append({
                "id": f"fountain_{col}_{row}",
                "type": "fountain",
                "name": "Town Fountain",
                "col": col,
                "row": row,
                "affordances": ["observe", "sit"],
            })
        elif tile == "pool":
            landmarks.append({
                "id": f"pool_{col}_{row}",
                "type": "pool",
                "name": "Pool",
                "col": col,
                "row": row,
                "affordances": ["observe"],
            })
    return landmarks


def _get_npc_states() -> list[dict]:
    """Get current NPC positions and activities from simulation."""
    sim = get_simulation()
    state = sim.get_state()
    return state.get("npcs", [])


# ── A* Pathfinding ────────────────────────────────────────────────────

def _astar(start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
    """A* pathfinding on the 18×18 grid. Returns list of (col, row) waypoints."""
    if not is_walkable(start[0], start[1]) or not is_walkable(goal[0], goal[1]):
        return []

    def h(a: tuple[int, int], b: tuple[int, int]) -> float:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    open_set: list[tuple[float, tuple[int, int]]] = [(0, start)]
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score: dict[tuple[int, int], float] = {start: 0}

    while open_set:
        _, current = heapq.heappop(open_set)

        if current == goal:
            # Reconstruct path
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path

        for dc, dr in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            neighbor = (current[0] + dc, current[1] + dr)
            if not is_walkable(neighbor[0], neighbor[1]):
                continue
            tentative = g_score[current] + 1
            if tentative < g_score.get(neighbor, float("inf")):
                came_from[neighbor] = current
                g_score[neighbor] = tentative
                heapq.heappush(open_set, (tentative + h(neighbor, goal), neighbor))

    return []  # No path found


# ── Map Routes ────────────────────────────────────────────────────────

@router.get("/map")
async def get_map(ome: Ome = Depends(get_ome)):
    """Full map state: grid dimensions, walkability, NPC positions, landmarks."""
    walkability = await asyncio.to_thread(_build_walkability_grid)
    npcs = _get_npc_states()
    landmarks = _get_landmarks()
    return {
        "grid_width": GRID_SIZE,
        "grid_height": GRID_SIZE,
        "walkability": walkability,
        "npcs": npcs,
        "landmarks": landmarks,
    }


@router.get("/map/npcs")
async def get_map_npcs(ome: Ome = Depends(get_ome)):
    """Current NPC positions and activities."""
    return {"npcs": _get_npc_states()}


class PathRequest(BaseModel):
    from_col: int
    from_row: int
    to_col: int
    to_row: int


@router.post("/map/path")
async def find_path(req: PathRequest, ome: Ome = Depends(get_ome)):
    """A* pathfinding between two grid positions."""
    path = await asyncio.to_thread(
        _astar, (req.from_col, req.from_row), (req.to_col, req.to_row),
    )
    return {
        "path": [{"col": c, "row": r} for c, r in path],
        "distance": len(path) - 1 if path else -1,
        "reachable": len(path) > 0,
    }


# ══════════════════════════════════════════════════════════════════════
#  CHECKLISTS — Task management stored as Mindos memories
# ══════════════════════════════════════════════════════════════════════

class TaskItem(BaseModel):
    id: str = ""
    text: str
    completed: bool = False
    due: str = ""
    priority: str = "medium"
    tags: List[str] = []


class ChecklistCreate(BaseModel):
    title: str


class TaskCreate(BaseModel):
    text: str
    due: str = ""
    priority: str = "medium"
    tags: List[str] = []


class TaskUpdate(BaseModel):
    text: Optional[str] = None
    completed: Optional[bool] = None
    due: Optional[str] = None
    priority: Optional[str] = None
    tags: Optional[List[str]] = None


# ── Checklist storage helpers ─────────────────────────────────────────
# Checklists are stored as type="checklist" memories with JSON content.

def _checklist_key(checklist_id: str) -> str:
    return f"checklist:{checklist_id}"


def _load_checklist(ome: Ome, checklist_id: str) -> Optional[dict]:
    """Load a checklist from Mindos soul_state."""
    raw = ome.soul.store.get_state(_checklist_key(checklist_id))
    if not raw:
        return None
    return json.loads(raw)


def _save_checklist(ome: Ome, checklist: dict) -> None:
    """Save a checklist to Mindos soul_state."""
    ome.soul.store.set_state(
        _checklist_key(checklist["id"]),
        json.dumps(checklist, ensure_ascii=False),
    )
    # Update the index
    idx = _load_index(ome)
    if checklist["id"] not in idx:
        idx.append(checklist["id"])
        _save_index(ome, idx)


def _delete_checklist(ome: Ome, checklist_id: str) -> None:
    """Remove a checklist."""
    ome.soul.store.set_state(_checklist_key(checklist_id), "")
    idx = _load_index(ome)
    if checklist_id in idx:
        idx.remove(checklist_id)
        _save_index(ome, idx)


def _load_index(ome: Ome) -> list[str]:
    """Load the checklist ID index."""
    raw = ome.soul.store.get_state("checklists:index")
    if not raw:
        return []
    return json.loads(raw)


def _save_index(ome: Ome, idx: list[str]) -> None:
    ome.soul.store.set_state("checklists:index", json.dumps(idx))


def _list_checklists_sync(ome: Ome) -> list[dict]:
    idx = _load_index(ome)
    checklists = []
    for cid in idx:
        cl = _load_checklist(ome, cid)
        if cl:
            checklists.append(cl)
    return checklists


# ── Checklist Routes ──────────────────────────────────────────────────

@router.get("/checklists")
async def list_checklists(ome: Ome = Depends(get_ome)):
    """List all checklists."""
    checklists = await asyncio.to_thread(_list_checklists_sync, ome)
    return {"checklists": checklists, "count": len(checklists)}


@router.post("/checklists")
async def create_checklist(req: ChecklistCreate, ome: Ome = Depends(get_ome)):
    """Create a new checklist."""
    checklist = {
        "id": uuid.uuid4().hex[:12],
        "title": req.title,
        "tasks": [],
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    await asyncio.to_thread(_save_checklist, ome, checklist)
    return {"checklist": checklist}


@router.get("/checklists/{checklist_id}")
async def get_checklist(checklist_id: str, ome: Ome = Depends(get_ome)):
    """Get a single checklist."""
    cl = await asyncio.to_thread(_load_checklist, ome, checklist_id)
    if not cl:
        raise HTTPException(status_code=404, detail="Checklist not found")
    return {"checklist": cl}


@router.delete("/checklists/{checklist_id}")
async def delete_checklist_route(checklist_id: str, ome: Ome = Depends(get_ome)):
    """Delete a checklist."""
    cl = await asyncio.to_thread(_load_checklist, ome, checklist_id)
    if not cl:
        raise HTTPException(status_code=404, detail="Checklist not found")
    await asyncio.to_thread(_delete_checklist, ome, checklist_id)
    return {"status": "deleted"}


@router.post("/checklists/{checklist_id}/tasks")
async def add_task(checklist_id: str, req: TaskCreate, ome: Ome = Depends(get_ome)):
    """Add a task to a checklist."""
    def _do():
        cl = _load_checklist(ome, checklist_id)
        if not cl:
            return None
        task = {
            "id": uuid.uuid4().hex[:8],
            "text": req.text,
            "completed": False,
            "due": req.due,
            "priority": req.priority,
            "tags": req.tags,
        }
        cl["tasks"].append(task)
        cl["updated_at"] = time.time()
        _save_checklist(ome, cl)
        return cl

    cl = await asyncio.to_thread(_do)
    if not cl:
        raise HTTPException(status_code=404, detail="Checklist not found")
    return {"checklist": cl}


@router.put("/checklists/{checklist_id}/tasks/{task_id}")
async def update_task(checklist_id: str, task_id: str, req: TaskUpdate,
                      ome: Ome = Depends(get_ome)):
    """Update a task in a checklist."""
    def _do():
        cl = _load_checklist(ome, checklist_id)
        if not cl:
            return None, "Checklist not found"
        for task in cl["tasks"]:
            if task["id"] == task_id:
                updates = req.model_dump(exclude_none=True)
                for k, v in updates.items():
                    task[k] = v
                cl["updated_at"] = time.time()
                _save_checklist(ome, cl)
                return cl, None
        return None, "Task not found"

    cl, err = await asyncio.to_thread(_do)
    if err:
        raise HTTPException(status_code=404, detail=err)
    return {"checklist": cl}


@router.delete("/checklists/{checklist_id}/tasks/{task_id}")
async def delete_task(checklist_id: str, task_id: str, ome: Ome = Depends(get_ome)):
    """Remove a task from a checklist."""
    def _do():
        cl = _load_checklist(ome, checklist_id)
        if not cl:
            return None, "Checklist not found"
        before = len(cl["tasks"])
        cl["tasks"] = [t for t in cl["tasks"] if t["id"] != task_id]
        if len(cl["tasks"]) == before:
            return None, "Task not found"
        cl["updated_at"] = time.time()
        _save_checklist(ome, cl)
        return cl, None

    cl, err = await asyncio.to_thread(_do)
    if err:
        raise HTTPException(status_code=404, detail=err)
    return {"checklist": cl}
