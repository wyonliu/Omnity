"""Auth flow — register, login, duplicate, JWT correctness."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from jose import jwt


def test_register_returns_token(client):
    uid = f"reg_{uuid.uuid4().hex[:8]}"
    r = client.post(
        "/api/auth/register",
        json={"user_id": uid, "password": "pw123", "name": "Reg User"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == uid
    assert body["name"] == "Reg User"
    assert isinstance(body["token"], str) and len(body["token"]) > 20


def test_register_duplicate_conflict(client):
    uid = f"dup_{uuid.uuid4().hex[:8]}"
    r1 = client.post("/api/auth/register", json={"user_id": uid, "password": "p"})
    assert r1.status_code == 200
    r2 = client.post("/api/auth/register", json={"user_id": uid, "password": "p"})
    assert r2.status_code == 409
    assert "already exists" in r2.json()["detail"]


def test_login_success(client):
    uid = f"log_{uuid.uuid4().hex[:8]}"
    client.post("/api/auth/register", json={"user_id": uid, "password": "secret", "name": "L"})
    r = client.post("/api/auth/login", json={"user_id": uid, "password": "secret"})
    assert r.status_code == 200
    assert r.json()["user_id"] == uid


def test_login_wrong_password(client):
    uid = f"lw_{uuid.uuid4().hex[:8]}"
    client.post("/api/auth/register", json={"user_id": uid, "password": "correct"})
    r = client.post("/api/auth/login", json={"user_id": uid, "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post(
        "/api/auth/login",
        json={"user_id": f"ghost_{uuid.uuid4().hex[:6]}", "password": "x"},
    )
    assert r.status_code == 401


def test_token_decodable_and_valid(registered_user):
    from ome_server.deps import ALGORITHM, SECRET_KEY

    payload = jwt.decode(registered_user["token"], SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == registered_user["user_id"]
    assert "exp" in payload


def test_expired_token_rejected(client):
    from ome_server.deps import ALGORITHM, SECRET_KEY

    expired = jwt.encode(
        {"sub": "x", "exp": datetime.utcnow() - timedelta(days=1)},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    r = client.get("/api/status", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401


def test_malformed_token_rejected(client):
    r = client.get("/api/status", headers={"Authorization": "Bearer notarealjwt"})
    assert r.status_code == 401


def test_missing_auth_header_rejected(client):
    r = client.get("/api/status")
    assert r.status_code == 401


def test_wrong_scheme_rejected(client):
    r = client.get("/api/status", headers={"Authorization": "Basic abc"})
    assert r.status_code == 401


def test_login_returns_same_user_twice(client):
    uid = f"tw_{uuid.uuid4().hex[:8]}"
    client.post("/api/auth/register", json={"user_id": uid, "password": "p", "name": "Twice"})
    t1 = client.post("/api/auth/login", json={"user_id": uid, "password": "p"}).json()["token"]
    t2 = client.post("/api/auth/login", json={"user_id": uid, "password": "p"}).json()["token"]
    # Tokens are signed with same secret and same subject — should both work
    r = client.get("/api/status", headers={"Authorization": f"Bearer {t1}"})
    assert r.status_code == 200
    r = client.get("/api/status", headers={"Authorization": f"Bearer {t2}"})
    assert r.status_code == 200
