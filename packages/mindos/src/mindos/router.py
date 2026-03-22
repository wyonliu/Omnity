"""LayerRouter — routes requests to the appropriate brain layer."""

from __future__ import annotations

from typing import Any, Optional

from mindos.config import MindosConfig, ModelRouter
from mindos.layers.l0_memory import Hippocampus
from mindos.layers.l1_instinct import Brainstem
from mindos.layers.l2_cognition import Cortex
from mindos.layers.l3_decision import Prefrontal
from mindos.layers.l4_self import Self
from mindos.store import MemoryStore


class LayerRouter:
    """Orchestrates the five brain layers.

    Request flow:
    1. L1 (Brainstem) classifies the request
    2. Routes to appropriate layer (L1/L2/L3/L4)
    3. All layers read from L0 (Hippocampus)
    4. Write operations go through L2 (commit) or L0 (direct store)
    """

    def __init__(self, store: MemoryStore, identity: dict[str, Any],
                 config: Optional[MindosConfig] = None) -> None:
        self.store = store
        self.identity = identity
        self.config = config

        router = ModelRouter(config) if config else None

        self.l0 = Hippocampus(store)
        self.l1 = Brainstem(self.l0, identity, store)
        self.l2 = Cortex(store, router)
        self.l3 = Prefrontal(router)
        self.l4 = Self(store, identity, router)

    def process(self, text: str, **kwargs: Any) -> dict[str, Any]:
        """Unified request entry — L1 classifies, then auto-routes to the right layer.

        This is THE preferred entry point for Ome and all external systems.
        90% of requests resolve at L1/L2. <10% escalate to L3/L4.
        """
        level = self.l1.classify_request(text)

        if level == "l1":
            reply = self.l1.quick_reply(text)
            return {"response": reply, "layer": "l1", "cost": 0}

        elif level == "l2":
            identity_ctx = self.hydrate(text)
            memories = self.l0.recall(text, top_k=5)
            memory_ctx = "\n".join(f"- {m.content}" for m in memories)
            if self.l2.router:
                response = self.l2.router.call_llm(
                    task="chat",
                    system=identity_ctx,
                    user=f"Context:\n{memory_ctx}\n\nUser: {text}",
                )
                if response:
                    return {"response": response, "layer": "l2"}
            # Fallback: return identity + memories as context
            return {
                "response": f"[L2 no-LLM] Context assembled with {len(memories)} memories.",
                "layer": "l2",
                "identity": identity_ctx,
                "memories": [m.content for m in memories],
            }

        elif level == "l3":
            response = self.reason(text)
            return {"response": response or "[L3] No reasoning result.", "layer": "l3"}

        else:  # l4
            reflection = self.reflect()
            summary = ""
            if reflection:
                summary = reflection.get("summary", "Reflection complete.")
            return {
                "response": summary or "No reflection needed.",
                "layer": "l4",
                "reflection": reflection,
            }

    def hydrate(self, context: str = "", max_tokens: int = 2000,
                query_vec: Any = None) -> str:
        """Assemble identity context (L1 → L0)."""
        return self.l1.hydrate(context, max_tokens, query_vec)

    def commit(self, conversation: str, source: str = "") -> dict[str, Any]:
        """Digest conversation into memories (L2 → L0).

        Triggers L4 reflection when enough commits accumulate.
        """
        existing = [m.content for m in self.l0.recent(20, mem_type="fact")]
        result = self.l2.commit(conversation, source, existing)

        reflection = self.l4.on_commit()
        if reflection:
            result["reflection"] = reflection

        return result

    def recall(self, query: str, top_k: int = 10,
               query_vec: Any = None) -> list[dict[str, Any]]:
        """Recall memories with relevance ranking (L0)."""
        memories = self.l0.recall(query, top_k, query_vec)
        return [
            {
                "id": m.id, "type": m.type, "content": m.content,
                "source": m.source, "confidence": m.confidence,
            }
            for m in memories
        ]

    def forget(self, pattern: str, scope: Optional[str] = None) -> dict[str, Any]:
        """Physical erasure (L0)."""
        mem_type = None
        if scope in ("fact", "episode", "preference", "skill", "relation"):
            mem_type = scope
        count = self.store.forget(pattern, mem_type)
        return {"deleted": count, "pattern": pattern, "scope": scope}

    def reason(self, query: str, context: str = "") -> Optional[str]:
        """Deep reasoning (L3 via L1 routing)."""
        identity_ctx = self.hydrate(query)
        memories = self.l0.recall(query, top_k=10)
        memory_ctx = "\n".join(f"- [{m.type}] {m.content}" for m in memories)
        return self.l3.reason(query, identity_ctx, memory_ctx)

    def reflect(self) -> Optional[dict[str, Any]]:
        """Force a reflection cycle (L4)."""
        return self.l4.reflect()

    def status(self) -> dict[str, Any]:
        """Full status across all layers."""
        return {
            "identity": self.l4.personality_snapshot(),
            "memory": self.l0.stats(),
            "emotion": self.l1.emotion.to_dict(),
            "commits_since_reflection": self.l4._commit_count_since_reflect,
        }
