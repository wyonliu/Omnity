"""Mindos core — the digital soul facade over the five-layer brain.

Provides the public API: hydrate / commit / forget / recall / status / reflect / export_ome.
Internally delegates to LayerRouter → L0-L4.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:
    yaml = None

from mindos.config import MindosConfig
from mindos.event_bus import EventBus, MEMORY_COMMITTED, REFLECT_COMPLETED, PERSONALITY_CHANGED
from mindos.router import LayerRouter
from mindos.store import MemoryStore

log = logging.getLogger("mindos.core")


def _dump_identity(data: dict, path: Path) -> None:
    if yaml:
        path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    else:
        import json as _json
        path.write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_identity(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if yaml:
        return yaml.safe_load(text) or {}
    import json as _json
    return _json.loads(text)


_DEFAULT_IDENTITY: dict[str, Any] = {
    "version": 2,
    "name": "User",
    "personality": {
        "anchors": [],
        "traits": [],
        "style": "",
        "values": [],
        "boundaries": [],
        "catchphrases": [],
        "emoji_habits": [],
    },
    "capabilities": [],
    "relations": [],
}


class Mindos:
    """Portable Digital Soul — public API backed by the five-layer brain.

    Usage:
        soul = Mindos.load("~/.mindos")
        context = soul.hydrate("Tell me about Python")
        soul.commit("user: I love Python\\nassistant: Great!", source="claude")
    """

    def __init__(self, root: Path, store: MemoryStore,
                 identity: dict[str, Any], config: Optional[MindosConfig] = None) -> None:
        self.root = root
        self.store = store
        self.identity = identity
        self.config = config

        # Flatten personality for layer consumption
        flat_identity = self._flatten_identity(identity)
        self.layers = LayerRouter(store, flat_identity, config)

        self._embedder: Any = None
        self.event_bus = EventBus()
        self._scheduler = None  # Lazy init
        self._setup_writeback()

        # EvoLog — bind late so any new event subscribers (layers / ome) are live.
        from mindos.evolog import EvoLogger
        self.evolog = EvoLogger(self)

    @classmethod
    def load(cls, path: str | Path = "~/.mindos",
             store: Optional["MemoryStore"] = None) -> "Mindos":
        """Load an existing Mindos from disk.

        Args:
            path: Root directory for identity/config files.
            store: Optional external store (e.g. PgMemoryStore for multi-tenant).
                   If None, uses the default SQLite store at path/memory.db.
        """
        root = Path(path).expanduser()
        root.mkdir(parents=True, exist_ok=True)

        id_path = root / "identity.yaml"
        if id_path.exists():
            identity = _load_identity(id_path)
        else:
            identity = dict(_DEFAULT_IDENTITY)
            _dump_identity(identity, id_path)

        config = MindosConfig.load(root)
        if store is None:
            store = MemoryStore(root / "memory.db")
        return cls(root, store, identity, config)

    @classmethod
    def init(cls, path: str | Path = "~/.mindos", name: str = "User",
             traits: Optional[list[str]] = None, style: str = "",
             values: Optional[list[str]] = None,
             capabilities: Optional[list[dict]] = None,
             store: Optional["MemoryStore"] = None) -> "Mindos":
        """Initialize a new Mindos soul.

        Args:
            store: Optional external store (e.g. PgMemoryStore for multi-tenant).
                   If None, uses the default SQLite store at path/memory.db.
        """
        root = Path(path).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        (root / "journal").mkdir(exist_ok=True)

        identity = dict(_DEFAULT_IDENTITY)
        identity["name"] = name
        if traits:
            identity["personality"]["traits"] = traits
        if style:
            identity["personality"]["style"] = style
        if values:
            identity["personality"]["values"] = values
        if capabilities:
            identity["capabilities"] = capabilities
        identity["created_at"] = time.strftime("%Y-%m-%d")
        identity["updated_at"] = time.strftime("%Y-%m-%d")

        id_path = root / "identity.yaml"
        _dump_identity(identity, id_path)

        config = MindosConfig.load(root)
        if store is None:
            store = MemoryStore(root / "memory.db")
        inst = cls(root, store, identity, config)
        store.record_personality(identity.get("personality", {}), trigger="init")
        return inst

    # -- public API (delegates to LayerRouter) ---------------------------------

    def process(self, text: str, **kwargs: Any) -> dict[str, Any]:
        """Unified entry point — L1 classifies and auto-routes to L1-L4.

        This is THE preferred API for Ome and all external systems.
        """
        return self.layers.process(text, **kwargs)

    def hydrate(self, context: str = "", max_tokens: int = 2000) -> str:
        """L1→L0: Assemble identity for injection into any AI session."""
        query_vec = self._embed(context) if context else None
        return self.layers.hydrate(context, max_tokens, query_vec)

    def commit(self, conversation: str, source: str = "unknown") -> dict[str, Any]:
        """L2→L0: Digest a conversation into long-term memories.

        Auto-embeds new facts if an embedding model is available.
        Emits MEMORY_COMMITTED event on success.
        """
        result = self.layers.commit(conversation, source)

        # Auto-embed newly added facts
        if result.get("facts_added", 0) > 0:
            self._auto_embed_recent(result.get("facts_added", 0))

        # Emit event
        self.event_bus.emit(MEMORY_COMMITTED, {
            "facts_added": result.get("facts_added", 0),
            "source": source,
        })

        # Check if reflection was triggered
        if result.get("reflection"):
            self.event_bus.emit(REFLECT_COMPLETED, result["reflection"])

        return result

    def _auto_embed_recent(self, count: int) -> None:
        """Generate embeddings for the most recent memories that lack them."""
        emb = self._get_embedder()
        if not emb:
            return
        try:
            recent = self.store.list_recent(limit=count)
            for mem in recent:
                if mem.embedding is not None:
                    continue
                vec = self._embed(mem.content)
                if vec is not None:
                    self.store.update_embedding(mem.id, vec.tolist())
        except Exception as e:
            log.debug("Auto-embed failed: %s", e)

    def commit_messages(self, messages: list[dict], source: str = "unknown") -> dict[str, Any]:
        """Convenience: commit from a list of {role, content} message dicts."""
        full_text = "\n".join(
            f"{m.get('role', '?')}: {m.get('content', '')}" for m in messages
        )
        return self.commit(full_text, source)

    def recall(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """L0: Search memories with relevance ranking."""
        query_vec = self._embed(query) if query else None
        return self.layers.recall(query, top_k, query_vec)

    def forget(self, pattern: str, scope: str = "all") -> dict[str, Any]:
        """L0: Physical erasure. GDPR Right to be Forgotten."""
        scope_val = None if scope == "all" else scope
        return self.layers.forget(pattern, scope_val)

    def reflect(self) -> Optional[dict[str, Any]]:
        """L4: Force a reflection cycle. Emits REFLECT_COMPLETED event."""
        result = self.layers.reflect()
        if result:
            self.event_bus.emit(REFLECT_COMPLETED, result)
            if result.get("identity_updated"):
                self.event_bus.emit(PERSONALITY_CHANGED, {
                    "traits": self.identity.get("personality", {}).get("traits", []),
                })
        return result

    def reason(self, query: str) -> Optional[str]:
        """L3: Deep reasoning with identity context."""
        return self.layers.reason(query)

    def consolidate(self) -> dict[str, Any]:
        """Merge similar memories to reduce redundancy."""
        return self.store.consolidate()

    def status(self) -> dict[str, Any]:
        """Full status across all layers."""
        s = self.layers.status()
        s["soul_age"] = self.identity.get("created_at", "unknown")
        s["device_id"] = self.store.device_id
        return s

    # -- scheduler & insights --------------------------------------------------

    def get_scheduler(self):
        """Lazy-init scheduler."""
        if self._scheduler is None:
            from mindos.scheduler import MindosScheduler
            self._scheduler = MindosScheduler(self, self.event_bus)
        return self._scheduler

    def maintenance(self) -> list[dict[str, Any]]:
        """Run all due maintenance jobs. Returns list of job results."""
        scheduler = self.get_scheduler()
        results = scheduler.check_and_run()
        return [{"name": r.name, "success": r.success, "data": r.data,
                 "duration_ms": r.duration_ms} for r in results]

    def insights(self, hours: int = 24) -> dict[str, Any]:
        """Get daily digest from InsightEngine."""
        from mindos.insight import InsightEngine
        engine = InsightEngine(self.store)
        return engine.daily_digest(hours=hours)

    def weekly_report(self) -> dict[str, Any]:
        """Get comprehensive weekly report."""
        from mindos.insight import InsightEngine
        engine = InsightEngine(self.store)
        return engine.weekly_summary()

    # -- sync ------------------------------------------------------------------

    def sync(self, hub_url: str = "") -> dict[str, Any]:
        """Push local events to hub and pull remote events. Full round-trip."""
        from mindos.sync import SyncClient
        client = SyncClient(self.store, hub_url=hub_url)
        return client.sync()

    # -- Ome generation --------------------------------------------------------

    def export_ome(self, context: str = "", include_memories: bool = True,
                   include_kg: bool = True, max_memories: int = 50) -> dict[str, Any]:
        """Generate an Ome-compatible persona package from this Mindos soul.

        An Ome is a lightweight, portable digital identity that can be injected
        into any AI platform. It contains:
          - identity: name, traits, style, values, capabilities
          - anchor: cross-platform identity anchor text
          - hydrated_context: pre-assembled identity prompt
          - memories: relevant memories (optional)
          - knowledge_graph: key relationships (optional)
          - emotion: current emotion state
          - metadata: version, exported_at, source_soul

        This is the bridge from Mindos (persistent soul) to Ome (instantiated persona).
        """
        p = self.identity.get("personality", {})
        ome: dict[str, Any] = {
            "ome_version": "0.1.0",
            "exported_at": time.time(),
            "source_soul": str(self.root),

            "identity": {
                "name": self.identity.get("name", "User"),
                "traits": p.get("traits", []),
                "style": p.get("style", ""),
                "values": p.get("values", []),
                "boundaries": p.get("boundaries", []),
                "capabilities": self.identity.get("capabilities", []),
            },

            "anchor": self.layers.l4.cross_platform_anchor(),
            "hydrated_context": self.hydrate(context=context, max_tokens=2000),
            "emotion": self.layers.l1.emotion.to_dict(),
        }

        if include_memories:
            memories = self.layers.l0.recall(context or "", top_k=max_memories)
            ome["memories"] = [
                {"type": m.type, "content": m.content,
                 "confidence": m.confidence, "source": m.source}
                for m in memories
            ]

        if include_kg:
            triples = self.store.triples()
            ome["knowledge_graph"] = [
                {"subject": t.subject, "predicate": t.predicate, "object": t.object}
                for t in triples[:100]
            ]

        return ome

    # -- SkillForge (auto-distilled reusable skills) --------------------------

    @property
    def skills(self) -> Any:
        """Lazy-instantiated :class:`~mindos.skillforge.SkillForge`."""
        if getattr(self, "_skills", None) is None:
            from mindos.skillforge import SkillForge
            self._skills = SkillForge(self)
        return self._skills

    def forge_skill(self, trace: dict[str, Any]) -> Optional[str]:
        """Distill a task trace into a SKILL.md. Returns skill_id or None."""
        return self.skills.forge(trace)

    # -- EvoLog (progressive life history) ------------------------------------

    def evo_timeline(self, limit: int = 100,
                     event_types: Optional[list[str]] = None,
                     since: Optional[float] = None) -> list[dict[str, Any]]:
        """Return the evolution timeline (newest first)."""
        return self.evolog.timeline(limit=limit, event_types=event_types,
                                    since=since)

    def evo_stats(self) -> dict[str, Any]:
        """Counts per evolution event type + first/last timestamps."""
        return self.evolog.stats()

    def record_evo(self, event_type: str, summary: str = "",
                   layer: str = "", details: Optional[dict] = None) -> str:
        """Manually record an evolution event. Returns the new event id."""
        return self.evolog.record(event_type=event_type, summary=summary,
                                  layer=layer, details=details)

    # -- MemoryDoc (human-readable export/import) -----------------------------

    def export_md(self, out_dir: str | Path, max_memories: int = 500,
                  min_confidence: float = 0.0) -> dict[str, Any]:
        """Dump the five-layer brain to IDENTITY.md / MEMORY.md / FACTS.md /
        SOUL.md / KG.json. Commit the folder to git to version-control your AI.
        """
        from mindos.memorydoc import export_md as _export_md
        return _export_md(self, out_dir, max_memories=max_memories,
                          min_confidence=min_confidence)

    def import_md(self, in_dir: str | Path,
                  merge_mode: str = "upsert") -> dict[str, Any]:
        """Restore a Mindos from a directory produced by :meth:`export_md`."""
        from mindos.memorydoc import import_md as _import_md
        return _import_md(self, in_dir, merge_mode=merge_mode)

    # -- identity management ---------------------------------------------------

    def save_identity(self) -> None:
        self.identity["updated_at"] = time.strftime("%Y-%m-%d")
        _dump_identity(self.identity, self.root / "identity.yaml")

    def reload_identity(self) -> None:
        id_path = self.root / "identity.yaml"
        if id_path.exists():
            self.identity = _load_identity(id_path)
            flat = self._flatten_identity(self.identity)
            self.layers.identity = flat
            self.layers.l1.identity = flat
            self.layers.l4.identity = flat

    # -- embedding (optional) --------------------------------------------------

    def _get_embedder(self) -> Any:
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                self._embedder = False
        return self._embedder

    def _embed(self, text: str) -> Any:
        emb = self._get_embedder()
        if not emb:
            return None
        try:
            import numpy as np
            vec = emb.encode(text, show_progress_bar=False)
            return np.array(vec, dtype=np.float32)
        except ImportError:
            return None

    # -- internal helpers ------------------------------------------------------

    def _setup_writeback(self) -> None:
        """Wire L4 identity writeback so reflect() changes persist to disk."""
        def _on_identity_changed():
            # Sync flat identity back to nested identity and save
            flat = self.layers.identity
            p = self.identity.setdefault("personality", {})
            p["traits"] = flat.get("traits", [])
            p["style"] = flat.get("style", "")
            self.save_identity()
            log.info("Identity updated by L4 reflection and saved to disk.")
        self.layers.l4._on_identity_changed = _on_identity_changed

    @staticmethod
    def _flatten_identity(identity: dict[str, Any]) -> dict[str, Any]:
        """Flatten nested personality into layer-friendly format."""
        p = identity.get("personality", {})
        caps = identity.get("capabilities", [])
        cap_strs = []
        for c in caps:
            if isinstance(c, dict):
                cap_strs.append(f"{c.get('domain', '')}({c.get('level', '')})")
            elif isinstance(c, str):
                cap_strs.append(c)
        return {
            "name": identity.get("name", "User"),
            "anchors": p.get("anchors", []),
            "traits": p.get("traits", []),
            "style": p.get("style", ""),
            "values": p.get("values", []),
            "boundaries": p.get("boundaries", []),
            "capabilities": cap_strs,
            "catchphrases": p.get("catchphrases", []),
            "emoji_habits": p.get("emoji_habits", []),
        }
