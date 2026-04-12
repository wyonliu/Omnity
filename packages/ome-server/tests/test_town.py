"""OmeTown routes — state, chat, scenario, clues, accuse. Simulation is stubbed."""
from __future__ import annotations


def test_town_state(client):
    r = client.get("/api/town/state")
    assert r.status_code == 200
    body = r.json()
    assert "npcs" in body
    assert "scenario" in body


def test_town_scenario(client):
    r = client.get("/api/town/scenario")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "stub-scenario"
    assert "brief" in body


def test_town_npc_chat(client):
    r = client.post(
        "/api/town/chat",
        json={"npc_id": "alice", "message": "hello"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "alice" in body["reply"]
    assert "mood" in body


def test_town_npc_chat_stream(client):
    with client.stream(
        "POST",
        "/api/town/chat/stream",
        json={"npc_id": "alice", "message": "stream hello"},
    ) as resp:
        assert resp.status_code == 200
        buf = b"".join(resp.iter_bytes())
    text = buf.decode("utf-8")
    assert "data: " in text
    assert "[DONE]" in text


def test_town_clues(client):
    r = client.get("/api/town/clues")
    assert r.status_code == 200
    body = r.json()
    assert "discovered" in body
    assert "total" in body
    assert "complete" in body


def test_town_accuse(client):
    r = client.post(
        "/api/town/accuse",
        json={"suspect_id": "alice"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["correct"] is True
    assert body["suspect"] == "alice"


def test_town_accuse_wrong(client):
    r = client.post(
        "/api/town/accuse",
        json={"suspect_id": "bob"},
    )
    assert r.status_code == 200
    assert r.json()["correct"] is False
