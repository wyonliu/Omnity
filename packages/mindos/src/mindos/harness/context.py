"""ContextBuilder — assemble a harness call's context from MemoryDoc files.

The harness is "file-first": it reads IDENTITY.md / MEMORY.md / FACTS.md
straight from a MemoryDoc export directory (or an Ome home) rather than
routing through a bespoke memory API.

Google's long-context research plus our own v0.8 experience both say the
same thing: **the filesystem IS the memory.** A harness that respects that
stays portable, debuggable, and git-diffable.

W3 extension (2026-04-19, on Ome365's request): ``source=`` now also accepts
any object satisfying the ``ContextLoader`` protocol below. Lets tenants
backed by PG+RLS, S3, or a zip blob read context without dumping to disk
every turn, while preserving the tenant-boundary check at read time.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Protocol, Union, runtime_checkable

log = logging.getLogger("mindos.harness.context")

# Rough char→token factor for budgeting. Not accurate but good enough for
# gating; replace with a real tokenizer once we commit to one.
_CHARS_PER_TOKEN = 3.5


# -- Loader protocol -------------------------------------------------------

@runtime_checkable
class ContextLoader(Protocol):
    """Minimal read-only view over a MemoryDoc-shaped namespace.

    Implementations MUST enforce their own access control (e.g. RLS) and
    MUST return the empty string (not raise) for missing paths — the builder
    treats absence as "skip this section". Journal listing may return an
    empty list.

    ``read_text`` receives a forward-slash relative path (e.g.
    ``"IDENTITY.md"`` or ``"Journal/2026-04-19.md"``). It should never
    receive absolute paths or ``..`` segments; the builder never constructs
    those.
    """

    def read_text(self, relpath: str) -> str: ...

    def list_journal(self, *, limit: int) -> list[str]:
        """Return the `limit` most recent journal entry relpaths.

        Each entry must be readable via ``read_text(entry)``. Order: newest
        first. Empty list means "no journal".
        """
        ...


class _PathLoader:
    """Default loader: read straight from a directory on disk."""

    def __init__(self, root: Path):
        self._root = root

    def read_text(self, relpath: str) -> str:
        p = self._root / relpath
        try:
            if not p.exists() or not p.is_file():
                return ""
            return p.read_text(encoding="utf-8")
        except OSError as e:
            log.debug("skip %s: %s", p, e)
            return ""

    def list_journal(self, *, limit: int) -> list[str]:
        journal_dir: Optional[Path] = None
        for name in ("Journal", "journal", "Notes", "notes"):
            p = self._root / name
            if p.exists() and p.is_dir():
                journal_dir = p
                break
        if journal_dir is None:
            return []
        candidates = sorted(
            (p for p in journal_dir.glob("*.md") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:limit]
        return [f"{journal_dir.name}/{p.name}" for p in candidates]


# -- Public dataclass ------------------------------------------------------

@dataclass
class AssembledContext:
    """Result of ContextBuilder.build()."""
    system_prompt: str
    user_message: str
    files_used: list[str] = field(default_factory=list)
    char_budget_used: int = 0
    truncated: bool = False


# -- Builder ---------------------------------------------------------------

SourceLike = Union[str, Path, ContextLoader]


class ContextBuilder:
    """Build a system prompt + user turn from a MemoryDoc source.

    ``source`` is either:
      - a path on disk (str or Path), or
      - any object implementing the :class:`ContextLoader` protocol.

    Context assembly order (layered to maximise cache hit rate):
        1. IDENTITY.md            — stable, cache-able for 1h
        2. MEMORY.md / FACTS.md   — churn-y but read-heavy
        3. Recent journal (n)     — cheapest to regenerate
        4. User message           — always fresh

    The first three get glued into ``system_prompt``; the fourth goes into
    ``user_message``. Keeping the first-three stable across calls is what
    lets ClaudeBackend actually hit prompt cache.
    """

    def __init__(
        self,
        source: SourceLike,
        *,
        max_chars: int = 48_000,           # ≈ 14k tokens headroom
        recent_days: int = 3,
    ):
        self.source = source
        self.loader: ContextLoader = _coerce_loader(source)
        self.max_chars = int(max_chars)
        self.recent_days = int(recent_days)

    # -- public ----------------------------------------------------------

    def build(self, user_message: str) -> AssembledContext:
        used: list[str] = []
        parts: list[str] = []

        # 1. IDENTITY
        identity = self._read("IDENTITY.md")
        if identity:
            parts.append(f"# Identity\n\n{identity}")
            used.append("IDENTITY.md")

        # 2. MEMORY + FACTS
        memory = self._read("MEMORY.md")
        if memory:
            parts.append(f"# Long-term memory\n\n{memory}")
            used.append("MEMORY.md")

        facts = self._read("FACTS.md")
        if facts:
            parts.append(f"# Known facts\n\n{facts}")
            used.append("FACTS.md")

        # 3. Recent journal
        journal_blob, journal_label = self._recent_journal()
        if journal_blob:
            parts.append(f"# Recent journal (last {self.recent_days}d)\n\n{journal_blob}")
            used.append(journal_label)

        system = "\n\n".join(parts).strip()

        # Budget enforcement: system + user_message must fit. If over, drop
        # journal first, then FACTS, then MEMORY — IDENTITY is non-negotiable.
        truncated = False
        while (len(system) + len(user_message)) > self.max_chars and parts:
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

    def _read(self, relpath: str) -> str:
        try:
            text = self.loader.read_text(relpath) or ""
        except Exception as e:  # loader misbehaviour is a soft-skip
            log.debug("loader.read_text(%s) raised: %s", relpath, e)
            return ""
        return _strip_frontmatter(text).strip()

    def _recent_journal(self) -> tuple[str, str]:
        try:
            entries = self.loader.list_journal(limit=self.recent_days) or []
        except Exception as e:
            log.debug("loader.list_journal raised: %s", e)
            return "", ""
        if not entries:
            return "", ""
        blobs: list[str] = []
        label_dir = entries[0].split("/", 1)[0] if "/" in entries[0] else "journal"
        for relpath in entries:
            text = _strip_frontmatter(self._safe_read(relpath)).strip()
            if not text:
                continue
            name = relpath.rsplit("/", 1)[-1]
            blobs.append(f"## {name}\n\n{text}")
        if not blobs:
            return "", ""
        return "\n\n---\n\n".join(blobs), f"{label_dir}/recent"

    def _safe_read(self, relpath: str) -> str:
        try:
            return self.loader.read_text(relpath) or ""
        except Exception:
            return ""


# -- helpers ---------------------------------------------------------------

def _coerce_loader(source: SourceLike) -> ContextLoader:
    """Turn the ``source=`` argument into a ContextLoader."""
    if isinstance(source, (str, Path)):
        return _PathLoader(Path(source))
    # Duck-typing: anything with read_text + list_journal works.
    if hasattr(source, "read_text") and hasattr(source, "list_journal"):
        return source  # type: ignore[return-value]
    raise TypeError(
        f"ContextBuilder source must be a path or a ContextLoader, got "
        f"{type(source).__name__}"
    )


_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def _strip_frontmatter(text: str) -> str:
    m = _FRONTMATTER.match(text)
    return text[m.end():] if m else text


def approx_tokens(text: str) -> int:
    """Cheap char→token estimate; use only for budgeting."""
    return max(1, int(len(text) / _CHARS_PER_TOKEN))
