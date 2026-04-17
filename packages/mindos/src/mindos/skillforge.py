"""SkillForge — distill task traces into reusable, portable skills.

When an Ome (or any agent on top of Mindos) completes a non-trivial task
successfully, SkillForge converts the tool-call trace into a ``SKILL.md`` —
a compact, human-readable playbook that Mindos (and other agentskills.io
compatible agents) can load for future tasks.

Storage layout
--------------
::

    <mindos_root>/skills/
        <skill-slug>/
            SKILL.md
            scripts/     (optional, reserved for future use)

Each skill is also indexed as a ``type="skill"`` memory so that :meth:`recall`
and :meth:`hydrate` surface it alongside regular memories.

Compatible with the `agentskills.io <https://agentskills.io>`_ packaging
convention — skills can be zipped up (``<slug>.zip`` containing ``SKILL.md``
at the root) and shared across agents.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from mindos.store import Memory

log = logging.getLogger("mindos.skillforge")

# --- thresholds (defaults — instances can override) ------------------------

DEFAULT_MIN_TOOL_CALLS = 5
DEFAULT_ALLOWED_OUTCOMES = frozenset({"success", "succeeded", "ok", "complete", "completed"})


# --- schema ---------------------------------------------------------------

@dataclass
class Skill:
    """In-memory representation of a skill."""
    id: str              # directory slug
    name: str            # human title
    description: str
    when_to_use: str = ""
    steps: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    trigger_keywords: list[str] = field(default_factory=list)
    author: str = "mindos-auto"
    version: int = 1
    created_at: str = ""
    source_trace_id: str = ""

    def to_markdown(self) -> str:
        fm: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "created_at": self.created_at,
        }
        if self.trigger_keywords:
            fm["trigger_keywords"] = self.trigger_keywords
        if self.source_trace_id:
            fm["source_trace_id"] = self.source_trace_id

        body = [f"# {self.name}\n"]
        if self.when_to_use:
            body.append("## When to use")
            body.append(self.when_to_use.strip() + "\n")
        if self.steps:
            body.append("## Steps")
            for i, s in enumerate(self.steps, 1):
                body.append(f"{i}. {s.strip()}")
            body.append("")
        if self.notes:
            body.append("## Notes")
            for n in self.notes:
                body.append(f"- {n.strip()}")
            body.append("")
        return (
            "---\n"
            + yaml.dump(fm, allow_unicode=True, sort_keys=False)
            + "---\n\n"
            + "\n".join(body)
        )

    @classmethod
    def from_markdown(cls, text: str, skill_id: Optional[str] = None) -> "Skill":
        fm: dict[str, Any] = {}
        body = text
        if text.startswith("---\n"):
            end = text.find("\n---\n", 4)
            if end != -1:
                try:
                    fm = yaml.safe_load(text[4:end]) or {}
                except yaml.YAMLError:
                    fm = {}
                body = text[end + 5:]

        name = fm.get("name") or ""
        description = fm.get("description") or ""

        # Pull sections from body
        when_to_use, steps, notes = _parse_skill_body(body)

        # Fallback: if no H1 inside body gave us name, derive from ID
        if not name:
            name = (skill_id or "unnamed").replace("-", " ").replace("_", " ").title()

        return cls(
            id=skill_id or _slugify(name),
            name=name,
            description=description,
            when_to_use=when_to_use,
            steps=steps,
            notes=notes,
            trigger_keywords=list(fm.get("trigger_keywords") or []),
            author=fm.get("author", "unknown"),
            version=int(fm.get("version", 1)),
            created_at=fm.get("created_at", ""),
            source_trace_id=fm.get("source_trace_id", ""),
        )


def _parse_skill_body(body: str) -> tuple[str, list[str], list[str]]:
    """Return (when_to_use, steps, notes) from skill body markdown."""
    when_to_use = ""
    steps: list[str] = []
    notes: list[str] = []
    current: Optional[str] = None
    buffer: list[str] = []

    def _flush():
        nonlocal when_to_use
        if current == "when_to_use":
            when_to_use = "\n".join(buffer).strip()
        buffer.clear()

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            _flush()
            title = stripped[3:].strip().lower()
            if title.startswith("when"):
                current = "when_to_use"
            elif title.startswith("step"):
                current = "steps"
            elif title.startswith("note"):
                current = "notes"
            else:
                current = None
            continue
        if current == "when_to_use":
            buffer.append(line)
        elif current == "steps":
            m = re.match(r"^\s*(?:\d+\.|[-*])\s+(.+)$", line)
            if m:
                steps.append(m.group(1).strip())
        elif current == "notes":
            m = re.match(r"^\s*[-*]\s+(.+)$", line)
            if m:
                notes.append(m.group(1).strip())
    _flush()
    return when_to_use, steps, notes


# --- helpers --------------------------------------------------------------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    s = _SLUG_RE.sub("-", text.strip().lower()).strip("-")
    return s or "skill"


def _trace_signature(trace: dict) -> str:
    """Stable hash of a trace for dedup. Shares the same slug → same skill."""
    goal = (trace.get("goal") or "").strip().lower()
    tools = tuple((c.get("tool") or "").lower() for c in trace.get("tool_calls") or [])
    key = goal + "|" + "|".join(tools)
    return _slugify(key)[:48] or uuid.uuid4().hex[:12]


# --- SkillForge -----------------------------------------------------------

class SkillForge:
    """Turn task traces into portable, recallable skills.

    Args:
        mindos: Parent :class:`~mindos.core.Mindos` instance.
        min_tool_calls: Skip traces with fewer tool calls than this (default 5).
        allowed_outcomes: Which outcome strings qualify for extraction
            (default: success / succeeded / ok / complete / completed).
        use_llm: If False, SkillForge uses only template extraction even when
            an LLM router is available. Useful for tests.
    """

    def __init__(self, mindos: Any, *,
                 min_tool_calls: int = DEFAULT_MIN_TOOL_CALLS,
                 allowed_outcomes: Optional[set[str]] = None,
                 use_llm: bool = True) -> None:
        self.mindos = mindos
        self.root: Path = Path(mindos.root) / "skills"
        self.root.mkdir(parents=True, exist_ok=True)
        self.min_tool_calls = min_tool_calls
        self.allowed_outcomes = allowed_outcomes or set(DEFAULT_ALLOWED_OUTCOMES)
        self.use_llm = use_llm

    # -- forging ---------------------------------------------------------

    def forge(self, trace: dict) -> Optional[str]:
        """Distill a task trace into a skill. Returns the ``skill_id`` or None.

        A trace is::

            {
                "goal": "Add JWT auth to /api/admin",
                "tool_calls": [{"tool": "Read", "input": {...}, "output": "..."},
                              ...],
                "outcome": "success" | "failure" | ...,
                "summary": "optional LLM-written summary",
            }
        """
        if not self._qualifies(trace):
            return None

        slug = _trace_signature(trace)
        existing = self.get(slug)
        if existing:
            # Bump version and overwrite — later run on the same pattern wins
            skill = self._extract(trace, slug=slug)
            skill.version = existing.version + 1
        else:
            skill = self._extract(trace, slug=slug)

        self._persist(skill)
        # Also index as a memory so `recall` / `hydrate` can surface it
        summary = skill.description or skill.name
        content = f"Skill: {skill.name} — {summary}"
        self.mindos.store.add(Memory(
            id=f"skill-{skill.id}", type="skill",
            content=content, source="skillforge",
            confidence=0.95, decay_weight=1.0,
            meta={"skill_id": skill.id, "keywords": skill.trigger_keywords},
        ))
        log.info("SkillForge forged skill: %s (v%d)", skill.id, skill.version)

        # EvoLog — persist a progressive history entry for this forge.
        store = getattr(self.mindos, "store", None)
        if store is not None and hasattr(store, "record_evo"):
            try:
                store.record_evo(
                    event_type="skill_forged", layer="L3",
                    summary=f"skill_forged: {skill.name} (v{skill.version})",
                    details={
                        "skill_id": skill.id, "version": skill.version,
                        "name": skill.name,
                        "trigger_keywords": list(skill.trigger_keywords),
                    },
                )
            except Exception as e:  # pragma: no cover — never break the forge
                log.debug("evo_log record failed: %s", e)

        return skill.id

    def _qualifies(self, trace: dict) -> bool:
        tool_calls = trace.get("tool_calls") or []
        if len(tool_calls) < self.min_tool_calls:
            return False
        outcome = str(trace.get("outcome") or "").strip().lower()
        if outcome not in self.allowed_outcomes:
            return False
        return True

    def _extract(self, trace: dict, slug: str) -> Skill:
        """Try LLM extraction; fall back to a deterministic template."""
        now = time.strftime("%Y-%m-%d")
        source_id = trace.get("trace_id") or uuid.uuid4().hex[:12]

        llm_skill = self._extract_with_llm(trace) if self.use_llm else None
        if llm_skill:
            llm_skill.id = slug
            llm_skill.created_at = now
            llm_skill.source_trace_id = source_id
            return llm_skill

        # Template fallback — always works, no LLM required
        return self._extract_template(trace, slug=slug, now=now, source_id=source_id)

    def _extract_with_llm(self, trace: dict) -> Optional[Skill]:
        router = getattr(self.mindos, "layers", None)
        router = getattr(router, "l2", None) if router else None
        router = getattr(router, "router", None) if router else None
        if router is None:
            return None

        trace_summary = _compact_trace(trace)
        system = (
            "You are a technical writer who turns successful task traces into "
            "reusable skill playbooks. Be concise and actionable. Use English."
        )
        user = (
            "Given this task trace, produce a JSON object with keys: "
            "name (5 words max), description (one sentence), when_to_use (1-2 sentences), "
            "steps (3-8 short imperative strings), notes (up to 4 lessons), "
            "trigger_keywords (3-6 lowercase words). Only JSON. No markdown fences.\n\n"
            f"Trace:\n{trace_summary}"
        )
        try:
            raw = router.call_llm(
                system=system, user=user, task="reasoning",
                max_tokens=800, json_mode=True, timeout=30.0,
            )
        except Exception as e:  # pragma: no cover — depends on external LLM
            log.debug("LLM extraction failed: %s", e)
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return Skill(
            id="",  # filled by caller
            name=str(data.get("name") or "").strip() or "Unnamed skill",
            description=str(data.get("description") or "").strip(),
            when_to_use=str(data.get("when_to_use") or "").strip(),
            steps=[str(s).strip() for s in (data.get("steps") or []) if s],
            notes=[str(n).strip() for n in (data.get("notes") or []) if n],
            trigger_keywords=[str(k).strip().lower()
                              for k in (data.get("trigger_keywords") or []) if k],
        )

    def _extract_template(self, trace: dict, *, slug: str, now: str,
                          source_id: str) -> Skill:
        goal = (trace.get("goal") or "").strip() or "Untitled task"
        tool_calls = trace.get("tool_calls") or []
        steps = []
        for call in tool_calls[:12]:
            tool = call.get("tool") or "?"
            inp = call.get("input") or {}
            focus = ""
            if isinstance(inp, dict):
                for key in ("file", "path", "file_path", "query", "command", "url"):
                    if inp.get(key):
                        focus = str(inp[key])[:80]
                        break
            steps.append(f"{tool}: {focus}" if focus else tool)

        # Trigger keywords: top few tool names + salient words from goal
        tool_names = sorted({(c.get("tool") or "").lower() for c in tool_calls if c.get("tool")})
        goal_words = [w.lower() for w in re.findall(r"[A-Za-z]{4,}", goal)]
        keywords = list(dict.fromkeys(tool_names + goal_words))[:6]

        return Skill(
            id=slug,
            name=goal[:80],
            description=(trace.get("summary") or goal)[:200],
            when_to_use="See source trace.",
            steps=steps,
            notes=[f"Auto-extracted from trace with {len(tool_calls)} tool calls."],
            trigger_keywords=keywords,
            author="mindos-auto",
            version=1,
            created_at=now,
            source_trace_id=source_id,
        )

    # -- persistence -----------------------------------------------------

    def _persist(self, skill: Skill) -> Path:
        skill_dir = self.root / skill.id
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(skill.to_markdown(), encoding="utf-8")
        return skill_dir

    # -- inventory -------------------------------------------------------

    def list(self) -> list[dict[str, Any]]:
        """Return lightweight metadata for every installed skill."""
        out: list[dict[str, Any]] = []
        if not self.root.exists():
            return out
        for child in sorted(self.root.iterdir()):
            if not child.is_dir():
                continue
            skill_md = child / "SKILL.md"
            if not skill_md.exists():
                continue
            skill = Skill.from_markdown(
                skill_md.read_text(encoding="utf-8"), skill_id=child.name
            )
            out.append({
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "version": skill.version,
                "trigger_keywords": skill.trigger_keywords,
                "path": str(skill_md),
            })
        return out

    def get(self, skill_id: str) -> Optional[Skill]:
        path = self.root / skill_id / "SKILL.md"
        if not path.exists():
            return None
        return Skill.from_markdown(path.read_text(encoding="utf-8"), skill_id=skill_id)

    def delete(self, skill_id: str) -> bool:
        skill_dir = self.root / skill_id
        if not skill_dir.exists():
            return False
        shutil.rmtree(skill_dir)
        # Remove the shadow memory too
        self.mindos.store.forget(f"Skill: ", mem_type="skill")  # coarse — safe fallback
        return True

    # -- import / export (agentskills.io compatible) ---------------------

    def import_skill(self, src: str | Path) -> str:
        """Install a skill from a local directory, SKILL.md file, or .zip file.

        Returns the installed ``skill_id``.
        """
        src_path = Path(src).expanduser()
        if not src_path.exists():
            raise FileNotFoundError(f"Skill source not found: {src_path}")

        # Case 1: bare SKILL.md file
        if src_path.is_file() and src_path.suffix == ".md":
            text = src_path.read_text(encoding="utf-8")
            skill = Skill.from_markdown(text, skill_id=_slugify(src_path.stem))
            if not skill.id:
                skill.id = _slugify(skill.name)
            self._persist(skill)
            return skill.id

        # Case 2: zip file containing SKILL.md at root (agentskills.io standard)
        if src_path.is_file() and src_path.suffix == ".zip":
            with zipfile.ZipFile(src_path) as zf:
                names = zf.namelist()
                skill_md_name = next(
                    (n for n in names if Path(n).name == "SKILL.md"), None
                )
                if not skill_md_name:
                    raise ValueError(f"Zip does not contain SKILL.md: {src_path}")
                text = zf.read(skill_md_name).decode("utf-8")
                skill = Skill.from_markdown(
                    text, skill_id=_slugify(src_path.stem)
                )
                target_dir = self.root / skill.id
                target_dir.mkdir(parents=True, exist_ok=True)
                (target_dir / "SKILL.md").write_text(
                    skill.to_markdown(), encoding="utf-8"
                )
                # Extract sibling scripts/ if present
                prefix = Path(skill_md_name).parent.as_posix().rstrip("/") + "/"
                for n in names:
                    if n.endswith("/"):
                        continue
                    if Path(n).name == "SKILL.md":
                        continue
                    rel = n[len(prefix):] if prefix != "/" and n.startswith(prefix) else n
                    if not rel or rel.startswith("/") or ".." in rel:
                        continue
                    out = target_dir / rel
                    out.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(n) as src_f, open(out, "wb") as dst_f:
                        dst_f.write(src_f.read())
                return skill.id

        # Case 3: directory containing SKILL.md
        if src_path.is_dir():
            skill_md = src_path / "SKILL.md"
            if not skill_md.exists():
                raise ValueError(f"Directory does not contain SKILL.md: {src_path}")
            text = skill_md.read_text(encoding="utf-8")
            skill = Skill.from_markdown(text, skill_id=_slugify(src_path.name))
            target_dir = self.root / skill.id
            if target_dir.exists():
                shutil.rmtree(target_dir)
            shutil.copytree(src_path, target_dir)
            # Normalize SKILL.md
            (target_dir / "SKILL.md").write_text(
                skill.to_markdown(), encoding="utf-8"
            )
            return skill.id

        raise ValueError(f"Unsupported skill source: {src_path}")

    def export_skill(self, skill_id: str, out_path: str | Path) -> Path:
        """Zip a skill to ``out_path`` (agentskills.io compatible)."""
        skill_dir = self.root / skill_id
        if not skill_dir.exists():
            raise FileNotFoundError(f"Skill not installed: {skill_id}")
        out = Path(out_path).expanduser()
        if out.is_dir():
            out = out / f"{skill_id}.zip"
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            for child in skill_dir.rglob("*"):
                if child.is_file():
                    zf.write(child, arcname=child.relative_to(skill_dir).as_posix())
        return out

    # -- retrieval -------------------------------------------------------

    def match(self, context: str, top_k: int = 3) -> list[Skill]:
        """Return the most relevant skills for a given context string.

        Simple token-overlap ranking over trigger_keywords + name + description.
        Good enough without LLM; upgraded by vector search if embeddings exist.
        """
        ctx_words = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", context)}
        if not ctx_words:
            return []
        scored: list[tuple[int, Skill]] = []
        for meta in self.list():
            skill = self.get(meta["id"])
            if not skill:
                continue
            skill_tokens = set()
            skill_tokens.update(w.lower() for w in skill.trigger_keywords)
            skill_tokens.update(re.findall(r"[A-Za-z]{3,}", skill.name.lower()))
            skill_tokens.update(re.findall(r"[A-Za-z]{3,}", skill.description.lower()))
            score = len(ctx_words & skill_tokens)
            if score > 0:
                scored.append((score, skill))
        scored.sort(key=lambda p: p[0], reverse=True)
        return [s for _, s in scored[:top_k]]


# --- helpers --------------------------------------------------------------

def _compact_trace(trace: dict, max_calls: int = 20, max_text: int = 200) -> str:
    """Render a trace into a compact text summary for LLM prompts."""
    lines = [f"Goal: {trace.get('goal', '')}"]
    outcome = trace.get("outcome", "")
    if outcome:
        lines.append(f"Outcome: {outcome}")
    summary = trace.get("summary")
    if summary:
        lines.append(f"Summary: {str(summary)[:max_text]}")
    lines.append("Tool calls:")
    for i, call in enumerate(trace.get("tool_calls") or [], 1):
        if i > max_calls:
            lines.append(f"  ... ({len(trace['tool_calls']) - max_calls} more)")
            break
        tool = call.get("tool", "?")
        inp = call.get("input") or {}
        out = call.get("output") or ""
        inp_str = json.dumps(inp, ensure_ascii=False)[:max_text] if isinstance(inp, dict) else str(inp)[:max_text]
        out_str = str(out)[:max_text]
        lines.append(f"  {i}. {tool}({inp_str}) → {out_str}")
    return "\n".join(lines)
