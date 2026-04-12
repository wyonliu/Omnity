"""D1 Voice — /api/voice/* routes."""
from __future__ import annotations

import io


def test_voice_providers(client, registered_user):
    """Check voice provider detection endpoint."""
    r = client.get("/api/voice/providers", headers=registered_user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert "stt" in body
    assert "tts" in body
    assert isinstance(body["stt_available"], bool)
    assert isinstance(body["tts_available"], bool)


def test_transcribe_requires_auth(client):
    r = client.post("/api/voice/transcribe", files={"audio": ("test.wav", b"fake", "audio/wav")})
    assert r.status_code == 401


def test_voice_chat_requires_auth(client):
    r = client.post("/api/voice/chat", files={"audio": ("test.wav", b"fake", "audio/wav")})
    assert r.status_code == 401


def test_synthesize_requires_auth(client):
    r = client.post("/api/voice/synthesize", json={"text": "hello"})
    assert r.status_code == 401


def test_transcribe_no_provider_returns_503(client, registered_user):
    """With no STT keys configured, should get 503."""
    import os
    # In test env, no OPENAI_API_KEY / DEEPSEEK_API_KEY is set
    if os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY"):
        return  # Skip if keys are actually set

    r = client.post(
        "/api/voice/transcribe",
        files={"audio": ("test.wav", b"\x00" * 100, "audio/wav")},
        headers=registered_user["headers"],
    )
    assert r.status_code == 503


def test_synthesize_empty_text(client, registered_user):
    r = client.post(
        "/api/voice/synthesize",
        json={"text": ""},
        headers=registered_user["headers"],
    )
    assert r.status_code == 400
