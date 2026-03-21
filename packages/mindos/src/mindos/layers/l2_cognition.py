"""L2 Cortex — Cognition layer: LLM-powered commit digestion, fact extraction.

Replaces the old regex-based extraction with real NLU via ModelRouter.
Falls back to rule-based extraction when no LLM is available.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any, Optional

from mindos.config import ModelRouter
from mindos.store import Memory, MemoryStore, Triple

_COMMIT_SYSTEM = """You are a memory extraction engine for a personal AI identity system.
Given a conversation, extract structured information. Output JSON with:
{
  "facts": [{"content": "...", "type": "fact|preference|skill|relation", "confidence": 0.0-1.0}],
  "triples": [{"subject": "...", "predicate": "...", "object": "..."}],
  "episode_summary": "One-sentence summary of the conversation",
  "contradictions": [{"existing": "...", "new": "...", "recommendation": "keep_old|keep_new|flag"}]
}
Rules:
- Extract preferences (likes, dislikes, habits), facts (biographical info, knowledge),
  skills (things the person knows/can do), and relations (people/organizations they know).
- Confidence: 1.0 for explicitly stated, 0.7 for strongly implied, 0.4 for weakly implied.
- Detect contradictions with existing facts provided in context.
- Skip greetings, filler, and overly specific transient details.
- Output valid JSON only, no markdown."""

_SENSITIVE_PATTERNS = [
    r"\b\d{15,18}\b",                      # ID numbers
    r"\b[A-Za-z0-9]{20,}\b",               # long tokens / API keys
    r"(sk-|ak-|pk-)[A-Za-z0-9]+",          # API key prefixes
    r"\b\d{16}\b",                          # credit card numbers
    r"密[码钥]|password|secret|token|credential|private.?key",
]


class Cortex:
    """L2: commit digestion via LLM with rule-based fallback."""

    def __init__(self, store: MemoryStore, model_router: Optional[ModelRouter] = None) -> None:
        self.store = store
        self.router = model_router

    def commit(self, conversation: str, source: str = "",
               existing_facts: Optional[list[str]] = None) -> dict[str, Any]:
        """Digest a conversation into memories.

        Returns a summary dict with counts and extraction details.
        """
        result: dict[str, Any] = {
            "facts_added": 0, "triples_added": 0,
            "skipped_duplicate": 0, "skipped_sensitive": 0,
            "contradictions": [], "episode": "",
            "method": "llm",
        }

        if self._is_sensitive(conversation):
            result["skipped_sensitive"] += 1
            result["method"] = "blocked"
            return result

        extraction = self._extract_llm(conversation, existing_facts)
        if extraction is None:
            extraction = self._extract_rules(conversation)
            result["method"] = "rules"

        for fact in extraction.get("facts", []):
            content = fact["content"]
            if self._is_sensitive(content):
                result["skipped_sensitive"] += 1
                continue
            if self.store.content_exists(content):
                result["skipped_duplicate"] += 1
                continue
            mem = Memory(
                id="", type=fact.get("type", "fact"), content=content,
                source=source, confidence=fact.get("confidence", 0.8),
            )
            self.store.add(mem)
            result["facts_added"] += 1

        for triple in extraction.get("triples", []):
            if any(self._is_sensitive(v) for v in [triple["subject"], triple["predicate"], triple["object"]]):
                result["skipped_sensitive"] += 1
                continue
            self.store.add_triple(Triple(
                subject=triple["subject"], predicate=triple["predicate"],
                object=triple["object"], source=source,
            ))
            result["triples_added"] += 1

        episode = extraction.get("episode_summary", "")
        if episode and not self.store.content_exists(episode) and not self._is_sensitive(episode):
            self.store.add(Memory(id="", type="episode", content=episode, source=source))
            result["episode"] = episode

        result["contradictions"] = extraction.get("contradictions", [])
        return result

    def _extract_llm(self, conversation: str, existing_facts: Optional[list[str]] = None) -> Optional[dict]:
        if self.router is None:
            return None

        context = ""
        if existing_facts:
            context = "\nExisting facts:\n" + "\n".join(f"- {f}" for f in existing_facts[:30])

        user_msg = f"Conversation to analyze:{context}\n\n---\n{conversation}\n---"
        raw = self.router.call_llm(
            system=_COMMIT_SYSTEM, user=user_msg,
            task="commit_digest", max_tokens=2048, json_mode=True,
        )
        if raw is None:
            return None

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            return None

    def _extract_rules(self, conversation: str) -> dict:
        """Rule-based fallback: extract obvious facts from markers."""
        facts: list[dict[str, Any]] = []
        lines = conversation.strip().split("\n")

        fact_markers = [
            "我是", "我叫", "我的", "我喜欢", "我讨厌", "我擅长", "我住在", "我在",
            "I am", "I'm", "My ", "I like", "I prefer", "I live", "I work",
        ]

        for line in lines:
            stripped = line.strip()
            if not stripped or len(stripped) < 4:
                continue
            for marker in fact_markers:
                if marker in stripped:
                    facts.append({"content": stripped, "type": "fact", "confidence": 0.7})
                    break

        episode = ""
        if lines:
            episode = f"Conversation ({time.strftime('%Y-%m-%d')}): {lines[0][:100]}..."

        return {"facts": facts, "triples": [], "episode_summary": episode, "contradictions": []}

    def _is_sensitive(self, text: str) -> bool:
        for pattern in _SENSITIVE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
