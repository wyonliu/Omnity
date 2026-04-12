"""D2 Smart Input — POST /api/smart-input."""
from __future__ import annotations


def test_smart_input_extracts_contact(client, registered_user):
    r = client.post(
        "/api/smart-input",
        json={"text": "张三的电话是 13800138000"},
        headers=registered_user["headers"],
    )
    assert r.status_code == 200
    body = r.json()
    assert "contacts" in body
    assert "tasks" in body
    assert "notes" in body


def test_smart_input_extracts_task(client, registered_user):
    r = client.post(
        "/api/smart-input",
        json={"text": "明天下午3点开会讨论项目方案"},
        headers=registered_user["headers"],
    )
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["tasks"], list)


def test_smart_input_fallback_to_note(client, registered_user):
    r = client.post(
        "/api/smart-input",
        json={"text": "今天天气不错"},
        headers=registered_user["headers"],
    )
    assert r.status_code == 200
    body = r.json()
    # Response structure is valid even with no LLM
    assert isinstance(body["notes"], list)
    assert isinstance(body["raw_facts"], list)


def test_smart_input_requires_auth(client):
    r = client.post("/api/smart-input", json={"text": "hello"})
    assert r.status_code == 401
