"""OmeBench corpus loader.

A corpus is a directory with any of these subdirectories:

    interviews/*.md        → each file ingested as one "episode"-type memory
    journal/*.md           → each file ingested as one "episode" memory
    facts/*.md             → each bullet parsed as one "fact" memory
    meta.json              → optional {"name": "...", "description": "..."}

Nothing fancier. We deliberately keep this simple so benchmark runs are
reproducible from a single ``--corpus`` flag.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass
class CorpusItem:
    content: str
    type: str
    source: str


@dataclass
class Corpus:
    name: str = ""
    description: str = ""
    items: list[CorpusItem] = field(default_factory=list)

    def counts_by_type(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for i in self.items:
            out[i.type] = out.get(i.type, 0) + 1
        return out


def load_corpus(path: str | Path) -> Corpus:
    root = Path(path)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"corpus dir not found: {root}")
    name = root.name
    description = ""
    meta = root / "meta.json"
    if meta.exists():
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
            name = str(data.get("name") or name)
            description = str(data.get("description") or "")
        except json.JSONDecodeError:
            pass

    items: list[CorpusItem] = []
    for interview in sorted((root / "interviews").glob("*.md")
                            if (root / "interviews").exists() else []):
        items.append(CorpusItem(
            content=_strip_frontmatter(interview.read_text(encoding="utf-8")).strip(),
            type="episode",
            source=f"interview:{interview.stem}",
        ))
    for j in sorted((root / "journal").glob("*.md")
                    if (root / "journal").exists() else []):
        items.append(CorpusItem(
            content=_strip_frontmatter(j.read_text(encoding="utf-8")).strip(),
            type="episode",
            source=f"journal:{j.stem}",
        ))
    facts_dir = root / "facts"
    if facts_dir.exists():
        for f in sorted(facts_dir.glob("*.md")):
            items.extend(_parse_facts(f))

    return Corpus(name=name, description=description, items=items)


_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def _strip_frontmatter(text: str) -> str:
    m = _FRONTMATTER.match(text)
    return text[m.end():] if m else text


def _parse_facts(path: Path) -> Iterable[CorpusItem]:
    """Take lines like `- fact text` and turn each into a fact memory."""
    text = _strip_frontmatter(path.read_text(encoding="utf-8"))
    for i, line in enumerate(text.splitlines()):
        stripped = line.strip()
        if stripped.startswith("- "):
            yield CorpusItem(
                content=stripped[2:].strip(),
                type="fact",
                source=f"facts:{path.stem}#{i+1}",
            )
