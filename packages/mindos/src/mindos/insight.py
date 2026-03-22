"""InsightEngine — extract patterns, contradictions, and digests from memory.

All methods are L1-level (rule-based + statistics), no LLM required.
Provides data for Ome's "weekly highlights", daily push notifications, etc.
"""

from __future__ import annotations

import logging
import re
import time
from collections import Counter, defaultdict
from typing import Any, Optional

from mindos.store import MemoryStore

log = logging.getLogger("mindos.insight")


class InsightEngine:
    """From memories to actionable insights — Ome's data source for growth reports."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def daily_digest(self, hours: int = 24) -> dict[str, Any]:
        """Summarize recent activity into a compact digest.

        Returns:
            {
                "period_hours": 24,
                "total_memories": N,
                "by_type": {"fact": N, "episode": N, ...},
                "by_source": {"claude": N, "cursor": N, ...},
                "top_topics": ["topic1", "topic2", ...],
                "highlights": ["insight1", "insight2", ...],
            }
        """
        cutoff = time.time() - hours * 3600
        recent = self.store.list_recent(limit=500)
        in_period = [m for m in recent if m.created_at >= cutoff]

        if not in_period:
            return {
                "period_hours": hours,
                "total_memories": 0,
                "by_type": {},
                "by_source": {},
                "top_topics": [],
                "highlights": ["今天没有新记忆。"],
            }

        by_type: dict[str, int] = Counter()
        by_source: dict[str, int] = Counter()
        words: Counter[str] = Counter()

        for m in in_period:
            by_type[m.type] += 1
            by_source[m.source] += 1
            # Extract topic words (CJK 2-grams + English words)
            for w in self._extract_keywords(m.content):
                words[w] += 1

        top_topics = [w for w, _ in words.most_common(10)]

        # Build highlights
        highlights: list[str] = []
        total = len(in_period)
        highlights.append(f"今天新增 {total} 条记忆")
        if by_source:
            top_src = max(by_source, key=by_source.get)  # type: ignore
            highlights.append(f"最活跃来源：{top_src}（{by_source[top_src]} 条）")
        fact_count = by_type.get("fact", 0)
        if fact_count:
            highlights.append(f"新增 {fact_count} 条事实")

        return {
            "period_hours": hours,
            "total_memories": total,
            "by_type": dict(by_type),
            "by_source": dict(by_source),
            "top_topics": top_topics,
            "highlights": highlights,
        }

    def contradiction_alert(self) -> list[dict[str, str]]:
        """Find potentially contradictory facts.

        Strategy: group facts by subject (first noun), find pairs with
        opposing sentiment or conflicting values.

        Returns list of {"fact_a": "...", "fact_b": "...", "reason": "..."}.
        """
        facts = self.store.list_recent(limit=200, mem_type="fact")
        if len(facts) < 2:
            return []

        contradictions: list[dict[str, str]] = []
        # Group by leading keyword
        groups: dict[str, list] = defaultdict(list)
        for f in facts:
            key = self._subject_key(f.content)
            if key:
                groups[key].append(f)

        for key, group in groups.items():
            if len(group) < 2:
                continue
            # Check pairs for opposition
            for i, a in enumerate(group):
                for b in group[i + 1:]:
                    reason = self._detect_contradiction(a.content, b.content)
                    if reason:
                        contradictions.append({
                            "fact_a": a.content,
                            "fact_b": b.content,
                            "reason": reason,
                        })

        return contradictions[:10]  # Cap at 10

    def pattern_discovery(self) -> list[dict[str, Any]]:
        """Discover behavioral patterns from memory metadata.

        Looks for:
        - Recurring time patterns (e.g., commits always on Friday afternoon)
        - Source clustering (heavy usage of one platform)
        - Topic trends over time

        Returns list of {"pattern": "...", "evidence": "...", "strength": float}.
        """
        all_mems = self.store.list_recent(limit=1000)
        if len(all_mems) < 10:
            return []

        patterns: list[dict[str, Any]] = []

        # 1. Time-of-day pattern
        hour_counts: Counter[int] = Counter()
        for m in all_mems:
            hour = int((m.created_at % 86400) / 3600)
            # Adjust for timezone (rough UTC+8 assumption for CJK users)
            hour = (hour + 8) % 24
            hour_counts[hour] += 1

        if hour_counts:
            peak_hour = hour_counts.most_common(1)[0]
            total = sum(hour_counts.values())
            if peak_hour[1] / total > 0.15:  # >15% of activity in one hour
                patterns.append({
                    "pattern": f"你最活跃的时间是 {peak_hour[0]}:00 左右",
                    "evidence": f"{peak_hour[1]}/{total} 条记忆在这个时段",
                    "strength": round(peak_hour[1] / total, 2),
                })

        # 2. Source dominance
        source_counts: Counter[str] = Counter()
        for m in all_mems:
            if m.source:
                source_counts[m.source] += 1
        if source_counts:
            top_source = source_counts.most_common(1)[0]
            total = sum(source_counts.values())
            if top_source[1] / total > 0.4:  # >40% from one source
                patterns.append({
                    "pattern": f"你的主要信息来源是 {top_source[0]}",
                    "evidence": f"占比 {top_source[1] / total:.0%}",
                    "strength": round(top_source[1] / total, 2),
                })

        # 3. Topic trend (recent vs older)
        mid = len(all_mems) // 2
        recent_words = Counter()
        older_words = Counter()
        for m in all_mems[:mid]:
            for w in self._extract_keywords(m.content):
                recent_words[w] += 1
        for m in all_mems[mid:]:
            for w in self._extract_keywords(m.content):
                older_words[w] += 1

        for word, count in recent_words.most_common(20):
            old_count = older_words.get(word, 0)
            if count >= 3 and old_count == 0:
                patterns.append({
                    "pattern": f"近期新话题：「{word}」",
                    "evidence": f"最近 {count} 次提及，之前没有",
                    "strength": min(1.0, count / 5),
                })
                if len(patterns) >= 8:
                    break

        return patterns

    def weekly_summary(self) -> dict[str, Any]:
        """Comprehensive weekly report combining all insight methods."""
        digest = self.daily_digest(hours=168)  # 7 days
        contradictions = self.contradiction_alert()
        patterns = self.pattern_discovery()

        stats = self.store.stats()
        timeline = self.store.personality_timeline()

        return {
            "period": "weekly",
            "digest": digest,
            "contradictions": contradictions,
            "patterns": patterns,
            "total_memories": stats.get("total_memories", 0),
            "personality_changes": len(timeline),
        }

    # -- internal helpers --

    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        """Extract meaningful keywords from text (CJK bigrams + English words)."""
        keywords: list[str] = []
        # English words (3+ chars)
        for w in re.findall(r"[a-zA-Z]{3,}", text):
            keywords.append(w.lower())
        # CJK: extract 2-grams, skip common particles
        _STOP = {"的", "了", "是", "在", "我", "有", "和", "人", "这", "中", "大", "为",
                 "上", "个", "到", "说", "会", "也", "就", "不", "你", "他", "她", "它"}
        chars = [c for c in text if '\u4e00' <= c <= '\u9fff' and c not in _STOP]
        for i in range(len(chars) - 1):
            bigram = chars[i] + chars[i + 1]
            keywords.append(bigram)
        return keywords

    @staticmethod
    def _subject_key(content: str) -> str:
        """Extract a rough subject key for grouping related facts.

        Groups by verb/action rather than object, so "我住在上海" and "我住在北京"
        both key to "住在" for contradiction detection.
        """
        # Try CJK pattern: "我(verb+)(object)" — group by verb
        m = re.match(r".*?我([是在喜欢讨厌住擅长]+)", content)
        if m:
            return m.group(1)
        # English: "I (verb)" — group by verb
        m = re.match(r".*?I\s+(\w+)", content, re.IGNORECASE)
        if m:
            return m.group(1).lower()
        return ""

    @staticmethod
    def _detect_contradiction(a: str, b: str) -> str:
        """Simple heuristic to detect contradictory statements."""
        # Pattern: same subject, opposite sentiment
        pos_words = {"喜欢", "爱", "擅长", "like", "love", "enjoy", "prefer", "good at"}
        neg_words = {"讨厌", "不喜欢", "hate", "dislike", "avoid", "bad at", "不擅长"}

        a_lower = a.lower()
        b_lower = b.lower()

        a_pos = any(w in a_lower for w in pos_words)
        a_neg = any(w in a_lower for w in neg_words)
        b_pos = any(w in b_lower for w in pos_words)
        b_neg = any(w in b_lower for w in neg_words)

        if (a_pos and b_neg) or (a_neg and b_pos):
            return "情感倾向矛盾"

        # Pattern: "住在X" vs "住在Y"
        m_a = re.search(r"住在(\S+)", a)
        m_b = re.search(r"住在(\S+)", b)
        if m_a and m_b and m_a.group(1) != m_b.group(1):
            return f"地点矛盾：{m_a.group(1)} vs {m_b.group(1)}"

        return ""
