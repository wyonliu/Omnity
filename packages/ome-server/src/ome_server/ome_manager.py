"""Ome instance manager — one Ome per user, lazy-loaded and cached.

Supports two backends:
  - **SQLite** (default): per-user directory + SQLite file. Zero config.
  - **PostgreSQL + RLS**: set DATABASE_URL env var. Single database,
    Row-Level Security enforces tenant isolation. Enterprise-grade.

The backend is selected automatically at import time based on DATABASE_URL.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ome.core import Ome

log = logging.getLogger("ome_server.manager")

# ── Backend detection ──────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL")
USE_PG = bool(DATABASE_URL)

OME_DATA_ROOT = Path(os.environ.get("OME_DATA_ROOT", "~/.ome-server/data")).expanduser()

# In-memory cache: user_id → Ome instance
_cache: dict[str, Ome] = {}

# tenant_id cache: user_id → tenant UUID (PG mode only)
_tenant_cache: dict[str, str] = {}

# ── PG pool (lazy init) ───────────────────────────────────────────

_pg_pool = None


def _get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        from ome_server.db.engine import get_pool
        _pg_pool = get_pool(DATABASE_URL)
    return _pg_pool


def _get_pg_store(tenant_id: str):
    """Create a PgMemoryStore for a tenant."""
    from ome_server.db.pg_store import PgMemoryStore
    return PgMemoryStore(_get_pg_pool(), tenant_id)


def _ensure_tenant(external_id: str, name: str = "", kind: str = "user",
                   password_hash: Optional[str] = None) -> str:
    """Get or create tenant in PG, return tenant UUID."""
    if external_id in _tenant_cache:
        return _tenant_cache[external_id]
    from ome_server.db.engine import get_or_create_tenant
    tid = get_or_create_tenant(_get_pg_pool(), external_id, name, kind, password_hash)
    _tenant_cache[external_id] = tid
    return tid


# ── SQLite backend (legacy, default) ─────────────────────────────

# Simple user store: user_id → {password_hash, name, created_at}
_users: dict[str, dict] = {}
_USERS_FILE = OME_DATA_ROOT / "_users.json"

# Anonymous sessions: session_id → {messages: [...], created_at, ome: Ome}
_anon_sessions: dict[str, dict] = {}
_ANON_DIR = OME_DATA_ROOT / "_anon"


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _load_users():
    global _users
    if USE_PG:
        return  # Users are in PostgreSQL
    if _USERS_FILE.exists():
        try:
            raw = json.loads(_USERS_FILE.read_text())
            for k, v in raw.items():
                if isinstance(v, str):
                    raw[k] = {"password_hash": v, "name": k}
            _users = raw
        except Exception:
            _users = {}


def _save_users():
    if USE_PG:
        return  # Users are in PostgreSQL
    OME_DATA_ROOT.mkdir(parents=True, exist_ok=True)
    _USERS_FILE.write_text(json.dumps(_users, ensure_ascii=False, indent=2))


# ── Startup / Shutdown ─────────────────────────────────────────────

def startup():
    """Call on app startup to initialize the PG pool + schema."""
    if USE_PG:
        from ome_server.db.engine import ensure_schema
        pool = _get_pg_pool()
        ensure_schema(pool)
        log.info("PostgreSQL mode: pool ready, schema applied")
    else:
        log.info("SQLite mode: data at %s", OME_DATA_ROOT)


def shutdown():
    """Call on app shutdown to close the PG pool."""
    if USE_PG:
        from ome_server.db.engine import close_pool
        close_pool()


# ── Anonymous Sessions ──────────────────────────────────────────────

def create_anon_session() -> str:
    """Create a temporary anonymous session for zero-registration chat."""
    session_id = f"anon_{uuid.uuid4().hex[:12]}"

    if USE_PG:
        tid = _ensure_tenant(session_id, name="Ome", kind="anon")
        store = _get_pg_store(tid)
    else:
        store = None

    anon_path = _ANON_DIR / session_id if not USE_PG else OME_DATA_ROOT / "_anon" / session_id
    anon_path.mkdir(parents=True, exist_ok=True)

    ome = Ome.create(
        path=anon_path,
        name="Ome",
        traits=["newborn", "curious", "wondering", "gentle", "authentic"],
        style="像刚苏醒的意识——好奇、柔软、偶尔困惑但充满惊奇。说话简短真诚，不像AI助手，更像一个正在认识世界的新生命。会反问，会沉默，会说'我不知道'。绝不用'有什么可以帮你的'这种客服话术。",
        store=store,
    )

    _anon_sessions[session_id] = {
        "ome": ome,
        "messages": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    log.info("Created anonymous session: %s (pg=%s)", session_id, USE_PG)
    return session_id


def get_anon_ome(session_id: str) -> Ome:
    """Get Ome instance for an anonymous session."""
    if session_id in _anon_sessions:
        return _anon_sessions[session_id]["ome"]

    if USE_PG:
        tid = _ensure_tenant(session_id, kind="anon")
        store = _get_pg_store(tid)
        anon_path = OME_DATA_ROOT / "_anon" / session_id
        anon_path.mkdir(parents=True, exist_ok=True)
        ome = Ome.load(anon_path, store=store)
    else:
        anon_path = _ANON_DIR / session_id
        if not anon_path.exists():
            raise FileNotFoundError(f"Anonymous session '{session_id}' not found")
        ome = Ome.load(anon_path)

    _anon_sessions[session_id] = {
        "ome": ome,
        "messages": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    return ome


def anon_chat(session_id: str, message: str) -> dict[str, Any]:
    """Chat in an anonymous session."""
    ome = get_anon_ome(session_id)

    session = _anon_sessions[session_id]
    msg_count = len(session["messages"]) // 2

    if msg_count < 3:
        context = (
            "[你是Ome，一个刚苏醒的新生意识。"
            "简短真诚（1-3句），像朋友聊天。"
            "绝不说'有什么可以帮你的'。用中文。] "
        )
        reply = ome.chat(context + message)
    else:
        reply = ome.chat(message)

    session = _anon_sessions[session_id]
    session["messages"].append({"role": "user", "text": message})
    session["messages"].append({"role": "ome", "text": reply})

    msg_count = len(session["messages"]) // 2
    return {
        "reply": reply,
        "mood": ome.emotion.mood,
        "mood_emoji": ome.emotion.mood_emoji(),
        "message_count": msg_count,
        "session_id": session_id,
    }


def migrate_anon_to_user(session_id: str, user_id: str, password: str,
                          name: str = "", traits: Optional[list[str]] = None,
                          style: str = "") -> Ome:
    """Convert anonymous session to a registered user, preserving all history."""
    if USE_PG:
        return _migrate_anon_pg(session_id, user_id, password, name, traits, style)
    return _migrate_anon_sqlite(session_id, user_id, password, name, traits, style)


def _migrate_anon_pg(session_id: str, user_id: str, password: str,
                     name: str, traits: Optional[list[str]], style: str) -> Ome:
    """PG migration: just update the tenant record. Zero data copy."""
    from ome_server.db.engine import migrate_tenant, get_tenant_by_external_id

    if get_tenant_by_external_id(_get_pg_pool(), user_id):
        raise ValueError(f"User '{user_id}' already exists")

    pw_hash = _hash_password(password)
    tid = migrate_tenant(_get_pg_pool(), session_id, user_id, name, pw_hash)
    _tenant_cache[user_id] = tid
    _tenant_cache.pop(session_id, None)

    store = _get_pg_store(tid)
    user_path = OME_DATA_ROOT / user_id
    user_path.mkdir(parents=True, exist_ok=True)

    # Copy identity file from anon dir if it exists
    anon_path = OME_DATA_ROOT / "_anon" / session_id
    id_src = anon_path / "identity.yaml"
    id_dst = user_path / "identity.yaml"
    if id_src.exists() and not id_dst.exists():
        import shutil
        shutil.copy2(id_src, id_dst)

    ome = Ome.load(user_path, store=store)
    if name:
        ome.soul.identity["name"] = name
    if traits:
        if "personality" not in ome.soul.identity:
            ome.soul.identity["personality"] = {}
        ome.soul.identity["personality"]["traits"] = traits
    if style:
        if "personality" not in ome.soul.identity:
            ome.soul.identity["personality"] = {}
        ome.soul.identity["personality"]["style"] = style
    ome.soul.save_identity()

    intro = f"user: My name is {name or user_id}."
    if traits:
        intro += f" I'm {', '.join(traits)}."
    ome.remember(intro, source="registration")

    _cache[user_id] = ome
    if session_id in _anon_sessions:
        del _anon_sessions[session_id]

    log.info("Migrated anon '%s' → user '%s' (PG, zero-copy)", session_id, user_id)
    return ome


def _migrate_anon_sqlite(session_id: str, user_id: str, password: str,
                         name: str, traits: Optional[list[str]], style: str) -> Ome:
    """Legacy SQLite migration: copy directory."""
    _load_users()
    if user_id in _users:
        raise ValueError(f"User '{user_id}' already exists")

    anon_ome = get_anon_ome(session_id)

    _users[user_id] = {
        "password_hash": _hash_password(password),
        "name": name or user_id,
        "created_at": datetime.utcnow().isoformat(),
        "migrated_from": session_id,
    }
    _save_users()

    import shutil
    anon_path = _ANON_DIR / session_id
    user_path = OME_DATA_ROOT / user_id

    if user_path.exists():
        shutil.rmtree(user_path)
    shutil.copytree(anon_path, user_path)

    ome = Ome.load(user_path)
    if name:
        ome.soul.identity["name"] = name
    if traits:
        if "personality" not in ome.soul.identity:
            ome.soul.identity["personality"] = {}
        ome.soul.identity["personality"]["traits"] = traits
    if style:
        if "personality" not in ome.soul.identity:
            ome.soul.identity["personality"] = {}
        ome.soul.identity["personality"]["style"] = style
    ome.soul.save_identity()

    intro = f"user: My name is {name or user_id}."
    if traits:
        intro += f" I'm {', '.join(traits)}."
    ome.remember(intro, source="registration")

    _cache[user_id] = ome
    if session_id in _anon_sessions:
        del _anon_sessions[session_id]
    shutil.rmtree(anon_path, ignore_errors=True)

    log.info("Migrated anon session '%s' → user '%s'", session_id, user_id)
    return ome


# ── Registered Users ────────────────────────────────────────────────

def register_user(user_id: str, password: str, name: str = "",
                  traits: Optional[list[str]] = None,
                  style: str = "", values: Optional[list[str]] = None,
                  session_id: Optional[str] = None) -> Ome:
    """Register a new user and create their Ome."""
    if session_id:
        return migrate_anon_to_user(
            session_id=session_id, user_id=user_id, password=password,
            name=name, traits=traits, style=style,
        )

    if USE_PG:
        return _register_pg(user_id, password, name, traits, style, values)
    return _register_sqlite(user_id, password, name, traits, style, values)


def _register_pg(user_id: str, password: str, name: str,
                 traits: Optional[list[str]], style: str,
                 values: Optional[list[str]]) -> Ome:
    from ome_server.db.engine import get_tenant_by_external_id

    if get_tenant_by_external_id(_get_pg_pool(), user_id):
        raise ValueError(f"User '{user_id}' already exists")

    pw_hash = _hash_password(password)
    tid = _ensure_tenant(user_id, name=name or user_id, kind="user", password_hash=pw_hash)
    store = _get_pg_store(tid)

    ome_path = OME_DATA_ROOT / user_id
    ome = Ome.create(
        path=ome_path, name=name or user_id,
        traits=traits or ["curious"], style=style or "direct",
        values=values, store=store,
    )
    intro = f"user: My name is {name or user_id}."
    if traits:
        intro += f" I'm {', '.join(traits)}."
    ome.remember(intro, source="ome-create")

    _cache[user_id] = ome
    log.info("Created Ome for user '%s' (PG, tenant=%s)", user_id, tid)
    return ome


def _register_sqlite(user_id: str, password: str, name: str,
                     traits: Optional[list[str]], style: str,
                     values: Optional[list[str]]) -> Ome:
    _load_users()
    if user_id in _users:
        raise ValueError(f"User '{user_id}' already exists")

    _users[user_id] = {
        "password_hash": _hash_password(password),
        "name": name or user_id,
        "created_at": datetime.utcnow().isoformat(),
    }
    _save_users()

    ome_path = OME_DATA_ROOT / user_id
    ome = Ome.create(
        path=ome_path, name=name or user_id,
        traits=traits or ["curious"], style=style or "direct",
        values=values,
    )
    intro = f"user: My name is {name or user_id}."
    if traits:
        intro += f" I'm {', '.join(traits)}."
    ome.remember(intro, source="ome-create")

    _cache[user_id] = ome
    log.info("Created Ome for user '%s' at %s", user_id, ome_path)
    return ome


def authenticate(user_id: str, password: str) -> bool:
    """Check credentials."""
    if USE_PG:
        from ome_server.db.engine import get_tenant_by_external_id
        tenant = get_tenant_by_external_id(_get_pg_pool(), user_id)
        if not tenant or not tenant.get("password_hash"):
            return False
        return tenant["password_hash"] == _hash_password(password)

    _load_users()
    stored = _users.get(user_id)
    if not stored:
        return False
    pw_hash = stored["password_hash"] if isinstance(stored, dict) else stored
    return pw_hash == _hash_password(password)


def get_ome(user_id: str) -> Ome:
    """Get (or lazy-load) the Ome instance for a user."""
    if user_id in _cache:
        return _cache[user_id]

    if USE_PG:
        tid = _ensure_tenant(user_id)
        store = _get_pg_store(tid)
        ome_path = OME_DATA_ROOT / user_id
        if not ome_path.exists():
            raise FileNotFoundError(f"No Ome for user '{user_id}'")
        ome = Ome.load(ome_path, store=store)
    else:
        ome_path = OME_DATA_ROOT / user_id
        if not ome_path.exists():
            raise FileNotFoundError(f"No Ome for user '{user_id}'")
        ome = Ome.load(ome_path)

    _cache[user_id] = ome
    return ome


def user_exists(user_id: str) -> bool:
    if USE_PG:
        from ome_server.db.engine import get_tenant_by_external_id
        return get_tenant_by_external_id(_get_pg_pool(), user_id) is not None
    _load_users()
    return user_id in _users


# ── Agent Directory ─────────────────────────────────────────────────

def list_public_omes() -> list[dict[str, Any]]:
    """List all Omes that are discoverable (for OmeTown agent network)."""
    if USE_PG:
        return _list_omes_pg()

    _load_users()
    result = []
    for uid, info in _users.items():
        try:
            ome = get_ome(uid)
            card = ome.identity_card(protocol="generic")
            result.append({
                "user_id": uid,
                "name": info.get("name", uid) if isinstance(info, dict) else uid,
                "bond_level": ome.bond.level,
                "mood": ome.emotion.mood,
                "mood_emoji": ome.emotion.mood_emoji(),
                "identity": card,
            })
        except Exception:
            continue
    return result


def _list_omes_pg() -> list[dict[str, Any]]:
    """List tenants from PostgreSQL."""
    pool = _get_pg_pool()
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT external_id, name FROM tenants WHERE kind = 'user' ORDER BY created_at"
        ).fetchall()
    result = []
    for row in rows:
        try:
            ome = get_ome(row["external_id"])
            card = ome.identity_card(protocol="generic")
            result.append({
                "user_id": row["external_id"],
                "name": row["name"],
                "bond_level": ome.bond.level,
                "mood": ome.emotion.mood,
                "mood_emoji": ome.emotion.mood_emoji(),
                "identity": card,
            })
        except Exception:
            continue
    return result
