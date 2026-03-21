"""L1 Brainstem — Instinct layer: fast routing, hydrate assembly, emotion state.

Handles 60%+ requests at near-zero cost by determining whether a request needs
L2/L3 processing or can be answered from cached identity + recent memories.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from mindos.layers.l0_memory import Hippocampus, relevance_score
from mindos.store import Memory


class Mood(Enum):
    NEUTRAL = "neutral"
    ENGAGED = "engaged"
    CAUTIOUS = "cautious"
    CREATIVE = "creative"
    TIRED = "tired"


@dataclass
class EmotionState:
    mood: Mood = Mood.NEUTRAL
    energy: float = 1.0       # 0.0-1.0
    last_update: float = 0.0

    def tick(self) -> None:
        """Circadian-style energy decay."""
        now = time.time()
        if self.last_update > 0:
            elapsed_hours = (now - self.last_update) / 3600
            self.energy = max(0.1, self.energy - 0.02 * elapsed_hours)
        self.last_update = now

    def boost(self, delta: float = 0.1) -> None:
        self.energy = min(1.0, self.energy + delta)
        self.mood = Mood.ENGAGED

    def to_dict(self) -> dict[str, Any]:
        return {"mood": self.mood.value, "energy": round(self.energy, 2)}


class Brainstem:
    """L1: fast routing and context assembly."""

    def __init__(self, hippocampus: Hippocampus, identity: dict[str, Any]) -> None:
        self.hippocampus = hippocampus
        self.identity = identity
        self.emotion = EmotionState(last_update=time.time())

    def hydrate(self, context: str = "", max_tokens: int = 2000,
                query_vec: Any = None) -> str:
        """Assemble a compact identity prompt from stored soul data.

        Token budget breakdown (approximate):
          - Core identity block: ~200 tokens
          - Capabilities: ~100 tokens
          - Relevant memories: remaining budget
          - Knowledge graph triples: up to 200 tokens
        """
        self.emotion.tick()
        blocks: list[str] = []

        name = self.identity.get("name", "Mindos")
        traits = self.identity.get("traits", [])
        style = self.identity.get("style", "")

        blocks.append(f"# {name}")
        if traits:
            blocks.append("Personality: " + ", ".join(traits))
        if style:
            blocks.append(f"Communication style: {style}")

        caps = self.identity.get("capabilities", [])
        if caps:
            blocks.append("\nCapabilities: " + ", ".join(caps))

        blocks.append(f"\n[Mood: {self.emotion.mood.value} | Energy: {self.emotion.energy:.0%}]")

        # Relevant memories
        memories = self.hippocampus.recall(
            context, top_k=15, query_vec=query_vec,
        )
        if memories:
            blocks.append("\n## Relevant memories")
            for m in memories:
                score = relevance_score(m)
                tag = f"[{m.type}|{score:.2f}]"
                blocks.append(f"- {tag} {m.content}")

        # Knowledge graph
        triples = self.hippocampus.store.triples()
        if triples:
            blocks.append("\n## Knowledge graph")
            for t in triples[:30]:
                blocks.append(f"- ({t.subject}) —{t.predicate}→ ({t.object})")

        assembled = "\n".join(blocks)

        # Rough token estimate (1 token ≈ 1.5 CJK chars or 0.75 English words)
        est_tokens = len(assembled) // 2
        if est_tokens > max_tokens:
            ratio = max_tokens / est_tokens
            lines = assembled.split("\n")
            assembled = "\n".join(lines[: int(len(lines) * ratio)])

        return assembled

    def classify_request(self, text: str) -> str:
        """Route request to appropriate layer.

        Returns: 'l1' (handle here), 'l2' (cortex), 'l3' (prefrontal), 'l4' (self)
        """
        text_lower = text.lower()

        l1_patterns = [
            r"^(hi|hello|hey|你好|嗨)",
            r"(what time|几点|天气)",
            r"^(thanks|谢谢|ok|好的|明白)",
        ]
        for p in l1_patterns:
            if re.search(p, text_lower):
                return "l1"

        l4_patterns = [
            r"(who are you|你是谁|what do you think|你怎么看|你的看法)",
            r"(reflect|反思|你的价值观|personality)",
        ]
        for p in l4_patterns:
            if re.search(p, text_lower):
                return "l4"

        l3_patterns = [
            r"(plan|规划|strategy|创作|design|architect|分析)",
            r"(write.*essay|写.*文章|summarize|总结.*报告)",
        ]
        for p in l3_patterns:
            if re.search(p, text_lower):
                return "l3"

        return "l2"
