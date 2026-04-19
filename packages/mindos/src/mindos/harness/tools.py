"""ToolRegistry — expose SkillForge skills as harness tools.

A tool, from the harness's POV, is:
    - a name + description  (what the model sees in the tools schema)
    - an input_schema       (what arguments the model may pass)
    - a handler             (python function the harness invokes)

We build this registry from three sources:
    1. SkillForge skills (the authored, trajectory-distilled ones)
    2. Built-in harness tools (`recall`, `commit`, `write_file`, …) — W2+
    3. User-registered callables

For W1 we wire #1 and #3. Built-ins land in W2 along with the first skills.sh
package.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

log = logging.getLogger("mindos.harness.tools")


@dataclass
class ToolSpec:
    """Single tool advertised to the model."""
    name: str
    description: str
    input_schema: dict = field(default_factory=lambda: {
        "type": "object", "properties": {}, "required": [],
    })
    handler: Optional[Callable[[dict], Any]] = None
    source: str = ""  # "skill:<id>" | "builtin" | "user"

    def as_anthropic(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }


@dataclass
class ToolCall:
    """A tool invocation recorded during a harness run."""
    id: str
    name: str
    arguments: dict
    result: Any = None
    error: Optional[str] = None
    ms: int = 0


class ToolRegistry:
    """Collection of tools the harness may invoke."""

    def __init__(self) -> None:
        self._by_name: dict[str, ToolSpec] = {}

    # -- registration ----------------------------------------------------

    def register(
        self,
        name: str,
        description: str,
        *,
        handler: Optional[Callable[[dict], Any]] = None,
        input_schema: Optional[dict] = None,
        source: str = "user",
    ) -> ToolSpec:
        spec = ToolSpec(
            name=_safe_tool_name(name),
            description=description or "",
            input_schema=input_schema or {
                "type": "object", "properties": {}, "required": [],
            },
            handler=handler,
            source=source,
        )
        self._by_name[spec.name] = spec
        return spec

    def register_spec(self, spec: ToolSpec) -> None:
        self._by_name[_safe_tool_name(spec.name)] = spec

    def load_from_skillforge(self, skillforge: Any) -> int:
        """Register every skill from a SkillForge (or compatible) as a tool.

        SkillForge.list_skills() yields `Skill` objects with at minimum:
            .id, .name, .description, .trigger_keywords, .steps
        """
        lister = getattr(skillforge, "list_skills", None) or \
                 getattr(skillforge, "list", None)
        if lister is None:
            log.debug("skillforge has no list_skills/list; registry empty")
            return 0
        count = 0
        for skill in lister() or []:
            name = getattr(skill, "name", None) or getattr(skill, "id", None)
            if not name:
                continue
            desc = getattr(skill, "description", "") or _describe_skill(skill)
            schema = getattr(skill, "input_schema", None) or {
                "type": "object",
                "properties": {
                    "input": {
                        "type": "string",
                        "description": "Freeform input for this skill.",
                    },
                },
                "required": [],
            }
            self.register(
                name=name,
                description=desc,
                input_schema=schema,
                handler=_skill_handler(skillforge, skill),
                source=f"skill:{getattr(skill, 'id', name)}",
            )
            count += 1
        return count

    # -- access ----------------------------------------------------------

    def __contains__(self, name: str) -> bool:
        return _safe_tool_name(name) in self._by_name

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._by_name.get(_safe_tool_name(name))

    def specs(self) -> list[ToolSpec]:
        return list(self._by_name.values())

    def as_anthropic_schema(self) -> list[dict]:
        return [s.as_anthropic() for s in self._by_name.values()]

    def __len__(self) -> int:
        return len(self._by_name)

    # -- dispatch --------------------------------------------------------

    def invoke(self, name: str, arguments: dict) -> tuple[Any, Optional[str]]:
        """Execute a tool. Returns (result, error_or_None)."""
        spec = self.get(name)
        if spec is None:
            return None, f"unknown tool: {name}"
        if spec.handler is None:
            return None, f"tool {name} has no handler"
        try:
            return spec.handler(dict(arguments or {})), None
        except Exception as e:  # fail-soft: models recover better from errors than exceptions
            log.exception("tool %s failed", name)
            return None, f"{type(e).__name__}: {e}"


# -- helpers ----------------------------------------------------------------

_ALLOWED = set("abcdefghijklmnopqrstuvwxyz0123456789_-")


def _safe_tool_name(name: str) -> str:
    """Coerce to Anthropic's tool-name constraint (`^[a-zA-Z0-9_-]{1,128}$`)."""
    out = []
    for ch in (name or "").strip().lower():
        if ch in _ALLOWED:
            out.append(ch)
        elif ch in (" ", "."):
            out.append("_")
    cleaned = "".join(out).strip("_-")
    return (cleaned or "tool")[:128]


def _describe_skill(skill: Any) -> str:
    kws = getattr(skill, "trigger_keywords", None) or []
    steps = getattr(skill, "steps", None) or []
    bits = []
    if kws:
        bits.append(f"Triggers: {', '.join(list(kws)[:6])}")
    if steps:
        bits.append(f"{len(steps)} step(s) forged from prior successful runs.")
    return " · ".join(bits) or "Forged skill."


def _skill_handler(skillforge: Any, skill: Any) -> Callable[[dict], Any]:
    """Default handler: hand the skill + input back for the caller to execute.

    W1 only *advertises* skills — the actual run logic (running the steps,
    calling LLMs inside a skill, etc.) stays inside SkillForge or the skill
    itself. Here we just return a structured description so the model can
    see it took effect.
    """
    sid = getattr(skill, "id", "")
    sname = getattr(skill, "name", "")

    def _run(arguments: dict) -> dict:
        runner = getattr(skillforge, "run_skill", None)
        if callable(runner):
            return {"skill_id": sid, "result": runner(sid, arguments)}
        return {
            "skill_id": sid,
            "skill_name": sname,
            "invoked_with": arguments,
            "note": "no run_skill() on skillforge; advertisement only",
        }

    return _run


def _iter_skills_safe(skillforge: Any) -> Iterable[Any]:
    """Defensive iterator for skill listing (never raises)."""
    try:
        items = list((getattr(skillforge, "list_skills", None) or
                      getattr(skillforge, "list", None) or (lambda: []))()
                     or [])
    except Exception as e:
        log.debug("skill list failed: %s", e)
        return ()
    return items
