"""Integration tests for PgMemoryStore + RLS tenant isolation.

These tests require a running PostgreSQL instance with pgvector + pg_trgm.
They are SKIPPED if DATABASE_URL is not set.

Setup:
    # Start a test database (Docker one-liner)
    docker run -d --name ome-pg-test -p 5433:5432 \
        -e POSTGRES_DB=ome_test -e POSTGRES_USER=ome -e POSTGRES_PASSWORD=ome \
        pgvector/pgvector:pg17

    # Install pg_trgm (run once)
    psql postgresql://ome:ome@localhost:5433/ome_test -c "CREATE EXTENSION IF NOT EXISTS pg_trgm"

    # Run tests
    DATABASE_URL=postgresql://ome:ome@localhost:5433/ome_test pytest tests/test_pg_store.py -v
"""

from __future__ import annotations

import json
import os
import uuid

import pytest

# Skip entire module if no DATABASE_URL
pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set — skip PG integration tests",
)


@pytest.fixture(scope="module")
def pg_pool():
    """Create pool + apply schema once per test module."""
    from ome_server.db.engine import get_pool, ensure_schema, close_pool
    pool = get_pool()
    ensure_schema(pool)
    yield pool
    close_pool()


@pytest.fixture
def tenant_a(pg_pool):
    """Create a fresh tenant A for isolation testing."""
    from ome_server.db.engine import get_or_create_tenant
    ext_id = f"test_a_{uuid.uuid4().hex[:8]}"
    tid = get_or_create_tenant(pg_pool, ext_id, name="Alice", kind="user")
    return tid


@pytest.fixture
def tenant_b(pg_pool):
    """Create a fresh tenant B for isolation testing."""
    from ome_server.db.engine import get_or_create_tenant
    ext_id = f"test_b_{uuid.uuid4().hex[:8]}"
    tid = get_or_create_tenant(pg_pool, ext_id, name="Bob", kind="user")
    return tid


@pytest.fixture
def store_a(pg_pool, tenant_a):
    from ome_server.db.pg_store import PgMemoryStore
    return PgMemoryStore(pg_pool, tenant_a)


@pytest.fixture
def store_b(pg_pool, tenant_b):
    from ome_server.db.pg_store import PgMemoryStore
    return PgMemoryStore(pg_pool, tenant_b)


# ── Basic CRUD ─────────────────────────────────────────────────────

class TestCRUD:
    def test_add_and_get(self, store_a):
        from mindos.store import Memory
        mem = Memory(id="", type="fact", content="Alice loves painting")
        mid = store_a.add(mem)
        assert mid
        got = store_a.get(mid)
        assert got is not None
        assert got.content == "Alice loves painting"
        assert got.type == "fact"

    def test_count(self, store_a):
        from mindos.store import Memory
        before = store_a.count()
        store_a.add(Memory(id="", type="fact", content=f"count test {uuid.uuid4().hex[:6]}"))
        assert store_a.count() == before + 1

    def test_search_text(self, store_a):
        from mindos.store import Memory
        store_a.add(Memory(id="", type="fact", content="She traveled to Kyoto last spring"))
        results = store_a.search_text("Kyoto")
        assert any("Kyoto" in m.content for m in results)

    def test_forget(self, store_a):
        from mindos.store import Memory
        store_a.add(Memory(id="", type="fact", content="secret_password_123"))
        assert store_a.count() > 0
        deleted = store_a.forget("secret_password_123")
        assert deleted >= 1

    def test_soul_state(self, store_a):
        store_a.set_state("test_key", json.dumps({"mood": "happy"}))
        val = store_a.get_state("test_key")
        assert val is not None
        parsed = json.loads(val)
        assert parsed["mood"] == "happy"

    def test_content_exists(self, store_a):
        from mindos.store import Memory
        store_a.add(Memory(id="", type="fact", content="unique content xyz"))
        assert store_a.content_exists("unique content xyz")
        assert not store_a.content_exists("nonexistent content abc")


# ── RLS Tenant Isolation ──────────────────────────────────────────

class TestRLSIsolation:
    """The most critical tests: tenant A cannot see tenant B's data."""

    def test_memory_isolation(self, store_a, store_b):
        from mindos.store import Memory
        store_a.add(Memory(id="", type="fact", content="Alice's private diary entry"))
        store_b.add(Memory(id="", type="fact", content="Bob's secret recipe"))

        a_mems = store_a.search_text("diary")
        b_mems = store_b.search_text("recipe")
        assert any("diary" in m.content for m in a_mems)
        assert any("recipe" in m.content for m in b_mems)

        # Cross-tenant: A cannot see B's data
        a_cross = store_a.search_text("recipe")
        assert not any("Bob" in m.content for m in a_cross)

        b_cross = store_b.search_text("diary")
        assert not any("Alice" in m.content for m in b_cross)

    def test_soul_state_isolation(self, store_a, store_b):
        store_a.set_state("secret", "alice_value")
        store_b.set_state("secret", "bob_value")

        assert json.loads(store_a.get_state("secret")) == "alice_value"
        assert json.loads(store_b.get_state("secret")) == "bob_value"

    def test_count_isolation(self, store_a, store_b):
        from mindos.store import Memory
        # Each store only counts its own memories
        a_before = store_a.count()
        b_before = store_b.count()

        store_a.add(Memory(id="", type="fact", content=f"a_only_{uuid.uuid4().hex[:6]}"))

        assert store_a.count() == a_before + 1
        assert store_b.count() == b_before  # B unchanged

    def test_triple_isolation(self, store_a, store_b):
        from mindos.store import Triple
        store_a.add_triple(Triple("Alice", "likes", "painting"))
        store_b.add_triple(Triple("Bob", "likes", "cooking"))

        a_triples = store_a.triples()
        b_triples = store_b.triples()
        assert any(t.subject == "Alice" for t in a_triples)
        assert not any(t.subject == "Bob" for t in a_triples)
        assert any(t.subject == "Bob" for t in b_triples)
        assert not any(t.subject == "Alice" for t in b_triples)

    def test_forget_isolation(self, store_a, store_b):
        from mindos.store import Memory
        store_a.add(Memory(id="", type="fact", content="forgettable_a"))
        store_b.add(Memory(id="", type="fact", content="forgettable_b"))

        # A forgets its own — B's data untouched
        store_a.forget("forgettable")
        assert not store_a.content_exists("forgettable_a")
        assert store_b.content_exists("forgettable_b")


# ── Stats & Lifecycle ─────────────────────────────────────────────

class TestStats:
    def test_stats(self, store_a):
        from mindos.store import Memory
        store_a.add(Memory(id="", type="fact", content="stat test fact"))
        store_a.add(Memory(id="", type="episode", content="stat test episode"))
        s = store_a.stats()
        assert s["total_memories"] >= 2
        assert "fact" in s["by_type"]

    def test_decay_status(self, store_a):
        d = store_a.decay_status()
        assert "active" in d
        assert "fading" in d
        assert "forgotten" in d

    def test_personality_timeline(self, store_a):
        store_a.record_personality({"mood": "calm"}, trigger="test")
        timeline = store_a.personality_timeline()
        assert len(timeline) >= 1


# ── Sync Journal ──────────────────────────────────────────────────

class TestSyncJournal:
    def test_journal_append_and_since(self, store_a):
        seq = store_a.journal_append("test_op", {"key": "value"})
        assert seq > 0
        events = store_a.journal_since(seq - 1)
        assert any(e["op"] == "test_op" for e in events)

    def test_journal_isolation(self, store_a, store_b):
        store_a.journal_append("a_event", {"from": "alice"})
        store_b.journal_append("b_event", {"from": "bob"})

        a_events = store_a.journal_since(0)
        b_events = store_b.journal_since(0)
        assert any(e["op"] == "a_event" for e in a_events)
        assert not any(e["op"] == "b_event" for e in a_events)
