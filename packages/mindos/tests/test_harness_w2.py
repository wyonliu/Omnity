"""W2 tests — built-in tools + skills.sh package loader.

Exercises the real Mindos store (no mocks) for recall/commit, and real disk
for read_file/write_file + SKILL.md loading.
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
    ToolRegistry,
    register_builtins,
    load_skill_package,
    load_skill_dir,
    shipped_skills_dir,
)


# -- builtins --------------------------------------------------------------

def test_builtins_recall_and_commit_hit_real_store():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=Path(tmp) / "m", name="C", traits=["x"], style="y")
        m.store.add(Memory(id="", type="fact",
                           content="龙湖千丁入职 2026-04-08", source="t", confidence=1.0))
        reg = ToolRegistry()
        n = register_builtins(reg, mindos=m)
        assert n == 2  # recall + commit (no sandbox → no fs tools)
        assert "recall" in reg and "commit" in reg

        # recall
        r_out, r_err = reg.invoke("recall", {"query": "龙湖", "limit": 3})
        assert r_err is None
        assert r_out["ok"] is True
        assert r_out["count"] >= 1
        assert any("龙湖" in (h.get("content") or "") for h in r_out["hits"])

        # commit writes straight through (no LLM)
        c_out, c_err = reg.invoke("commit", {
            "content": "米莱 11 岁爱打鼓", "type": "fact", "source": "harness-test",
        })
        assert c_err is None and c_out["ok"] is True
        hits2 = m.store.search_text("米莱", limit=5) or []
        assert len(hits2) >= 1

        # guard: empty query / content rejected, not raised
        e1, _ = reg.invoke("recall", {"query": "  "})
        assert e1["ok"] is False
        e2, _ = reg.invoke("commit", {"content": ""})
        assert e2["ok"] is False
        # guard: bad type rejected
        e3, _ = reg.invoke("commit", {"content": "x", "type": "zzz"})
        assert e3["ok"] is False
    print("  PASSED")


def test_builtins_fs_sandbox_jails_paths():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "jail"
        reg = ToolRegistry()
        n = register_builtins(reg, sandbox_root=root)  # no mindos → just fs
        assert n == 2
        assert "read_file" in reg and "write_file" in reg
        assert "recall" not in reg  # no mindos → no recall/commit

        # normal write + read round-trip
        w, werr = reg.invoke("write_file",
                             {"path": "notes/hi.txt", "content": "hello"})
        assert werr is None and w["ok"] is True and w["bytes"] == 5
        r, rerr = reg.invoke("read_file", {"path": "notes/hi.txt"})
        assert rerr is None and r["ok"] is True and r["content"] == "hello"

        # escape attempts rejected (fail-soft, not raised)
        for evil in ["../outside.txt", "/etc/passwd",
                     "notes/../../etc/passwd"]:
            out, err = reg.invoke("write_file", {"path": evil, "content": "x"})
            assert err is None
            assert out["ok"] is False, evil
        # still in jail
        assert not (Path(tmp) / "outside.txt").exists()

        # unknown file → fail-soft
        out, err = reg.invoke("read_file", {"path": "nope.txt"})
        assert err is None and out["ok"] is False
    print("  PASSED")


def test_builtins_allow_filter():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=Path(tmp) / "m", name="C", traits=["x"], style="y")
        reg = ToolRegistry()
        n = register_builtins(reg, mindos=m, allow={"recall"})
        assert n == 1 and "recall" in reg and "commit" not in reg
    print("  PASSED")


# -- skills.sh packages ----------------------------------------------------

def test_shipped_skills_dir_exists():
    d = shipped_skills_dir()
    assert d.exists() and d.is_dir()
    mds = list(d.rglob("SKILL.md"))
    assert len(mds) >= 2  # tdd-ship + personal-cache-audit
    names = {p.parent.name for p in mds}
    assert {"tdd-ship", "personal-cache-audit"}.issubset(names)
    print("  PASSED")


def test_load_single_skill_package_from_dir():
    reg = ToolRegistry()
    pkg = shipped_skills_dir() / "tdd-ship"
    name = load_skill_package(reg, pkg)
    assert name is not None
    assert len(reg) == 1
    spec = reg.specs()[0]
    assert spec.source.startswith("skills.sh:tdd-ship")
    assert "test-first" in spec.description.lower() or "tdd" in spec.name.lower()
    # advertise handler returns steps + name
    out, err = reg.invoke(name, {"input": "run it"})
    assert err is None
    assert out["skill_name"] == "tdd-ship"
    assert len(out["steps"]) >= 3
    assert "invoked_with" in out
    print("  PASSED")


def test_load_all_shipped_skills():
    reg = ToolRegistry()
    n = load_skill_dir(reg, shipped_skills_dir())
    assert n >= 2
    names = {s.name for s in reg.specs()}
    assert "tdd-ship" in names
    assert "personal-cache-audit" in names
    print("  PASSED")


def test_skill_package_missing_is_noop():
    reg = ToolRegistry()
    # Non-existent path
    assert load_skill_package(reg, "/tmp/does-not-exist-xyz") is None
    # Empty dir
    with tempfile.TemporaryDirectory() as tmp:
        assert load_skill_package(reg, tmp) is None
        # load_skill_dir on empty returns 0
        assert load_skill_dir(reg, tmp) == 0
    assert len(reg) == 0
    print("  PASSED")


def test_skill_package_from_zip():
    import zipfile
    with tempfile.TemporaryDirectory() as tmp:
        src = shipped_skills_dir() / "tdd-ship" / "SKILL.md"
        zp = Path(tmp) / "tdd-ship.zip"
        with zipfile.ZipFile(zp, "w") as zf:
            zf.writestr("SKILL.md", src.read_text(encoding="utf-8"))
        reg = ToolRegistry()
        name = load_skill_package(reg, zp)
        assert name is not None
        assert len(reg) == 1
    print("  PASSED")


# -- integration: harness runs with builtins + shipped skills --------------

def test_harness_with_builtins_and_shipped_skills():
    from mindos.harness import HarnessEngine, StubBackend
    from mindos.harness.models.base import ToolCallRequest

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        m = Mindos.init(path=root / "m", name="Captain",
                        traits=["builder"], style="direct")
        m.store.add(Memory(id="", type="episode",
                           content="shipping W2 today", source="t", confidence=1.0))
        snap = root / "snap"
        m.export_md(snap)

        reg = ToolRegistry()
        register_builtins(reg, mindos=m, sandbox_root=root / "scratch")
        load_skill_dir(reg, shipped_skills_dir())
        assert len(reg) >= 4  # recall + commit + read_file + write_file + >=2 skills

        # Script the stub to call recall then reply
        stub = StubBackend(
            tool_script=[[ToolCallRequest(id="u1", name="recall",
                                          arguments={"query": "W2"})]],
            reply="found it",
        )
        r = HarnessEngine(context_source=snap, model=stub, tools=reg).run("搜一下 W2")
        assert r.steps == 2
        assert r.tool_calls[0].name == "recall"
        assert r.tool_calls[0].error is None
        assert r.tool_calls[0].result["ok"] is True
        # fs tool round-trip
        stub2 = StubBackend(
            tool_script=[[ToolCallRequest(id="u2", name="write_file",
                                          arguments={"path": "note.md",
                                                     "content": "hi"})]],
            reply="wrote it",
        )
        r2 = HarnessEngine(context_source=snap, model=stub2, tools=reg).run("记一下")
        assert r2.tool_calls[0].error is None
        assert r2.tool_calls[0].result["ok"] is True
        assert (root / "scratch" / "note.md").read_text() == "hi"
    print("  PASSED")


if __name__ == "__main__":
    test_builtins_recall_and_commit_hit_real_store()
    test_builtins_fs_sandbox_jails_paths()
    test_builtins_allow_filter()
    test_shipped_skills_dir_exists()
    test_load_single_skill_package_from_dir()
    test_load_all_shipped_skills()
    test_skill_package_missing_is_noop()
    test_skill_package_from_zip()
    test_harness_with_builtins_and_shipped_skills()
    print("\n✔ harness W2: 9 tests passed")
