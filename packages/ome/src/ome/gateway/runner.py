"""GatewayRunner — the brain-side router for :mod:`ome.gateway` adapters.

Adapters just ship inbound :class:`IncomingMessage` objects and a ``reply``
callback; the runner looks up the bound Ome root, opens the right Ome, and
routes the text through ``ome.chat``. One runner can back many adapters.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Callable, Optional

from ome.gateway.base import (
    BindingRegistry,
    GatewayAdapter,
    IncomingMessage,
    MessageHandler,
    OutgoingMessage,
)

log = logging.getLogger("ome.gateway.runner")


# Slash commands we handle before forwarding to Ome.chat
_BIND_WORDS = {"/bind", "/start", "/link"}
_UNBIND_WORDS = {"/unbind", "/stop"}
_HELP_WORDS = {"/help", "/?", "help"}


class GatewayRunner:
    """Compose multiple adapters behind a shared :class:`BindingRegistry`.

    Usage::

        runner = GatewayRunner(registry=BindingRegistry(),
                                default_ome_path="~/.ome",
                                allow_auto_bind=True)
        tg = TelegramAdapter(token=TOKEN)
        runner.attach(tg)
        runner.run(tg)     # blocks
    """

    def __init__(self, *, registry: Optional[BindingRegistry] = None,
                 default_ome_path: str | Path = "~/.ome",
                 allow_auto_bind: bool = False,
                 ome_factory: Optional[Callable[[Path], Any]] = None) -> None:
        self.registry = registry or BindingRegistry()
        self.default_ome_path = Path(default_ome_path).expanduser()
        self.allow_auto_bind = allow_auto_bind
        self._lock = threading.RLock()
        self._cache: dict[str, Any] = {}              # ome_root_str → Ome
        self._adapters: list[GatewayAdapter] = []
        self._ome_factory = ome_factory  # test injection

    # -- registration ---------------------------------------------------------

    def attach(self, adapter: GatewayAdapter) -> None:
        self._adapters.append(adapter)

    def handle(self, msg: IncomingMessage,
               _root_hint: Optional[Path] = None) -> Optional[OutgoingMessage]:
        """The :data:`MessageHandler` adapters should call us through."""
        text = msg.text.strip()
        low = text.lower()

        # -- slash commands ---------------------------------------------------
        first = low.split()[0] if low else ""
        if first in _HELP_WORDS:
            return self._reply(msg, (
                "Ome Gateway — commands:\n"
                "  /bind   link this account to your local Ome\n"
                "  /unbind stop routing your messages\n"
                "  /help   show this help\n"
                "Anything else I'll hand off to your Ome."
            ))
        if first in _BIND_WORDS:
            return self._cmd_bind(msg, text)
        if first in _UNBIND_WORDS:
            return self._cmd_unbind(msg)

        # -- normal flow ------------------------------------------------------
        root = self.registry.resolve(msg.platform, msg.platform_user_id)
        if root is None:
            if self.allow_auto_bind:
                root = self.default_ome_path
                self.registry.bind(msg.platform, msg.platform_user_id, root)
            else:
                return self._reply(msg,
                    "You're not bound to an Ome yet. Send /bind to link this account.")

        try:
            ome = self._open(root)
        except FileNotFoundError as e:
            return self._reply(msg, f"Bound Ome at {root} is missing: {e}")
        reply = ome.chat(text)
        return self._reply(msg, reply)

    # -- command implementations ---------------------------------------------

    def _cmd_bind(self, msg: IncomingMessage, text: str) -> OutgoingMessage:
        parts = text.split(maxsplit=1)
        target = Path(parts[1]).expanduser() if len(parts) > 1 else self.default_ome_path
        try:
            self._open(target)   # validate existence / loadability
        except FileNotFoundError:
            return self._reply(msg,
                f"No Ome at {target}. Run `ome create --path {target}` first.")
        self.registry.bind(msg.platform, msg.platform_user_id, target)
        return self._reply(msg, f"Bound to Ome at {target}. Say hi!")

    def _cmd_unbind(self, msg: IncomingMessage) -> OutgoingMessage:
        ok = self.registry.unbind(msg.platform, msg.platform_user_id)
        return self._reply(msg,
            "Unbound. Your Ome stays safe at rest." if ok
            else "You weren't bound.")

    # -- plumbing -------------------------------------------------------------

    def _reply(self, msg: IncomingMessage, text: str) -> OutgoingMessage:
        return OutgoingMessage(
            chat_id=msg.chat_id,
            text=text,
            reply_to_message_id=msg.message_id,
        )

    def _open(self, root: Path) -> Any:
        key = str(root.resolve()) if root.exists() else str(root)
        with self._lock:
            if key in self._cache:
                return self._cache[key]
            if self._ome_factory is not None:
                ome = self._ome_factory(root)
            else:
                from ome.core import Ome
                if not root.exists():
                    raise FileNotFoundError(root)
                ome = Ome.load(root)
            self._cache[key] = ome
            return ome

    # -- lifecycle ------------------------------------------------------------

    def run(self, adapter: GatewayAdapter) -> None:
        """Blocking — start one specific adapter with this runner as handler."""
        adapter.start(self.handle)

    def stop_all(self) -> None:
        for a in self._adapters:
            try:
                a.stop()
            except Exception:  # pragma: no cover
                pass
