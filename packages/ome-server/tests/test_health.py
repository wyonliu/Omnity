"""Smoke tests for root and health endpoints."""
from __future__ import annotations


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["service"] == "ome-server"
    assert body["status"] == "running"
    assert "version" in body


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_openapi_exposed(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert schema["info"]["title"] == "Ome Server"
    # All major routers must be mounted
    paths = schema["paths"]
    assert "/api/auth/register" in paths
    assert "/api/auth/login" in paths
    assert "/api/anon/session" in paths
    assert "/api/chat" in paths
    assert "/api/remember" in paths
    assert "/api/skills" in paths
    assert "/api/town/state" in paths


def test_404_on_unknown_path(client):
    r = client.get("/api/definitely-not-a-real-route")
    assert r.status_code == 404


def test_health_is_public(client):
    # Health must not require auth
    r = client.get("/api/health", headers={})
    assert r.status_code == 200
