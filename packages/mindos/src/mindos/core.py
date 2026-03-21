"""Mindos core — the digital soul facade over the five-layer brain.

Provides the public API: hydrate / commit / forget / recall / status / reflect.
Internally delegates to LayerRouter → L0-L4.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:
    yaml = None

from mindos.config import MindosConfig
from mindos.router import LayerRouter
from mindos.store import MemoryStore


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
    "version": 1,
    "name": "User",
    "personality": {
        "traits": [],
        "style": "",
        "values": [],
        "boundaries": [],
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

    @classmethod
    def load(cls, path: str | Path = "~/.mindos") -> "Mindos":
        root = Path(path).expanduser()
        root.mkdir(parents=True, exist_ok=True)

        id_path = root / "identity.yaml"
        if id_path.exists():
            identity = _load_identity(id_path)
        else:
            identity = dict(_DEFAULT_IDENTITY)
            _dump_identity(identity, id_path)

        config = MindosConfig.load(root)
        store = MemoryStore(root / "memory.db")
        return cls(root, store, identity, config)

    @classmethod
    def init(cls, path: str | Path = "~/.mindos", name: str = "User",
             traits: Optional[list[str]] = None, style: str = "",
             values: Optional[list[str]] = None,
             capabilities: Optional[list[dict]] = None) -> "Mindos":
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
        store = MemoryStore(root / "memory.db")
        inst = cls(root, store, identity, config)
        store.record_personality(identity.get("personality", {}), trigger="init")
        return inst

    # -- public API (delegates to LayerRouter) ---------------------------------

    def hydrate(self, context: str = "", max_tokens: int = 2000) -> str:
        """L1→L0: Assemble identity for injection into any AI session."""
        query_vec = self._embed(context) if context else None
        return self.layers.hydrate(context, max_tokens, query_vec)

    def commit(self, conversation: str, source: str = "unknown") -> dict[str, Any]:
        """L2→L0: Digest a conversation into long-term memories."""
        return self.layers.commit(conversation, source)

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
        """L4: Force a reflection cycle."""
        return self.layers.reflect()

    def reason(self, query: str) -> Optional[str]:
        """L3: Deep reasoning with identity context."""
        return self.layers.reason(query)

    def status(self) -> dict[str, Any]:
        """Full status across all layers."""
        s = self.layers.status()
        s["soul_age"] = self.identity.get("created_at", "unknown")
        return s

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
            "traits": p.get("traits", []),
            "style": p.get("style", ""),
            "values": p.get("values", []),
            "boundaries": p.get("boundaries", []),
            "capabilities": cap_strs,
        }
