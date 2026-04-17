"""MemoryDoc — export/import the five-layer brain as human-readable markdown.

Motivation
----------
Users can `git commit` their AI's personality. Share their Ome as a .omeseed
folder. Audit what their AI has learned. The key cultural point: **you can see
everything your AI remembers, in plain markdown.**

Files produced by :func:`export_md`
-----------------------------------
- ``IDENTITY.md``  — L3/L4 personality (name, traits, style, values,
  boundaries, catchphrases, capabilities).
- ``MEMORY.md``    — episodes / narratives / high-value memories.
- ``FACTS.md``     — facts / preferences / relations grouped by type.
- ``SOUL.md``      — constitution rules + personality evolution timeline.
- ``KG.json``      — knowledge graph triples (structured, machine-only).

Round-trip
----------
:func:`import_md` reads these files and restores state into a Mindos. IDs and
timestamps are preserved via trailing HTML comment metadata, so exporting to
a git repo and re-importing is lossless for the pieces we persist.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional

import yaml

from mindos.store import Memory, Triple

EXPORT_VERSION = 1

# Types that land in FACTS.md (flat bullet lists grouped by type)
_FACT_TYPES = {"fact", "preference", "relation"}
# Types that land in MEMORY.md (narrative paragraphs)
_NARRATIVE_TYPES = {"episode", "skill", "narrative", "insight"}

_META_RE = re.compile(
    r"<!--\s*(?P<kv>(?:[a-z_]+:[^ \n]+\s*)+)\s*-->\s*$"
)


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------

def _frontmatter(file_type: str, version_str: str, extra: dict | None = None) -> str:
    """Build a YAML frontmatter block."""
    fm: dict[str, Any] = {
        "mindos_version": version_str,
        "export_version": EXPORT_VERSION,
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "file_type": file_type,
    }
    if extra:
        fm.update(extra)
    return "---\n" + yaml.dump(fm, allow_unicode=True, sort_keys=False) + "---\n"


def _strip_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Empty dict if no frontmatter."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    fm_text = text[4:end]
    body = text[end + 5:]
    try:
        fm = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, body


def _meta_comment(**kv: Any) -> str:
    """Render a trailing HTML comment capturing metadata for round-trip.

    Example: ``_meta_comment(id="abc123", source="claude", decay=0.95)``
    """
    parts = []
    for k, v in kv.items():
        if v is None or v == "":
            continue
        # Keep values terse — no spaces, no quotes
        s = str(v).replace("\n", " ").replace(" ", "_")
        parts.append(f"{k}:{s}")
    return "<!-- " + " ".join(parts) + " -->" if parts else ""


def _parse_meta_comment(line: str) -> dict[str, str]:
    """Extract the ``key:value`` pairs from a trailing HTML comment."""
    m = _META_RE.search(line)
    if not m:
        return {}
    result: dict[str, str] = {}
    for pair in m.group("kv").strip().split():
        if ":" in pair:
            k, v = pair.split(":", 1)
            result[k] = v.replace("_", " ")
    return result


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_md(mindos: Any, out_dir: str | Path,
              max_memories: int = 500,
              min_confidence: float = 0.0) -> dict[str, Any]:
    """Export the full five-layer brain to markdown + one JSON file.

    Args:
        mindos: A :class:`~mindos.core.Mindos` instance.
        out_dir: Target directory (created if missing).
        max_memories: Cap memories per file (default 500 — enough for humans,
            small enough to git-diff).
        min_confidence: Drop memories below this confidence (default 0 = keep
            everything).

    Returns:
        Dict with ``files`` list and counts per file.
    """
    from mindos import __version__ as _v

    out = Path(out_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True)

    files_written: list[str] = []
    counts: dict[str, int] = {}

    # IDENTITY.md --------------------------------------------------------
    identity_path = out / "IDENTITY.md"
    identity_path.write_text(_render_identity(mindos, _v), encoding="utf-8")
    files_written.append("IDENTITY.md")

    # MEMORY.md + FACTS.md ----------------------------------------------
    all_mems = mindos.store.list_recent(limit=max_memories)
    narrative = [m for m in all_mems
                 if m.type in _NARRATIVE_TYPES and m.confidence >= min_confidence]
    facts = [m for m in all_mems
             if m.type in _FACT_TYPES and m.confidence >= min_confidence]
    other = [m for m in all_mems
             if m.type not in _NARRATIVE_TYPES and m.type not in _FACT_TYPES
             and m.confidence >= min_confidence]
    # "other" types join MEMORY.md by default so nothing is silently dropped
    narrative.extend(other)

    (out / "MEMORY.md").write_text(
        _render_memory(narrative, _v), encoding="utf-8"
    )
    files_written.append("MEMORY.md")
    counts["memories"] = len(narrative)

    (out / "FACTS.md").write_text(
        _render_facts(facts, _v), encoding="utf-8"
    )
    files_written.append("FACTS.md")
    counts["facts"] = len(facts)

    # SOUL.md ------------------------------------------------------------
    (out / "SOUL.md").write_text(_render_soul(mindos, _v), encoding="utf-8")
    files_written.append("SOUL.md")

    # KG.json ------------------------------------------------------------
    triples = mindos.store.triples()
    kg_data = {
        "mindos_version": _v,
        "export_version": EXPORT_VERSION,
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "triples": [
            {"subject": t.subject, "predicate": t.predicate, "object": t.object,
             "source": t.source, "confidence": t.confidence}
            for t in triples
        ],
    }
    (out / "KG.json").write_text(
        json.dumps(kg_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    files_written.append("KG.json")
    counts["triples"] = len(triples)

    return {
        "out_dir": str(out),
        "files": files_written,
        **counts,
    }


def _render_identity(mindos: Any, version_str: str) -> str:
    ident = mindos.identity
    p = ident.get("personality", {})
    lines = [_frontmatter("identity", version_str)]
    lines.append(f"# {ident.get('name', 'User')}\n")
    created = ident.get("created_at", "")
    updated = ident.get("updated_at", "")
    if created:
        lines.append(f"**Created:** {created}  ")
    if updated:
        lines.append(f"**Updated:** {updated}\n")

    def _section(title: str, items: Iterable[str]) -> None:
        items = [x for x in items if x]
        if not items:
            return
        lines.append(f"\n## {title}")
        for it in items:
            lines.append(f"- {it}")

    _section("Traits", p.get("traits", []))
    style = p.get("style", "")
    if style:
        lines.append("\n## Style")
        lines.append(style)
    _section("Values", p.get("values", []))
    _section("Boundaries", p.get("boundaries", []))
    _section("Catchphrases", p.get("catchphrases", []))
    _section("Emoji habits", p.get("emoji_habits", []))
    _section("Anchors", p.get("anchors", []))

    caps = ident.get("capabilities", [])
    if caps:
        lines.append("\n## Capabilities")
        for c in caps:
            if isinstance(c, dict):
                lines.append(
                    f"- {c.get('domain', '')} ({c.get('level', '')})"
                )
            else:
                lines.append(f"- {c}")

    return "\n".join(lines) + "\n"


def _render_memory(memories: list[Memory], version_str: str) -> str:
    lines = [_frontmatter("memory", version_str, {"count": len(memories)})]
    if not memories:
        lines.append("\n*(no memories yet)*\n")
        return "\n".join(lines)
    # Sort descending by created_at so the latest is at top
    memories = sorted(memories, key=lambda m: m.created_at or 0, reverse=True)
    for m in memories:
        date = time.strftime("%Y-%m-%d", time.localtime(m.created_at or time.time()))
        lines.append(f"\n## {date} · {m.type} · conf={m.confidence:.2f}\n")
        lines.append(m.content.strip())
        meta = _meta_comment(
            id=m.id, source=m.source, decay=round(m.decay_weight, 3),
            accessed=m.access_count,
        )
        if meta:
            lines.append("")
            lines.append(meta)
    return "\n".join(lines) + "\n"


def _render_facts(memories: list[Memory], version_str: str) -> str:
    lines = [_frontmatter("facts", version_str, {"count": len(memories)})]
    by_type: dict[str, list[Memory]] = {}
    for m in memories:
        by_type.setdefault(m.type, []).append(m)
    # Preferred order — preference / fact / relation / other
    preferred = ["preference", "fact", "relation"]
    ordered_types = [t for t in preferred if t in by_type]
    ordered_types.extend(t for t in sorted(by_type) if t not in preferred)
    if not ordered_types:
        lines.append("\n*(no facts yet)*\n")
        return "\n".join(lines)
    for t in ordered_types:
        lines.append(f"\n## {t.capitalize()}s" if not t.endswith("s") else f"\n## {t.capitalize()}")
        for m in by_type[t]:
            content = m.content.strip().replace("\n", " ")
            meta = _meta_comment(
                id=m.id, source=m.source, decay=round(m.decay_weight, 3),
                conf=round(m.confidence, 2),
            )
            lines.append(f"- {content}  {meta}".rstrip())
    return "\n".join(lines) + "\n"


def _render_soul(mindos: Any, version_str: str) -> str:
    lines = [_frontmatter("soul", version_str)]
    lines.append("# Soul — constitution & evolution\n")

    # Constitution
    constitution = getattr(mindos.layers.l4, "constitution", None)
    rules = getattr(constitution, "rules", []) if constitution else []
    lines.append("## Constitution")
    if not rules:
        lines.append("*(no rules set — defaults apply)*")
    else:
        for r in rules:
            params = ", ".join(f"{k}={v}" for k, v in (r.params or {}).items())
            lines.append(f"- **{r.id}** [{r.type}] `{r.target}`  {params}".rstrip())

    # Personality timeline
    timeline = mindos.store.personality_timeline()
    lines.append("\n## Evolution timeline")
    if not timeline:
        lines.append("*(no history yet)*")
    else:
        # Most recent first, cap at 50
        for row in reversed(timeline[-50:]):
            date = time.strftime("%Y-%m-%d %H:%M",
                                 time.localtime(row.get("created_at") or time.time()))
            trigger = row.get("trigger") or "?"
            lines.append(f"\n### {date} — {trigger}")
            diff = row.get("diff") or ""
            if diff:
                lines.append(diff.strip())
            snapshot = row.get("snapshot") or ""
            try:
                snap = json.loads(snapshot) if isinstance(snapshot, str) else snapshot
                traits = snap.get("traits") or []
                if traits:
                    lines.append(f"- traits: {', '.join(traits)}")
                style = snap.get("style") or ""
                if style:
                    lines.append(f"- style: {style}")
            except (json.JSONDecodeError, AttributeError):
                pass
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

@dataclass
class ImportReport:
    identity_updated: bool = False
    memories_imported: int = 0
    facts_imported: int = 0
    triples_imported: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity_updated": self.identity_updated,
            "memories_imported": self.memories_imported,
            "facts_imported": self.facts_imported,
            "triples_imported": self.triples_imported,
            "errors": self.errors,
        }


def import_md(mindos: Any, in_dir: str | Path,
              merge_mode: str = "upsert") -> dict[str, Any]:
    """Import markdown + KG.json back into a Mindos.

    Args:
        mindos: Target :class:`~mindos.core.Mindos` instance.
        in_dir: Directory produced by :func:`export_md`. Missing files are
            skipped (partial imports are allowed).
        merge_mode:
            - ``"upsert"`` (default): insert or replace memories by ID.
            - ``"append"``: always generate fresh IDs (may duplicate).

    Returns:
        An :class:`ImportReport` as a dict.
    """
    src = Path(in_dir).expanduser()
    if not src.exists():
        raise FileNotFoundError(f"Import directory not found: {src}")
    if merge_mode not in ("upsert", "append"):
        raise ValueError(f"merge_mode must be 'upsert' or 'append', got {merge_mode!r}")

    report = ImportReport()

    # IDENTITY.md
    ident_path = src / "IDENTITY.md"
    if ident_path.exists():
        try:
            _import_identity(mindos, ident_path.read_text(encoding="utf-8"))
            report.identity_updated = True
        except Exception as e:
            report.errors.append(f"IDENTITY.md: {e}")

    # MEMORY.md
    mem_path = src / "MEMORY.md"
    if mem_path.exists():
        try:
            n = _import_memory(mindos, mem_path.read_text(encoding="utf-8"), merge_mode)
            report.memories_imported = n
        except Exception as e:
            report.errors.append(f"MEMORY.md: {e}")

    # FACTS.md
    facts_path = src / "FACTS.md"
    if facts_path.exists():
        try:
            n = _import_facts(mindos, facts_path.read_text(encoding="utf-8"), merge_mode)
            report.facts_imported = n
        except Exception as e:
            report.errors.append(f"FACTS.md: {e}")

    # KG.json
    kg_path = src / "KG.json"
    if kg_path.exists():
        try:
            data = json.loads(kg_path.read_text(encoding="utf-8"))
            for t in data.get("triples", []):
                mindos.store.add_triple(Triple(
                    subject=t["subject"], predicate=t["predicate"], object=t["object"],
                    source=t.get("source", "import"),
                    confidence=float(t.get("confidence", 1.0)),
                ))
                report.triples_imported += 1
        except Exception as e:
            report.errors.append(f"KG.json: {e}")

    return report.to_dict()


# -- identity import --------------------------------------------------------

_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$")


def _import_identity(mindos: Any, text: str) -> None:
    _, body = _strip_frontmatter(text)
    lines = body.splitlines()

    # First H1 line is the name
    name: Optional[str] = None
    for line in lines:
        if line.startswith("# "):
            name = line[2:].strip()
            break

    sections: dict[str, list[str]] = {}
    current: Optional[str] = None
    style_lines: list[str] = []
    capturing_style = False

    for line in lines:
        h = _HEADING_RE.match(line)
        if h:
            title = h.group(1).strip().lower().rstrip("s")  # 'traits' → 'trait'
            current = title
            capturing_style = current == "style"
            sections.setdefault(current, [])
            continue
        if capturing_style and line.strip() and not line.startswith("#"):
            style_lines.append(line.strip())
            continue
        if current and line.startswith("- "):
            sections[current].append(line[2:].strip())

    ident = mindos.identity
    if name:
        ident["name"] = name
    p = ident.setdefault("personality", {})
    if "trait" in sections:
        p["traits"] = sections["trait"]
    if style_lines:
        p["style"] = " ".join(style_lines).strip()
    if "value" in sections:
        p["values"] = sections["value"]
    if "boundarie" in sections:  # 'boundaries' stripped of trailing 's' → 'boundarie'
        p["boundaries"] = sections["boundarie"]
    if "catchphrase" in sections:
        p["catchphrases"] = sections["catchphrase"]
    if "emoji habit" in sections:
        p["emoji_habits"] = sections["emoji habit"]
    if "anchor" in sections:
        p["anchors"] = sections["anchor"]
    if "capabilitie" in sections:
        caps = []
        for c in sections["capabilitie"]:
            m = re.match(r"^(.+?)\s*\((.+?)\)\s*$", c)
            if m:
                caps.append({"domain": m.group(1).strip(), "level": m.group(2).strip()})
            else:
                caps.append(c)
        ident["capabilities"] = caps

    mindos.save_identity()
    mindos.reload_identity()


# -- memory / facts import --------------------------------------------------

def _parse_memory_block_header(header: str) -> tuple[Optional[str], Optional[float], Optional[str]]:
    """Parse a ``## 2026-04-15 · episode · conf=0.90`` heading.

    Returns (type, confidence, date_str). Each may be None if unparseable.
    """
    # Split on middle-dot or en-dash separator
    parts = [p.strip() for p in re.split(r"[·•]|\s-\s", header)]
    date_str = parts[0] if parts else None
    mem_type: Optional[str] = None
    conf: Optional[float] = None
    for part in parts[1:]:
        if part.startswith("conf="):
            try:
                conf = float(part.split("=", 1)[1])
            except ValueError:
                pass
        elif part and not mem_type:
            mem_type = part
    return mem_type, conf, date_str


def _import_memory(mindos: Any, text: str, merge_mode: str) -> int:
    _, body = _strip_frontmatter(text)
    # Split on H2 headings
    blocks = re.split(r"(?m)^## ", body)
    count = 0
    for block in blocks[1:]:  # blocks[0] is text before first heading
        lines = block.splitlines()
        if not lines:
            continue
        mem_type, conf, date_str = _parse_memory_block_header(lines[0])
        mem_type = mem_type or "episode"
        conf = conf if conf is not None else 0.8

        # Body = everything else, minus the trailing meta comment line
        body_lines = lines[1:]
        meta: dict[str, str] = {}
        while body_lines and body_lines[-1].strip() == "":
            body_lines.pop()
        if body_lines:
            maybe = _parse_meta_comment(body_lines[-1])
            if maybe:
                meta = maybe
                body_lines.pop()
            while body_lines and body_lines[-1].strip() == "":
                body_lines.pop()

        content = "\n".join(body_lines).strip()
        if not content:
            continue

        created_at: Optional[float] = None
        if date_str:
            try:
                created_at = time.mktime(time.strptime(date_str, "%Y-%m-%d"))
            except ValueError:
                pass

        mem_id = meta.get("id", "") if merge_mode == "upsert" else ""
        try:
            decay = float(meta.get("decay", 1.0))
        except ValueError:
            decay = 1.0
        try:
            accessed = int(meta.get("accessed", 0))
        except ValueError:
            accessed = 0

        mindos.store.add(Memory(
            id=mem_id, type=mem_type, content=content,
            source=meta.get("source", "import"),
            confidence=conf, created_at=created_at or 0.0,
            access_count=accessed, decay_weight=decay,
        ))
        count += 1
    return count


def _import_facts(mindos: Any, text: str, merge_mode: str) -> int:
    _, body = _strip_frontmatter(text)
    lines = body.splitlines()
    count = 0
    current_type = "fact"
    for line in lines:
        h = _HEADING_RE.match(line)
        if h:
            # 'Preferences' → 'preference', 'Facts' → 'fact', 'Relations' → 'relation'
            t = h.group(1).strip().lower().rstrip("s")
            current_type = t or "fact"
            continue
        if not line.startswith("- "):
            continue
        rest = line[2:]
        # Split content from trailing meta comment
        meta = _parse_meta_comment(rest)
        content = _META_RE.sub("", rest).strip()
        if not content:
            continue
        try:
            conf = float(meta.get("conf", 1.0))
        except ValueError:
            conf = 1.0
        try:
            decay = float(meta.get("decay", 1.0))
        except ValueError:
            decay = 1.0
        mem_id = meta.get("id", "") if merge_mode == "upsert" else ""
        mindos.store.add(Memory(
            id=mem_id, type=current_type, content=content,
            source=meta.get("source", "import"),
            confidence=conf, decay_weight=decay,
        ))
        count += 1
    return count
