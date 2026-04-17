"""Day 1 of your AI — the five-minute viral demo.

Walks through the whole 0.8 story in one script:

    1. Spin up a fresh Ome
    2. Migrate ChatGPT history
    3. Forge a skill from a successful task trace
    4. Dump a human-readable snapshot you can `git init` on
    5. Peek at the evolution timeline
    6. Route a message through OmeGate as Telegram would

Run:
    python day1_viral_demo.py

No API keys required — everything runs locally on your machine.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ome.core import Ome
from ome.gateway import (
    BindingRegistry, GatewayRunner, IncomingMessage,
)
from ome.gateway.base import GatewayAdapter
from ome.migrate import migrate


def _hr(title: str) -> None:
    print(f"\n── {title} " + "─" * (60 - len(title)))


def _fake_chatgpt(path: Path) -> None:
    path.write_text(json.dumps([{
        "id": "c-1",
        "mapping": {
            "n1": {"message": {
                "author": {"role": "user"},
                "content": {"content_type": "text",
                            "parts": ["I ship side projects every weekend."]},
                "create_time": 1}},
            "n2": {"message": {
                "author": {"role": "assistant"},
                "content": {"content_type": "text",
                            "parts": ["What's your stack?"]},
                "create_time": 2}},
            "n3": {"message": {
                "author": {"role": "user"},
                "content": {"content_type": "text",
                            "parts": ["FastAPI + SQLite. I live and die by TDD."]},
                "create_time": 3}},
        }}]), encoding="utf-8")


def _task_trace() -> dict:
    return {
        "goal": "Ship a /health endpoint with tests-first discipline",
        "outcome": "success",
        "summary": "Wrote failing test, implemented handler, all green, pushed.",
        "tool_calls": [
            {"tool": "Write", "input": {"file_path": "tests/test_health.py"}, "output": "ok"},
            {"tool": "Bash",  "input": {"command": "pytest"}, "output": "1 failing"},
            {"tool": "Write", "input": {"file_path": "app/routes.py"}, "output": "ok"},
            {"tool": "Bash",  "input": {"command": "pytest"}, "output": "10 passed"},
            {"tool": "Edit",  "input": {"file_path": "README.md"}, "output": "ok"},
            {"tool": "Bash",  "input": {"command": "git push"}, "output": "pushed"},
        ],
    }


class _PretendAdapter(GatewayAdapter):
    platform = "telegram"
    def __init__(self, messages): super().__init__(); self.inbox = messages; self.outbox = []
    def start(self, handler):
        for m in self.inbox:
            r = handler(m, None)
            if r: self.outbox.append(r)
    def send(self, msg): self.outbox.append(msg)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        ome_home = tmp / "my-ome"
        snapshot = tmp / "snapshot"
        chatgpt  = tmp / "conversations.json"
        _fake_chatgpt(chatgpt)

        _hr("1. Create your Ome")
        ome = Ome.create(path=ome_home, name="Captain",
                         traits=["curious", "direct"], style="terse tech")
        print(f"  ✔ Ome created at {ome_home}")

        _hr("2. Migrate ChatGPT history")
        report = migrate(ome, "chatgpt", chatgpt)
        print(f"  ✔ Imported {report.committed} messages "
              f"from {report.conversations} conversation(s)")

        _hr("3. Forge a skill from a task trace")
        ome.soul.skills.use_llm = False
        sid = ome.soul.forge_skill(_task_trace())
        skill = ome.soul.skills.get(sid)
        print(f"  ✔ Forged skill id={sid}")
        print(f"      name   : {skill.name}")
        print(f"      v{skill.version}, {len(skill.steps)} steps")
        print(f"      keywords: {', '.join(skill.trigger_keywords[:6])}")

        _hr("4. Dump the soul as git-diffable markdown")
        dump = ome.soul.export_md(snapshot)
        print(f"  ✔ Wrote {len(dump['files'])} files to {snapshot}")
        for f in dump["files"][:6]:
            print(f"      {f}")
        print("     Tip: `git init && git add . && git commit -m 'day 1 of my AI'`")

        _hr("5. Your evolution timeline")
        for row in ome.soul.evo_timeline(limit=10):
            print(f"  • {row['event_type']:18s}  {row['summary']}")
        print(f"  stats: {ome.soul.evo_stats()['by_type']}")

        _hr("6. Serve this same Ome on Telegram (simulated)")
        registry = BindingRegistry(tmp / "gw.json")
        registry.bind("telegram", "42", ome_home)
        runner = GatewayRunner(
            registry=registry, default_ome_path=ome_home,
            ome_factory=lambda _p: _DemoChat(),
        )
        adapter = _PretendAdapter([
            IncomingMessage(platform="telegram", platform_user_id="42",
                            text="remind me what I'm into",
                            chat_id="42", message_id="1"),
            IncomingMessage(platform="telegram", platform_user_id="777",
                            text="/help", chat_id="777", message_id="2"),
        ])
        runner.run(adapter)
        for out in adapter.outbox:
            print(f"  → chat {out.chat_id}: {out.text[:80]}")

        print("\n  That's day 1. Your AI follows you across platforms,")
        print("  grows visibly, and lives inside a git repo you own.")
        ome.close()


class _DemoChat:
    """Light stand-in so the demo runs with no network / LLM key."""
    def chat(self, text: str) -> str:
        return f"[demo] got: {text!r}"


if __name__ == "__main__":
    main()
