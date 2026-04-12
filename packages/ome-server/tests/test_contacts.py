"""E1 Contacts — CRUD at /api/contacts."""
from __future__ import annotations


def test_create_and_list_contacts(client, registered_user):
    h = registered_user["headers"]

    # Create
    r = client.post("/api/contacts", json={
        "name": "Alice",
        "phone": "13900139000",
        "relationship": "colleague",
    }, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["contact"]["name"] == "Alice"

    # List
    r = client.get("/api/contacts", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1
    names = [c["name"] for c in body["contacts"]]
    assert "Alice" in names


def test_search_contacts(client, registered_user):
    h = registered_user["headers"]

    # Seed
    client.post("/api/contacts", json={"name": "Bob", "email": "bob@test.com"}, headers=h)

    r = client.get("/api/contacts/search?q=Bob", headers=h)
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_delete_contact(client, registered_user):
    h = registered_user["headers"]

    # Create
    r = client.post("/api/contacts", json={"name": "ToDelete"}, headers=h)
    cid = r.json()["contact"]["id"]

    # Delete
    r = client.delete(f"/api/contacts/{cid}", headers=h)
    assert r.status_code == 200
    assert r.json()["status"] == "deleted"


def test_contacts_require_auth(client):
    assert client.get("/api/contacts").status_code == 401
    assert client.post("/api/contacts", json={"name": "X"}).status_code == 401
