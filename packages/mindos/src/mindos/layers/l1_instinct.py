"""L1 Brainstem — Instinct layer: fast routing, hydrate assembly, emotion state.

Handles 60%+ requests at near-zero cost by determining whether a request needs
L2/L3 processing or can be answered from cached identity + recent memories.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from mindos.layers.l0_memory import Hippocampus, relevance_score
from mindos.store import Memory, MemoryStore

log = logging.getLogger("mindos.l1")


def _estimate_tokens(text: str) -> int:
    """Better token estimation that accounts for CJK vs ASCII.

    CJK characters are roughly 1.5 tokens each (BPE splits them more).
    ASCII words average ~1.3 tokens (subword tokenization).
    """
    cjk_count = 0
    ascii_count = 0
    for ch in text:
        cp = ord(ch)
        if (0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or
                0xF900 <= cp <= 0xFAFF or 0x2E80 <= cp <= 0x2FFF or
                0x3000 <= cp <= 0x303F):
            cjk_count += 1
        else:
            ascii_count += 1
    # CJK: ~1.5 tokens/char, ASCII: ~0.25 tokens/char (4 chars ≈ 1 token)
    return int(cjk_count * 1.5 + ascii_count * 0.25)


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

    def __init__(self, hippocampus: Hippocampus, identity: dict[str, Any],
                 store: Optional[MemoryStore] = None) -> None:
        self.hippocampus = hippocampus
        self.identity = identity
        self._store = store
        self.emotion = self._load_emotion()

    def _load_emotion(self) -> EmotionState:
        """Restore emotion state from persistent storage."""
        if self._store:
            raw = self._store.get_state("emotion")
            if raw:
                try:
                    d = json.loads(raw)
                    return EmotionState(
                        mood=Mood(d.get("mood", "neutral")),
                        energy=d.get("energy", 1.0),
                        last_update=d.get("last_update", time.time()),
                    )
                except Exception:
                    pass
        return EmotionState(last_update=time.time())

    def save_emotion(self) -> None:
        """Persist current emotion state."""
        if self._store:
            self._store.set_state("emotion", json.dumps({
                "mood": self.emotion.mood.value,
                "energy": self.emotion.energy,
                "last_update": self.emotion.last_update,
            }))

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

        # Token estimation: CJK chars ≈ 1.5 tokens each, ASCII ≈ 0.25 tokens per char
        est_tokens = _estimate_tokens(assembled)
        if est_tokens > max_tokens:
            ratio = max_tokens / est_tokens
            lines = assembled.split("\n")
            assembled = "\n".join(lines[: int(len(lines) * ratio)])

        # Persist emotion after hydrate
        self.save_emotion()
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
