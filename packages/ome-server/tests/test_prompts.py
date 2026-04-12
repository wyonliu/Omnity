"""Prompt generation routes — /prompts/generate, /greeting."""
from __future__ import annotations


def test_generate_prompts(client, registered_user):
    r = client.post(
        "/api/prompts/generate",
        json={"count": 3, "context": ""},
        headers=registered_user["headers"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["prompts"] == ["prompt-0", "prompt-1", "prompt-2"]
    assert "mood" in body
    assert "mood_emoji" in body
    assert "bond_level" in body


def test_generate_prompts_custom_count(client, registered_user):
    r = client.post(
        "/api/prompts/generate",
        json={"count": 5, "context": "morning"},
        headers=registered_user["headers"],
    )
    assert r.status_code == 200
    assert len(r.json()["prompts"]) == 5


def test_generate_prompts_requires_auth(client):
    r = client.post("/api/prompts/generate", json={"count": 3})
    assert r.status_code == 401


def test_greeting(client, registered_user):
    r = client.get("/api/greeting", headers=registered_user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["greeting"] == "stub-greeting"
    assert "mood" in body


def test_greeting_requires_auth(client):
    r = client.get("/api/greeting")
    assert r.status_code == 401
