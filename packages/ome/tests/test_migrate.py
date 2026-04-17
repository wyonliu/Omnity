"""Tests for ome.migrate — import competitors' history into an Ome."""

from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path

# Add both ome and mindos packages to path
_here = Path(__file__).resolve()
sys.path.insert(0, str(_here.parent.parent / "src"))
sys.path.insert(0, str(_here.parent.parent.parent / "mindos" / "src"))

from ome.core import Ome
from ome.migrate import MigrationRecord, SUPPORTED, migrate


# -- helpers --------------------------------------------------------------

def _ome(tmp: str) -> Ome:
    return Ome.create(path=tmp, name="U", traits=["curious"], style="direct")


def _chatgpt_fixture(path: Path) -> None:
    """Write a minimal OpenAI data-export style file."""
    path.write_text(json.dumps([
        {
            "id": "conv-1",
            "mapping": {
                "n1": {"message": {
                    "author": {"role": "user"},
                    "content": {"content_type": "text",
                                "parts": ["Hello from ChatGPT"]},
                    "create_time": 1700000000,
                }},
                "n2": {"message": {
                    "author": {"role": "assistant"},
                    "content": {"content_type": "text",
                                "parts": ["Hi — glad to help."]},
                    "create_time": 1700000001,
                }},
                "n3": {"message": {
                    "author": {"role": "system"},
                    "content": {"content_type": "text", "parts": ["(system note)"]},
                    "create_time": 1700000002,
                }},
                # A non-text node that should be skipped
                "n4": {"message": {
                    "author": {"role": "user"},
                    "content": {"content_type": "image",
                                "parts": ["ignored"]},
                    "create_time": 1700000003,
                }},
            },
        }
    ], ensure_ascii=False), encoding="utf-8")


def _claude_fixture_zip(path: Path) -> None:
    payload = json.dumps([
        {
            "uuid": "claude-conv-1",
            "name": "Test chat",
            "chat_messages": [
                {"sender": "human",
                 "text": "Hi Claude!", "created_at": "2026-01-01T10:00:00Z"},
                {"sender": "assistant",
                 "text": "Hello! How can I help?",
                 "created_at": "2026-01-01T10:00:05Z"},
                # List-of-blocks style
                {"sender": "assistant",
                 "text": [{"text": "Second block"}, {"text": " continued."}],
                 "created_at": "2026-01-01T10:00:10Z"},
            ],
        }
    ])
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("conversations.json", payload)


def _hermes_fixture(dir_path: Path) -> None:
    (dir_path / "m1.json").write_text(json.dumps(
        {"id": "1", "kind": "user", "content": "Remember: I love typescript",
         "created_at": "2025-12-31T08:00:00Z"}
    ), encoding="utf-8")
    (dir_path / "m2.json").write_text(json.dumps(
        {"id": "2", "type": "note",
         "text": "Use pnpm for this repo", "ts": 1700001234}
    ), encoding="utf-8")
    # A multi-item array
    (dir_path / "m3.json").write_text(json.dumps([
        {"content": "first array item", "kind": "user"},
        {"content": "second array item"},
    ]), encoding="utf-8")
    # Bad file — must not abort the run
    (dir_path / "bad.json").write_text("{not json", encoding="utf-8")


def _jsonl_fixture(path: Path) -> None:
    lines = [
        json.dumps({"role": "user", "content": "How do I ship a product?"}),
        json.dumps({"role": "assistant", "content": "Start with customers."}),
        "",                                           # blank line
        "{bad json",                                  # malformed
        json.dumps({"speaker": "human",
                    "message": "Third message",
                    "ts": 1700100000}),
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


# -- tests ----------------------------------------------------------------

def test_supported_sources_listed():
    assert set(SUPPORTED) >= {"chatgpt", "claude", "hermes", "jsonl", "mindos", "chat"}
    print("  PASSED")


def test_unknown_source_raises():
    with tempfile.TemporaryDirectory() as tmp:
        with _ome(tmp) as ome:
            try:
                migrate(ome, "deepseek", tmp)
            except ValueError:
                print("  PASSED")
                return
    raise AssertionError("expected ValueError")


def test_missing_path_raises():
    with tempfile.TemporaryDirectory() as tmp:
        with _ome(tmp) as ome:
            try:
                migrate(ome, "jsonl", "/tmp/does-not-exist-999")
            except FileNotFoundError:
                print("  PASSED")
                return
    raise AssertionError("expected FileNotFoundError")


def test_chatgpt_import():
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "conversations.json"
        _chatgpt_fixture(src)
        with _ome(tmp) as ome:
            before = ome.soul.store.stats()["total_memories"]
            r = migrate(ome, "chatgpt", src)
            after = ome.soul.store.stats()["total_memories"]
            # 3 text records (user + assistant + system), image skipped
            assert r.total_records == 3, r
            assert r.committed == 3
            assert r.conversations == 1
            assert after >= before
    print("  PASSED")


def test_chatgpt_dry_run_commits_nothing():
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "conversations.json"
        _chatgpt_fixture(src)
        with _ome(tmp) as ome:
            before = ome.soul.store.stats()["total_memories"]
            r = migrate(ome, "chatgpt", src, dry_run=True)
            after = ome.soul.store.stats()["total_memories"]
            assert r.committed == 3
            assert before == after  # nothing persisted
    print("  PASSED")


def test_claude_zip_import():
    with tempfile.TemporaryDirectory() as tmp:
        zp = Path(tmp) / "claude-export.zip"
        _claude_fixture_zip(zp)
        with _ome(tmp) as ome:
            r = migrate(ome, "claude", zp)
            assert r.total_records == 3
            assert r.committed == 3
            assert r.conversations == 1
    print("  PASSED")


def test_hermes_directory_import_tolerates_bad_files():
    with tempfile.TemporaryDirectory() as tmp:
        hermes_dir = Path(tmp) / "hermes"
        hermes_dir.mkdir()
        _hermes_fixture(hermes_dir)
        with _ome(tmp) as ome:
            r = migrate(ome, "hermes", hermes_dir)
            # 2 (m1, m2) + 2 (m3 array) = 4 good
            assert r.total_records == 4, r
            assert r.committed == 4
            assert r.errors, "expected at least one parse error for bad.json"
    print("  PASSED")


def test_jsonl_import_tolerates_bad_lines():
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "log.jsonl"
        _jsonl_fixture(src)
        with _ome(tmp) as ome:
            r = migrate(ome, "jsonl", src)
            # 3 good records (2 good + "third" with speaker=human)
            assert r.total_records == 3, r
            assert r.committed == 3
            assert r.errors  # malformed line recorded
    print("  PASSED")


def test_chat_plain_text_import():
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "chat.txt"
        src.write_text("hello\nhow are you\nlet's ship\n", encoding="utf-8")
        with _ome(tmp) as ome:
            r = migrate(ome, "chat", src)
            assert r.total_records >= 3
            assert r.committed >= 3
    print("  PASSED")


def test_mindos_snapshot_round_trip():
    with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
        # Build a Mindos, populate, dump
        with _ome(tmp_a) as source_ome:
            source_ome.remember("user: I love typescript.")
            source_ome.remember("user: I work at Omnity.")
            dump_dir = Path(tmp_a) / "dump"
            source_ome.soul.export_md(dump_dir)

        # Fresh Ome B, migrate from dump
        with _ome(tmp_b) as target_ome:
            before = target_ome.soul.store.stats()["total_memories"]
            r = migrate(target_ome, "mindos", dump_dir)
            after = target_ome.soul.store.stats()["total_memories"]
            assert r.total_records > 0
            assert r.committed > 0
            assert after >= before
    print("  PASSED")


def test_batch_size_and_max_records():
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "log.jsonl"
        rows = [json.dumps({"role": "user", "content": f"msg-{i}"})
                for i in range(20)]
        src.write_text("\n".join(rows), encoding="utf-8")
        with _ome(tmp) as ome:
            r = migrate(ome, "jsonl", src, batch_size=3, max_records=10)
            assert r.committed == 10  # stops exactly at cap
    print("  PASSED")


def test_migration_records_evo_log_breadcrumb():
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "log.jsonl"
        src.write_text(json.dumps({"role": "user", "content": "hi"}) + "\n",
                       encoding="utf-8")
        with _ome(tmp) as ome:
            migrate(ome, "jsonl", src)
            timeline = ome.soul.evo_timeline(event_types=["migrated"])
            assert len(timeline) == 1
            assert timeline[0]["details"]["source"] == "jsonl"
    print("  PASSED")


def test_migration_record_dataclass():
    r = MigrationRecord(role="user", content="hello")
    assert r.as_commit() == "user: hello"
    r2 = MigrationRecord(role="assistant", content="  hi\n\n")
    assert r2.as_commit() == "assistant: hi"
    print("  PASSED")


if __name__ == "__main__":
    test_supported_sources_listed()
    test_unknown_source_raises()
    test_missing_path_raises()
    test_chatgpt_import()
    test_chatgpt_dry_run_commits_nothing()
    test_claude_zip_import()
    test_hermes_directory_import_tolerates_bad_files()
    test_jsonl_import_tolerates_bad_lines()
    test_chat_plain_text_import()
    test_mindos_snapshot_round_trip()
    test_batch_size_and_max_records()
    test_migration_records_evo_log_breadcrumb()
    test_migration_record_dataclass()
    print("\n✔ all OmeMigrate tests passed")
