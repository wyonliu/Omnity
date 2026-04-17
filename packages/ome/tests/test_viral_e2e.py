"""End-to-end integration: the full 'day 1 of your AI' story.

Proves the five v0.8 features compose into a single user journey:

    1. OmeMigrate  — user imports their ChatGPT history
    2. SkillForge  — a task trace distills into SKILL.md
    3. MemoryDoc   — the whole soul rounds-trips to markdown + git-diffable
    4. EvoLog      — every meaningful evolution event is auditable
    5. OmeGate     — the same soul answers on a messaging platform
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_here = Path(__file__).resolve()
sys.path.insert(0, str(_here.parent.parent / "src"))
sys.path.insert(0, str(_here.parent.parent.parent / "mindos" / "src"))

from ome.core import Ome
from ome.gateway import (
    BindingRegistry,
    GatewayRunner,
    IncomingMessage,
    OutgoingMessage,
)
from ome.gateway.base import GatewayAdapter
from ome.migrate import migrate


# -- helpers ---------------------------------------------------------------

def _fake_chatgpt_export(path: Path) -> None:
    path.write_text(json.dumps([{
        "id": "c-1",
        "mapping": {
            "n1": {"message": {
                "author": {"role": "user"},
                "content": {"content_type": "text",
                            "parts": ["I ship side projects every weekend."]},
                "create_time": 1,
            }},
            "n2": {"message": {
                "author": {"role": "assistant"},
                "content": {"content_type": "text",
                            "parts": ["Nice — what's the stack?"]},
                "create_time": 2,
            }},
            "n3": {"message": {
                "author": {"role": "user"},
                "content": {"content_type": "text",
                            "parts": ["FastAPI + SQLite. Obsession w/ TDD."]},
                "create_time": 3,
            }},
        },
    }]), encoding="utf-8")


def _task_trace() -> dict:
    return {
        "goal": "Ship a new side-project endpoint with tests first",
        "outcome": "success",
        "tool_calls": [
            {"tool": "Write", "input": {"file_path": "tests/test_health.py"},
             "output": "ok"},
            {"tool": "Bash", "input": {"command": "pytest tests/test_health.py"},
             "output": "1 passed"},
            {"tool": "Write", "input": {"file_path": "app/routes.py"},
             "output": "ok"},
            {"tool": "Bash", "input": {"command": "pytest"},
             "output": "10 passed"},
            {"tool": "Edit", "input": {"file_path": "README.md"},
             "output": "ok"},
            {"tool": "Bash", "input": {"command": "git push"},
             "output": "pushed"},
        ],
        "summary": "TDD-first, pushed after green.",
    }


class _ScriptedAdapter(GatewayAdapter):
    platform = "telegram"
    def __init__(self, inbox):
        super().__init__()
        self.inbox = list(inbox)
        self.outbox: list[OutgoingMessage] = []
    def start(self, handler):
        for m in self.inbox:
            reply = handler(m, None)
            if reply:
                self.outbox.append(reply)
    def send(self, msg):
        self.outbox.append(msg)


# -- the big one -----------------------------------------------------------

def test_day1_full_journey():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        ome_home = tmp_path / "ome"
        export_dir = tmp_path / "snapshot"
        chatgpt_dump = tmp_path / "conversations.json"
        registry_path = tmp_path / "gw.json"

        _fake_chatgpt_export(chatgpt_dump)

        # --- Step 1: create Ome ------------------------------------------
        ome = Ome.create(path=ome_home, name="Captain",
                         traits=["curious", "direct"], style="no-bullshit")
        assert ome.soul.evo_timeline() == []

        # --- Step 2: OmeMigrate from ChatGPT ------------------------------
        report = migrate(ome, "chatgpt", chatgpt_dump)
        assert report.committed == 3, report
        mem_count_after_migrate = ome.soul.store.stats()["total_memories"]
        assert mem_count_after_migrate > 0

        # EvoLog captured the migration
        migrated = ome.soul.evo_timeline(event_types=["migrated"])
        assert len(migrated) == 1
        assert migrated[0]["details"]["source"] == "chatgpt"

        # --- Step 3: SkillForge on a successful task trace ---------------
        ome.soul.skills.use_llm = False          # deterministic in CI
        sid = ome.soul.forge_skill(_task_trace())
        assert sid is not None
        assert ome.soul.skills.get(sid) is not None

        # EvoLog also caught the skill_forged event
        forged = ome.soul.evo_timeline(event_types=["skill_forged"])
        assert len(forged) == 1
        assert forged[0]["details"]["skill_id"] == sid

        # --- Step 4: MemoryDoc export/import round-trip ------------------
        dump = ome.soul.export_md(export_dir)
        assert (export_dir / "IDENTITY.md").exists()
        assert (export_dir / "MEMORY.md").exists()
        assert dump["memories"] > 0

        # Fresh soul in a new directory imports the dump cleanly.
        restored_home = tmp_path / "restored"
        restored = Ome.create(path=restored_home, name="Shadow")
        restored.soul.import_md(export_dir)
        assert restored.soul.store.stats()["total_memories"] > 0

        # --- Step 5: OmeGate routes messages to the bound Ome ------------
        registry = BindingRegistry(registry_path)
        registry.bind("telegram", "42", ome_home)

        captured: list[str] = []
        class RouteOme:
            def chat(self, text):
                captured.append(text)
                return f"captain says: {text}"

        runner = GatewayRunner(
            registry=registry,
            default_ome_path=ome_home,
            ome_factory=lambda _p: RouteOme(),
        )
        adapter = _ScriptedAdapter([
            IncomingMessage(platform="telegram", platform_user_id="42",
                            text="what did I teach you?", chat_id="42",
                            message_id="1", user_display_name="me"),
            IncomingMessage(platform="telegram", platform_user_id="99",
                            text="/help", chat_id="99",
                            message_id="2", user_display_name="other"),
        ])
        runner.run(adapter)

        # Bound user went through → captured on the Ome side
        assert captured == ["what did I teach you?"]
        # Unbound user got the bind prompt
        assert "/bind" in adapter.outbox[1].text or "commands" in adapter.outbox[1].text.lower()

        # --- Cross-check: evo stats now show a growth story -------------
        stats = ome.soul.evo_stats()
        assert stats["total"] >= 2
        assert "migrated" in stats["by_type"]
        assert "skill_forged" in stats["by_type"]

        ome.close()
        restored.close()
    print("  PASSED")


if __name__ == "__main__":
    test_day1_full_journey()
    print("\n✔ day-1 full journey passes")
