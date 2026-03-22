"""PersonalityEngine — ensures Ome maintains consistent personality across all contexts.

Core capabilities:
  - anchors: immutable core principles (3-5 statements)
  - style_fingerprint: speaking style metrics (msg length, formality, emoji density)
  - validate(response, context): check output for personality consistency
  - social_mask(trust_level): expose different persona layers by trust level
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StyleFingerprint:
    """Quantified speaking style — used for consistency validation."""
    avg_msg_length: float = 50.0  # expected average chars per message
    formality: float = 0.5  # 0.0 = very casual, 1.0 = very formal
    emoji_density: float = 0.0  # emoji count per 100 chars
    catchphrases: list[str] = field(default_factory=list)
    forbidden_phrases: list[str] = field(default_factory=list)


class PersonalityEngine:
    """Ensure Ome's personality is consistent everywhere it appears.

    Usage:
        engine = PersonalityEngine(identity)
        ok, fixed = engine.validate(response, context)
        mask = engine.social_mask(trust_level=2)
    """

    def __init__(self, identity: dict[str, Any]) -> None:
        personality = identity.get("personality", {})
        self.name = identity.get("name", "User")
        self.anchors: list[str] = personality.get("anchors", [])
        self.traits: list[str] = personality.get("traits", [])
        self.values: list[str] = personality.get("values", [])
        self.boundaries: list[str] = personality.get("boundaries", [])
        self.style_fingerprint = self._build_fingerprint(personality)

    def validate(self, response: str, context: str = "") -> tuple[bool, str]:
        """Validate that a response is consistent with personality.

        L1 fast check (rules + keywords). Returns (passed, possibly_fixed_text).
        """
        # Check anchor violations
        for anchor in self.anchors:
            violation = self._check_anchor_violation(response, anchor)
            if violation:
                fixed = self._fix_violation(response, anchor, violation)
                return False, fixed

        # Check boundary violations
        for boundary in self.boundaries:
            if self._violates_boundary(response, boundary):
                return False, self._redact_boundary(response, boundary)

        # Check style consistency
        style_ok, style_fixed = self._check_style(response)
        if not style_ok:
            return False, style_fixed

        return True, response

    def social_mask(self, trust_level: int) -> dict[str, Any]:
        """Generate a filtered persona view based on trust level.

        Trust 0: Only interest tags (topics)
        Trust 1: Public persona + profession
        Trust 2: Work-related memories allowed
        Trust 3: Auto-reply + life preferences
        Trust 4: Deep memory sharing
        Trust 5: Full identity representation
        """
        if trust_level <= 0:
            return {
                "display_name": self.name,
                "topics": self._extract_public_topics(),
            }
        elif trust_level == 1:
            return {
                "display_name": self.name,
                "traits": self.traits[:3],
                "topics": self._extract_public_topics(),
            }
        elif trust_level == 2:
            return {
                "display_name": self.name,
                "traits": self.traits[:5],
                "values": self.values[:3],
                "topics": self._extract_public_topics(),
                "style": self.style_fingerprint.avg_msg_length,
            }
        elif trust_level == 3:
            return {
                "display_name": self.name,
                "traits": self.traits,
                "values": self.values,
                "can_auto_reply": True,
                "catchphrases": self.style_fingerprint.catchphrases[:5],
            }
        elif trust_level == 4:
            return {
                "display_name": self.name,
                "traits": self.traits,
                "values": self.values,
                "anchors": self.anchors,
                "catchphrases": self.style_fingerprint.catchphrases,
                "deep_memory_access": True,
            }
        else:  # 5 = full trust
            return {
                "display_name": self.name,
                "traits": self.traits,
                "values": self.values,
                "anchors": self.anchors,
                "boundaries": self.boundaries,
                "catchphrases": self.style_fingerprint.catchphrases,
                "full_representation": True,
            }

    def system_prompt_injection(self) -> str:
        """Generate anchor/value constraints for injection into system prompts."""
        parts = []
        if self.anchors:
            parts.append("## Core Principles (NEVER violate)")
            for a in self.anchors:
                parts.append(f"- {a}")
        if self.boundaries:
            parts.append("\n## Boundaries (NEVER discuss)")
            for b in self.boundaries:
                parts.append(f"- {b}")
        return "\n".join(parts)

    # -- Internal methods --

    def _build_fingerprint(self, personality: dict) -> StyleFingerprint:
        """Build style fingerprint from personality data."""
        catchphrases = personality.get("catchphrases", [])
        emoji_habits = personality.get("emoji_habits", [])
        style = personality.get("style", "")

        # Infer formality from traits/style
        formality = 0.5
        casual_words = {"随意", "轻松", "casual", "informal", "chill"}
        formal_words = {"正式", "严谨", "formal", "professional", "precise"}
        style_lower = style.lower()
        for w in casual_words:
            if w in style_lower:
                formality -= 0.2
        for w in formal_words:
            if w in style_lower:
                formality += 0.2
        formality = max(0.0, min(1.0, formality))

        return StyleFingerprint(
            avg_msg_length=50.0,  # will be calibrated from usage
            formality=formality,
            emoji_density=len(emoji_habits) / 10.0,
            catchphrases=catchphrases[:10],
            forbidden_phrases=self._extract_forbidden(personality),
        )

    @staticmethod
    def _extract_forbidden(personality: dict) -> list[str]:
        """Extract phrases the personality should never say."""
        forbidden = []
        boundaries = personality.get("boundaries", [])
        for b in boundaries:
            # Extract quoted phrases from boundaries
            for m in re.findall(r'[「"](.*?)[」"]', b):
                forbidden.append(m)
        return forbidden

    def _check_anchor_violation(self, response: str, anchor: str) -> str:
        """Check if response violates an anchor principle. Returns violation type or ''."""
        resp_lower = response.lower()
        anchor_lower = anchor.lower()

        # "简洁" anchor: check for excessively long responses
        if "简洁" in anchor_lower or "concise" in anchor_lower:
            if len(response) > 500:
                return "too_long"

        # "不替用户做不可逆决策" anchor: check for definitive actions
        if "不可逆" in anchor_lower or "确认" in anchor_lower:
            action_words = ["我已经", "已发送", "已删除", "已执行", "done", "sent", "deleted"]
            if any(w in resp_lower for w in action_words):
                return "irreversible_action"

        # "隐私" anchor: check for personal info exposure
        if "隐私" in anchor_lower or "privacy" in anchor_lower:
            pii_patterns = [r"\d{11}", r"\d{15,18}", r"\d{4}[-\s]\d{4}"]
            for pat in pii_patterns:
                if re.search(pat, response):
                    return "pii_leak"

        return ""

    def _fix_violation(self, response: str, anchor: str, violation: str) -> str:
        """Attempt to fix a response that violates an anchor."""
        if violation == "too_long":
            # Truncate to roughly 300 chars at sentence boundary
            sentences = re.split(r'[。！？.!?]', response)
            result = ""
            for s in sentences:
                if len(result) + len(s) > 300:
                    break
                result += s + "。"
            return result.rstrip("。") + "。" if result else response[:300] + "..."

        if violation == "irreversible_action":
            return response + "\n\n⚠️ 注意：这个操作需要你确认后才能执行。"

        if violation == "pii_leak":
            # Redact numbers that look like PII
            return re.sub(r"\d{11,}", "[已隐藏]", response)

        return response

    def _violates_boundary(self, response: str, boundary: str) -> bool:
        """Check if response discusses a forbidden topic."""
        for phrase in self.style_fingerprint.forbidden_phrases:
            if phrase.lower() in response.lower():
                return True
        return False

    def _redact_boundary(self, response: str, boundary: str) -> str:
        """Redact boundary-violating content."""
        for phrase in self.style_fingerprint.forbidden_phrases:
            response = re.sub(re.escape(phrase), "[...]", response, flags=re.IGNORECASE)
        return response

    def _check_style(self, response: str) -> tuple[bool, str]:
        """Check response against style fingerprint."""
        # Check forbidden phrases
        for phrase in self.style_fingerprint.forbidden_phrases:
            if phrase.lower() in response.lower():
                response = response.replace(phrase, "")
                return False, response.strip()
        return True, response

    def _extract_public_topics(self) -> list[str]:
        """Extract safe-to-share topic tags from traits."""
        topics = []
        for t in self.traits[:5]:
            topics.append(t)
        return topics

    def to_dict(self) -> dict[str, Any]:
        return {
            "anchors": self.anchors,
            "traits": self.traits,
            "values": self.values,
            "formality": self.style_fingerprint.formality,
            "catchphrases_count": len(self.style_fingerprint.catchphrases),
        }
