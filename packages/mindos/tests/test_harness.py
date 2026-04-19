"""Tests for mindos.harness — the Personal Harness skeleton.

Covers:
    - ContextBuilder: reads IDENTITY/MEMORY/FACTS, strips frontmatter, budget
    - ToolRegistry: registration, Anthropic schema, SkillForge integration, dispatch
    - ModelBackend.StubBackend: deterministic behaviour + tool_script
    - ClaudeBackend: cache TTL policy + response parsing via injected transport
    - KimiBackend: OpenAI-shape transform + response parsing
    - HarnessEngine: end-to-end run (no tools), run with tools, fail-soft tool,
                     max_steps guard, agent_team gate
    - Recovery: retry on transient errors, no retry on 4xx
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_here = Path(__file__).resolve()
sys.path.insert(0, str(_here.parent.parent / "src"))

from mindos.harness import (
    ContextBuilder,
    HarnessEngine,
    HarnessResult,
    StubBackend,
    ToolRegistry,
)
from mindos.harness.models.base import ToolCallRequest
from mindos.harness.models.claude import ClaudeBackend
from mindos.harness.models.kimi import KimiBackend
from mindos.harness.recovery import HarnessError, with_retries


# -- ContextBuilder --------------------------------------------------------

def _fake_memorydoc(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "IDENTITY.md").write_text(
        "---\nmindos_version: 0.7.1\n---\n\n# Captain\n\ntraits: curious\n",
        encoding="utf-8",
    )
    (root / "MEMORY.md").write_text(
        "---\ncount: 1\n---\n\n## 2026-04-18 episode\n\nSigned CTO @ Longfor.\n",
        encoding="utf-8",
    )
    (root / "FACTS.md").write_text(
        "---\ncount: 1\n---\n\n- 1986年生于河南夏邑\n",
        encoding="utf-8",
    )


def test_context_builder_reads_all_three_files():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fake_memorydoc(root)
        ctx = ContextBuilder(root).build("你好")
        assert "Captain" in ctx.system_prompt
        assert "Longfor" in ctx.system_prompt
        assert "夏邑" in ctx.system_prompt
        assert "mindos_version" not in ctx.system_prompt  # frontmatter stripped
        assert "IDENTITY.md" in ctx.files_used
        assert "MEMORY.md" in ctx.files_used
        assert "FACTS.md" in ctx.files_used
        assert ctx.truncated is False
    print("  PASSED")


def test_context_builder_strips_frontmatter_when_missing():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "IDENTITY.md").write_text("# No Frontmatter Here", encoding="utf-8")
        ctx = ContextBuilder(root).build("hi")
        assert "No Frontmatter" in ctx.system_prompt
    print("  PASSED")


def test_context_builder_budget_truncates_low_priority_first():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "IDENTITY.md").write_text("# I\n" + "i" * 100, encoding="utf-8")
        (root / "MEMORY.md").write_text("# M\n" + "m" * 500, encoding="utf-8")
        (root / "FACTS.md").write_text("# F\n" + "f" * 500, encoding="utf-8")
        # Budget forces drop of everything but IDENTITY
        ctx = ContextBuilder(root, max_chars=200).build("x")
        assert ctx.truncated is True
        assert "IDENTITY.md" in ctx.files_used
        # MEMORY / FACTS got dropped
        assert "m" * 500 not in ctx.system_prompt
    print("  PASSED")


def test_context_builder_missing_dir_is_empty_context():
    with tempfile.TemporaryDirectory() as tmp:
        ctx = ContextBuilder(Path(tmp) / "does-not-exist").build("hi")
        assert ctx.system_prompt == ""
        assert ctx.files_used == []
        assert ctx.user_message == "hi"
    print("  PASSED")


def test_context_builder_includes_recent_journal():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        journal = root / "Journal"
        journal.mkdir()
        (journal / "2026-04-18.md").write_text("Signed CTO.\n", encoding="utf-8")
        (journal / "2026-04-19.md").write_text("First week agenda.\n", encoding="utf-8")
        ctx = ContextBuilder(root, recent_days=2).build("hi")
        assert "Signed CTO" in ctx.system_prompt
        assert "First week agenda" in ctx.system_prompt
        assert any("Journal" in f for f in ctx.files_used)
    print("  PASSED")


# -- ToolRegistry ----------------------------------------------------------

def test_tool_registry_register_and_schema():
    reg = ToolRegistry()
    reg.register("recall", "search memories",
                 input_schema={"type": "object",
                               "properties": {"q": {"type": "string"}},
                               "required": ["q"]},
                 handler=lambda args: ["mem1", "mem2"])
    assert "recall" in reg
    assert len(reg) == 1
    schema = reg.as_anthropic_schema()
    assert schema[0]["name"] == "recall"
    assert schema[0]["input_schema"]["required"] == ["q"]
    print("  PASSED")


def test_tool_registry_invoke_ok_and_error():
    reg = ToolRegistry()
    reg.register("ok", "", handler=lambda args: {"echo": args})
    reg.register("bad", "", handler=lambda args: (_ for _ in ()).throw(RuntimeError("boom")))
    out, err = reg.invoke("ok", {"x": 1})
    assert err is None and out == {"echo": {"x": 1}}
    out, err = reg.invoke("bad", {})
    assert out is None and "boom" in err
    out, err = reg.invoke("missing", {})
    assert "unknown tool" in err
    print("  PASSED")


def test_tool_registry_safe_name_coercion():
    reg = ToolRegistry()
    spec = reg.register("weekly summary (journal)", "d")
    assert spec.name == "weekly_summary_journal"  # spaces → _, parens stripped
    print("  PASSED")


def test_tool_registry_loads_skillforge():
    """A minimal duck-typed skillforge is enough."""
    class _Skill:
        def __init__(self, sid, name):
            self.id = sid
            self.name = name
            self.description = f"skill {sid}"
            self.trigger_keywords = ("trigger",)
            self.steps = [1, 2, 3]

    class _SF:
        def list_skills(self):
            return [_Skill("s1", "journal_summary"), _Skill("s2", "interview_clean")]
        def run_skill(self, sid, args):
            return {"ran": sid, "args": args}

    reg = ToolRegistry()
    n = reg.load_from_skillforge(_SF())
    assert n == 2
    assert "journal_summary" in reg
    out, err = reg.invoke("journal_summary", {"week": "2026-W16"})
    assert err is None
    assert out["skill_id"] == "s1"
    assert out["result"]["ran"] == "s1"
    print("  PASSED")


# -- StubBackend -----------------------------------------------------------

def test_stub_backend_echoes_last_user():
    b = StubBackend()
    r = b.complete(system="", messages=[{"role": "user", "content": "hi there"}])
    assert r.text == "[stub] hi there"
    assert r.stop_reason == "end_turn"
    print("  PASSED")


def test_stub_backend_tool_script():
    tc = ToolCallRequest(id="t1", name="recall", arguments={"q": "longfor"})
    b = StubBackend(tool_script=[[tc]], reply="done")
    r1 = b.complete(system="", messages=[{"role": "user", "content": "?"}])
    assert r1.tool_calls == [tc]
    assert r1.stop_reason == "tool_use"
    r2 = b.complete(system="", messages=[{"role": "user", "content": "?"}])
    assert r2.text == "done"
    assert r2.stop_reason == "end_turn"
    print("  PASSED")


# -- ClaudeBackend ---------------------------------------------------------

def test_claude_backend_attaches_cache_control_by_default():
    captured = {}
    def fake_transport(url, payload, headers):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        return {
            "content": [{"type": "text", "text": "ok"}],
            "usage": {"input_tokens": 10, "output_tokens": 2,
                      "cache_read_input_tokens": 8,
                      "cache_creation_input_tokens": 0},
            "stop_reason": "end_turn", "model": "claude-opus-4-6",
        }
    b = ClaudeBackend(api_key="k", transport=fake_transport)
    r = b.complete(system="YOU ARE CAPTAIN",
                   messages=[{"role": "user", "content": "hi"}])
    assert r.text == "ok"
    assert r.tokens.cached_read == 8
    # system must be a list of blocks with cache_control on the text block
    sys_blocks = captured["payload"]["system"]
    assert sys_blocks[0]["type"] == "text"
    assert sys_blocks[0]["cache_control"]["ttl"] == "1h"
    # no tools → no tools key
    assert "tools" not in captured["payload"]
    assert r.cache_ttl_used == "1h"
    print("  PASSED")


def test_claude_backend_parses_tool_use():
    def fake_transport(url, payload, headers):
        return {
            "content": [
                {"type": "text", "text": "thinking..."},
                {"type": "tool_use", "id": "u1", "name": "recall",
                 "input": {"q": "米莱"}},
            ],
            "usage": {"input_tokens": 5, "output_tokens": 5},
            "stop_reason": "tool_use", "model": "claude-opus-4-6",
        }
    b = ClaudeBackend(api_key="k", transport=fake_transport)
    r = b.complete(system="", messages=[{"role": "user", "content": "?"}])
    assert len(r.tool_calls) == 1
    assert r.tool_calls[0].name == "recall"
    assert r.tool_calls[0].arguments == {"q": "米莱"}
    assert r.stop_reason == "tool_use"
    print("  PASSED")


def test_claude_backend_respects_explicit_ttl_override():
    seen = {}
    def transport(url, payload, headers):
        seen["ttl"] = payload["system"][0]["cache_control"]["ttl"]
        return {"content": [{"type": "text", "text": ""}], "usage": {},
                "stop_reason": "end_turn", "model": "claude-opus-4-6"}
    b = ClaudeBackend(api_key="k", transport=transport)
    b.complete(system="s", messages=[{"role": "user", "content": "?"}],
               cache_ttl="5m")
    assert seen["ttl"] == "5m"
    print("  PASSED")


def test_claude_backend_rejects_unknown_ttl_and_falls_back():
    seen = {}
    def transport(url, payload, headers):
        seen["ttl"] = payload["system"][0]["cache_control"]["ttl"]
        return {"content": [{"type": "text", "text": ""}], "usage": {},
                "stop_reason": "end_turn", "model": "claude-opus-4-6"}
    b = ClaudeBackend(api_key="k", transport=transport)
    b.complete(system="s", messages=[{"role": "user", "content": "?"}],
               cache_ttl="forever")
    assert seen["ttl"] == "5m"  # fallback
    print("  PASSED")


def test_claude_backend_cache_control_none_when_ttl_none():
    seen = {}
    def transport(url, payload, headers):
        seen["block"] = payload["system"][0]
        return {"content": [{"type": "text", "text": ""}], "usage": {},
                "stop_reason": "end_turn", "model": "claude-opus-4-6"}
    b = ClaudeBackend(api_key="k", transport=transport)
    b.complete(system="s", messages=[{"role": "user", "content": "?"}],
               cache_ttl="none")
    assert "cache_control" not in seen["block"]
    print("  PASSED")


def test_claude_backend_attaches_cache_control_to_last_tool():
    seen = {}
    def transport(url, payload, headers):
        seen["tools"] = payload["tools"]
        return {"content": [{"type": "text", "text": ""}], "usage": {},
                "stop_reason": "end_turn", "model": "claude-opus-4-6"}
    b = ClaudeBackend(api_key="k", transport=transport)
    b.complete(
        system="s",
        messages=[{"role": "user", "content": "?"}],
        tools=[
            {"name": "a", "description": "", "input_schema": {"type": "object"}},
            {"name": "b", "description": "", "input_schema": {"type": "object"}},
        ],
    )
    assert "cache_control" not in seen["tools"][0]
    assert seen["tools"][-1]["cache_control"]["ttl"] == "1h"
    print("  PASSED")


def test_claude_backend_requires_key_without_transport():
    import os
    saved = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        b = ClaudeBackend()
        try:
            b.complete(system="", messages=[{"role": "user", "content": "?"}])
        except RuntimeError as e:
            assert "api_key" in str(e)
            print("  PASSED")
            return
        raise AssertionError("expected RuntimeError")
    finally:
        if saved:
            os.environ["ANTHROPIC_API_KEY"] = saved


# -- KimiBackend -----------------------------------------------------------

def test_kimi_backend_openai_shape_and_parse():
    captured = {}
    def transport(url, payload, headers):
        captured["payload"] = payload
        return {
            "model": "kimi-k2-thinking",
            "choices": [{"finish_reason": "stop", "message": {"content": "你好"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        }
    b = KimiBackend(api_key="k", transport=transport)
    r = b.complete(system="be concise", messages=[{"role": "user", "content": "hi"}])
    # system becomes first message
    assert captured["payload"]["messages"][0]["role"] == "system"
    assert r.text == "你好"
    assert r.tokens.input == 3
    assert r.cache_ttl_used == "none"
    print("  PASSED")


def test_kimi_backend_parses_tool_calls():
    def transport(url, payload, headers):
        return {
            "model": "kimi-k2-thinking",
            "choices": [{
                "finish_reason": "tool_calls",
                "message": {
                    "content": "",
                    "tool_calls": [{
                        "id": "c1",
                        "function": {
                            "name": "recall",
                            "arguments": '{"q":"longfor"}',
                        },
                    }],
                },
            }],
            "usage": {"prompt_tokens": 1, "completion_tokens": 0},
        }
    b = KimiBackend(api_key="k", transport=transport)
    r = b.complete(system="", messages=[{"role": "user", "content": "?"}])
    assert len(r.tool_calls) == 1
    assert r.tool_calls[0].name == "recall"
    assert r.tool_calls[0].arguments == {"q": "longfor"}
    assert r.stop_reason == "tool_use"
    print("  PASSED")


def test_kimi_backend_stub_without_transport_raises():
    b = KimiBackend(api_key="k")
    try:
        b.complete(system="", messages=[{"role": "user", "content": "?"}])
    except NotImplementedError as e:
        assert "W2" in str(e)
        print("  PASSED")
        return
    raise AssertionError("expected NotImplementedError")


# -- HarnessEngine end-to-end ---------------------------------------------

def test_engine_run_no_tools_returns_text():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fake_memorydoc(root)
        eng = HarnessEngine(context_source=root, model=StubBackend(reply="hi back"))
        r = eng.run("hello")
        assert isinstance(r, HarnessResult)
        assert r.response == "hi back"
        assert r.steps == 1
        assert r.tool_calls == []
        assert "IDENTITY.md" in r.context_files
        assert r.stop_reason == "end_turn"
    print("  PASSED")


def test_engine_runs_tool_loop_and_feeds_results_back():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fake_memorydoc(root)

        reg = ToolRegistry()
        reg.register("recall", "get memories",
                     handler=lambda args: [{"mem": "captain is 1986"}])

        script = [[ToolCallRequest(id="u1", name="recall",
                                   arguments={"q": "age"})]]
        stub = StubBackend(tool_script=script, reply="you were born 1986")

        eng = HarnessEngine(context_source=root, model=stub, tools=reg)
        r = eng.run("how old am I?")
        assert r.steps == 2
        assert len(r.tool_calls) == 1
        assert r.tool_calls[0].name == "recall"
        assert r.tool_calls[0].error is None
        assert "1986" in r.response

        # Second call to the backend received the tool_result message
        second = stub.calls[1]
        last_user = second["messages"][-1]
        assert last_user["role"] == "user"
        assert last_user["content"][0]["type"] == "tool_result"
    print("  PASSED")


def test_engine_failing_tool_is_fail_soft():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fake_memorydoc(root)
        reg = ToolRegistry()
        def _raise(args): raise ValueError("no such memory")
        reg.register("recall", "", handler=_raise)

        script = [[ToolCallRequest(id="u1", name="recall", arguments={})]]
        stub = StubBackend(tool_script=script, reply="sorry couldn't find it")
        r = HarnessEngine(context_source=root, model=stub, tools=reg).run("?")
        assert r.tool_calls[0].error is not None
        assert "no such memory" in r.tool_calls[0].error
        assert "sorry" in r.response
    print("  PASSED")


def test_engine_respects_max_steps():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fake_memorydoc(root)
        reg = ToolRegistry()
        reg.register("loop", "", handler=lambda args: "ok")
        # Model keeps requesting tool calls forever
        infinite = [[ToolCallRequest(id=f"u{i}", name="loop", arguments={})]
                    for i in range(50)]
        stub = StubBackend(tool_script=infinite, reply="never")
        r = HarnessEngine(context_source=root, model=stub, tools=reg,
                          max_steps=3).run("spin")
        assert r.steps == 3
        assert r.stop_reason == "max_steps"
    print("  PASSED")


def test_engine_agent_team_bad_shape_rejected():
    """agent_team was gated in W1, opened in W4 — bad shapes still rejected."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fake_memorydoc(root)
        eng = HarnessEngine(context_source=root, model=StubBackend(reply="ok"))
        try:
            eng.run("x", agent_team=object())
        except ValueError as e:
            assert "list" in str(e)
            print("  PASSED")
            return
        raise AssertionError("expected ValueError for non-list agent_team")


def test_engine_extra_system_merges_into_prompt():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fake_memorydoc(root)
        stub = StubBackend(reply="ok")
        eng = HarnessEngine(context_source=root, model=stub)
        eng.run("hi", extra_system="Be brief.")
        assert "Be brief." in stub.calls[0]["system"]
    print("  PASSED")


def test_engine_cache_ttl_override_propagates():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _fake_memorydoc(root)
        stub = StubBackend(reply="ok")
        eng = HarnessEngine(context_source=root, model=stub, cache_ttl="5m")
        r = eng.run("hi")
        assert stub.calls[0]["cache_ttl"] == "5m"
        assert r.cache_ttl_used == "5m"
    print("  PASSED")


# -- Recovery --------------------------------------------------------------

def test_with_retries_eventually_succeeds():
    attempts = {"n": 0}
    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise TimeoutError("temporarily unavailable")
        return "ok"
    out = with_retries(flaky, attempts=5, base_delay=0.001, sleep=lambda s: None)
    assert out == "ok"
    assert attempts["n"] == 3
    print("  PASSED")


def test_with_retries_gives_up_on_4xx():
    class _E(Exception):
        def __init__(self):
            super().__init__("bad request")
            self.code = 400
    def broken():
        raise _E()
    try:
        with_retries(broken, attempts=3, base_delay=0.001, sleep=lambda s: None)
    except HarnessError as e:
        assert "1 attempt" in str(e)
        print("  PASSED")
        return
    raise AssertionError("expected HarnessError")


def test_with_retries_raises_after_exhaustion():
    def flaky(): raise TimeoutError("timed out")
    try:
        with_retries(flaky, attempts=2, base_delay=0.001, sleep=lambda s: None)
    except HarnessError as e:
        assert "2 attempt" in str(e)
        print("  PASSED")
        return
    raise AssertionError("expected HarnessError")


# -- Runner ----------------------------------------------------------------

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        print(t.__name__)
        t()
    print(f"\n✔ harness skeleton: {len(tests)} tests passed")
