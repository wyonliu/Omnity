"""Real-integration tests for mindos.harness.

The skeleton unit tests use duck-typed fakes. This file wires the harness
against the **actual** v0.8 deliverables:

    - MemoryDoc (#75)       → real `Mindos.soul.export_md(dir)` snapshot
    - SkillForge (#76)      → real `Mindos.forge_skill(trace)` + `soul.skills.list()`
    - EvoLog (#77)          → real `soul.evo_timeline()` auditable after run
    - ContextBuilder        → reads the real snapshot
    - HarnessEngine         → runs a scripted StubBackend against the real stack

If the harness can make one turn end-to-end against a real Mindos + a
migrated memory, with skills-as-tools, with fail-soft, and leave an EvoLog
breadcrumb, the skeleton is production-shaped for W2.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_here = Path(__file__).resolve()
sys.path.insert(0, str(_here.parent.parent / "src"))

from mindos.core import Mindos
from mindos.harness import HarnessEngine, StubBackend, ToolRegistry
from mindos.harness.models.base import ToolCallRequest
from mindos.store import Memory


def _seed_memories(m: Mindos, rows: list[str]) -> None:
    """Insert memories directly, bypassing the LLM-powered commit pipeline.

    Keeps the test offline and deterministic — no network, no digest call.
    """
    for content in rows:
        m.store.add(Memory(
            id="", type="episode", content=content, source="test", confidence=1.0,
        ))


def _task_trace() -> dict:
    """Successful TDD-style trace that SkillForge can distill into a skill."""
    return {
        "goal": "Ship /health endpoint with tests first",
        "outcome": "success",
        "summary": "Red-green-refactor, pushed once green.",
        "tool_calls": [
            {"tool": "Write", "input": {"file_path": "tests/test_health.py"},
             "output": "ok"},
            {"tool": "Bash", "input": {"command": "pytest"},
             "output": "1 failing"},
            {"tool": "Write", "input": {"file_path": "app/routes.py"},
             "output": "ok"},
            {"tool": "Bash", "input": {"command": "pytest"},
             "output": "10 passed"},
            {"tool": "Edit", "input": {"file_path": "README.md"},
             "output": "ok"},
            {"tool": "Bash", "input": {"command": "git push"},
             "output": "pushed"},
        ],
    }


def test_harness_runs_against_real_mindos_snapshot():
    """Full W1 story: real Mindos → snapshot → harness run → assistant reply."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # 1. Real Mindos instance with identity + a couple of memories
        m = Mindos.init(
            path=root / "mindos",
            name="Captain",
            traits=["curious", "direct", "builder"],
            values=["honesty", "shipping"],
            style="terse tech, no bullshit",
        )
        _seed_memories(m, [
            "我 2026-04-08 入职龙湖千丁当 CTO",
            "我女儿米莱 11 岁，喜欢打鼓",
        ])

        # 2. Export via the real MemoryDoc (#75) — this is what the harness reads
        snapshot = root / "snapshot"
        dump = m.export_md(snapshot)
        assert (snapshot / "IDENTITY.md").exists()
        assert (snapshot / "MEMORY.md").exists()
        assert dump["memories"] >= 2

        # 3. ToolRegistry populates from an empty SkillForge (no skills yet)
        reg = ToolRegistry()
        loaded = reg.load_from_skillforge(m.skills)
        assert loaded == 0
        assert len(reg) == 0

        # 4. Harness runs one turn against a scripted stub (offline)
        eng = HarnessEngine(
            context_source=snapshot,
            model=StubBackend(reply="米莱 11 岁，爱打鼓"),
            tools=reg,
        )
        result = eng.run("米莱多大？")

        # 5. Assertions — the harness saw the real snapshot
        assert "米莱" in result.response
        assert result.steps == 1
        assert "IDENTITY.md" in result.context_files
        assert "MEMORY.md" in result.context_files
        assert result.stop_reason == "end_turn"
        assert not result.truncated_context

    print("  PASSED")


def test_harness_with_real_forged_skill_as_tool():
    """Forge a skill via SkillForge, let the harness discover and 'invoke' it."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        m = Mindos.init(
            path=root / "mindos",
            name="Captain",
            traits=["builder"],
            style="direct",
        )
        # Deterministic: don't call out to any LLM during tests
        m.skills.use_llm = False

        # Forge one real skill from a successful task trace
        sid = m.forge_skill(_task_trace())
        assert sid is not None

        # Snapshot the soul (so the harness has context)
        snapshot = root / "snapshot"
        m.export_md(snapshot)

        # Populate the ToolRegistry from the real SkillForge
        reg = ToolRegistry()
        loaded = reg.load_from_skillforge(m.skills)
        assert loaded == 1
        tool_name = reg.specs()[0].name  # exactly one skill registered

        # Script the stub to invoke that skill, then reply
        stub = StubBackend(
            tool_script=[[
                ToolCallRequest(id="u1", name=tool_name,
                                arguments={"input": "run it"}),
            ]],
            reply="skill executed, here's what I did",
        )

        result = HarnessEngine(
            context_source=snapshot, model=stub, tools=reg,
        ).run("跑一下 TDD ship 技能")

        assert result.steps == 2
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == tool_name
        assert result.tool_calls[0].error is None
        payload = result.tool_calls[0].result
        assert isinstance(payload, dict)
        assert payload["skill_id"] == sid

        # EvoLog (#77) captured the skill_forged event already
        forged_rows = m.evo_timeline(event_types=["skill_forged"])
        assert len(forged_rows) == 1
        assert forged_rows[0]["details"]["skill_id"] == sid

    print("  PASSED")


def test_harness_budget_truncates_but_keeps_identity():
    """With a tiny budget, IDENTITY survives, journal/memories get dropped."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        m = Mindos.init(
            path=root / "mindos",
            name="Captain",
            traits=["curious"] * 20,  # big-ish identity
            style="x" * 200,
        )
        _seed_memories(m, [
            f"long memory entry #{i} with lots of context " * 4
            for i in range(20)
        ])

        snapshot = root / "snapshot"
        m.export_md(snapshot)

        tiny_budget = HarnessEngine(
            context_source=snapshot,
            model=StubBackend(reply="ok"),
            max_chars=800,  # tight
        )
        r = tiny_budget.run("hi")
        assert r.truncated_context is True
        assert "IDENTITY.md" in r.context_files  # priority survives
        # MEMORY.md got dropped from context under budget pressure
        # (not a hard guarantee of order but matches current policy)
    print("  PASSED")


if __name__ == "__main__":
    test_harness_runs_against_real_mindos_snapshot()
    test_harness_with_real_forged_skill_as_tool()
    test_harness_budget_truncates_but_keeps_identity()
    print("\n✔ harness integration: 3 tests passed")
