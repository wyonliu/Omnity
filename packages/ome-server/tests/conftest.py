"""Shared pytest fixtures for ome-server tests.

Design principles:
- OME_DATA_ROOT is redirected to a session-scoped tmpdir BEFORE any import.
- LLM-dependent Ome methods (chat/mirror/use_skill/etc.) are monkey-patched to
  deterministic stubs — tests must run offline in <30s.
- TestClient is instantiated WITHOUT the `with` context manager so the
  app lifespan (heavy OmeTown simulation init) does not fire. Town routes
  are exercised via a stubbed `get_simulation`.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Iterator

import pytest

# ── Redirect data root BEFORE ome_server imports ─────────────────────
_TMP_ROOT = Path(tempfile.mkdtemp(prefix="ome_server_test_"))
os.environ["OME_DATA_ROOT"] = str(_TMP_ROOT)
os.environ.setdefault("OME_JWT_SECRET", "test-secret-deterministic")
os.environ.setdefault("OME_NO_LLM", "1")

# Nuke any inherited proxy config that would slow down network probes
for _pv in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
    os.environ.pop(_pv, None)

# Short-circuit ModelRouter.call_llm so Mindos never hits Ollama/OpenAI.
# Rule-based fallbacks in L0/L2/L3 produce deterministic results offline.
from mindos.config import ModelRouter  # noqa: E402


def _stub_call_llm(self, system, user, task="reasoning", max_tokens=1024,
                   json_mode=False, use_cache=False, timeout=30.0):
    return None


ModelRouter.call_llm = _stub_call_llm  # type: ignore[assignment]
# Also short-circuit candidate selection so _select_candidates returns [] fast
ModelRouter._select_candidates = lambda self, task: []  # type: ignore[assignment]


# ── Ome method stubs ─────────────────────────────────────────────────

def _stub_chat(self, message, provider: str = ""):
    # Bump bond.total_interactions so life metrics advance naturally
    self.bond.total_interactions += 1
    return f"stub-reply:{message[:32]}"


def _stub_mirror_chat(self, message):
    return f"stub-mirror:{message[:32]}"


def _stub_suggest_follow_ups(self, message, reply, n=3):
    return [f"followup-{i}" for i in range(n)]


def _stub_generate_prompts(self, count=3, context=""):
    return [f"prompt-{i}" for i in range(count)]


def _stub_generate_greeting(self):
    return "stub-greeting"


def _stub_calibrate(self, message, response, feedback):
    return {"calibrated": True, "note": "stub"}


def _stub_check_events(self):
    return []


def _stub_use_skill(self, skill_name, **kwargs):
    from ome.skills import SkillResult

    return SkillResult(
        success=True,
        output=f"stub-skill:{skill_name}",
        output_type="text",
        needs_approval=False,
        metadata={"args": kwargs},
    )


def _stub_soul_card(self):
    class _Card:
        def to_dict(self):
            return {
                "name": "stub",
                "traits": ["curious"],
                "top_values": ["honesty"],
                "essence": "stub-essence",
            }

    return _Card()


def _stub_soul_card_image(self):
    return b"\x89PNG\r\n\x1a\nSTUB"  # PNG magic bytes + marker


def _stub_chat_stream_prepare(self, message):
    # Mirror the real prepare: bump emotion, return meta + dummy system_prompt
    self.emotion.update_from_message(message)
    self._stream_contexts = getattr(self, "_stream_contexts", {})
    self._stream_contexts[id(message)] = {
        "is_crisis": False,
        "is_low_engagement": False,
        "phase": {"phase_id": 0, "name": "stub"},
        "memories_recalled": [],
    }
    return {
        "system_prompt": "stub-system-prompt",
        "user_message": message,
        "meta": {
            "mood": self.emotion.mood,
            "mood_emoji": self.emotion.mood_emoji(),
            "bond_level": self.bond.level,
            "streak_days": self.bond.streak_days,
            "phase_id": 0,
            "phase_name": "stub",
            "memories_recalled_count": 0,
            "is_crisis": False,
        },
    }


def _stub_stream_tokens(self, system_prompt, user_message):
    # Emit a few deterministic chunks that simulate true streaming
    for chunk in ("Hel", "lo ", "from ", "stream"):
        yield chunk


def _stub_chat_stream_finalize(self, message, raw_reply):
    # Consume the cached stream context if present
    getattr(self, "_stream_contexts", {}).pop(id(message), None)
    # Bump bond counter so life metrics advance naturally
    self.bond.total_interactions += 1
    return {
        "reply": raw_reply or "stub-finalize-empty",
        "mood": self.emotion.mood,
        "mood_emoji": self.emotion.mood_emoji(),
        "bond_level": self.bond.level,
        "streak_days": self.bond.streak_days,
    }


# ── Patch Ome class at import time ───────────────────────────────────

from ome.core import Ome  # noqa: E402  (after env setup)

Ome.chat = _stub_chat  # type: ignore[assignment]
Ome.mirror_chat = _stub_mirror_chat  # type: ignore[assignment]
Ome.suggest_follow_ups = _stub_suggest_follow_ups  # type: ignore[assignment]
Ome.generate_prompts = _stub_generate_prompts  # type: ignore[assignment]
Ome.generate_greeting = _stub_generate_greeting  # type: ignore[assignment]
Ome.calibrate = _stub_calibrate  # type: ignore[assignment]
Ome.check_events = _stub_check_events  # type: ignore[assignment]
Ome.use_skill = _stub_use_skill  # type: ignore[assignment]
Ome.soul_card = _stub_soul_card  # type: ignore[assignment]
Ome.soul_card_image = _stub_soul_card_image  # type: ignore[assignment]
Ome.chat_stream_prepare = _stub_chat_stream_prepare  # type: ignore[assignment]
Ome.stream_tokens = _stub_stream_tokens  # type: ignore[assignment]
Ome.chat_stream_finalize = _stub_chat_stream_finalize  # type: ignore[assignment]


# ── Stub OmeTown simulation ──────────────────────────────────────────


class _StubSimulation:
    def __init__(self):
        self.player_discovered_clues: list[str] = []
        self.scenario_complete = False
        self.initialized = True

    def get_state(self):
        return {
            "tick": 1,
            "npcs": [
                {"id": "alice", "name": "Alice", "col": 5, "row": 5, "activity": "idle"},
            ],
            "scenario": {
                "name": "stub-scenario",
                "brief": "A stub scenario for tests",
                "progress": 0,
                "complete": False,
            },
        }

    async def npc_chat(self, npc_id, message):
        return {"reply": f"npc {npc_id} says: stub", "mood": "calm", "mood_emoji": "😌"}

    async def npc_chat_stream(self, npc_id, message):
        for chunk in ["stu", "b-", "ok"]:
            yield chunk

    def accuse(self, suspect_id):
        return {"correct": suspect_id == "alice", "suspect": suspect_id}


_STUB_SIM = _StubSimulation()


def _get_stub_simulation():
    return _STUB_SIM


# Patch simulation BEFORE app import (town routes will pick up the stub)
import ome_server.town.simulation as _sim_mod  # noqa: E402

_sim_mod.get_simulation = _get_stub_simulation  # type: ignore[assignment]

import ome_server.town.routes as _town_routes  # noqa: E402

_town_routes.get_simulation = _get_stub_simulation  # type: ignore[assignment]


# ── Import app (after all patches) ───────────────────────────────────

from fastapi.testclient import TestClient  # noqa: E402

from ome_server import ome_manager  # noqa: E402
from ome_server.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    # No `with` → lifespan does NOT run → no OmeTown init, no background loop
    yield TestClient(app)


@pytest.fixture()
def unique_user_id() -> str:
    return f"u_{uuid.uuid4().hex[:10]}"


@pytest.fixture()
def registered_user(client: TestClient, unique_user_id: str) -> dict:
    """Register a fresh user and return {user_id, password, token, headers}."""
    password = "pw-" + uuid.uuid4().hex[:6]
    resp = client.post(
        "/api/auth/register",
        json={
            "user_id": unique_user_id,
            "password": password,
            "name": "Test " + unique_user_id,
            "traits": ["curious", "warm"],
            "style": "direct",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return {
        "user_id": unique_user_id,
        "password": password,
        "token": body["token"],
        "headers": {"Authorization": f"Bearer {body['token']}"},
        "name": body["name"],
    }


@pytest.fixture()
def second_user(client: TestClient) -> dict:
    uid = f"u_{uuid.uuid4().hex[:10]}"
    password = "pw-" + uuid.uuid4().hex[:6]
    resp = client.post(
        "/api/auth/register",
        json={"user_id": uid, "password": password, "name": "Peer " + uid},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return {
        "user_id": uid,
        "password": password,
        "token": body["token"],
        "headers": {"Authorization": f"Bearer {body['token']}"},
    }


@pytest.fixture()
def anon_session(client: TestClient) -> str:
    resp = client.post("/api/anon/session")
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]
