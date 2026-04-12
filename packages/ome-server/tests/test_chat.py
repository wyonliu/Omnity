"""Chat routes — /chat, /chat/stream, /mirror, /calibrate, /events."""
from __future__ import annotations

import json


def test_chat_happy_path(client, registered_user):
    r = client.post(
        "/api/chat",
        json={"message": "hello ome"},
        headers=registered_user["headers"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["reply"].startswith("stub-reply")
    assert "mood" in body
    assert "mood_emoji" in body
    assert "bond_level" in body
    assert "streak_days" in body


def test_chat_empty_message_rejected(client, registered_user):
    r = client.post(
        "/api/chat",
        json={"message": "   "},
        headers=registered_user["headers"],
    )
    assert r.status_code == 400


def test_chat_requires_auth(client):
    r = client.post("/api/chat", json={"message": "hi"})
    assert r.status_code == 401


def test_chat_unknown_user_returns_404_on_ome(client):
    # Craft a token for a user that was never registered
    from ome_server.deps import create_token

    token = create_token("ghost_user_nope_123")
    r = client.post(
        "/api/chat",
        json={"message": "hi"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


def test_mirror_happy_path(client, registered_user):
    r = client.post(
        "/api/mirror",
        json={"message": "what would I say?"},
        headers=registered_user["headers"],
    )
    assert r.status_code == 200
    assert r.json()["reply"].startswith("stub-mirror")


def test_calibrate_happy_path(client, registered_user):
    r = client.post(
        "/api/calibrate",
        json={
            "message": "q",
            "response": "stub-mirror:q",
            "feedback": "too formal",
        },
        headers=registered_user["headers"],
    )
    assert r.status_code == 200
    assert r.json()["calibrated"] is True


def test_events_returns_list(client, registered_user):
    r = client.get("/api/events", headers=registered_user["headers"])
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def _parse_sse(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        if not line.startswith("data: "):
            continue
        try:
            events.append(json.loads(line.removeprefix("data: ")))
        except json.JSONDecodeError:
            pass
    return events


def test_chat_stream_emits_sse(client, registered_user):
    with client.stream(
        "POST",
        "/api/chat/stream",
        json={"message": "stream me"},
        headers=registered_user["headers"],
    ) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        buf = b"".join(resp.iter_bytes())
    events = _parse_sse(buf.decode("utf-8"))
    assert events, "SSE stream produced no events"
    # First event must be the meta (zero-LLM first-token placeholder)
    assert events[0]["type"] == "meta"
    assert "mood" in events[0]
    assert "bond_level" in events[0]
    # Must have at least one token event before done
    tokens = [e for e in events if e.get("type") == "token"]
    assert tokens, "no token events emitted"
    # Last event must be done with full_reply
    assert events[-1]["type"] == "done"
    assert events[-1]["done"] is True
    assert events[-1]["full_reply"]
    # full_reply must be the concatenation of all token chunks (true streaming,
    # not one big final chunk)
    joined = "".join(t["token"] for t in tokens)
    assert events[-1]["full_reply"] == joined


def test_chat_stream_meta_comes_before_tokens(client, registered_user):
    """TTFT guarantee: the meta event is the FIRST event emitted, before any LLM output."""
    with client.stream(
        "POST",
        "/api/chat/stream",
        json={"message": "hi"},
        headers=registered_user["headers"],
    ) as resp:
        assert resp.status_code == 200
        buf = b"".join(resp.iter_bytes())
    events = _parse_sse(buf.decode("utf-8"))
    # Walk the events — everything before the first token must be meta
    seen_token = False
    for e in events:
        if e.get("type") == "token":
            seen_token = True
        elif e.get("type") == "meta":
            assert not seen_token, "meta must arrive BEFORE any token"


def test_chat_stream_token_chunks_match_stubbed_generator(client, registered_user):
    """The server must forward stream_tokens chunks verbatim."""
    with client.stream(
        "POST",
        "/api/chat/stream",
        json={"message": "anything"},
        headers=registered_user["headers"],
    ) as resp:
        buf = b"".join(resp.iter_bytes())
    events = _parse_sse(buf.decode("utf-8"))
    tokens = [e["token"] for e in events if e.get("type") == "token"]
    assert tokens == ["Hel", "lo ", "from ", "stream"]


def test_chat_stream_empty_message_rejected(client, registered_user):
    r = client.post(
        "/api/chat/stream",
        json={"message": ""},
        headers=registered_user["headers"],
    )
    assert r.status_code == 400


def test_chat_stream_requires_auth(client):
    r = client.post("/api/chat/stream", json={"message": "hi"})
    assert r.status_code == 401
