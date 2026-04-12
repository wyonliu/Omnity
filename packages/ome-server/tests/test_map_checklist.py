"""C7 Map & Checklist — /api/map/* and /api/checklists/*."""
from __future__ import annotations


# ── Map ────────────────────────────────────────────────────────────────

def test_get_map(client, registered_user):
    r = client.get("/api/map", headers=registered_user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["grid_width"] == 18
    assert body["grid_height"] == 18
    assert len(body["walkability"]) == 18
    assert len(body["walkability"][0]) == 18
    assert isinstance(body["npcs"], list)
    assert isinstance(body["landmarks"], list)


def test_get_map_npcs(client, registered_user):
    r = client.get("/api/map/npcs", headers=registered_user["headers"])
    assert r.status_code == 200
    assert "npcs" in r.json()


def test_pathfinding(client, registered_user):
    r = client.post("/api/map/path", json={
        "from_col": 1, "from_row": 1,
        "to_col": 3, "to_row": 3,
    }, headers=registered_user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert "path" in body
    assert "distance" in body
    assert "reachable" in body


def test_pathfinding_unreachable(client, registered_user):
    """Path to an out-of-bounds cell should return reachable=false."""
    r = client.post("/api/map/path", json={
        "from_col": 1, "from_row": 1,
        "to_col": 99, "to_row": 99,
    }, headers=registered_user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["reachable"] is False


def test_map_requires_auth(client):
    assert client.get("/api/map").status_code == 401
    assert client.get("/api/map/npcs").status_code == 401


# ── Checklists ─────────────────────────────────────────────────────────

def test_create_and_list_checklists(client, registered_user):
    h = registered_user["headers"]

    # Create
    r = client.post("/api/checklists", json={"title": "Shopping"}, headers=h)
    assert r.status_code == 200
    cl = r.json()["checklist"]
    assert cl["title"] == "Shopping"
    assert cl["tasks"] == []
    cl_id = cl["id"]

    # List
    r = client.get("/api/checklists", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    assert any(c["id"] == cl_id for c in body["checklists"])


def test_add_and_update_task(client, registered_user):
    h = registered_user["headers"]

    # Create checklist
    r = client.post("/api/checklists", json={"title": "Work"}, headers=h)
    cl_id = r.json()["checklist"]["id"]

    # Add task
    r = client.post(f"/api/checklists/{cl_id}/tasks", json={
        "text": "Write report",
        "priority": "high",
    }, headers=h)
    assert r.status_code == 200
    tasks = r.json()["checklist"]["tasks"]
    assert len(tasks) == 1
    assert tasks[0]["text"] == "Write report"
    task_id = tasks[0]["id"]

    # Update: mark completed
    r = client.put(f"/api/checklists/{cl_id}/tasks/{task_id}", json={
        "completed": True,
    }, headers=h)
    assert r.status_code == 200
    task = [t for t in r.json()["checklist"]["tasks"] if t["id"] == task_id][0]
    assert task["completed"] is True


def test_delete_task(client, registered_user):
    h = registered_user["headers"]

    # Create + add task
    r = client.post("/api/checklists", json={"title": "Temp"}, headers=h)
    cl_id = r.json()["checklist"]["id"]
    r = client.post(f"/api/checklists/{cl_id}/tasks", json={"text": "Delete me"}, headers=h)
    task_id = r.json()["checklist"]["tasks"][0]["id"]

    # Delete task
    r = client.delete(f"/api/checklists/{cl_id}/tasks/{task_id}", headers=h)
    assert r.status_code == 200
    assert len(r.json()["checklist"]["tasks"]) == 0


def test_delete_checklist(client, registered_user):
    h = registered_user["headers"]

    r = client.post("/api/checklists", json={"title": "ToDelete"}, headers=h)
    cl_id = r.json()["checklist"]["id"]

    r = client.delete(f"/api/checklists/{cl_id}", headers=h)
    assert r.status_code == 200

    r = client.get(f"/api/checklists/{cl_id}", headers=h)
    assert r.status_code == 404


def test_checklists_require_auth(client):
    assert client.get("/api/checklists").status_code == 401
    assert client.post("/api/checklists", json={"title": "x"}).status_code == 401
