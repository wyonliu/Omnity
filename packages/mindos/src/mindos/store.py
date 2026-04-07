"""L0 Hippocampus — Memory storage backed by SQLite + vector search.

Storage features:
  - Full-text search via SQLite FTS5 (CJK + Latin)
  - Content-hash deduplication (handles minor variations)
  - Vector search via in-process cosine similarity
  - Knowledge graph with subject/predicate/object triples
  - Personality history timeline
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

try:
    import numpy as np
except ImportError:
    np = None  # vector search disabled

log = logging.getLogger("mindos.store")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id           TEXT PRIMARY KEY,
    type         TEXT NOT NULL,
    content      TEXT NOT NULL,
    content_hash TEXT,
    source       TEXT,
    confidence   REAL DEFAULT 1.0,
    created_at   REAL,
    accessed_at  REAL,
    access_count INTEGER DEFAULT 0,
    decay_weight REAL DEFAULT 1.0,
    embedding    BLOB,
    meta         TEXT
);

CREATE TABLE IF NOT EXISTS knowledge_graph (
    subject    TEXT,
    predicate  TEXT,
    object     TEXT,
    source     TEXT,
    confidence REAL DEFAULT 1.0,
    created_at REAL,
    PRIMARY KEY (subject, predicate, object)
);

CREATE TABLE IF NOT EXISTS personality_history (
    id         TEXT PRIMARY KEY,
    snapshot   TEXT,
    trigger    TEXT,
    diff       TEXT,
    created_at REAL
);

CREATE TABLE IF NOT EXISTS soul_state (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_mem_type ON memories(type);
CREATE INDEX IF NOT EXISTS idx_mem_source ON memories(source);
CREATE INDEX IF NOT EXISTS idx_mem_created ON memories(created_at);
CREATE INDEX IF NOT EXISTS idx_mem_hash ON memories(content_hash);
"""

_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content, content='memories', content_rowid='rowid',
    tokenize='unicode61'
);
"""

_SYNC_SCHEMA = """
CREATE TABLE IF NOT EXISTS sync_journal (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id   TEXT UNIQUE NOT NULL,
    device_id  TEXT NOT NULL,
    op         TEXT NOT NULL,
    payload    TEXT NOT NULL,
    created_at REAL NOT NULL,
    synced_at  REAL
);
CREATE INDEX IF NOT EXISTS idx_sync_unsynced ON sync_journal(synced_at) WHERE synced_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_sync_device ON sync_journal(device_id);
"""


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Memory:
    id: str
    type: str  # fact | episode | preference | relation | skill
    content: str
    source: str = ""
    confidence: float = 1.0
    created_at: float = 0.0
    accessed_at: float = 0.0
    access_count: int = 0
    decay_weight: float = 1.0
    embedding: Optional[Any] = field(default=None, repr=False)  # np.ndarray when numpy available
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Triple:
    subject: str
    predicate: str
    object: str
    source: str = ""
    confidence: float = 1.0


# ---------------------------------------------------------------------------
# MemoryStore
# ---------------------------------------------------------------------------

class MemoryStore:
    """SQLite-backed memory store with FTS5 + in-process vector search."""

    def __init__(self, db_path: str | Path, sync_enabled: bool = True) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._sync_enabled = sync_enabled
        self._applying_remote = False  # Prevent re-journaling during remote apply
        self._migrate()
        self._init_fts()
        self._embeddings_cache: dict[str, Any] = {}
        self._load_embeddings()

    def _migrate(self) -> None:
        """Add columns introduced after v0.2.0."""
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(memories)").fetchall()}
        if "content_hash" not in cols:
            self._conn.execute("ALTER TABLE memories ADD COLUMN content_hash TEXT")
            # Backfill hashes
            for row in self._conn.execute("SELECT id, content FROM memories").fetchall():
                h = self._content_hash(row["content"])
                self._conn.execute("UPDATE memories SET content_hash=? WHERE id=?", (h, row["id"]))
            self._conn.commit()
            log.info("Migrated: added content_hash column")
        # Ensure soul_state table exists (for emotion persistence)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS soul_state (key TEXT PRIMARY KEY, value TEXT)"
        )
        # Sync journal
        self._conn.executescript(_SYNC_SCHEMA)
        self._conn.commit()
        # Initialize device_id if not set
        if not self.get_state("device_id"):
            self.set_state("device_id", uuid.uuid4().hex[:8])

    def _init_fts(self) -> None:
        """Initialize FTS5 full-text search index."""
        try:
            self._conn.executescript(_FTS_SCHEMA)
            # Rebuild FTS if empty but memories exist
            fts_count = self._conn.execute(
                "SELECT COUNT(*) FROM memories_fts"
            ).fetchone()[0]
            mem_count = self.count()
            if mem_count > 0 and fts_count == 0:
                self._rebuild_fts()
            self._fts_available = True
        except Exception:
            self._fts_available = False
            log.debug("FTS5 not available, falling back to LIKE queries")

    def _rebuild_fts(self) -> None:
        """Rebuild FTS index from memories table."""
        self._conn.execute("DELETE FROM memories_fts")
        self._conn.execute(
            "INSERT INTO memories_fts(rowid, content) "
            "SELECT rowid, content FROM memories"
        )
        self._conn.commit()

    @staticmethod
    def _content_hash(content: str) -> str:
        """Normalized content hash for fuzzy dedup.

        Strips whitespace and punctuation variations so
        '我住在上海' and '我住在 上海。' hash the same.
        """
        import re
        normalized = re.sub(r'[\s\u3000,.;:!?。，；：！？、\-—\'"\"\"\'\']+', '', content.lower())
        return hashlib.md5(normalized.encode()).hexdigest()[:16]

    # -- write -----------------------------------------------------------------

    def add(self, mem: Memory) -> str:
        if not mem.id:
            mem.id = uuid.uuid4().hex[:12]
        now = time.time()
        if not mem.created_at:
            mem.created_at = now
        mem.accessed_at = now
        content_hash = self._content_hash(mem.content)
        emb_blob = mem.embedding.tobytes() if mem.embedding is not None else None
        self._conn.execute(
            "INSERT OR REPLACE INTO memories "
            "(id, type, content, content_hash, source, confidence, created_at, accessed_at, "
            " access_count, decay_weight, embedding, meta) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (mem.id, mem.type, mem.content, content_hash, mem.source, mem.confidence,
             mem.created_at, mem.accessed_at, mem.access_count,
             mem.decay_weight, emb_blob, json.dumps(mem.meta, ensure_ascii=False)),
        )
        self._conn.commit()
        # Sync FTS index
        if self._fts_available:
            try:
                rowid = self._conn.execute(
                    "SELECT rowid FROM memories WHERE id=?", (mem.id,)
                ).fetchone()
                if rowid:
                    self._conn.execute(
                        "INSERT OR REPLACE INTO memories_fts(rowid, content) VALUES (?, ?)",
                        (rowid[0], mem.content),
                    )
                    self._conn.commit()
            except Exception:
                pass  # FTS sync failure is non-fatal
        if mem.embedding is not None:
            self._embeddings_cache[mem.id] = mem.embedding
        # Auto-journal for sync
        if self._sync_enabled and not self._applying_remote:
            self.journal_append("add_memory", {
                "id": mem.id, "type": mem.type, "content": mem.content,
                "source": mem.source, "confidence": mem.confidence,
                "decay_weight": mem.decay_weight,
            })
        return mem.id

    def update_embedding(self, mem_id: str, embedding: Any) -> bool:
        """Update the embedding vector for an existing memory."""
        if np is None:
            return False
        import numpy as _np
        vec = _np.array(embedding, dtype=_np.float32)
        blob = vec.tobytes()
        cur = self._conn.execute(
            "UPDATE memories SET embedding=? WHERE id=?", (blob, mem_id)
        )
        self._conn.commit()
        if cur.rowcount > 0:
            self._embeddings_cache[mem_id] = vec
            return True
        return False

    def add_triple(self, t: Triple) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO knowledge_graph "
            "(subject, predicate, object, source, confidence, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (t.subject, t.predicate, t.object, t.source, t.confidence, time.time()),
        )
        self._conn.commit()
        if self._sync_enabled and not self._applying_remote:
            self.journal_append("add_triple", {
                "subject": t.subject, "predicate": t.predicate,
                "object": t.object, "source": t.source, "confidence": t.confidence,
            })

    def record_personality(self, snapshot: dict, trigger: str, diff: str = "") -> None:
        self._conn.execute(
            "INSERT INTO personality_history (id, snapshot, trigger, diff, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (uuid.uuid4().hex[:12], json.dumps(snapshot, ensure_ascii=False),
             trigger, diff, time.time()),
        )
        self._conn.commit()

    # -- read ------------------------------------------------------------------

    def get(self, mem_id: str) -> Optional[Memory]:
        row = self._conn.execute("SELECT * FROM memories WHERE id=?", (mem_id,)).fetchone()
        if not row:
            return None
        self._touch(mem_id)
        return self._row_to_memory(row)

    def search_text(self, query: str, limit: int = 20) -> list[Memory]:
        """Full-text search via FTS5, with LIKE fallback."""
        if self._fts_available and query.strip():
            try:
                # FTS5 match query — escape special chars
                safe_q = query.replace('"', '""')
                rows = self._conn.execute(
                    "SELECT m.* FROM memories m "
                    "JOIN memories_fts f ON m.rowid = f.rowid "
                    "WHERE memories_fts MATCH ? "
                    "ORDER BY rank LIMIT ?",
                    (f'"{safe_q}"', limit),
                ).fetchall()
                if rows:
                    return [self._row_to_memory(r) for r in rows]
            except Exception:
                pass  # Fall through to LIKE
        rows = self._conn.execute(
            "SELECT * FROM memories WHERE content LIKE ? ORDER BY accessed_at DESC LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        return [self._row_to_memory(r) for r in rows]

    def search_vector(self, query_vec: Any, top_k: int = 10,
                       return_scores: bool = False) -> list[Any]:
        """Cosine-similarity vector search against cached embeddings.

        Args:
            return_scores: If True, returns list of (Memory, float) tuples
                           where float is the cosine similarity [0, 1].
                           If False (default), returns list of Memory for backward compat.
        """
        if np is None or not self._embeddings_cache:
            return []
        ids = list(self._embeddings_cache.keys())
        mat = np.stack([self._embeddings_cache[i] for i in ids])
        qn = query_vec / (np.linalg.norm(query_vec) + 1e-9)
        mn = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
        scores = mn @ qn
        top_idx = np.argsort(scores)[::-1][:top_k]
        result = []
        for idx in top_idx:
            mid = ids[idx]
            mem = self.get(mid)
            if mem:
                if return_scores:
                    result.append((mem, float(scores[idx])))
                else:
                    result.append(mem)
        return result

    def list_recent(self, limit: int = 50, mem_type: Optional[str] = None) -> list[Memory]:
        if mem_type:
            rows = self._conn.execute(
                "SELECT * FROM memories WHERE type=? ORDER BY created_at DESC LIMIT ?",
                (mem_type, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?", (limit,),
            ).fetchall()
        return [self._row_to_memory(r) for r in rows]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]

    def triples(self, subject: Optional[str] = None) -> list[Triple]:
        if subject:
            rows = self._conn.execute(
                "SELECT * FROM knowledge_graph WHERE subject=?", (subject,),
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM knowledge_graph").fetchall()
        return [Triple(r["subject"], r["predicate"], r["object"], r["source"], r["confidence"])
                for r in rows]

    def stats(self) -> dict[str, Any]:
        total = self.count()
        by_type = {}
        for row in self._conn.execute(
            "SELECT type, COUNT(*) as c FROM memories GROUP BY type"
        ).fetchall():
            by_type[row["type"]] = row["c"]
        kg_count = self._conn.execute("SELECT COUNT(*) FROM knowledge_graph").fetchone()[0]
        return {"total_memories": total, "by_type": by_type, "knowledge_graph_triples": kg_count}

    def personality_timeline(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM personality_history ORDER BY created_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]

    # -- forget (hard delete) --------------------------------------------------

    def forget(self, pattern: str, mem_type: Optional[str] = None) -> int:
        """Physical erasure of memories matching pattern. Returns count deleted."""
        if mem_type:
            rows = self._conn.execute(
                "SELECT id FROM memories WHERE content LIKE ? AND type=?",
                (f"%{pattern}%", mem_type),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id FROM memories WHERE content LIKE ?", (f"%{pattern}%",),
            ).fetchall()
        ids = [r["id"] for r in rows]
        if ids:
            placeholders = ",".join("?" * len(ids))
            self._conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)
            for mid in ids:
                self._embeddings_cache.pop(mid, None)
        # Always scrub knowledge graph (even when no memory rows matched)
        self._conn.execute(
            "DELETE FROM knowledge_graph WHERE subject LIKE ? OR object LIKE ? OR predicate LIKE ?",
            (f"%{pattern}%", f"%{pattern}%", f"%{pattern}%"),
        )
        self._conn.commit()
        if self._sync_enabled and not self._applying_remote and len(ids) > 0:
            self.journal_append("forget", {"pattern": pattern, "mem_type": mem_type})
        return len(ids)

    def consolidate(self, similarity_threshold: float = 0.75) -> dict[str, int]:
        """Merge similar memories of the same type into single entries.

        Uses character-level Jaccard similarity when numpy is unavailable,
        or cosine similarity on embeddings when available.
        Returns stats about what was merged.
        """
        merged_count = 0
        kept = 0

        by_type: dict[str, list[Memory]] = {}
        for m in self.list_recent(limit=10000):
            by_type.setdefault(m.type, []).append(m)

        for mtype, mems in by_type.items():
            if len(mems) < 2:
                kept += len(mems)
                continue

            groups: list[list[Memory]] = []
            used: set[str] = set()

            for i, a in enumerate(mems):
                if a.id in used:
                    continue
                group = [a]
                used.add(a.id)
                for j in range(i + 1, len(mems)):
                    b = mems[j]
                    if b.id in used:
                        continue
                    if self._text_similarity(a.content, b.content) >= similarity_threshold:
                        group.append(b)
                        used.add(b.id)
                groups.append(group)

            for group in groups:
                if len(group) <= 1:
                    kept += 1
                    continue
                # Keep the one with highest confidence and most accesses
                group.sort(key=lambda m: (m.confidence, m.access_count), reverse=True)
                keeper = group[0]
                keeper.access_count += sum(m.access_count for m in group[1:])
                keeper.confidence = max(m.confidence for m in group)
                self.add(keeper)
                for discard in group[1:]:
                    self._conn.execute("DELETE FROM memories WHERE id=?", (discard.id,))
                    self._embeddings_cache.pop(discard.id, None)
                    merged_count += 1
                kept += 1

            self._conn.commit()

        return {"merged": merged_count, "kept": kept, "total_after": self.count()}

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        """Bigram Jaccard similarity — works well for both CJK and Latin text."""
        if not a or not b:
            return 0.0
        if len(a) < 2 or len(b) < 2:
            return 1.0 if a == b else 0.0
        bigrams_a = {a[i:i+2] for i in range(len(a) - 1)}
        bigrams_b = {b[i:i+2] for i in range(len(b) - 1)}
        intersection = len(bigrams_a & bigrams_b)
        union = len(bigrams_a | bigrams_b)
        return intersection / union if union > 0 else 0.0

    def content_exists(self, content: str) -> bool:
        """True if a semantically similar memory already exists (hash-based fuzzy match)."""
        h = self._content_hash(content)
        row = self._conn.execute(
            "SELECT 1 FROM memories WHERE content_hash = ? LIMIT 1", (h,),
        ).fetchone()
        if row:
            return True
        # Fallback: exact match (for pre-hash records)
        row = self._conn.execute(
            "SELECT 1 FROM memories WHERE content = ? LIMIT 1", (content,),
        ).fetchone()
        return row is not None

    # -- sync journal -----------------------------------------------------------

    @property
    def device_id(self) -> str:
        return self.get_state("device_id") or "unknown"

    def journal_append(self, op: str, payload: dict) -> int:
        """Append a mutation event to the sync journal. Returns the seq number."""
        event_id = uuid.uuid4().hex
        now = time.time()
        self._conn.execute(
            "INSERT INTO sync_journal (event_id, device_id, op, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (event_id, self.device_id, op, json.dumps(payload, ensure_ascii=False), now),
        )
        self._conn.commit()
        seq = self._conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return seq

    def journal_since(self, after_seq: int = 0, limit: int = 1000) -> list[dict]:
        """Get journal events after a given sequence number."""
        rows = self._conn.execute(
            "SELECT seq, event_id, device_id, op, payload, created_at, synced_at "
            "FROM sync_journal WHERE seq > ? ORDER BY seq ASC LIMIT ?",
            (after_seq, limit),
        ).fetchall()
        return [
            {"seq": r["seq"], "event_id": r["event_id"], "device_id": r["device_id"],
             "op": r["op"], "payload": json.loads(r["payload"]),
             "created_at": r["created_at"], "synced_at": r["synced_at"]}
            for r in rows
        ]

    def journal_unsynced(self, limit: int = 500) -> list[dict]:
        """Get events that haven't been synced yet."""
        rows = self._conn.execute(
            "SELECT seq, event_id, device_id, op, payload, created_at "
            "FROM sync_journal WHERE synced_at IS NULL ORDER BY seq ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {"seq": r["seq"], "event_id": r["event_id"], "device_id": r["device_id"],
             "op": r["op"], "payload": json.loads(r["payload"]),
             "created_at": r["created_at"]}
            for r in rows
        ]

    def journal_mark_synced(self, up_to_seq: int) -> int:
        """Mark events as synced up to a given sequence number."""
        now = time.time()
        cur = self._conn.execute(
            "UPDATE sync_journal SET synced_at=? WHERE seq <= ? AND synced_at IS NULL",
            (now, up_to_seq),
        )
        self._conn.commit()
        return cur.rowcount

    def journal_apply_remote(self, event: dict) -> bool:
        """Apply a remote event to the local store. Returns True if applied (not duplicate)."""
        # Check for duplicate event_id
        row = self._conn.execute(
            "SELECT 1 FROM sync_journal WHERE event_id=?", (event["event_id"],)
        ).fetchone()
        if row:
            return False  # Already applied

        self._applying_remote = True  # Prevent re-journaling
        op = event["op"]
        payload = event["payload"]

        if op == "add_memory":
            mem = Memory(
                id=payload.get("id", ""), type=payload["type"],
                content=payload["content"], source=payload.get("source", "sync"),
                confidence=payload.get("confidence", 0.8),
                decay_weight=payload.get("decay_weight", 1.0),
            )
            if not self.content_exists(mem.content):
                self.add(mem)

        elif op == "add_triple":
            self.add_triple(Triple(
                subject=payload["subject"], predicate=payload["predicate"],
                object=payload["object"], source=payload.get("source", "sync"),
                confidence=payload.get("confidence", 1.0),
            ))

        elif op == "forget":
            self.forget(payload["pattern"], payload.get("mem_type"))

        elif op == "update_identity":
            # Identity updates are stored as soul_state for the caller to apply
            self.set_state("pending_identity_update", json.dumps(payload))

        elif op == "reflect":
            if "snapshot" in payload:
                self.record_personality(
                    payload["snapshot"], trigger="sync_reflect",
                    diff=payload.get("diff", ""),
                )

        self._applying_remote = False  # Re-enable journaling

        # Record in local journal (with remote device_id)
        self._conn.execute(
            "INSERT OR IGNORE INTO sync_journal (event_id, device_id, op, payload, created_at, synced_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (event["event_id"], event["device_id"], op,
             json.dumps(payload, ensure_ascii=False),
             event["created_at"], time.time()),
        )
        self._conn.commit()
        return True

    def journal_latest_seq(self) -> int:
        """Get the latest sequence number in the journal."""
        row = self._conn.execute("SELECT MAX(seq) FROM sync_journal").fetchone()
        return row[0] or 0

    # -- soul state (key-value persistence) ------------------------------------

    def get_state(self, key: str) -> Optional[str]:
        """Read a soul state value."""
        row = self._conn.execute("SELECT value FROM soul_state WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None

    def set_state(self, key: str, value: str) -> None:
        """Write a soul state value."""
        self._conn.execute(
            "INSERT OR REPLACE INTO soul_state (key, value) VALUES (?, ?)", (key, value)
        )
        self._conn.commit()

    # -- internal --------------------------------------------------------------

    def _touch(self, mem_id: str) -> None:
        self._conn.execute(
            "UPDATE memories SET accessed_at=?, access_count=access_count+1 WHERE id=?",
            (time.time(), mem_id),
        )
        self._conn.commit()

    def _load_embeddings(self) -> None:
        if np is None:
            return
        rows = self._conn.execute("SELECT id, embedding FROM memories WHERE embedding IS NOT NULL").fetchall()
        for r in rows:
            arr = np.frombuffer(r["embedding"], dtype=np.float32)
            self._embeddings_cache[r["id"]] = arr

    def _row_to_memory(self, row: sqlite3.Row) -> Memory:
        emb = None
        if row["embedding"] and np is not None:
            emb = np.frombuffer(row["embedding"], dtype=np.float32)
        meta = json.loads(row["meta"]) if row["meta"] else {}
        return Memory(
            id=row["id"], type=row["type"], content=row["content"],
            source=row["source"] or "", confidence=row["confidence"],
            created_at=row["created_at"], accessed_at=row["accessed_at"],
            access_count=row["access_count"], decay_weight=row["decay_weight"],
            embedding=emb, meta=meta,
        )

    # -- memory compression ------------------------------------------------------

    def compress_old_episodes(self, older_than_days: int = 90) -> dict[str, int]:
        """Compress old episode memories into condensed summaries.

        Episodes older than `older_than_days` get their content truncated to
        the first 100 chars + "...". High-confidence or frequently-accessed
        memories are preserved in full.

        Returns: {"compressed": N, "preserved": N}
        """
        cutoff = time.time() - older_than_days * 86400
        rows = self._conn.execute(
            "SELECT id, content, confidence, access_count FROM memories "
            "WHERE type='episode' AND created_at < ? AND LENGTH(content) > 120",
            (cutoff,),
        ).fetchall()

        compressed = 0
        preserved = 0
        for r in rows:
            # Preserve important memories
            if r["confidence"] >= 0.9 or r["access_count"] >= 5:
                preserved += 1
                continue
            short = r["content"][:100] + "..."
            self._conn.execute(
                "UPDATE memories SET content=? WHERE id=?", (short, r["id"])
            )
            compressed += 1

        if compressed:
            self._conn.commit()
            if self._fts_available:
                self._rebuild_fts()

        return {"compressed": compressed, "preserved": preserved}

    def merge_redundant_facts(self, similarity_threshold: float = 0.8) -> dict[str, int]:
        """Merge redundant facts: identical meaning expressed differently.

        Uses the existing consolidate() but only for facts, with a higher threshold.
        Merged entries get boosted confidence and access_count.

        Returns: {"merged": N, "kept": N}
        """
        facts = self.list_recent(limit=5000, mem_type="fact")
        if len(facts) < 2:
            return {"merged": 0, "kept": len(facts)}

        merged_count = 0
        kept = 0
        used: set[str] = set()

        for i, a in enumerate(facts):
            if a.id in used:
                continue
            group = [a]
            used.add(a.id)
            for j in range(i + 1, len(facts)):
                b = facts[j]
                if b.id in used:
                    continue
                if self._text_similarity(a.content, b.content) >= similarity_threshold:
                    group.append(b)
                    used.add(b.id)

            if len(group) <= 1:
                kept += 1
                continue

            # Keep highest confidence, merge access counts
            group.sort(key=lambda m: (m.confidence, m.access_count), reverse=True)
            keeper = group[0]
            keeper.access_count += sum(m.access_count for m in group[1:])
            keeper.confidence = min(1.0, max(m.confidence for m in group) + 0.05)
            self.add(keeper)
            for discard in group[1:]:
                self._conn.execute("DELETE FROM memories WHERE id=?", (discard.id,))
                self._embeddings_cache.pop(discard.id, None)
                merged_count += 1
            kept += 1

        if merged_count:
            self._conn.commit()

        return {"merged": merged_count, "kept": kept}

    def archive_stale(self, inactive_days: int = 180, min_access: int = 2) -> dict[str, int]:
        """Mark long-inactive low-importance memories as archived.

        Archived memories are not deleted but get decay_weight set to 0.1,
        so they rarely appear in recall results.

        Returns: {"archived": N, "skipped": N}
        """
        cutoff = time.time() - inactive_days * 86400
        rows = self._conn.execute(
            "SELECT id, confidence, access_count, decay_weight FROM memories "
            "WHERE accessed_at < ? AND access_count < ? AND decay_weight > 0.1",
            (cutoff, min_access),
        ).fetchall()

        archived = 0
        skipped = 0
        for r in rows:
            if r["confidence"] >= 0.9:
                skipped += 1
                continue
            self._conn.execute(
                "UPDATE memories SET decay_weight=0.1 WHERE id=?", (r["id"],)
            )
            archived += 1

        if archived:
            self._conn.commit()

        return {"archived": archived, "skipped": skipped}

    def close(self) -> None:
        self._conn.close()
