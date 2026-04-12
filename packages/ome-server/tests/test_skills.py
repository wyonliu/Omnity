"""Skills routes — list + execute."""
from __future__ import annotations


def test_list_skills(client, registered_user):
    r = client.get("/api/skills", headers=registered_user["headers"])
    assert r.status_code == 200
    skills = r.json()
    assert isinstance(skills, list)


def test_list_skills_requires_auth(client):
    r = client.get("/api/skills")
    assert r.status_code == 401


def test_use_skill_happy_path(client, registered_user):
    r = client.post(
        "/api/skills/anything",
        json={"kwargs": {"topic": "hello"}},
        headers=registered_user["headers"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["output"].startswith("stub-skill:")
    assert body["output_type"] == "text"
    assert body["needs_approval"] is False


def test_use_skill_with_empty_kwargs(client, registered_user):
    r = client.post(
        "/api/skills/any",
        json={"kwargs": {}},
        headers=registered_user["headers"],
    )
    assert r.status_code == 200


def test_use_skill_requires_auth(client):
    r = client.post("/api/skills/any", json={"kwargs": {}})
    assert r.status_code == 401
