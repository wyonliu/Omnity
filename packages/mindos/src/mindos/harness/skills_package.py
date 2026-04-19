"""Skills Registry — load agentskills.io / skills.sh packages into the harness.

A skills.sh package is a directory (or zip) containing ``SKILL.md`` at the
root. The header frontmatter names the skill; the body describes when/how
to use it. We already have :mod:`mindos.skillforge` for authoring skills
out of task traces — this module is the *reader* side, letting the harness
advertise any SKILL.md on disk as a tool.

Use this to ship pre-built skill packs alongside Mindos (`mindos/harness/skills/`)
or to install third-party packs (`~/.mindos/skills/`). The harness surfaces
them exactly like SkillForge-forged skills: name + description + input_schema
+ a handler that, absent a runner, returns a structured advertisement.

See: https://agentskills.io (the community packaging convention Anthropic
adopted in 2026-Q1 alongside Vercel's skills.sh).
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path
from typing import Any, Optional

from mindos.harness.tools import ToolRegistry
from mindos.skillforge import Skill

log = logging.getLogger("mindos.harness.skills_package")


def load_skill_package(
    registry: ToolRegistry,
    path: str | Path,
    *,
    handler: Optional[Any] = None,
    source_tag: str = "skills.sh",
) -> Optional[str]:
    """Load a single SKILL.md package (dir or .zip). Returns registered name."""
    p = Path(path)
    if not p.exists():
        log.warning("skill package missing: %s", p)
        return None
    text = _read_skill_md(p)
    if text is None:
        return None
    skill = Skill.from_markdown(text, skill_id=_default_id(p))
    name = registry.register(
        name=skill.name or skill.id,
        description=skill.description or "Shipped skill package.",
        input_schema=_skill_schema(),
        handler=handler or _default_handler(skill, p),
        source=f"{source_tag}:{skill.id}",
    ).name
    return name


def load_skill_dir(
    registry: ToolRegistry,
    directory: str | Path,
    *,
    source_tag: str = "skills.sh",
) -> int:
    """Load every SKILL.md under `directory`. Returns count registered."""
    root = Path(directory)
    if not root.exists():
        return 0
    count = 0
    for md in sorted(root.rglob("SKILL.md")):
        if load_skill_package(registry, md.parent, source_tag=source_tag):
            count += 1
    # Also pick up *.zip packages at the top level
    for zp in sorted(root.glob("*.zip")):
        if load_skill_package(registry, zp, source_tag=source_tag):
            count += 1
    return count


def shipped_skills_dir() -> Path:
    """Return the path to the skills bundled with this mindos install."""
    return Path(__file__).resolve().parent / "skills"


# --- internals ------------------------------------------------------------

def _read_skill_md(p: Path) -> Optional[str]:
    """Read SKILL.md from a dir or a .zip archive."""
    if p.is_dir():
        md = p / "SKILL.md"
        if not md.exists():
            log.warning("no SKILL.md in %s", p)
            return None
        return md.read_text(encoding="utf-8")
    if p.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(p) as zf:
                for name in zf.namelist():
                    if name.endswith("SKILL.md"):
                        return zf.read(name).decode("utf-8")
        except zipfile.BadZipFile as e:
            log.warning("bad skill zip %s: %s", p, e)
        return None
    if p.name == "SKILL.md":
        return p.read_text(encoding="utf-8")
    log.warning("not a skill package: %s", p)
    return None


def _default_id(p: Path) -> str:
    if p.is_dir():
        return p.name
    if p.suffix.lower() == ".zip":
        return p.stem
    return p.parent.name


def _skill_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "input": {
                "type": "string",
                "description": "Freeform input forwarded to the skill.",
            },
        },
        "required": [],
    }


def _default_handler(skill: Skill, origin: Path):
    """Advertisement-only handler. Matches SkillForge tools.py behavior.

    Running a skill's steps requires either a SkillForge `run_skill` method
    or a user-supplied runner — we deliberately don't auto-execute arbitrary
    markdown steps.
    """
    def _run(arguments: dict) -> dict:
        return {
            "skill_id": skill.id,
            "skill_name": skill.name,
            "origin": str(origin),
            "when_to_use": skill.when_to_use,
            "steps": skill.steps[:10],
            "notes": skill.notes[:5],
            "invoked_with": arguments,
            "note": ("advertisement only — execute the steps yourself, "
                     "or wire a run_skill() into the skillforge."),
        }
    return _run
