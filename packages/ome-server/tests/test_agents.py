"""Agent-to-agent routes — directory, introduce, message, profile."""
from __future__ import annotations


def test_directory_excludes_self(client, registered_user, second_user):
    r = client.get("/api/agents/directory", headers=registered_user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert "agents" in body
    assert "total" in body
    ids = [a["user_id"] for a in body["agents"]]
    # Self must be filtered out
    assert registered_user["user_id"] not in ids


def test_directory_requires_auth(client):
    r = client.get("/api/agents/directory")
    assert r.status_code == 401


def test_agent_profile_happy_path(client, registered_user, second_user):
    r = client.get(
        f"/api/agents/{second_user['user_id']}/profile",
        headers=registered_user["headers"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"]
    assert "traits" in body
    assert "bond_level" in body
    assert "mood" in body


def test_agent_profile_not_found(client, registered_user):
    r = client.get(
        "/api/agents/ghost_agent_xyz/profile",
        headers=registered_user["headers"],
    )
    assert r.status_code == 404


def test_agent_profile_requires_auth(client, second_user):
    r = client.get(f"/api/agents/{second_user['user_id']}/profile")
    assert r.status_code == 401


def test_introduce(client, registered_user, second_user):
    r = client.post(
        f"/api/agents/{second_user['user_id']}/introduce",
        json={"greeting": "hello peer"},
        headers=registered_user["headers"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert "my_card" in body
    assert "their_card" in body
    assert body["their_name"]


def test_introduce_unknown_target(client, registered_user):
    r = client.post(
        "/api/agents/ghost_target_xyz/introduce",
        json={"greeting": ""},
        headers=registered_user["headers"],
    )
    assert r.status_code == 404


def test_send_message(client, registered_user, second_user):
    r = client.post(
        f"/api/agents/{second_user['user_id']}/message",
        json={"message": "ping", "context": ""},
        headers=registered_user["headers"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["my_message"].startswith("stub-mirror")
    assert body["their_reply"].startswith("stub-reply")


def test_send_message_empty_rejected(client, registered_user, second_user):
    r = client.post(
        f"/api/agents/{second_user['user_id']}/message",
        json={"message": "  ", "context": ""},
        headers=registered_user["headers"],
    )
    assert r.status_code == 400


def test_send_message_unknown_target(client, registered_user):
    r = client.post(
        "/api/agents/ghost_nope/message",
        json={"message": "hi"},
        headers=registered_user["headers"],
    )
    assert r.status_code == 404
