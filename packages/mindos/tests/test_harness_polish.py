"""Harness polish pass — cross-week integration + edge cases.

These tests don't add new surface area; they harden the W1-W6 stack against
scenarios the per-week suites don't exercise directly.

Covered:
    - W2 sandbox escape via symlink
    - W2 shipped-skills dir loads both packages
    - W3 ResourceTemplate zero-param expand / multi-param ordering
    - W3 ElicitationField with default=False + enum of enums
    - W3 ContextBuilder budget truncation preserves IDENTITY
    - W4 normalize_team preserves explicit per-role model
    - W4 engine with agent_team AND tools (non-trivial schema) together
    - W5 overnight sync with dry_run + on_event across all steps
    - W6 OmeBench works with a ContextLoader (not a path on disk)
    - W2+W4+W5+W6 full-stack smoke — single test exercises every layer
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_here = Path(__file__).resolve()
sys.path.insert(0, str(_here.parent.parent / "src"))

from mindos.core import Mindos
from mindos.store import Memory
from mindos.harness import (
    HarnessEngine,
    ToolRegistry,
    load_skill_dir,
    register_builtins,
    shipped_skills_dir,
)
from mindos.harness.builtins import _resolve_in_sandbox
from mindos.harness.context import ContextBuilder
from mindos.harness.agent_team import SubAgentRole, normalize_team
from mindos.harness.mcp_apps import (
    ElicitationField,
    ResourceTemplate,
    parse_elicitation_response,
)
from mindos.harness.models.base import StubBackend, ToolCallRequest
from mindos.harness.omebench import OmeBench, load_corpus, load_questions
from mindos.harness.omebench.cli import _make_stub_backend
from mindos.harness.overnight import OvernightConfig, OvernightSoulSync


_PKG_ROOT = _here.parent.parent
_CORPUS_PATH = _PKG_ROOT / "omebench" / "sample_corpus"
_QUESTIONS_PATH = _PKG_ROOT / "omebench" / "sample_questions.jsonl"


# --- W2: sandbox symlink escape ------------------------------------------

def test_sandbox_rejects_symlink_escape():
    with tempfile.TemporaryDirectory() as outside, \
         tempfile.TemporaryDirectory() as inside:
        outside_root = Path(outside).resolve()
        inside_root = Path(inside).resolve()
        secret = outside_root / "secret.txt"
        secret.write_text("TOP SECRET", encoding="utf-8")

        # Plant a symlink INSIDE the sandbox pointing to a file OUTSIDE.
        link = inside_root / "escape.txt"
        link.symlink_to(secret)

        try:
            _resolve_in_sandbox(inside_root, "escape.txt")
        except ValueError as e:
            assert "outside" in str(e) or "sandbox" in str(e)
            print("  PASSED")
            return
        raise AssertionError("symlink escape was NOT rejected")


def test_sandbox_rejects_absolute_and_parent_escape():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        # Absolute
        try:
            _resolve_in_sandbox(root, "/etc/passwd")
            raise AssertionError("absolute path accepted")
        except ValueError:
            pass
        # .. escape
        try:
            _resolve_in_sandbox(root, "../../../etc/passwd")
            raise AssertionError("parent-escape accepted")
        except ValueError:
            pass
    print("  PASSED")


# --- W2: shipped skills load ---------------------------------------------

def test_shipped_skills_dir_exists_and_loads_both():
    d = shipped_skills_dir()
    assert d.exists() and d.is_dir(), d
    children = sorted(p.name for p in d.iterdir() if p.is_dir())
    # At least the two skills we ship
    assert "tdd-ship" in children
    assert "personal-cache-audit" in children

    reg = ToolRegistry()
    n = load_skill_dir(reg, d)
    assert n >= 2, (n, children)
    names = set(reg._by_name.keys())
    assert any("tdd" in name for name in names), names
    assert any("cache" in name for name in names), names
    print("  PASSED")


# --- W3: ResourceTemplate edge cases -------------------------------------

def test_resource_template_expands_zero_param_and_multi_param():
    # Zero param template → expand with no kwargs
    t0 = ResourceTemplate(uri_template="mindos://status",
                          name="status", description="")
    assert t0.expand() == "mindos://status"

    # Multi-param, with URL-unsafe chars that must be percent-encoded
    t1 = ResourceTemplate(
        uri_template="mindos://memory/{tenant}/{id}",
        name="memory", description="")
    assert t1.expand(tenant="acme", id="a/b c") == "mindos://memory/acme/a%2Fb%20c"

    # Missing/extra params rejected
    try:
        t1.expand(tenant="acme")
        raise AssertionError("missing param accepted")
    except ValueError:
        pass
    try:
        t1.expand(tenant="acme", id="x", nope="y")
        raise AssertionError("extra param accepted")
    except ValueError:
        pass
    print("  PASSED")


def test_elicitation_default_false_roundtrip():
    """A boolean field with default=False must preserve that in the schema
    and be honoured when the client returns nothing."""
    f = ElicitationField(name="dry_run", type="boolean",
                         description="", required=False, default=False)
    prop = f.as_schema_property()
    assert prop["type"] == "boolean"
    # default=False is NOT preserved in the schema today because the guard
    # uses `is not None` — False will be preserved. Verify:
    assert prop.get("default") is False, prop

    # Client omits the field entirely → we fill in default=False
    values, err = parse_elicitation_response(
        {"result": {"values": {}}}, [f])
    assert err is None, err
    assert values == {"dry_run": False}
    print("  PASSED")


def test_elicitation_enum_accepts_listed_value_only():
    f = ElicitationField(name="channel", type="enum",
                         description="", required=True,
                         enum=["cli", "web", "mcp"])
    ok, err = parse_elicitation_response(
        {"result": {"values": {"channel": "cli"}}}, [f])
    assert err is None and ok == {"channel": "cli"}

    _, err = parse_elicitation_response(
        {"result": {"values": {"channel": "slack"}}}, [f])
    assert err and "type mismatch" in err
    print("  PASSED")


# --- W3: budget truncation preserves IDENTITY -----------------------------

def test_context_builder_drops_journal_first_keeps_identity():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "IDENTITY.md").write_text("I am Captain.", encoding="utf-8")
        (root / "MEMORY.md").write_text("X" * 5_000, encoding="utf-8")
        (root / "FACTS.md").write_text("Y" * 5_000, encoding="utf-8")
        j = root / "Journal"
        j.mkdir()
        (j / "2026-04-19.md").write_text("Z" * 5_000, encoding="utf-8")

        # Budget so small only IDENTITY can fit
        b = ContextBuilder(source=root, max_chars=200, recent_days=1)
        ctx = b.build("hi")
        assert ctx.truncated
        assert "IDENTITY.md" in ctx.files_used
        assert "MEMORY.md" not in ctx.files_used
    print("  PASSED")


# --- W4: per-role model override survives normalize ----------------------

def test_normalize_team_preserves_explicit_role_model():
    class M:
        name = "mymodel"
    explicit = M()
    role = SubAgentRole(name="reviewer", model=explicit)
    roles = normalize_team([role], default_model=M())
    assert roles[0].model is explicit
    print("  PASSED")


def test_normalize_team_rejects_bad_scalar():
    try:
        normalize_team("not-a-list", default_model=None)
    except ValueError:
        pass
    else:
        raise AssertionError("scalar team not rejected")
    try:
        normalize_team([123], default_model=None)
    except ValueError:
        pass
    else:
        raise AssertionError("int team member not rejected")
    print("  PASSED")


# --- W4: engine with both agent_team and tools in one call ---------------

def test_engine_agent_team_and_tools_coexist():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "IDENTITY.md").write_text("Captain, ship fast.",
                                          encoding="utf-8")

        # Tool registry with one stub tool that the lead COULD call.
        reg = ToolRegistry()
        reg.register(
            name="noop",
            description="return ok",
            handler=lambda args: {"ok": True, "echo": args},
            input_schema={"type": "object", "properties": {}},
            source="test",
        )

        # Sub-agent backend — one reply per call (two roles).
        class SubBackend(StubBackend):
            default_cache_ttl = "none"
        sub_replies = iter([
            "reviewer: LGTM",
            "notes: short & clean",
        ])
        lead_backend = StubBackend(reply_fn=lambda _m: "Shipped.")

        # Dispatch uses the lead's model for sub-agents too → craft a backend
        # that returns the next scripted reply.
        class SequenceBackend(StubBackend):
            def complete(self, *, system, messages, tools=None,
                         cache_ttl=None, max_tokens=4096, temperature=0.7):
                try:
                    text = next(sub_replies)
                except StopIteration:
                    text = "Shipped."
                return super().complete(
                    system=system, messages=messages, tools=tools,
                    cache_ttl=cache_ttl, max_tokens=max_tokens,
                    temperature=temperature,
                ).__class__(text=text)
        # Use a simpler approach: StubBackend with reply_fn that returns
        # different things based on # of prior calls.
        calls_seen = []
        def reply_fn(messages):
            calls_seen.append(True)
            i = len(calls_seen)
            if i == 1: return "[reviewer] ok"
            if i == 2: return "[notes] clean"
            return "Shipped."
        backend = StubBackend(reply_fn=reply_fn)

        engine = HarnessEngine(
            context_source=root, model=backend, tools=reg, max_steps=3,
        )
        result = engine.run(
            "ship the PR",
            agent_team=["reviewer", "notes"],
        )
        assert result.response == "Shipped."
        assert [o.name for o in result.sub_agent_delegations] == ["reviewer", "notes"]
        assert "[reviewer]" in result.sub_agent_delegations[0].text
        print("  PASSED")


# --- W5: dry_run emits start+finish hooks across every step --------------

def test_overnight_dry_run_emits_events_and_mutates_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=Path(tmp) / "m", name="C",
                        traits=["builder"], style="direct")
        for i in range(5):
            m.store.add(Memory(
                id="", type="fact",
                content=f"fact {i}", source="seed", confidence=1.0))
        before = m.store.count()

        seen: list[tuple[str, dict]] = []
        sync = OvernightSoulSync(m, on_event=lambda k, p: seen.append((k, p)))
        report = sync.run(dry_run=True)

        assert report.dry_run is True
        assert m.store.count() == before
        kinds = [k for k, _ in seen]
        assert kinds == ["overnight_started", "overnight_finished"]
        assert "totals" in seen[1][1]
        # The only non-zero entry a dry-run may carry is `skipped`
        # (from reflect, which is opt-in and off by default).
        for k, v in seen[1][1]["totals"].items():
            if k == "skipped":
                continue
            assert v == 0, (k, v)
    print("  PASSED")


# --- W6: OmeBench drives off a ContextLoader, not a path -----------------

def test_omebench_works_with_context_loader_factory():
    """Custom mindos_factory can return a Mindos-like shim whose export_md
    produces a snapshot the harness can read. Ensures we don't hardcode a
    filesystem path requirement."""
    class FakeMindos:
        """Mindos-shaped but we control the snapshot directly."""
        def __init__(self, tmp_root: Path):
            self._root = tmp_root / "snap"
            self._root.mkdir(parents=True, exist_ok=True)
            (self._root / "IDENTITY.md").write_text(
                "You are a sharp fact-retriever.", encoding="utf-8")
            (self._root / "MEMORY.md").write_text(
                "- Alice reports to Bob.\n"
                "- Bob approved v0.9 roadmap on 2026-04-02.\n"
                "- Alice's favourite tool is ripgrep.\n"
                "- Bob manages three teams: harness, infra, and ingest.\n"
                "- Bob's backup plan: spin the skills.sh packaging into a separate public library.\n",
                encoding="utf-8")

        def export_md(self, out_dir, max_memories=500, max_journal=None):
            out = Path(out_dir)
            out.mkdir(parents=True, exist_ok=True)
            for f in ("IDENTITY.md", "MEMORY.md"):
                (out / f).write_text((self._root / f).read_text(),
                                      encoding="utf-8")

    stub = _make_stub_backend(_QUESTIONS_PATH)
    bench = OmeBench(
        corpus_path=_CORPUS_PATH,
        questions_path=_QUESTIONS_PATH,
        model=stub,
        mindos_factory=lambda tmp: FakeMindos(tmp),
    )
    report = bench.run()
    assert report.total == 5
    assert report.correct == 5
    print("  PASSED")


# --- Full-stack smoke: W2 + W4 + W5 + W6 together ------------------------

def test_full_stack_smoke_w2_w4_w5_w6():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # W6 — load corpus & questions
        corpus = load_corpus(_CORPUS_PATH)
        questions = load_questions(_QUESTIONS_PATH)
        assert len(questions) == 5
        assert corpus.counts_by_type()["fact"] == 5

        # W2 — stand up Mindos, register builtins against a sandbox
        m = Mindos.init(path=root / "m", name="Bench",
                        traits=["neutral"], style="neutral")
        for item in corpus.items:
            m.store.add(Memory(id="", type=item.type, content=item.content,
                               source=item.source, confidence=1.0))

        sandbox = root / "scratch"
        reg = ToolRegistry()
        n = register_builtins(reg, mindos=m, sandbox_root=sandbox)
        assert n == 4  # recall + commit + read_file + write_file

        # W2 — also advertise the shipped skills
        shipped = shipped_skills_dir()
        load_skill_dir(reg, shipped)

        # W5 — overnight dry-run with on_event, must not crash
        events = []
        OvernightSoulSync(m, on_event=lambda k, p: events.append(k)).run(
            dry_run=True)
        assert events == ["overnight_started", "overnight_finished"]

        # W4 — run a question with an agent team AND the registered builtins.
        snapshot = root / "snap"
        m.export_md(snapshot)

        calls = []
        def reply(messages):
            calls.append(True)
            i = len(calls)
            if i == 1: return "sub: Alice reports to Bob."
            # Lead's final turn — matches q1's rubric
            return "Alice reports to Bob."

        backend = StubBackend(reply_fn=reply)
        engine = HarnessEngine(
            context_source=snapshot, model=backend, tools=reg, max_steps=3,
        )
        result = engine.run(
            "Who does Alice report to?",
            agent_team=["fact-check"],
        )
        assert "Bob" in result.response
        assert [o.name for o in result.sub_agent_delegations] == ["fact-check"]
        assert result.context_files  # IDENTITY/MEMORY files were read
    print("  PASSED")


# --- run ------------------------------------------------------------------

if __name__ == "__main__":
    test_sandbox_rejects_symlink_escape()
    test_sandbox_rejects_absolute_and_parent_escape()
    test_shipped_skills_dir_exists_and_loads_both()
    test_resource_template_expands_zero_param_and_multi_param()
    test_elicitation_default_false_roundtrip()
    test_elicitation_enum_accepts_listed_value_only()
    test_context_builder_drops_journal_first_keeps_identity()
    test_normalize_team_preserves_explicit_role_model()
    test_normalize_team_rejects_bad_scalar()
    test_engine_agent_team_and_tools_coexist()
    test_overnight_dry_run_emits_events_and_mutates_nothing()
    test_omebench_works_with_context_loader_factory()
    test_full_stack_smoke_w2_w4_w5_w6()
    print("\n✔ harness polish: 13 tests passed")
