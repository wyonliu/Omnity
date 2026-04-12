"""Memory routes — /remember, /recall, /forget."""
from __future__ import annotations


def test_remember_returns_metadata(client, registered_user):
    r = client.post(
        "/api/remember",
        json={"text": "user: I love hiking", "source": "test"},
        headers=registered_user["headers"],
    )
    assert r.status_code == 200
    body = r.json()
    assert "facts_added" in body or "method" in body


def test_recall_returns_results_key(client, registered_user):
    # Seed a memory first
    client.post(
        "/api/remember",
        json={"text": "user: my favorite color is indigo", "source": "test"},
        headers=registered_user["headers"],
    )
    r = client.post(
        "/api/recall",
        json={"query": "favorite color", "top_k": 5},
        headers=registered_user["headers"],
    )
    assert r.status_code == 200
    body = r.json()
    assert "results" in body
    assert "count" in body
    assert isinstance(body["results"], list)
    assert body["count"] == len(body["results"])


def test_forget_returns_metadata(client, registered_user):
    # Seed something to forget
    client.post(
        "/api/remember",
        json={"text": "user: I dislike coriander", "source": "test"},
        headers=registered_user["headers"],
    )
    r = client.post(
        "/api/forget",
        json={"text": "coriander", "source": "test"},
        headers=registered_user["headers"],
    )
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


def test_remember_requires_auth(client):
    r = client.post("/api/remember", json={"text": "hi"})
    assert r.status_code == 401


def test_recall_requires_auth(client):
    r = client.post("/api/recall", json={"query": "hi"})
    assert r.status_code == 401


def test_forget_requires_auth(client):
    r = client.post("/api/forget", json={"text": "hi"})
    assert r.status_code == 401


def test_recall_default_top_k(client, registered_user):
    r = client.post(
        "/api/recall",
        json={"query": "anything"},
        headers=registered_user["headers"],
    )
    assert r.status_code == 200


def test_remember_default_source(client, registered_user):
    r = client.post(
        "/api/remember",
        json={"text": "user: I drink oolong tea"},
        headers=registered_user["headers"],
    )
    assert r.status_code == 200
