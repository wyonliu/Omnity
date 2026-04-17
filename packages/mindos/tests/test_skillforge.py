"""SkillForge — auto-distill task traces into portable SKILL.md playbooks."""

from __future__ import annotations

import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mindos.core import Mindos
from mindos.skillforge import Skill, SkillForge, _slugify, _trace_signature


# -- fixtures --------------------------------------------------------------

def _trace(goal: str = "Add JWT auth to /api/admin",
           n_calls: int = 6,
           outcome: str = "success") -> dict:
    tool_calls = [
        {"tool": "Read", "input": {"file_path": "main.py"}, "output": "# main"},
        {"tool": "Read", "input": {"file_path": "auth.py"}, "output": "# auth"},
        {"tool": "Grep", "input": {"query": "JWT"}, "output": "no matches"},
        {"tool": "Write", "input": {"file_path": "auth.py"}, "output": "ok"},
        {"tool": "Edit", "input": {"file_path": "main.py"}, "output": "ok"},
        {"tool": "Bash", "input": {"command": "pytest"}, "output": "10 passed"},
        {"tool": "Bash", "input": {"command": "git commit"}, "output": "committed"},
    ][:n_calls]
    return {
        "goal": goal,
        "tool_calls": tool_calls,
        "outcome": outcome,
        "summary": f"Completed: {goal}",
    }


# -- threshold behavior ----------------------------------------------------

def test_below_threshold_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        forge = SkillForge(m, use_llm=False)
        # Only 3 tool calls < default 5 → no skill
        sid = forge.forge(_trace(n_calls=3))
        assert sid is None
        assert forge.list() == []
    print("  PASSED")


def test_failure_outcome_returns_none():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        forge = SkillForge(m, use_llm=False)
        sid = forge.forge(_trace(outcome="failure"))
        assert sid is None
    print("  PASSED")


def test_success_above_threshold_forges():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        forge = SkillForge(m, use_llm=False)
        sid = forge.forge(_trace())
        assert sid is not None
        installed = forge.list()
        assert len(installed) == 1
        assert installed[0]["id"] == sid
        # Memory is also indexed
        skill_mems = m.store.search_text("Skill:")
        assert len(skill_mems) >= 1
    print("  PASSED")


def test_skill_md_is_well_formed():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        forge = SkillForge(m, use_llm=False)
        sid = forge.forge(_trace())
        skill_md = Path(tmp) / "skills" / sid / "SKILL.md"
        assert skill_md.exists()
        text = skill_md.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        assert "\n---\n" in text[4:]  # closing frontmatter
        assert "## Steps" in text
        # Round-trip parse
        skill = Skill.from_markdown(text, skill_id=sid)
        assert skill.name
        assert len(skill.steps) >= 3
        assert skill.trigger_keywords  # template derives keywords
    print("  PASSED")


def test_dedup_by_signature_bumps_version():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        forge = SkillForge(m, use_llm=False)
        sid1 = forge.forge(_trace())
        sid2 = forge.forge(_trace())
        sid3 = forge.forge(_trace())
        assert sid1 == sid2 == sid3  # same slug
        assert len(forge.list()) == 1
        skill = forge.get(sid1)
        assert skill.version == 3
    print("  PASSED")


def test_get_and_delete():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        forge = SkillForge(m, use_llm=False)
        sid = forge.forge(_trace())
        assert forge.get(sid) is not None
        assert forge.delete(sid) is True
        assert forge.get(sid) is None
        assert forge.list() == []
        assert forge.delete("does-not-exist") is False
    print("  PASSED")


# -- import / export -------------------------------------------------------

def test_export_produces_agentskills_zip():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        forge = SkillForge(m, use_llm=False)
        sid = forge.forge(_trace())
        out = Path(tmp) / "out"
        out.mkdir()
        zip_path = forge.export_skill(sid, out)
        assert zip_path.exists()
        assert zip_path.suffix == ".zip"
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            assert "SKILL.md" in names
            # And the content is valid markdown we wrote
            text = zf.read("SKILL.md").decode("utf-8")
            assert text.startswith("---\n")
    print("  PASSED")


def test_import_zip_round_trip():
    with tempfile.TemporaryDirectory() as tmp_src, tempfile.TemporaryDirectory() as tmp_dst:
        m_src = Mindos.init(path=tmp_src, name="Src")
        forge_src = SkillForge(m_src, use_llm=False)
        sid = forge_src.forge(_trace())
        zip_path = forge_src.export_skill(sid, Path(tmp_src) / f"{sid}.zip")

        m_dst = Mindos.init(path=tmp_dst, name="Dst")
        forge_dst = SkillForge(m_dst, use_llm=False)
        imported_sid = forge_dst.import_skill(zip_path)
        skill = forge_dst.get(imported_sid)
        assert skill is not None
        assert skill.steps == forge_src.get(sid).steps
        assert skill.trigger_keywords == forge_src.get(sid).trigger_keywords
    print("  PASSED")


def test_import_directory():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        forge = SkillForge(m, use_llm=False)
        # Hand-craft a skill directory
        skill_dir = Path(tmp) / "handmade"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: Write tests first\n"
            "description: TDD mini-playbook\n"
            "version: 1\n"
            "trigger_keywords: [test, tdd]\n"
            "---\n\n"
            "# Write tests first\n\n"
            "## When to use\n"
            "Any new feature.\n\n"
            "## Steps\n"
            "1. Write failing test\n"
            "2. Make it pass\n"
            "3. Refactor\n",
            encoding="utf-8",
        )
        sid = forge.import_skill(skill_dir)
        skill = forge.get(sid)
        assert skill.name == "Write tests first"
        assert "tdd" in skill.trigger_keywords
        assert len(skill.steps) == 3
    print("  PASSED")


def test_import_bare_md_file():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        forge = SkillForge(m, use_llm=False)
        md = Path(tmp) / "quick-skill.md"
        md.write_text(
            "---\nname: Quick Skill\ndescription: Imported from bare file\n---\n\n"
            "# Quick Skill\n\n## Steps\n1. Do thing\n2. Do next thing\n3. Done\n",
            encoding="utf-8",
        )
        sid = forge.import_skill(md)
        assert forge.get(sid).name == "Quick Skill"
    print("  PASSED")


def test_import_rejects_missing_source():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        forge = SkillForge(m, use_llm=False)
        try:
            forge.import_skill("/tmp/definitely-does-not-exist-abc999")
        except FileNotFoundError:
            print("  PASSED")
            return
        assert False, "expected FileNotFoundError"


def test_import_rejects_zip_without_skill_md():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        forge = SkillForge(m, use_llm=False)
        bad_zip = Path(tmp) / "bad.zip"
        with zipfile.ZipFile(bad_zip, "w") as zf:
            zf.writestr("README.md", "not a skill")
        try:
            forge.import_skill(bad_zip)
        except ValueError:
            print("  PASSED")
            return
        assert False, "expected ValueError"


# -- retrieval -------------------------------------------------------------

def test_match_returns_relevant_skills():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        forge = SkillForge(m, use_llm=False)
        forge.forge(_trace(goal="Add JWT auth to /api/admin"))
        forge.forge(_trace(goal="Deploy to Kubernetes cluster", n_calls=6))
        forge.forge(_trace(goal="Setup postgres database migration", n_calls=7))

        hits = forge.match("I need to add JWT authentication", top_k=3)
        assert hits
        assert "auth" in hits[0].name.lower() or "jwt" in hits[0].name.lower()

        # Context with no overlap → no hits
        assert forge.match("xyzzy qwerty nothing", top_k=3) == []
    print("  PASSED")


# -- mindos integration ----------------------------------------------------

def test_mindos_forge_skill_convenience():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        # Disable LLM for test
        m.skills.use_llm = False
        sid = m.forge_skill(_trace())
        assert sid is not None
        assert m.skills.get(sid) is not None
        # The shadow memory shows up in recall
        hits = m.recall("Skill", top_k=5)
        assert len(hits) >= 1
    print("  PASSED")


# -- pure helpers ----------------------------------------------------------

def test_slugify_and_signature():
    assert _slugify("Add JWT Auth!") == "add-jwt-auth"
    assert _slugify("   ") == "skill"
    sig1 = _trace_signature(_trace(goal="Goal A"))
    sig2 = _trace_signature(_trace(goal="Goal A"))  # same
    sig3 = _trace_signature(_trace(goal="Goal B"))  # different
    assert sig1 == sig2
    assert sig1 != sig3
    print("  PASSED")


if __name__ == "__main__":
    test_below_threshold_returns_none()
    test_failure_outcome_returns_none()
    test_success_above_threshold_forges()
    test_skill_md_is_well_formed()
    test_dedup_by_signature_bumps_version()
    test_get_and_delete()
    test_export_produces_agentskills_zip()
    test_import_zip_round_trip()
    test_import_directory()
    test_import_bare_md_file()
    test_import_rejects_missing_source()
    test_import_rejects_zip_without_skill_md()
    test_match_returns_relevant_skills()
    test_mindos_forge_skill_convenience()
    test_slugify_and_signature()
    print("\n✔ all SkillForge tests passed")
