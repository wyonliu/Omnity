"""Life routes — dashboard, status, identity, profile, daily-challenge, soul-card."""
from __future__ import annotations


def test_dashboard(client, registered_user):
    r = client.get("/api/dashboard", headers=registered_user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert "bond" in body
    assert "achievements" in body
    assert "streak" in body


def test_status(client, registered_user):
    r = client.get("/api/status", headers=registered_user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert "memory" in body or "identity" in body


def test_identity_default_protocol(client, registered_user):
    r = client.get("/api/identity", headers=registered_user["headers"])
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


def test_identity_custom_protocol(client, registered_user):
    r = client.get(
        "/api/identity?protocol=a2a",
        headers=registered_user["headers"],
    )
    assert r.status_code == 200


def test_daily_challenge(client, registered_user):
    r = client.get("/api/daily-challenge", headers=registered_user["headers"])
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


def test_profile(client, registered_user):
    r = client.get("/api/profile", headers=registered_user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["name"]
    assert "traits" in body
    assert "bond" in body
    assert "streak" in body
    assert "emotion" in body
    assert "autonomy" in body


def test_soul_card_not_ready(client, registered_user):
    # Fresh user has 0 interactions — card shouldn't be ready
    r = client.get("/api/soul-card", headers=registered_user["headers"])
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is False
    assert "conversations_needed" in body


def test_soul_card_image_not_ready(client, registered_user):
    r = client.get("/api/soul-card/image", headers=registered_user["headers"])
    assert r.status_code == 400


def test_dashboard_requires_auth(client):
    r = client.get("/api/dashboard")
    assert r.status_code == 401


def test_profile_requires_auth(client):
    r = client.get("/api/profile")
    assert r.status_code == 401
