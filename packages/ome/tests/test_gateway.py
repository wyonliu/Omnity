"""Tests for ome.gateway — OmeGate multi-platform bridge."""

from __future__ import annotations

import sys
import tempfile
import threading
import time
from pathlib import Path

_here = Path(__file__).resolve()
sys.path.insert(0, str(_here.parent.parent / "src"))
sys.path.insert(0, str(_here.parent.parent.parent / "mindos" / "src"))

from ome.core import Ome
from ome.gateway import (
    BindingRegistry,
    GatewayAdapter,
    GatewayRunner,
    IncomingMessage,
    OutgoingMessage,
    TelegramAdapter,
)


# -- BindingRegistry -------------------------------------------------------

def test_binding_registry_crud():
    with tempfile.TemporaryDirectory() as tmp:
        reg_path = Path(tmp) / "reg" / "bindings.json"
        reg = BindingRegistry(reg_path)
        assert reg.resolve("telegram", "123") is None
        reg.bind("telegram", "123", "/tmp/ome-a")
        reg.bind("telegram", "456", "/tmp/ome-b")
        reg.bind("slack", "U1", "/tmp/ome-c")
        assert reg.resolve("telegram", "123") == Path("/tmp/ome-a")
        assert sorted(reg.list()) == [
            ("slack", "U1", "/tmp/ome-c"),
            ("telegram", "123", "/tmp/ome-a"),
            ("telegram", "456", "/tmp/ome-b"),
        ]
        assert reg.unbind("telegram", "123") is True
        assert reg.unbind("telegram", "999") is False
        assert reg.resolve("telegram", "123") is None

        # Round-trip via disk
        reg2 = BindingRegistry(reg_path)
        assert reg2.resolve("telegram", "456") == Path("/tmp/ome-b")
    print("  PASSED")


# -- TelegramAdapter.parse_update -----------------------------------------

def test_telegram_parse_update_text():
    tg = TelegramAdapter("dummy-token", transport=lambda *a: {"ok": True})
    inc = tg.parse_update({
        "update_id": 7,
        "message": {
            "message_id": 42,
            "text": "Hello!",
            "from": {"id": 100, "username": "alice"},
            "chat": {"id": 100},
        },
    })
    assert inc is not None
    assert inc.platform == "telegram"
    assert inc.platform_user_id == "100"
    assert inc.chat_id == "100"
    assert inc.text == "Hello!"
    assert inc.user_display_name == "alice"
    print("  PASSED")


def test_telegram_parse_update_skips_non_text():
    tg = TelegramAdapter("t", transport=lambda *a: {"ok": True})
    assert tg.parse_update({"update_id": 1, "message": {
        "from": {"id": 1}, "chat": {"id": 1}
    }}) is None
    assert tg.parse_update({"update_id": 2}) is None
    print("  PASSED")


def test_telegram_parse_update_accepts_caption_and_edited():
    tg = TelegramAdapter("t", transport=lambda *a: {"ok": True})
    inc = tg.parse_update({
        "update_id": 10,
        "edited_message": {
            "message_id": 1, "caption": "with caption",
            "from": {"id": 5, "first_name": "Bob", "last_name": "O"},
            "chat": {"id": 5},
        },
    })
    assert inc is not None
    assert inc.text == "with caption"
    assert inc.user_display_name == "Bob O"
    print("  PASSED")


def test_telegram_missing_token_raises():
    try:
        TelegramAdapter("")
    except ValueError:
        print("  PASSED")
        return
    raise AssertionError("expected ValueError")


def test_telegram_send_calls_transport():
    calls: list[tuple[str, dict]] = []
    tg = TelegramAdapter(
        "t", transport=lambda m, p: (calls.append((m, p)) or {"ok": True}),
    )
    tg.send(OutgoingMessage(chat_id="42", text="hi",
                            reply_to_message_id="7"))
    assert calls == [("sendMessage", {"chat_id": "42", "text": "hi",
                                       "reply_to_message_id": "7"})]
    print("  PASSED")


# -- End-to-end using a FakeAdapter ---------------------------------------

class FakeAdapter(GatewayAdapter):
    """Scripted adapter for deterministic tests."""
    platform = "telegram"

    def __init__(self, incoming: list[IncomingMessage]):
        super().__init__()
        self.incoming = list(incoming)
        self.sent: list[OutgoingMessage] = []

    def start(self, handler):
        for msg in self.incoming:
            out = handler(msg, None)
            if out:
                self.sent.append(out)

    def send(self, msg):
        self.sent.append(msg)


def _msg(uid="1", text="hi", platform="telegram") -> IncomingMessage:
    return IncomingMessage(platform=platform, platform_user_id=uid,
                           text=text, chat_id=uid, message_id="m1",
                           user_display_name="user")


def test_runner_unbound_user_gets_prompt():
    with tempfile.TemporaryDirectory() as tmp:
        runner = GatewayRunner(
            registry=BindingRegistry(Path(tmp) / "reg.json"),
            default_ome_path=tmp, allow_auto_bind=False,
        )
        adapter = FakeAdapter([_msg(text="Hi")])
        runner.attach(adapter)
        runner.run(adapter)
        assert len(adapter.sent) == 1
        assert "/bind" in adapter.sent[0].text
    print("  PASSED")


def test_runner_help_command():
    with tempfile.TemporaryDirectory() as tmp:
        runner = GatewayRunner(
            registry=BindingRegistry(Path(tmp) / "reg.json"),
            default_ome_path=tmp,
        )
        adapter = FakeAdapter([_msg(text="/help")])
        runner.run(adapter)
        assert "commands" in adapter.sent[0].text.lower()
    print("  PASSED")


def test_runner_bind_unbind_cycle():
    with tempfile.TemporaryDirectory() as tmp:
        ome_path = Path(tmp) / "alice-ome"
        Ome.create(path=ome_path, name="Alice",
                   traits=["curious"], style="direct").close()

        registry = BindingRegistry(Path(tmp) / "reg.json")
        runner = GatewayRunner(registry=registry, default_ome_path=ome_path)
        adapter = FakeAdapter([
            _msg(text=f"/bind {ome_path}"),
            _msg(text="/unbind"),
            _msg(text="/unbind"),  # second unbind reports "not bound"
        ])
        runner.run(adapter)
        assert "Bound to Ome" in adapter.sent[0].text
        assert "Unbound" in adapter.sent[1].text
        assert "weren't bound" in adapter.sent[2].text
    print("  PASSED")


def test_runner_bind_to_missing_ome_returns_error():
    with tempfile.TemporaryDirectory() as tmp:
        registry = BindingRegistry(Path(tmp) / "reg.json")
        runner = GatewayRunner(registry=registry, default_ome_path=tmp)
        adapter = FakeAdapter([_msg(text="/bind /definitely-not-a-path-xyz")])
        runner.run(adapter)
        assert "No Ome" in adapter.sent[0].text
    print("  PASSED")


def test_runner_routes_bound_user_to_ome_chat():
    """The core promise: a bound user's text reaches Ome.chat()."""
    class FakeOme:
        def __init__(self): self.messages: list[str] = []
        def chat(self, text: str) -> str:
            self.messages.append(text)
            return f"echo: {text}"

    captured = FakeOme()

    with tempfile.TemporaryDirectory() as tmp:
        ome_root = Path(tmp) / "ome-bob"
        ome_root.mkdir()                    # pass existence check
        registry = BindingRegistry(Path(tmp) / "reg.json")
        registry.bind("telegram", "42", ome_root)

        runner = GatewayRunner(
            registry=registry,
            default_ome_path=ome_root,
            ome_factory=lambda _path: captured,
        )
        adapter = FakeAdapter([
            _msg(uid="42", text="hello there"),
            _msg(uid="42", text="how are you"),
        ])
        runner.run(adapter)

        assert captured.messages == ["hello there", "how are you"]
        assert adapter.sent[0].text == "echo: hello there"
        assert adapter.sent[1].text == "echo: how are you"
    print("  PASSED")


def test_runner_auto_bind():
    class FakeOme:
        def chat(self, text: str) -> str:
            return f"ok:{text}"

    with tempfile.TemporaryDirectory() as tmp:
        ome_root = Path(tmp) / "default-ome"
        ome_root.mkdir()
        registry = BindingRegistry(Path(tmp) / "reg.json")
        runner = GatewayRunner(
            registry=registry,
            default_ome_path=ome_root,
            allow_auto_bind=True,
            ome_factory=lambda _p: FakeOme(),
        )
        adapter = FakeAdapter([_msg(uid="99", text="first ping")])
        runner.run(adapter)
        assert registry.resolve("telegram", "99") == ome_root
        assert adapter.sent[0].text == "ok:first ping"
    print("  PASSED")


def test_telegram_adapter_stop_breaks_loop():
    """Smoke-test that stop() ends the blocking loop promptly."""
    tg = TelegramAdapter(
        "t", poll_timeout=0,
        transport=lambda m, p: {"ok": True, "result": []},
    )
    done = threading.Event()

    def runner():
        tg.start(lambda m, _: None)
        done.set()

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    time.sleep(0.05)
    tg.stop()
    assert done.wait(timeout=2.0), "adapter did not stop"
    print("  PASSED")


if __name__ == "__main__":
    test_binding_registry_crud()
    test_telegram_parse_update_text()
    test_telegram_parse_update_skips_non_text()
    test_telegram_parse_update_accepts_caption_and_edited()
    test_telegram_missing_token_raises()
    test_telegram_send_calls_transport()
    test_runner_unbound_user_gets_prompt()
    test_runner_help_command()
    test_runner_bind_unbind_cycle()
    test_runner_bind_to_missing_ome_returns_error()
    test_runner_routes_bound_user_to_ome_chat()
    test_runner_auto_bind()
    test_telegram_adapter_stop_breaks_loop()
    print("\n✔ all OmeGate tests passed")
