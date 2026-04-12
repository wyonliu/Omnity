"""F3 Memory Library — browse, stats, bulk ops at /api/memories/*."""
from __future__ import annotations


def test_memory_stats(client, registered_user):
    h = registered_user["headers"]
    # Seed some memories
    client.post("/api/remember", json={"text": "user: I love Python"}, headers=h)
    client.post("/api/remember", json={"text": "user: I live in Beijing"}, headers=h)

    r = client.get("/api/memories/stats", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert "total" in body
    assert "by_type" in body
    assert body["total"] >= 2


def test_memory_types(client, registered_user):
    h = registered_user["headers"]
    r = client.get("/api/memories/types", headers=h)
    assert r.status_code == 200
    assert "types" in r.json()


def test_browse_memories(client, registered_user):
    h = registered_user["headers"]
    # Seed
    client.post("/api/remember", json={"text": "user: I like hiking"}, headers=h)

    r = client.post("/api/memories/browse", json={"limit": 10}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert "memories" in body
    assert "total" in body


def test_browse_with_type_filter(client, registered_user):
    h = registered_user["headers"]
    r = client.post("/api/memories/browse", json={"type": "fact", "limit": 10}, headers=h)
    assert r.status_code == 200
    for mem in r.json()["memories"]:
        assert mem["type"] == "fact"


def test_browse_with_query(client, registered_user):
    h = registered_user["headers"]
    client.post("/api/remember", json={"text": "user: I enjoy swimming"}, headers=h)

    r = client.post("/api/memories/browse", json={"query": "swimming", "limit": 10}, headers=h)
    assert r.status_code == 200


def test_recall_with_type_filter(client, registered_user):
    h = registered_user["headers"]
    r = client.post("/api/recall", json={
        "query": "anything",
        "type_filter": ["fact"],
    }, headers=h)
    assert r.status_code == 200


def test_export_memories(client, registered_user):
    h = registered_user["headers"]
    r = client.post("/api/memories/export", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert "memories" in body
    assert "count" in body
    assert "exported_at" in body


def test_bulk_import(client, registered_user):
    h = registered_user["headers"]
    r = client.post("/api/memories/import", json={
        "memories": [
            {"content": "imported fact 1", "type": "fact"},
            {"content": "imported fact 2", "type": "fact", "source": "bulk"},
        ],
    }, headers=h)
    assert r.status_code == 200
    assert r.json()["imported"] == 2


def test_bulk_delete(client, registered_user):
    h = registered_user["headers"]
    # Import then export to get IDs
    client.post("/api/memories/import", json={
        "memories": [{"content": "deleteme-unique-string-xyz"}],
    }, headers=h)
    export = client.post("/api/memories/export", headers=h).json()
    ids_to_delete = [m["id"] for m in export["memories"]
                     if "deleteme-unique-string-xyz" in m["content"]]
    if ids_to_delete:
        r = client.post("/api/memories/delete-batch", json={"ids": ids_to_delete}, headers=h)
        assert r.status_code == 200
        assert r.json()["deleted"] >= 1


def test_memory_library_requires_auth(client):
    assert client.get("/api/memories/stats").status_code == 401
    assert client.post("/api/memories/browse", json={}).status_code == 401
    assert client.post("/api/memories/export").status_code == 401
