"""W4 tests — Agent Teams opt-in multi-agent.

Exercises `normalize_team`, `dispatch_team`, and `HarnessEngine.run(...,
agent_team=...)` end-to-end against a scripted StubBackend. No network.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_here = Path(__file__).resolve()
sys.path.insert(0, str(_here.parent.parent / "src"))

from mindos.harness import HarnessEngine, StubBackend
from mindos.harness.agent_team import (
    SubAgentOutput,
    SubAgentRole,
    TeamResult,
    dispatch_team,
    normalize_team,
)


# -- helpers ---------------------------------------------------------------

def _fake_snapshot(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "IDENTITY.md").write_text(
        "---\nname: Captain\n---\n# IDENTITY\ntraits: builder\n",
        encoding="utf-8")
    (root / "MEMORY.md").write_text(
        "# MEMORY\n- 2026-04-19 W4 ships today\n", encoding="utf-8")
    (root / "FACTS.md").write_text("# FACTS\n- fact: one\n", encoding="utf-8")
    return root


# -- normalize_team --------------------------------------------------------

def test_normalize_team_accepts_mixed_shapes():
    roles = normalize_team(
        ["reviewer",
         {"name": "fact-checker", "instruction": "verify dates"},
         SubAgentRole(name="planner", system="be terse")],
        default_model=StubBackend(),
    )
    assert [r.name for r in roles] == ["reviewer", "fact-checker", "planner"]
    assert roles[1].instruction == "verify dates"
    assert roles[2].system == "be terse"
    assert all(r.model is not None for r in roles)
    print("  PASSED")


def test_normalize_team_none_and_empty():
    assert normalize_team(None) == []
    assert normalize_team([]) == []
    print("  PASSED")


def test_normalize_team_bad_shape_raises():
    try:
        normalize_team(42)
    except ValueError as e:
        assert "list" in str(e)
    else:
        raise AssertionError("expected ValueError")
    try:
        normalize_team([3.14])
    except ValueError as e:
        assert "unsupported" in str(e)
    else:
        raise AssertionError("expected ValueError")
    print("  PASSED")


# -- dispatch_team ---------------------------------------------------------

def test_dispatch_team_sequential_shared_context():
    class SeqStub(StubBackend):
        name = "seq"
        def __init__(self):
            super().__init__()
            self.systems: list[str] = []
            self._i = 0
            self._replies = ["R1", "R2", "R3"]
        def complete(self, *, system, messages, tools=None, cache_ttl=None,
                     max_tokens=4096, temperature=0.7):
            self.systems.append(system)
            reply = self._replies[self._i]
            self._i += 1
            return super().__class__.__bases__[0].__new__  # not reachable; use direct build below

    # Simpler approach: single stub instance re-used by all roles
    stub = StubBackend(reply=None, reply_fn=lambda msgs: "role-reply")
    roles = normalize_team(["alpha", "beta"], default_model=stub)
    out = dispatch_team(
        roles=roles,
        lead_system="LEAD SYSTEM",
        lead_user_message="do the thing",
        default_model=stub,
    )
    assert out.ok
    assert [o.name for o in out.outputs] == ["alpha", "beta"]
    # Each sub-agent call saw the lead system prompt prefix
    for call in stub.calls:
        assert call["system"].startswith("LEAD SYSTEM")
        assert "Sub-agent role" in call["system"]
    # Two calls total, sequential
    assert len(stub.calls) == 2
    print("  PASSED")


def test_dispatch_team_falls_back_instruction_to_lead_user_message():
    stub = StubBackend(reply_fn=lambda msgs: "x")
    roles = normalize_team([{"name": "plain"}], default_model=stub)
    dispatch_team(roles=roles, lead_system="S", lead_user_message="LEAD USER",
                  default_model=stub)
    # The sub-agent's user message was the lead's message
    last_msg = stub.calls[0]["messages"][-1]["content"]
    assert any(b.get("text") == "LEAD USER" for b in last_msg)
    print("  PASSED")


def test_dispatch_team_fails_soft_per_role():
    class ExplodingBackend(StubBackend):
        name = "boom"
        def complete(self, *, system, messages, tools=None, cache_ttl=None,
                     max_tokens=4096, temperature=0.7):
            raise RuntimeError("kaboom")

    bad = ExplodingBackend()
    good = StubBackend(reply="ok")
    roles = [
        SubAgentRole(name="bad", model=bad),
        SubAgentRole(name="good", model=good),
    ]
    out = dispatch_team(roles=roles, lead_system="S", lead_user_message="u",
                        default_model=good)
    assert not out.ok
    assert out.outputs[0].error is not None
    assert "kaboom" in out.outputs[0].error
    assert out.outputs[1].error is None
    assert out.outputs[1].text == "ok"
    print("  PASSED")


# -- engine integration ----------------------------------------------------

def test_engine_agent_team_single_string_role():
    with tempfile.TemporaryDirectory() as tmp:
        root = _fake_snapshot(Path(tmp) / "snap")

        # The stub replies to every call with "SUB-REPLY" or "LEAD-REPLY"
        # depending on who asks. We use reply_fn to inspect messages.
        def reply_fn(msgs):
            # Sub-agent calls contain only one user message (no tool loop)
            # Lead tool loop calls go via the same backend; distinguish by a
            # marker we embed into the system or the user text.
            return "X"
        stub = StubBackend(reply=None, reply_fn=reply_fn)
        eng = HarnessEngine(context_source=root, model=stub)
        r = eng.run("plan the launch", agent_team=["reviewer"])
        assert len(r.sub_agent_delegations) == 1
        assert r.sub_agent_delegations[0].name == "reviewer"
        assert r.response == "X"  # lead turn's text
        assert r.steps == 1
    print("  PASSED")


def test_engine_agent_team_two_roles_folds_into_system():
    with tempfile.TemporaryDirectory() as tmp:
        root = _fake_snapshot(Path(tmp) / "snap")

        class SpyBackend(StubBackend):
            name = "spy"
            def __init__(self):
                super().__init__(reply="LEAD")
                self.systems_seen: list[str] = []
            def complete(self, *, system, messages, **kw):
                self.systems_seen.append(system)
                return super().complete(system=system, messages=messages, **kw)

        spy = SpyBackend()
        eng = HarnessEngine(context_source=root, model=spy)
        r = eng.run("ship it", agent_team=[
            {"name": "reviewer", "system": "review code"},
            {"name": "checker", "system": "verify facts"},
        ])
        # Two sub-agent calls + one lead call
        assert len(spy.systems_seen) == 3
        # Sub-agents see lead-system + role block
        assert "review code" in spy.systems_seen[0]
        assert "verify facts" in spy.systems_seen[1]
        # Lead sees a system that includes the sub-agent report
        lead_sys = spy.systems_seen[-1]
        assert "Sub-agent report" in lead_sys
        assert "## reviewer" in lead_sys and "## checker" in lead_sys
        # Delegations captured in result
        assert {o.name for o in r.sub_agent_delegations} == {"reviewer", "checker"}
    print("  PASSED")


def test_engine_agent_team_none_runs_single_agent_unchanged():
    with tempfile.TemporaryDirectory() as tmp:
        root = _fake_snapshot(Path(tmp) / "snap")
        stub = StubBackend(reply="solo")
        eng = HarnessEngine(context_source=root, model=stub)
        r = eng.run("solo task")
        assert r.sub_agent_delegations == []
        assert r.response == "solo"
    print("  PASSED")


def test_team_result_as_tool_result_block():
    tr = TeamResult(outputs=[
        SubAgentOutput(name="a", text="found x"),
        SubAgentOutput(name="b", error="timeout"),
    ])
    block = tr.as_tool_result_block()
    assert "# Sub-agent report" in block
    assert "## a" in block and "found x" in block
    assert "## b" in block and "timeout" in block
    assert tr.ok is False
    print("  PASSED")


if __name__ == "__main__":
    test_normalize_team_accepts_mixed_shapes()
    test_normalize_team_none_and_empty()
    test_normalize_team_bad_shape_raises()
    test_dispatch_team_sequential_shared_context()
    test_dispatch_team_falls_back_instruction_to_lead_user_message()
    test_dispatch_team_fails_soft_per_role()
    test_engine_agent_team_single_string_role()
    test_engine_agent_team_two_roles_folds_into_system()
    test_engine_agent_team_none_runs_single_agent_unchanged()
    test_team_result_as_tool_result_block()
    print("\n✔ harness W4: 10 tests passed")
