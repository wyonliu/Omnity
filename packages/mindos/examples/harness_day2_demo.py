#!/usr/bin/env python3
"""Personal Harness Runtime — Day 2 demo (offline, no API key required).

Shows the full W1 story in ~60 lines:

    Mindos (identity + memories)
      → MemoryDoc.export_md (IDENTITY.md / MEMORY.md / FACTS.md)
      → SkillForge (forge one skill from a trajectory)
      → ToolRegistry.load_from_skillforge (skills become tools)
      → HarnessEngine (tool loop with file-first context, explicit cache TTL)
      → HarnessResult (what actually happened: context files, tokens, tools)

Run:
    python examples/harness_day2_demo.py

Why this matters:
    "Agent = Model + Harness." Everything around the model — context,
    skills-as-tools, fail-soft recovery — is the harness. This demo
    proves the harness works end-to-end against a real Mindos soul,
    with zero network traffic, using StubBackend as the model.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_here = Path(__file__).resolve()
sys.path.insert(0, str(_here.parent.parent / "src"))

from mindos.core import Mindos
from mindos.harness import HarnessEngine, StubBackend, ToolRegistry
from mindos.harness.models.base import ToolCallRequest
from mindos.store import Memory


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # 1. Birth a soul with identity + a few memories
        m = Mindos.init(
            path=root / "mindos",
            name="Captain",
            traits=["curious", "builder", "direct"],
            values=["honesty", "shipping"],
            style="terse tech, no bullshit",
        )
        for text in [
            "我 2026-04-08 入职龙湖千丁当 CTO",
            "我女儿米莱 11 岁，喜欢打鼓和小提琴",
            "Mindos 在 2026-04-17 完成 v0.8 五件套发版",
        ]:
            m.store.add(Memory(
                id="", type="episode", content=text,
                source="demo", confidence=1.0,
            ))

        # 2. Forge one skill from a successful trajectory (offline)
        m.skills.use_llm = False
        skill_id = m.forge_skill({
            "goal": "Ship /health endpoint with tests first",
            "outcome": "success",
            "summary": "Red-green-refactor, pushed once green.",
            "tool_calls": [
                {"tool": "Write", "input": {"file_path": "tests/test_health.py"}, "output": "ok"},
                {"tool": "Bash",  "input": {"command": "pytest"},                   "output": "fail"},
                {"tool": "Write", "input": {"file_path": "app/routes.py"},          "output": "ok"},
                {"tool": "Bash",  "input": {"command": "pytest"},                   "output": "pass"},
                {"tool": "Bash",  "input": {"command": "git push"},                 "output": "pushed"},
            ],
        })
        print(f"  forged skill: {skill_id}")

        # 3. Snapshot the soul into a MemoryDoc dir
        snapshot = root / "snapshot"
        dump = m.export_md(snapshot)
        print(f"  snapshot files: {dump['files']} "
              f"(memories={dump['memories']}, facts={dump['facts']})")

        # 4. Build the ToolRegistry from the real SkillForge
        reg = ToolRegistry()
        loaded = reg.load_from_skillforge(m.skills)
        tool_name = reg.specs()[0].name
        print(f"  tools loaded: {loaded} ({tool_name})")

        # 5. Turn 1 — pure chat, harness reads MEMORY.md + IDENTITY.md
        stub = StubBackend(reply="米莱 11 岁，爱打鼓和小提琴")
        r1 = HarnessEngine(context_source=snapshot, model=stub).run("米莱多大？")
        print(f"\n[turn 1 · chat] {r1.response}")
        print(f"  context files: {r1.context_files}")
        print(f"  steps={r1.steps}  truncated={r1.truncated_context}")

        # 6. Turn 2 — scripted tool invocation of the forged skill
        scripted = StubBackend(
            tool_script=[[
                ToolCallRequest(id="u1", name=tool_name, arguments={"input": "run TDD ship"}),
            ]],
            reply="skill executed, here's what I did",
        )
        r2 = HarnessEngine(
            context_source=snapshot, model=scripted, tools=reg,
        ).run("跑一下 TDD ship 技能")
        print(f"\n[turn 2 · tool]  {r2.response}")
        print(f"  tool_calls={[(c.name, c.error) for c in r2.tool_calls]}")
        print(f"  tool_result={json.dumps(r2.tool_calls[0].result, ensure_ascii=False)}")

        # 7. EvoLog breadcrumb — the skill_forged event is in the timeline
        forged = m.evo_timeline(event_types=["skill_forged"])
        print(f"\n[evolog] skill_forged rows: {len(forged)}  "
              f"latest id={forged[0]['details'].get('skill_id')}")


if __name__ == "__main__":
    main()
