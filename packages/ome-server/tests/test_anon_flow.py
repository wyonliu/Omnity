"""Anonymous session flow — zero-registration first chat and migration."""
from __future__ import annotations

import uuid


def test_create_anon_session(client):
    r = client.post("/api/anon/session")
    assert r.status_code == 200
    sid = r.json()["session_id"]
    assert sid.startswith("anon_")


def test_anon_chat_requires_session_header(client):
    r = client.post("/api/anon/chat", json={"message": "hi"})
    # Missing X-Session-ID header → 422 (FastAPI) or 400
    assert r.status_code in (400, 422)


def test_anon_chat_happy_path(client, anon_session):
    r = client.post(
        "/api/anon/chat",
        json={"message": "hello"},
        headers={"X-Session-ID": anon_session},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["reply"].startswith("stub-reply")
    assert body["session_id"] == anon_session
    assert body["message_count"] == 1
    assert "mood" in body
    assert "mood_emoji" in body


def test_anon_chat_unknown_session(client):
    r = client.post(
        "/api/anon/chat",
        json={"message": "hi"},
        headers={"X-Session-ID": "anon_doesnotexist999"},
    )
    assert r.status_code == 404


def test_anon_chat_message_count_increments(client, anon_session):
    for expected in (1, 2, 3):
        r = client.post(
            "/api/anon/chat",
            json={"message": f"msg {expected}"},
            headers={"X-Session-ID": anon_session},
        )
        assert r.status_code == 200
        assert r.json()["message_count"] == expected


def test_anon_to_user_migration(client):
    sid = client.post("/api/anon/session").json()["session_id"]
    client.post(
        "/api/anon/chat",
        json={"message": "my first message"},
        headers={"X-Session-ID": sid},
    )
    uid = f"mig_{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/api/auth/register",
        json={
            "user_id": uid,
            "password": "pw",
            "name": "Migrated",
            "session_id": sid,
        },
    )
    assert r.status_code == 200
    assert r.json()["user_id"] == uid
    # Subsequent chat under the new user should work
    headers = {"Authorization": f"Bearer {r.json()['token']}"}
    chat = client.post("/api/chat", json={"message": "after migration"}, headers=headers)
    assert chat.status_code == 200


def test_migration_with_unknown_session_errors(client):
    uid = f"badmig_{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/api/auth/register",
        json={"user_id": uid, "password": "pw", "session_id": "anon_nope"},
    )
    # Should fail gracefully — either 404/409/500 not crash the server
    assert r.status_code >= 400
