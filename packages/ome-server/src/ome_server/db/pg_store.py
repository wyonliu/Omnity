"""PostgreSQL + RLS drop-in replacement for Mindos MemoryStore.

Implements the same interface as mindos.store.MemoryStore so it can be
injected into Mindos(root, store=PgMemoryStore(...), identity, config).

Key differences from SQLite MemoryStore:
  - Full-text search via tsvector + pg_trgm (replaces FTS5)
  - Vector search via pgvector HNSW index (replaces in-process numpy cosine)
  - RLS enforces tenant isolation — tenant_id set at pool level, invisible to callers
  - No file I/O — all state lives in PostgreSQL
  - Content-hash dedup uses same MD5-prefix as SQLite for compatibility
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from typing import Any, Optional

from psycopg_pool import ConnectionPool

from mindos.store import Memory, Triple

log = logging.getLogger("ome_server.db.pg_store")


class PgMemoryStore:
    """PostgreSQL-backed memory store with pgvector + tsvector + RLS.

    Designed as a drop-in for mindos.store.MemoryStore. Every method signature
    matches so that Mindos, Ome, and all layers work without modification.

    The caller must ensure `app.current_tenant` is set on the connection
    before calling any method (handled by tenant_connection context manager).
    """

    def __init__(self, pool: ConnectionPool, tenant_id: str) -> None:
        self._pool = pool
        self._tenant_id = tenant_id
        # Compatibility: SQLite MemoryStore has these attributes
        self._fts_available = True
        self._sync_enabled = True
        self._applying_remote = False
        self._embeddings_cache: dict[str, Any] = {}

    def _conn(self):
        """Get a connection with tenant context set."""
        conn = self._pool.getconn()
        conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
        return conn

    @staticmethod
    def _content_hash(content: str) -> str:
        """Normalized content hash — identical to SQLite MemoryStore."""
        normalized = re.sub(r'[\s\u3000,.;:!?。，；：！？、\-—\'"\"\"\'\']+', '', content.lower())
        return hashlib.md5(normalized.encode()).hexdigest()[:16]

    @staticmethod
    def _ts_epoch(ts) -> float:
        """Convert PG timestamp to Unix epoch float (for Memory dataclass compat)."""
        if ts is None:
            return 0.0
        if isinstance(ts, (int, float)):
            return float(ts)
        return ts.timestamp()

    def _row_to_memory(self, row: dict) -> Memory:
        """Convert a PG dict row to a Memory dataclass."""
        try:
            import numpy as np
            emb = np.array(row["embedding"], dtype=np.float32) if row.get("embedding") else None
        except (ImportError, TypeError):
            emb = None

        meta = row.get("meta") or {}
        if isinstance(meta, str):
            meta = json.loads(meta)

        return Memory(
            id=str(row["id"]),
            type=row["type"],
            content=row["content"],
            source=row.get("source") or "",
            confidence=row.get("confidence", 1.0),
            created_at=self._ts_epoch(row.get("created_at")),
            accessed_at=self._ts_epoch(row.get("accessed_at")),
            access_count=row.get("access_count", 0),
            decay_weight=row.get("decay_weight", 1.0),
            embedding=emb,
            meta=meta,
        )

    # ── Write ──────────────────────────────────────────────────────────

    def add(self, mem: Memory) -> str:
        if not mem.id:
            mem.id = uuid.uuid4().hex[:12]

        content_hash = self._content_hash(mem.content)
        emb_list = mem.embedding.tolist() if mem.embedding is not None else None

        meta_json = json.dumps(mem.meta, ensure_ascii=False) if mem.meta else "{}"

        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                conn.execute(
                    """INSERT INTO memories
                       (id, tenant_id, type, content, content_hash, source, confidence,
                        access_count, decay_weight, embedding, meta)
                       VALUES (
                         %(id)s::uuid, %(tid)s::uuid, %(type)s, %(content)s, %(hash)s,
                         %(source)s, %(conf)s, %(ac)s, %(dw)s,
                         %(emb)s::vector, %(meta)s::jsonb
                       )
                       ON CONFLICT (id) DO UPDATE SET
                         content = EXCLUDED.content,
                         content_hash = EXCLUDED.content_hash,
                         confidence = EXCLUDED.confidence,
                         access_count = EXCLUDED.access_count,
                         decay_weight = EXCLUDED.decay_weight,
                         embedding = EXCLUDED.embedding,
                         meta = EXCLUDED.meta,
                         accessed_at = now()
                    """,
                    {
                        "id": self._ensure_uuid(mem.id),
                        "tid": self._tenant_id,
                        "type": mem.type,
                        "content": mem.content,
                        "hash": content_hash,
                        "source": mem.source,
                        "conf": mem.confidence,
                        "ac": mem.access_count,
                        "dw": mem.decay_weight,
                        "emb": str(emb_list) if emb_list else None,
                        "meta": meta_json,
                    },
                )

                if self._sync_enabled and not self._applying_remote:
                    self._journal_append_inner(conn, "add_memory", {
                        "id": mem.id, "type": mem.type, "content": mem.content,
                        "source": mem.source, "confidence": mem.confidence,
                        "decay_weight": mem.decay_weight,
                    })

        return mem.id

    def add_batch(self, memories: list[Memory]) -> list[str]:
        """Batch insert in a single transaction."""
        ids: list[str] = []
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                for mem in memories:
                    if not mem.id:
                        mem.id = uuid.uuid4().hex[:12]
                    content_hash = self._content_hash(mem.content)
                    emb_list = mem.embedding.tolist() if mem.embedding is not None else None
                    meta_json = json.dumps(mem.meta, ensure_ascii=False) if mem.meta else "{}"
                    conn.execute(
                        """INSERT INTO memories
                           (id, tenant_id, type, content, content_hash, source, confidence,
                            access_count, decay_weight, embedding, meta)
                           VALUES (
                             %(id)s::uuid, %(tid)s::uuid, %(type)s, %(content)s, %(hash)s,
                             %(source)s, %(conf)s, %(ac)s, %(dw)s,
                             %(emb)s::vector, %(meta)s::jsonb
                           )
                           ON CONFLICT (id) DO NOTHING
                        """,
                        {
                            "id": self._ensure_uuid(mem.id),
                            "tid": self._tenant_id,
                            "type": mem.type,
                            "content": mem.content,
                            "hash": content_hash,
                            "source": mem.source,
                            "conf": mem.confidence,
                            "ac": mem.access_count,
                            "dw": mem.decay_weight,
                            "emb": str(emb_list) if emb_list else None,
                            "meta": meta_json,
                        },
                    )
                    ids.append(mem.id)
        return ids

    def update_embedding(self, mem_id: str, embedding: Any) -> bool:
        try:
            import numpy as np
            vec = np.array(embedding, dtype=np.float32)
        except ImportError:
            return False

        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                cur = conn.execute(
                    "UPDATE memories SET embedding = %s::vector WHERE id = %s::uuid",
                    (str(vec.tolist()), self._ensure_uuid(mem_id)),
                )
                return cur.rowcount > 0

    def add_triple(self, t: Triple) -> None:
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                conn.execute(
                    """INSERT INTO knowledge_graph
                       (tenant_id, subject, predicate, object, source, confidence)
                       VALUES (%s::uuid, %s, %s, %s, %s, %s)
                       ON CONFLICT (tenant_id, subject, predicate, object) DO UPDATE SET
                         confidence = EXCLUDED.confidence
                    """,
                    (self._tenant_id, t.subject, t.predicate, t.object, t.source, t.confidence),
                )

    def record_personality(self, snapshot: dict, trigger: str, diff: str = "") -> None:
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                conn.execute(
                    """INSERT INTO personality_history (tenant_id, snapshot, trigger, diff)
                       VALUES (%s::uuid, %s::jsonb, %s, %s::jsonb)
                    """,
                    (self._tenant_id,
                     json.dumps(snapshot, ensure_ascii=False),
                     trigger,
                     json.dumps({"text": diff}, ensure_ascii=False) if diff else "{}"),
                )

    # ── Read ───────────────────────────────────────────────────────────

    def get(self, mem_id: str) -> Optional[Memory]:
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                row = conn.execute(
                    "SELECT * FROM memories WHERE id = %s::uuid",
                    (self._ensure_uuid(mem_id),),
                ).fetchone()
                if not row:
                    return None
                # Touch
                conn.execute(
                    "UPDATE memories SET accessed_at = now(), access_count = access_count + 1 "
                    "WHERE id = %s::uuid",
                    (self._ensure_uuid(mem_id),),
                )
                return self._row_to_memory(row)

    def search_text(self, query: str, limit: int = 20) -> list[Memory]:
        """Full-text search using tsvector + pg_trgm fallback.

        Strategy:
          1. Try tsvector websearch (good for multi-word queries)
          2. Fall back to trigram similarity (good for CJK, partial words)
          3. Final fallback: ILIKE
        """
        if not query or not query.strip():
            return []

        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))

                # Strategy 1: tsvector plainto_tsquery
                rows = conn.execute(
                    """SELECT *, ts_rank(tsv, plainto_tsquery('simple', %s)) AS rank
                       FROM memories
                       WHERE tsv @@ plainto_tsquery('simple', %s)
                       ORDER BY rank DESC
                       LIMIT %s
                    """,
                    (query, query, limit),
                ).fetchall()
                if rows:
                    return [self._row_to_memory(r) for r in rows]

                # Strategy 2: pg_trgm similarity (handles CJK, typos, substrings)
                rows = conn.execute(
                    """SELECT *, similarity(content, %s) AS sim
                       FROM memories
                       WHERE content %% %s
                       ORDER BY sim DESC
                       LIMIT %s
                    """,
                    (query, query, limit),
                ).fetchall()
                if rows:
                    return [self._row_to_memory(r) for r in rows]

                # Strategy 3: ILIKE fallback
                rows = conn.execute(
                    """SELECT * FROM memories
                       WHERE content ILIKE %s
                       ORDER BY accessed_at DESC
                       LIMIT %s
                    """,
                    (f"%{query}%", limit),
                ).fetchall()
                return [self._row_to_memory(r) for r in rows]

    def search_vector(self, query_vec: Any, top_k: int = 10,
                      return_scores: bool = False) -> list[Any]:
        """Vector similarity search via pgvector HNSW index."""
        try:
            import numpy as np
            vec = np.array(query_vec, dtype=np.float32)
        except ImportError:
            return []

        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                rows = conn.execute(
                    """SELECT *, 1 - (embedding <=> %s::vector) AS cosine_sim
                       FROM memories
                       WHERE embedding IS NOT NULL
                       ORDER BY embedding <=> %s::vector
                       LIMIT %s
                    """,
                    (str(vec.tolist()), str(vec.tolist()), top_k),
                ).fetchall()

                results = []
                for r in rows:
                    mem = self._row_to_memory(r)
                    if return_scores:
                        results.append((mem, float(r.get("cosine_sim", 0))))
                    else:
                        results.append(mem)
                return results

    def list_recent(self, limit: int = 50, mem_type: Optional[str] = None) -> list[Memory]:
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                if mem_type:
                    rows = conn.execute(
                        "SELECT * FROM memories WHERE type = %s ORDER BY created_at DESC LIMIT %s",
                        (mem_type, limit),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM memories ORDER BY created_at DESC LIMIT %s",
                        (limit,),
                    ).fetchall()
                return [self._row_to_memory(r) for r in rows]

    def count(self) -> int:
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                row = conn.execute("SELECT COUNT(*) AS c FROM memories").fetchone()
                return row["c"]

    def triples(self, subject: Optional[str] = None) -> list[Triple]:
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                if subject:
                    rows = conn.execute(
                        "SELECT * FROM knowledge_graph WHERE subject = %s",
                        (subject,),
                    ).fetchall()
                else:
                    rows = conn.execute("SELECT * FROM knowledge_graph").fetchall()
                return [Triple(r["subject"], r["predicate"], r["object"],
                               r["source"], r["confidence"]) for r in rows]

    def stats(self) -> dict[str, Any]:
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                total = conn.execute("SELECT COUNT(*) AS c FROM memories").fetchone()["c"]
                by_type = {}
                for row in conn.execute(
                    "SELECT type, COUNT(*) AS c FROM memories GROUP BY type"
                ).fetchall():
                    by_type[row["type"]] = row["c"]
                kg = conn.execute("SELECT COUNT(*) AS c FROM knowledge_graph").fetchone()["c"]
                return {"total_memories": total, "by_type": by_type, "knowledge_graph_triples": kg}

    def decay_status(self) -> dict[str, int]:
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                row = conn.execute(
                    """SELECT
                         COUNT(*) FILTER (WHERE decay_weight > 0.6)  AS active,
                         COUNT(*) FILTER (WHERE decay_weight > 0.2 AND decay_weight <= 0.6) AS fading,
                         COUNT(*) FILTER (WHERE decay_weight <= 0.2) AS forgotten
                       FROM memories
                    """
                ).fetchone()
                return {
                    "active": row["active"] or 0,
                    "fading": row["fading"] or 0,
                    "forgotten": row["forgotten"] or 0,
                }

    def count_recent(self, days: int = 7) -> dict[str, int]:
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                row = conn.execute(
                    """SELECT
                         COUNT(*) FILTER (WHERE created_at > now() - interval '%s days')  AS added,
                         COUNT(*) FILTER (WHERE accessed_at > now() - interval '%s days'
                                          AND access_count > 0) AS recalled
                       FROM memories
                    """,
                    (days, days),
                ).fetchone()
                return {"added": row["added"] or 0, "recalled": row["recalled"] or 0}

    def personality_timeline(self) -> list[dict]:
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                rows = conn.execute(
                    "SELECT * FROM personality_history ORDER BY created_at ASC"
                ).fetchall()
                return [dict(r) for r in rows]

    # ── Forget ─────────────────────────────────────────────────────────

    def forget(self, pattern: str, mem_type: Optional[str] = None) -> int:
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                if mem_type:
                    cur = conn.execute(
                        "DELETE FROM memories WHERE content ILIKE %s AND type = %s RETURNING id",
                        (f"%{pattern}%", mem_type),
                    )
                else:
                    cur = conn.execute(
                        "DELETE FROM memories WHERE content ILIKE %s RETURNING id",
                        (f"%{pattern}%",),
                    )
                deleted_ids = cur.fetchall()
                # Scrub knowledge graph
                conn.execute(
                    "DELETE FROM knowledge_graph WHERE subject ILIKE %s OR object ILIKE %s OR predicate ILIKE %s",
                    (f"%{pattern}%", f"%{pattern}%", f"%{pattern}%"),
                )
                return len(deleted_ids)

    def consolidate(self, similarity_threshold: float = 0.85) -> dict[str, int]:
        """Merge similar memories using pg_trgm similarity in-database."""
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))

                # Find duplicate pairs within same type using content_hash
                dupes = conn.execute(
                    """SELECT content_hash, type, array_agg(id ORDER BY confidence DESC, access_count DESC) AS ids
                       FROM memories
                       GROUP BY content_hash, type
                       HAVING COUNT(*) > 1
                    """
                ).fetchall()

                merged = 0
                for row in dupes:
                    ids = row["ids"]
                    keep_id = ids[0]  # highest confidence
                    discard_ids = ids[1:]
                    if discard_ids:
                        # Merge access counts into keeper
                        conn.execute(
                            """UPDATE memories SET
                                 access_count = access_count + (
                                   SELECT COALESCE(SUM(access_count), 0)
                                   FROM memories WHERE id = ANY(%s::uuid[])
                                 )
                               WHERE id = %s::uuid
                            """,
                            (discard_ids, keep_id),
                        )
                        conn.execute(
                            "DELETE FROM memories WHERE id = ANY(%s::uuid[])",
                            (discard_ids,),
                        )
                        merged += len(discard_ids)

                total = conn.execute("SELECT COUNT(*) AS c FROM memories").fetchone()["c"]
                return {"merged": merged, "kept": total, "total_after": total}

    def content_exists(self, content: str) -> bool:
        h = self._content_hash(content)
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                row = conn.execute(
                    "SELECT 1 FROM memories WHERE content_hash = %s LIMIT 1", (h,)
                ).fetchone()
                if row:
                    return True
                row = conn.execute(
                    "SELECT 1 FROM memories WHERE content = %s LIMIT 1", (content,)
                ).fetchone()
                return row is not None

    # ── Sync Journal ───────────────────────────────────────────────────

    @property
    def device_id(self) -> str:
        return self.get_state("device_id") or "server"

    def _journal_append_inner(self, conn, op: str, payload: dict) -> None:
        """Append to sync journal within an existing transaction."""
        conn.execute(
            """INSERT INTO sync_journal (tenant_id, device_id, op, payload)
               VALUES (%s::uuid, %s, %s, %s::jsonb)
            """,
            (self._tenant_id, self.device_id, op, json.dumps(payload, ensure_ascii=False)),
        )

    def journal_append(self, op: str, payload: dict) -> int:
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                row = conn.execute(
                    """INSERT INTO sync_journal (tenant_id, device_id, op, payload)
                       VALUES (%s::uuid, %s, %s, %s::jsonb)
                       RETURNING seq
                    """,
                    (self._tenant_id, self.device_id, op, json.dumps(payload, ensure_ascii=False)),
                ).fetchone()
                return row["seq"]

    def journal_since(self, after_seq: int = 0, limit: int = 1000) -> list[dict]:
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                rows = conn.execute(
                    """SELECT seq, event_id, device_id, op, payload, created_at, synced_at
                       FROM sync_journal
                       WHERE seq > %s
                       ORDER BY seq ASC LIMIT %s
                    """,
                    (after_seq, limit),
                ).fetchall()
                return [
                    {"seq": r["seq"], "event_id": str(r["event_id"]),
                     "device_id": r["device_id"], "op": r["op"],
                     "payload": r["payload"],
                     "created_at": self._ts_epoch(r["created_at"]),
                     "synced_at": self._ts_epoch(r["synced_at"])}
                    for r in rows
                ]

    def journal_unsynced(self, limit: int = 500) -> list[dict]:
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                rows = conn.execute(
                    """SELECT seq, event_id, device_id, op, payload, created_at
                       FROM sync_journal
                       WHERE synced_at IS NULL
                       ORDER BY seq ASC LIMIT %s
                    """,
                    (limit,),
                ).fetchall()
                return [
                    {"seq": r["seq"], "event_id": str(r["event_id"]),
                     "device_id": r["device_id"], "op": r["op"],
                     "payload": r["payload"],
                     "created_at": self._ts_epoch(r["created_at"])}
                    for r in rows
                ]

    def journal_mark_synced(self, up_to_seq: int) -> int:
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                cur = conn.execute(
                    "UPDATE sync_journal SET synced_at = now() WHERE seq <= %s AND synced_at IS NULL",
                    (up_to_seq,),
                )
                return cur.rowcount

    def journal_apply_remote(self, event: dict) -> bool:
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                dup = conn.execute(
                    "SELECT 1 FROM sync_journal WHERE event_id = %s::uuid",
                    (event["event_id"],),
                ).fetchone()
                if dup:
                    return False

                self._applying_remote = True
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
                    self.set_state("pending_identity_update", json.dumps(payload))
                elif op == "reflect" and "snapshot" in payload:
                    self.record_personality(
                        payload["snapshot"], trigger="sync_reflect",
                        diff=payload.get("diff", ""),
                    )

                self._applying_remote = False

                conn.execute(
                    """INSERT INTO sync_journal (tenant_id, event_id, device_id, op, payload, synced_at)
                       VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb, now())
                       ON CONFLICT (event_id) DO NOTHING
                    """,
                    (self._tenant_id, event["event_id"], event["device_id"],
                     op, json.dumps(payload, ensure_ascii=False)),
                )
                return True

    def journal_latest_seq(self) -> int:
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                row = conn.execute("SELECT COALESCE(MAX(seq), 0) AS m FROM sync_journal").fetchone()
                return row["m"]

    # ── Soul State ─────────────────────────────────────────────────────

    def get_state(self, key: str) -> Optional[str]:
        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                row = conn.execute(
                    "SELECT value FROM soul_state WHERE key = %s", (key,)
                ).fetchone()
                if not row:
                    return None
                val = row["value"]
                # Compat: SQLite stored raw strings; PG uses JSONB.
                # If JSONB is a bare string, unwrap it. Otherwise json.dumps for callers
                # that expect str from get_state.
                if isinstance(val, str):
                    return val
                return json.dumps(val, ensure_ascii=False)

    def set_state(self, key: str, value: str) -> None:
        # Store as JSONB if valid JSON, otherwise as JSON string
        try:
            json_val = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            json_val = value

        with self._pool.connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL app.current_tenant = %s", (self._tenant_id,))
                conn.execute(
                    """INSERT INTO soul_state (tenant_id, key, value)
                       VALUES (%s::uuid, %s, %s::jsonb)
                       ON CONFLICT (tenant_id, key) DO UPDATE SET value = EXCLUDED.value
                    """,
                    (self._tenant_id, key, json.dumps(json_val, ensure_ascii=False)),
                )

    # ── Context manager ────────────────────────────────────────────────

    def __enter__(self) -> "PgMemoryStore":
        return self

    def __exit__(self, *exc: Any) -> None:
        pass  # Pool connections are returned automatically

    def close(self) -> None:
        pass  # Pool-level concern, not store-level

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _ensure_uuid(id_str: str) -> str:
        """Convert a 12-char hex ID to a valid UUID (pad with zeros)."""
        clean = id_str.replace("-", "")
        if len(clean) < 32:
            clean = clean.ljust(32, "0")
        return f"{clean[:8]}-{clean[8:12]}-{clean[12:16]}-{clean[16:20]}-{clean[20:32]}"
