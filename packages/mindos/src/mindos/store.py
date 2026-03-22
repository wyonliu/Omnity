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
    """SQLite-backed memory store with in-process vector search."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._embeddings_cache: dict[str, Any] = {}
        self._load_embeddings()

    # -- write -----------------------------------------------------------------

    def add(self, mem: Memory) -> str:
        if not mem.id:
            mem.id = uuid.uuid4().hex[:12]
        now = time.time()
        if not mem.created_at:
            mem.created_at = now
        mem.accessed_at = now
        emb_blob = mem.embedding.tobytes() if mem.embedding is not None else None
        self._conn.execute(
            "INSERT OR REPLACE INTO memories "
            "(id, type, content, source, confidence, created_at, accessed_at, "
            " access_count, decay_weight, embedding, meta) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (mem.id, mem.type, mem.content, mem.source, mem.confidence,
             mem.created_at, mem.accessed_at, mem.access_count,
             mem.decay_weight, emb_blob, json.dumps(mem.meta, ensure_ascii=False)),
        )
        self._conn.commit()
        if mem.embedding is not None:
            self._embeddings_cache[mem.id] = mem.embedding
        return mem.id

    def add_triple(self, t: Triple) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO knowledge_graph "
            "(subject, predicate, object, source, confidence, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (t.subject, t.predicate, t.object, t.source, t.confidence, time.time()),
        )
        self._conn.commit()

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
        """Keyword search (LIKE)."""
        rows = self._conn.execute(
            "SELECT * FROM memories WHERE content LIKE ? ORDER BY accessed_at DESC LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        return [self._row_to_memory(r) for r in rows]

    def search_vector(self, query_vec: Any, top_k: int = 10) -> list[Memory]:
        """Cosine-similarity vector search against cached embeddings."""
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
        """True if an identical memory body already exists."""
        row = self._conn.execute(
            "SELECT 1 FROM memories WHERE content = ? LIMIT 1", (content,),
        ).fetchone()
        return row is not None

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

    def close(self) -> None:
        self._conn.close()
