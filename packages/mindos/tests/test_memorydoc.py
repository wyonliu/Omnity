"""MemoryDoc — export/import Mindos as human-readable markdown."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import yaml

from mindos.core import Mindos
from mindos.store import Memory, Triple
from mindos.memorydoc import _parse_meta_comment, _strip_frontmatter


# -- helpers ----------------------------------------------------------------

def _seed(m: Mindos) -> None:
    """Seed a Mindos with a known mix of memories across all four markdown targets."""
    m.store.add(Memory(
        id="", type="episode", content="Met Bob at the conference today.",
        source="claude", confidence=0.9,
    ))
    m.store.add(Memory(
        id="", type="skill", content="Learned FastAPI dependency injection.",
        source="direct", confidence=0.85,
    ))
    m.store.add(Memory(
        id="", type="preference", content="Prefers cold brew over hot coffee.",
        source="inferred", confidence=0.95,
    ))
    m.store.add(Memory(
        id="", type="fact", content="Birthday is August 12.",
        source="user", confidence=1.0,
    ))
    m.store.add(Memory(
        id="", type="relation", content="Bob is co-founder at XiseeTech.",
        source="user", confidence=0.9,
    ))
    m.store.add_triple(Triple("User", "likes", "coffee"))
    m.store.add_triple(Triple("User", "visited", "Tokyo"))


# -- export ----------------------------------------------------------------

def test_export_writes_all_files():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="Alice", traits=["curious", "precise"],
                        style="concise", values=["honesty"])
        _seed(m)

        out = Path(tmp) / "doc"
        result = m.export_md(out)

        assert set(result["files"]) == {
            "IDENTITY.md", "MEMORY.md", "FACTS.md", "SOUL.md", "KG.json"
        }
        for fname in result["files"]:
            assert (out / fname).exists(), f"missing {fname}"
        assert result["memories"] >= 2   # episode + skill
        assert result["facts"] >= 3      # preference + fact + relation
        assert result["triples"] == 2
    print("  PASSED")


def test_export_identity_content():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="Alice",
                        traits=["curious", "precise"],
                        style="concise and direct",
                        values=["honesty", "growth"])
        out = Path(tmp) / "doc"
        m.export_md(out)

        text = (out / "IDENTITY.md").read_text(encoding="utf-8")
        fm, body = _strip_frontmatter(text)
        assert fm["file_type"] == "identity"
        assert fm["export_version"] >= 1
        assert "# Alice" in body
        assert "curious" in body
        assert "precise" in body
        assert "concise and direct" in body
        assert "honesty" in body
    print("  PASSED")


def test_export_memory_groups_narrative_and_facts():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="B")
        _seed(m)
        out = Path(tmp) / "doc"
        m.export_md(out)

        memory_text = (out / "MEMORY.md").read_text(encoding="utf-8")
        facts_text = (out / "FACTS.md").read_text(encoding="utf-8")

        # Narrative → MEMORY.md
        assert "Met Bob at the conference" in memory_text
        assert "FastAPI" in memory_text
        # Structured → FACTS.md
        assert "cold brew" in facts_text
        assert "August 12" in facts_text
        assert "XiseeTech" in facts_text

        # And they're NOT crossed
        assert "cold brew" not in memory_text
        assert "Met Bob" not in facts_text
    print("  PASSED")


def test_export_frontmatter_parses_as_yaml():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="C")
        _seed(m)
        out = Path(tmp) / "doc"
        m.export_md(out)
        for fname in ["IDENTITY.md", "MEMORY.md", "FACTS.md", "SOUL.md"]:
            text = (out / fname).read_text(encoding="utf-8")
            fm, _ = _strip_frontmatter(text)
            assert fm, f"{fname}: empty frontmatter"
            assert "mindos_version" in fm
            assert "file_type" in fm
            # Explicit re-parse to confirm valid YAML
            _ = yaml.safe_load(
                text.split("---\n", 2)[1]
            )
    print("  PASSED")


def test_export_kg_json_structure():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="D")
        m.store.add_triple(Triple("Alice", "knows", "Bob"))
        m.store.add_triple(Triple("Alice", "works_at", "Acme"))
        out = Path(tmp) / "doc"
        m.export_md(out)
        data = json.loads((out / "KG.json").read_text(encoding="utf-8"))
        assert len(data["triples"]) == 2
        subjects = {t["subject"] for t in data["triples"]}
        assert "Alice" in subjects
    print("  PASSED")


def test_export_soul_with_constitution():
    from mindos.constitution import Constitution, ConstitutionRule

    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="E", traits=["honest"])
        m.layers.l4.constitution = Constitution([
            ConstitutionRule("honest-locked", "trait_immutable", "honest", {}),
            ConstitutionRule("slow-change", "max_delta", "*", {"delta": 0.1}),
        ])
        out = Path(tmp) / "doc"
        m.export_md(out)
        soul = (out / "SOUL.md").read_text(encoding="utf-8")
        assert "honest-locked" in soul
        assert "trait_immutable" in soul
        assert "slow-change" in soul
    print("  PASSED")


# -- import ----------------------------------------------------------------

def test_import_identity():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="OldName", traits=["old"])
        out = Path(tmp) / "doc"
        m.export_md(out)

        # Hand-edit IDENTITY.md to change the name
        ident_path = out / "IDENTITY.md"
        text = ident_path.read_text(encoding="utf-8")
        text = text.replace("# OldName", "# NewName")
        text = text.replace("- old", "- old\n- bold")
        ident_path.write_text(text, encoding="utf-8")

        report = m.import_md(out)
        assert report["identity_updated"] is True
        assert m.identity["name"] == "NewName"
        assert "bold" in m.identity["personality"]["traits"]
    print("  PASSED")


def test_round_trip_preserves_memories():
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        # Soul A: seed and export
        a = Mindos.init(path=tmp_a, name="Origin")
        _seed(a)
        before_total = a.store.count()
        out = Path(tmp_a) / "doc"
        a.export_md(out)

        # Soul B: fresh init, then import
        b = Mindos.init(path=tmp_b, name="Target")
        report = b.import_md(out)

        assert report["memories_imported"] >= 2
        assert report["facts_imported"] >= 3
        assert report["triples_imported"] == 2

        # Verify content landed
        assert len(b.store.search_text("cold brew")) == 1
        assert len(b.store.search_text("FastAPI")) == 1
        assert len(b.store.search_text("XiseeTech")) == 1
        # Imported set should be >= what we wrote (identity seeds 0 memories)
        assert b.store.count() >= before_total
    print("  PASSED")


def test_upsert_does_not_duplicate():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="U")
        m.store.add(Memory(id="fixed-id-1", type="episode",
                           content="Stable memory", confidence=0.8))
        out = Path(tmp) / "doc"
        m.export_md(out)

        count_before = m.store.count()
        m.import_md(out, merge_mode="upsert")
        m.import_md(out, merge_mode="upsert")
        m.import_md(out, merge_mode="upsert")
        # Re-importing the same export 3 times must not duplicate.
        assert m.store.count() == count_before
    print("  PASSED")


def test_append_generates_fresh_ids():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="A")
        m.store.add(Memory(id="src-id", type="episode",
                           content="Appendable memory", confidence=0.8))
        out = Path(tmp) / "doc"
        m.export_md(out)
        count_before = m.store.count()
        m.import_md(out, merge_mode="append")
        assert m.store.count() > count_before  # Fresh IDs → duplicate row
    print("  PASSED")


def test_partial_import_is_allowed():
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        a = Mindos.init(path=tmp_a, name="P")
        _seed(a)
        out = Path(tmp_a) / "doc"
        a.export_md(out)
        # Remove everything except FACTS.md
        (out / "IDENTITY.md").unlink()
        (out / "MEMORY.md").unlink()
        (out / "SOUL.md").unlink()
        (out / "KG.json").unlink()

        b = Mindos.init(path=tmp_b, name="Q")
        report = b.import_md(out)
        assert report["identity_updated"] is False
        assert report["memories_imported"] == 0
        assert report["facts_imported"] >= 3
        assert report["triples_imported"] == 0
    print("  PASSED")


def test_meta_comment_roundtrip():
    meta = _parse_meta_comment(
        "- content here  <!-- id:abc123 source:claude decay:0.95 conf:0.9 -->"
    )
    assert meta == {"id": "abc123", "source": "claude",
                    "decay": "0.95", "conf": "0.9"}
    # Garbage in → empty dict, no crash
    assert _parse_meta_comment("no meta here") == {}
    assert _parse_meta_comment("<!-- garbage -->") == {}
    print("  PASSED")


def test_missing_dir_raises():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="X")
        try:
            m.import_md("/tmp/definitely-does-not-exist-999999")
        except FileNotFoundError:
            print("  PASSED")
            return
        assert False, "expected FileNotFoundError"


def test_invalid_merge_mode_raises():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="Y")
        out = Path(tmp) / "doc"
        m.export_md(out)
        try:
            m.import_md(out, merge_mode="bogus")
        except ValueError:
            print("  PASSED")
            return
        assert False, "expected ValueError"


if __name__ == "__main__":
    test_export_writes_all_files()
    test_export_identity_content()
    test_export_memory_groups_narrative_and_facts()
    test_export_frontmatter_parses_as_yaml()
    test_export_kg_json_structure()
    test_export_soul_with_constitution()
    test_import_identity()
    test_round_trip_preserves_memories()
    test_upsert_does_not_duplicate()
    test_append_generates_fresh_ids()
    test_partial_import_is_allowed()
    test_meta_comment_roundtrip()
    test_missing_dir_raises()
    test_invalid_merge_mode_raises()
    print("\n✔ all MemoryDoc tests passed")
