"""OmeBench question bank loader.

Accepts JSONL or a single JSON array. One question per row:

    {
      "id": "q1",
      "question": "When did I start at Longfor?",
      "category": "temporal",
      "expected_contains": ["2026-04-08"],
      "expected_any": ["April", "四月"],
      "expected_regex": ["2026-0[34]-\\d{2}"],
      "forbid_contains": ["未知", "不知道"]
    }
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator


@dataclass
class Question:
    id: str
    question: str
    category: str = "uncategorized"
    expected_contains: list[str] = field(default_factory=list)
    expected_any: list[str] = field(default_factory=list)
    expected_regex: list[str] = field(default_factory=list)
    forbid_contains: list[str] = field(default_factory=list)
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "Question":
        return cls(
            id=str(data.get("id") or ""),
            question=str(data.get("question") or ""),
            category=str(data.get("category") or "uncategorized"),
            expected_contains=list(data.get("expected_contains") or []),
            expected_any=list(data.get("expected_any") or []),
            expected_regex=list(data.get("expected_regex") or []),
            forbid_contains=list(data.get("forbid_contains") or []),
            notes=str(data.get("notes") or ""),
        )


def load_questions(path: str | Path) -> list[Question]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"questions file not found: {p}")
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        return []
    # Try JSON array first
    if text.lstrip().startswith("["):
        arr = json.loads(text)
        return [Question.from_dict(d) for d in arr]
    # Otherwise JSONL
    return [Question.from_dict(json.loads(line))
            for line in _iter_nonempty(text)]


def _iter_nonempty(text: str) -> Iterator[str]:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            yield stripped
