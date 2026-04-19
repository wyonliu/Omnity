"""ContextBuilder — assemble a harness call's context from MemoryDoc files.

The harness is "file-first": it reads IDENTITY.md / MEMORY.md / FACTS.md
straight from a MemoryDoc export directory (or an Ome home) rather than
routing through a bespoke memory API.

Google's long-context research plus our own v0.8 experience both say the
same thing: **the filesystem IS the memory.** A harness that respects that
stays portable, debuggable, and git-diffable.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger("mindos.harness.context")

# Rough char→token factor for budgeting. Not accurate but good enough for
# gating; replace with a real tokenizer once we commit to one.
_CHARS_PER_TOKEN = 3.5


@dataclass
class AssembledContext:
    """Result of ContextBuilder.build()."""
    system_prompt: str
    user_message: str
    files_used: list[str] = field(default_factory=list)
    char_budget_used: int = 0
    truncated: bool = False


class ContextBuilder:
    """Build a system prompt + user turn from a MemoryDoc directory.

    Context assembly order (layered to maximise cache hit rate):
        1. IDENTITY.md            — stable, cache-able for 1h
        2. MEMORY.md / FACTS.md   — churn-y but read-heavy
        3. Recent journal (n)     — cheapest to regenerate
        4. User message           — always fresh

    The first three get glued into `system_prompt`; the fourth goes into
    `user_message`. Keeping the first-three stable across calls is what
    lets ClaudeBackend actually hit prompt cache.
    """

    def __init__(
        self,
        source: Path | str,
        *,
        max_chars: int = 48_000,           # ≈ 14k tokens headroom
        recent_days: int = 3,
    ):
        self.source = Path(source)
        self.max_chars = int(max_chars)
        self.recent_days = int(recent_days)

    # -- public ----------------------------------------------------------

    def build(self, user_message: str) -> AssembledContext:
        used: list[str] = []
        parts: list[str] = []

        # 1. IDENTITY
        identity = self._read(self.source / "IDENTITY.md")
        if identity:
            parts.append(f"# Identity\n\n{identity}")
            used.append("IDENTITY.md")

        # 2. MEMORY + FACTS
        memory = self._read(self.source / "MEMORY.md")
        if memory:
            parts.append(f"# Long-term memory\n\n{memory}")
            used.append("MEMORY.md")

        facts = self._read(self.source / "FACTS.md")
        if facts:
            parts.append(f"# Known facts\n\n{facts}")
            used.append("FACTS.md")

        # 3. Recent journal: look for a Journal/ dir under the source
        journal_dir = self.source / "Journal"
        if not journal_dir.exists():
            # Alternate layout: home/ome/journal or user-defined
            for alt in ("journal", "Notes", "notes"):
                p = self.source / alt
                if p.exists():
                    journal_dir = p
                    break

        journal_blob = self._recent_journal(journal_dir)
        if journal_blob:
            parts.append(f"# Recent journal (last {self.recent_days}d)\n\n{journal_blob}")
            used.append(f"{journal_dir.name}/recent")

        system = "\n\n".join(parts).strip()

        # Budget enforcement: system + user_message must fit. If over, drop
        # journal first, then FACTS, then MEMORY — IDENTITY is non-negotiable.
        truncated = False
        while (len(system) + len(user_message)) > self.max_chars and parts:
            # remove from the end of parts — it's ordered cheapest-to-regen last
            parts.pop()
            used.pop()
            system = "\n\n".join(parts).strip()
            truncated = True

        return AssembledContext(
            system_prompt=system,
            user_message=user_message,
            files_used=used,
            char_budget_used=len(system) + len(user_message),
            truncated=truncated,
        )

    # -- internals -------------------------------------------------------

    @staticmethod
    def _read(path: Path) -> str:
        try:
            if not path.exists():
                return ""
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            log.debug("skip %s: %s", path, e)
            return ""
        # Strip YAML frontmatter — it's machine metadata, not context
        return _strip_frontmatter(text).strip()

    def _recent_journal(self, journal_dir: Path) -> str:
        if not journal_dir.exists() or not journal_dir.is_dir():
            return ""
        # Take up to `recent_days` files, newest-mtime first
        candidates = sorted(
            (p for p in journal_dir.glob("*.md") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[: self.recent_days]
        if not candidates:
            return ""
        return "\n\n---\n\n".join(
            f"## {p.name}\n\n{_strip_frontmatter(p.read_text(encoding='utf-8')).strip()}"
            for p in candidates
        )


_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def _strip_frontmatter(text: str) -> str:
    m = _FRONTMATTER.match(text)
    return text[m.end():] if m else text


def approx_tokens(text: str) -> int:
    """Cheap char→token estimate; use only for budgeting."""
    return max(1, int(len(text) / _CHARS_PER_TOKEN))
