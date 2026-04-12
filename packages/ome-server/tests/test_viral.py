"""Viral routes — guess-who game."""
from __future__ import annotations


def _create_game(client, registered_user):
    return client.post(
        "/api/viral/guess-game/create",
        json={
            "question": "What's your favorite color?",
            "user_answer": "Deep indigo — like twilight",
            "ome_answer": "I'd say teal — reminds me of the ocean at dusk",
        },
        headers=registered_user["headers"],
    )


def test_create_guess_game(client, registered_user):
    r = _create_game(client, registered_user)
    assert r.status_code == 200
    gid = r.json()["game_id"]
    assert len(gid) == 10


def test_create_guess_game_requires_auth(client):
    r = client.post(
        "/api/viral/guess-game/create",
        json={"question": "q", "user_answer": "a", "ome_answer": "b"},
    )
    assert r.status_code == 401


def test_guess_game_page_html(client, registered_user):
    gid = _create_game(client, registered_user).json()["game_id"]
    r = client.get(f"/api/viral/guess-game/{gid}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "猜猜哪个是AI" in r.text


def test_guess_game_page_not_found(client):
    r = client.get("/api/viral/guess-game/nonexistent")
    assert r.status_code == 404


def test_submit_guess(client, registered_user):
    gid = _create_game(client, registered_user).json()["game_id"]
    r = client.post(f"/api/viral/guess-game/{gid}/guess?guess=a")
    assert r.status_code == 200
    body = r.json()
    assert "correct" in body
    assert "human_was" in body
    assert body["total_guesses"] == 1


def test_submit_guess_unknown_game(client):
    r = client.post("/api/viral/guess-game/nope/guess?guess=a")
    assert r.status_code == 404


def test_submit_guess_updates_stats(client, registered_user):
    gid = _create_game(client, registered_user).json()["game_id"]
    client.post(f"/api/viral/guess-game/{gid}/guess?guess=a")
    r = client.post(f"/api/viral/guess-game/{gid}/guess?guess=b")
    assert r.status_code == 200
    assert r.json()["total_guesses"] == 2
