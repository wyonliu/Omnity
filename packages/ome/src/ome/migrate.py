"""OmeMigrate — one-shot importer from competing AI persona stores into Ome.

Supported sources (``--from``):

    chatgpt         OpenAI data-export ``conversations.json``
    claude          Anthropic Claude Projects export (``.zip`` or folder)
    hermes          Hermes Agent memory directory (``*.json`` per memory)
    jsonl           Generic JSONL: ``{"role", "content", "ts"?}``
    mindos          Folder produced by ``mindos dump`` (IDENTITY.md ...)
    chat            Plaintext / WeChat chat log (single file)

Every adapter normalises its input to a stream of :class:`MigrationRecord`
objects, which are then committed via :meth:`Ome.remember` — so the user's
Mindos learns from the imported history the same way as from live chat.

Design rules kept deliberately simple:
    * Batched, idempotent-ish: each migration writes a provenance memory so
      repeat imports are easy to spot (``source="migrate:<src>"``).
    * Fail-soft per record: a bad message must not abort the whole run.
    * No LLM dependency — parsers are pure Python, offline-capable.
"""

from __future__ import annotations

import json
import logging
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterable, Iterator, Optional

if TYPE_CHECKING:
    from ome.core import Ome

log = logging.getLogger("ome.migrate")


# ---------------------------------------------------------------------------
# Normalised record + report
# ---------------------------------------------------------------------------

@dataclass
class MigrationRecord:
    """A single normalised piece of history to commit."""
    role: str                    # "user" | "assistant" | "system" | "note"
    content: str
    timestamp: Optional[float] = None
    conversation_id: str = ""
    source_label: str = ""

    def as_commit(self) -> str:
        return f"{self.role}: {self.content.strip()}"


@dataclass
class MigrationReport:
    source: str
    total_records: int = 0
    committed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    conversations: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "total_records": self.total_records,
            "committed": self.committed,
            "skipped": self.skipped,
            "conversations": self.conversations,
            "errors": list(self.errors),
        }


SUPPORTED = ("chatgpt", "claude", "hermes", "jsonl", "mindos", "chat")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def migrate(ome: "Ome", source: str, path: str | Path,
            *, dry_run: bool = False, batch_size: int = 25,
            max_records: int = 0) -> MigrationReport:
    """Import history from ``path`` into ``ome``.

    Args:
        ome:        a live :class:`ome.core.Ome` instance.
        source:     one of :data:`SUPPORTED`.
        path:       file or directory to read.
        dry_run:    parse only, commit nothing — useful for previewing.
        batch_size: bundle this many records per ``soul.commit`` call
                    (reduces embedding / reflection overhead).
        max_records: if > 0, stop after this many records (cheap sampling).
    """
    source = source.lower().strip()
    if source not in SUPPORTED:
        raise ValueError(
            f"Unknown migration source {source!r}. "
            f"Supported: {', '.join(SUPPORTED)}"
        )
    path = Path(path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Migration source not found: {path}")

    report = MigrationReport(source=source)

    # mindos-dump is a special case: delegate to memorydoc.import_md and bail
    if source == "mindos":
        from mindos.memorydoc import import_md as _import_md
        if dry_run:
            report.total_records = 1
            return report
        r = _import_md(ome.soul, path, merge_mode="upsert")
        report.total_records = (r.get("memories_imported", 0)
                                + r.get("facts_imported", 0)
                                + r.get("triples_imported", 0))
        report.committed = report.total_records
        report.conversations = 1
        report.errors.extend(r.get("errors", []))
        try:
            ome.soul.store.record_evo(
                event_type="migrated", layer="L0",
                summary=f"imported mindos snapshot from {path}",
                details=report.to_dict(),
            )
        except Exception as e:  # pragma: no cover
            log.debug("evo_log record failed: %s", e)
        return report

    adapter = _ADAPTERS[source]
    records_iter = adapter(path, report)

    buffer: list[MigrationRecord] = []
    seen_convs: set[str] = set()

    def _flush():
        if not buffer:
            return
        conversation = "\n".join(r.as_commit() for r in buffer)
        if dry_run:
            report.committed += len(buffer)
        else:
            try:
                ome.soul.commit(conversation,
                                source=f"migrate:{source}")
                report.committed += len(buffer)
            except Exception as e:  # pragma: no cover
                report.errors.append(f"commit failed: {e}")
        buffer.clear()

    for rec in records_iter:
        report.total_records += 1
        if rec.conversation_id:
            seen_convs.add(rec.conversation_id)
        if not rec.content or not rec.content.strip():
            report.skipped += 1
            continue
        buffer.append(rec)
        if len(buffer) >= batch_size:
            _flush()
        if max_records and report.committed + len(buffer) >= max_records:
            _flush()
            break
    _flush()

    report.conversations = len(seen_convs)

    # Provenance breadcrumb so future runs / dashboards can see it
    if not dry_run and report.committed:
        try:
            ome.soul.store.record_evo(
                event_type="migrated", layer="L0",
                summary=(f"imported {report.committed} records from "
                         f"{source} ({report.conversations} conversations)"),
                details=report.to_dict(),
            )
        except Exception as e:  # pragma: no cover
            log.debug("evo_log record failed: %s", e)

    return report


# ---------------------------------------------------------------------------
# Adapters
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_chatgpt(path: Path, report: MigrationReport) -> Iterator[MigrationRecord]:
    """Parse OpenAI data-export ``conversations.json``.

    Each item has a ``mapping`` of node_id → message, chained via parent links.
    Messages of content_type ``text`` carry ``parts: [str, ...]``.
    """
    if path.is_dir():
        path = path / "conversations.json"
    try:
        convs = _read_json(path)
    except Exception as e:
        report.errors.append(f"chatgpt: cannot parse {path}: {e}")
        return

    if not isinstance(convs, list):
        report.errors.append("chatgpt: expected a top-level array")
        return

    for conv in convs:
        cid = str(conv.get("id") or conv.get("conversation_id") or "")
        mapping = conv.get("mapping") or {}
        # Walk in create-time order
        nodes = list(mapping.values())
        nodes.sort(key=lambda n: (n.get("message") or {}).get("create_time") or 0)
        for n in nodes:
            msg = n.get("message") or {}
            author = (msg.get("author") or {}).get("role") or ""
            if author not in ("user", "assistant", "system"):
                continue
            content = msg.get("content") or {}
            ctype = content.get("content_type") or "text"
            if ctype != "text":
                continue
            parts = content.get("parts") or []
            text = "\n".join(p for p in parts if isinstance(p, str) and p)
            if not text:
                continue
            yield MigrationRecord(
                role=author, content=text,
                timestamp=msg.get("create_time"),
                conversation_id=cid, source_label="chatgpt",
            )


def _iter_claude(path: Path, report: MigrationReport) -> Iterator[MigrationRecord]:
    """Parse Anthropic Claude Projects export.

    Export is a folder (or zip) containing ``conversations.json`` with items
    like ``{"uuid", "name", "chat_messages": [{"sender", "text", ...}]}``.
    """
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            if "conversations.json" not in zf.namelist():
                report.errors.append("claude: zip missing conversations.json")
                return
            raw = zf.read("conversations.json").decode("utf-8")
    else:
        root = path if path.is_dir() else path.parent
        cjson = root / "conversations.json" if path.is_dir() else path
        if not cjson.exists():
            report.errors.append(f"claude: no conversations.json at {cjson}")
            return
        raw = cjson.read_text(encoding="utf-8")
    try:
        convs = json.loads(raw)
    except Exception as e:
        report.errors.append(f"claude: JSON parse failed: {e}")
        return

    if isinstance(convs, dict):
        convs = [convs]

    for conv in convs:
        cid = str(conv.get("uuid") or conv.get("id") or "")
        msgs = (conv.get("chat_messages") or conv.get("messages")
                or conv.get("chat_messages_list") or [])
        for m in msgs:
            sender = (m.get("sender") or m.get("role") or "").lower()
            if sender in ("human", "user"):
                role = "user"
            elif sender in ("assistant", "ai", "claude"):
                role = "assistant"
            else:
                continue
            text = (m.get("text") or m.get("content")
                    or m.get("message") or "")
            if isinstance(text, list):
                # Some exports use content blocks
                text = "\n".join(b.get("text", "") if isinstance(b, dict) else str(b)
                                 for b in text)
            if not text:
                continue
            yield MigrationRecord(
                role=role, content=str(text),
                timestamp=_parse_ts(m.get("created_at") or m.get("timestamp")),
                conversation_id=cid, source_label="claude",
            )


def _iter_hermes(path: Path, report: MigrationReport) -> Iterator[MigrationRecord]:
    """Parse a Hermes Agent memory directory.

    Hermes stores each memory as a small JSON file with common fields:
        {"id", "content"|"text", "kind"|"type", "created_at"|"ts"}
    Unknown shapes are tolerated — we grab the first plausible text field.
    """
    if path.is_file():
        files = [path]
    else:
        files = sorted(path.rglob("*.json"))
    for f in files:
        try:
            data = _read_json(f)
        except Exception as e:
            report.errors.append(f"hermes: {f.name}: {e}")
            continue

        if isinstance(data, list):
            items = data
        else:
            items = [data]

        for item in items:
            if not isinstance(item, dict):
                continue
            text = (item.get("content") or item.get("text")
                    or item.get("body") or item.get("message") or "")
            if not text:
                continue
            kind = item.get("kind") or item.get("type") or "note"
            role = "user" if kind in ("user", "input", "question") else "note"
            yield MigrationRecord(
                role=role, content=str(text),
                timestamp=_parse_ts(item.get("created_at") or item.get("ts")),
                conversation_id=str(item.get("session")
                                    or item.get("conversation_id") or f.stem),
                source_label="hermes",
            )


def _iter_jsonl(path: Path, report: MigrationReport) -> Iterator[MigrationRecord]:
    """Parse a generic JSONL with one object per line."""
    if path.is_dir():
        report.errors.append("jsonl: point at a file, not a directory")
        return
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError as e:
            report.errors.append(f"jsonl line {i}: {e}")
            continue
        role = (obj.get("role") or obj.get("speaker") or "user").lower()
        if role in ("human",):
            role = "user"
        text = (obj.get("content") or obj.get("text") or obj.get("message")
                or "")
        if not text:
            continue
        yield MigrationRecord(
            role=role, content=str(text),
            timestamp=_parse_ts(obj.get("ts") or obj.get("created_at")),
            conversation_id=str(obj.get("conversation_id") or ""),
            source_label="jsonl",
        )


def _iter_chat(path: Path, report: MigrationReport) -> Iterator[MigrationRecord]:
    """Parse a plaintext / WeChat chat log using Ome's existing parser."""
    from ome.life.persona import parse_chat_export
    if path.is_dir():
        report.errors.append("chat: point at a file, not a directory")
        return
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        report.errors.append(f"chat: cannot read {path}: {e}")
        return
    for msg in parse_chat_export(text):
        yield MigrationRecord(
            role="user", content=msg,
            conversation_id=path.stem, source_label="chat",
        )


_ADAPTERS: dict[str, Callable[[Path, MigrationReport],
                              Iterable[MigrationRecord]]] = {
    "chatgpt": _iter_chatgpt,
    "claude":  _iter_claude,
    "hermes":  _iter_hermes,
    "jsonl":   _iter_jsonl,
    "chat":    _iter_chat,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_ts(val: Any) -> Optional[float]:
    """Coerce ``val`` to a unix timestamp if possible."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        # Cheap ISO-8601 parse
        try:
            from datetime import datetime
            return datetime.fromisoformat(val.replace("Z", "+00:00")).timestamp()
        except Exception:
            return None
    return None
