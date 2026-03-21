"""Mindos core — the digital soul: hydrate / commit / forget."""

from __future__ import annotations

import re
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import yaml

from mindos.store import Memory, MemoryStore, Triple

_DEFAULT_IDENTITY = {
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

_SENSITIVE_PATTERNS = [
    re.compile(r"\b\d{15,18}\b"),                       # ID numbers
    re.compile(r"\b(?:sk-|key-|api[_-]?key)[A-Za-z0-9_-]{10,}\b", re.I),  # API keys
    re.compile(r"(?:密钥|密码|API.?[Kk]ey|password|secret)\s*[:=是]\s*\S+", re.I),
]


class Mindos:
    """Portable Digital Soul — load from ~/.mindos/ directory."""

    def __init__(self, root: Path, store: MemoryStore, identity: dict[str, Any]) -> None:
        self.root = root
        self.store = store
        self.identity = identity
        self._embedder: Any = None

    # -- factory ---------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path = "~/.mindos") -> "Mindos":
        root = Path(path).expanduser()
        root.mkdir(parents=True, exist_ok=True)

        id_path = root / "identity.yaml"
        if id_path.exists():
            identity = yaml.safe_load(id_path.read_text(encoding="utf-8")) or {}
        else:
            identity = dict(_DEFAULT_IDENTITY)
            id_path.write_text(yaml.dump(identity, allow_unicode=True, sort_keys=False),
                               encoding="utf-8")

        store = MemoryStore(root / "memory.db")
        return cls(root, store, identity)

    @classmethod
    def init(cls, path: str | Path = "~/.mindos", name: str = "User",
             traits: Optional[list[str]] = None, style: str = "") -> "Mindos":
        root = Path(path).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        (root / "journal").mkdir(exist_ok=True)

        identity = dict(_DEFAULT_IDENTITY)
        identity["name"] = name
        if traits:
            identity["personality"]["traits"] = traits
        if style:
            identity["personality"]["style"] = style
        identity["created_at"] = time.strftime("%Y-%m-%d")
        identity["updated_at"] = time.strftime("%Y-%m-%d")

        id_path = root / "identity.yaml"
        id_path.write_text(yaml.dump(identity, allow_unicode=True, sort_keys=False),
                           encoding="utf-8")

        store = MemoryStore(root / "memory.db")
        inst = cls(root, store, identity)
        store.record_personality(identity.get("personality", {}), trigger="init")
        return inst

    # -- embedder --------------------------------------------------------------

    def _get_embedder(self) -> Any:
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            except ImportError:
                self._embedder = False  # sentinel: not available
        return self._embedder

    def _embed(self, text: str):
        emb = self._get_embedder()
        if not emb:
            return None
        import numpy as np
        vec = emb.encode(text, show_progress_bar=False)
        return np.array(vec, dtype=np.float32)

    # -- hydrate ---------------------------------------------------------------

    def hydrate(self, situation: str = "", recent_messages: Optional[list[dict]] = None,
                max_tokens: int = 2000) -> str:
        """Assemble identity context for injection into an AI session's system prompt."""
        parts: list[str] = []

        # 1. Core identity
        p = self.identity.get("personality", {})
        name = self.identity.get("name", "User")
        parts.append(f"[Mindos Identity] 用户名：{name}")
        if p.get("traits"):
            parts.append(f"性格特征：{', '.join(p['traits'])}")
        if p.get("style"):
            parts.append(f"沟通风格：{p['style']}")
        if p.get("values"):
            parts.append(f"核心价值观：{', '.join(p['values'])}")
        if p.get("boundaries"):
            parts.append(f"边界：{', '.join(p['boundaries'])}")

        # 2. Capabilities
        caps = self.identity.get("capabilities", [])
        if caps:
            cap_strs = [f"{c['domain']}({c.get('level', '?')})" for c in caps if isinstance(c, dict)]
            if cap_strs:
                parts.append(f"能力：{', '.join(cap_strs)}")

        # 3. Relevant memories via vector search
        query = situation
        if recent_messages:
            last_msgs = [m.get("content", "") for m in recent_messages[-3:]]
            query = situation + " " + " ".join(last_msgs)

        memories: list[Memory] = []
        qvec = self._embed(query) if query else None
        if qvec is not None:
            memories = self.store.search_vector(qvec, top_k=15)
        if not memories and query:
            memories = self.store.search_text(query.split()[0] if query.split() else "", limit=15)

        # 4. Assemble within budget (rough char estimate: 1 token ≈ 2 chars for CJK)
        char_budget = max_tokens * 2
        used = sum(len(p) for p in parts)
        if memories:
            parts.append("\n[相关记忆]")
            used += 10
            for mem in memories:
                line = f"- [{mem.type}] {mem.content}"
                if used + len(line) > char_budget:
                    break
                parts.append(line)
                used += len(line)

        # 5. Relevant relations
        if query:
            for word in query.split()[:3]:
                triples = self.store.triples(subject=word)
                for t in triples[:5]:
                    line = f"- {t.subject} {t.predicate} {t.object}"
                    if used + len(line) > char_budget:
                        break
                    parts.append(line)
                    used += len(line)

        return "\n".join(parts)

    # -- commit ----------------------------------------------------------------

    def commit(self, messages: list[dict], source: str = "unknown",
               auto_extract: bool = True) -> dict[str, Any]:
        """Digest a conversation and write new memories."""
        result = {"memories_added": 0, "facts": [], "skipped_sensitive": 0}

        full_text = "\n".join(
            f"{m.get('role', '?')}: {m.get('content', '')}" for m in messages
        )

        if auto_extract:
            facts = self._extract_facts(full_text)
            for fact in facts:
                if self._is_sensitive(fact["content"]):
                    result["skipped_sensitive"] += 1
                    continue
                mem = Memory(
                    id=uuid.uuid4().hex[:12],
                    type=fact.get("type", "fact"),
                    content=fact["content"],
                    source=source,
                    confidence=fact.get("confidence", 0.8),
                    embedding=self._embed(fact["content"]),
                )
                self.store.add(mem)
                result["memories_added"] += 1
                result["facts"].append(fact["content"])

        # Also scan full text for sensitive content
        if self._is_sensitive(full_text):
            result["skipped_sensitive"] += 1

        # Store episode summary (skip if sensitive)
        summary = self._summarize(full_text)
        if summary and not self._is_sensitive(summary):
            ep = Memory(
                id=uuid.uuid4().hex[:12],
                type="episode",
                content=summary,
                source=source,
                confidence=1.0,
                embedding=self._embed(summary),
            )
            self.store.add(ep)
            result["memories_added"] += 1

        return result

    # -- forget ----------------------------------------------------------------

    def forget(self, pattern: str, scope: str = "all", hard_delete: bool = True) -> int:
        """Physically erase memories matching pattern. GDPR Right to be Forgotten."""
        mem_type = None if scope == "all" else scope
        count = self.store.forget(pattern, mem_type=mem_type)
        return count

    # -- status ----------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        stats = self.store.stats()
        identity = self.identity
        p = identity.get("personality", {})
        age_str = identity.get("created_at", "unknown")
        return {
            "name": identity.get("name", "User"),
            "soul_age": age_str,
            "personality": p.get("traits", []),
            "style": p.get("style", ""),
            **stats,
        }

    # -- internal extraction (rule-based for v0.1, LLM in v0.2) ----------------

    def _extract_facts(self, text: str) -> list[dict]:
        """Simple rule-based fact extraction. Will be replaced by LLM in v0.2."""
        facts = []
        markers = [
            ("我住在", "fact"), ("我是", "fact"), ("我喜欢", "preference"),
            ("我不喜欢", "preference"), ("我擅长", "skill"), ("我在学", "skill"),
            ("我的工作是", "fact"), ("我叫", "fact"), ("我想", "preference"),
            ("我计划", "fact"), ("我决定", "fact"),
        ]
        for line in text.split("\n"):
            content = line.split(":", 1)[-1].strip() if ":" in line else line.strip()
            if not content or len(content) < 4:
                continue
            for marker, ftype in markers:
                if marker in content:
                    facts.append({"content": content, "type": ftype, "confidence": 0.7})
                    break
        return facts

    def _summarize(self, text: str) -> str:
        """Simple extractive summary. Returns first meaningful assistant message."""
        lines = text.strip().split("\n")
        for line in lines:
            if line.startswith("assistant:") and len(line) > 20:
                return f"对话摘要：{line[10:].strip()[:200]}"
        if len(text) > 50:
            return f"对话摘要：{text[:200].strip()}"
        return ""

    def _is_sensitive(self, text: str) -> bool:
        for pat in _SENSITIVE_PATTERNS:
            if pat.search(text):
                return True
        return False

    def save_identity(self) -> None:
        self.identity["updated_at"] = time.strftime("%Y-%m-%d")
        path = self.root / "identity.yaml"
        path.write_text(yaml.dump(self.identity, allow_unicode=True, sort_keys=False),
                        encoding="utf-8")
