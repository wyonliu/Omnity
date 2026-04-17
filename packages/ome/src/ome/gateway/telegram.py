"""TelegramAdapter — long-polling Telegram Bot API bridge.

Zero third-party deps: uses :mod:`urllib` so the same codepath works in any
Python 3.9+ environment. The HTTP client is pluggable for tests — pass a
``transport=`` callable that accepts ``(method, params)`` and returns the
parsed JSON dict that Telegram would have replied with.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Optional

from ome.gateway.base import (
    GatewayAdapter,
    IncomingMessage,
    MessageHandler,
    OutgoingMessage,
)

log = logging.getLogger("ome.gateway.telegram")


Transport = Callable[[str, dict[str, Any]], dict[str, Any]]


class TelegramAdapter(GatewayAdapter):
    platform = "telegram"

    def __init__(self, token: str, *, poll_timeout: int = 25,
                 api_base: str = "https://api.telegram.org",
                 transport: Optional[Transport] = None) -> None:
        super().__init__()
        if not token:
            raise ValueError("Telegram bot token is required")
        self.token = token
        self.api_base = api_base.rstrip("/")
        self.poll_timeout = poll_timeout
        self._transport: Transport = transport or self._default_transport
        self._offset: int = 0

    # -- public lifecycle -----------------------------------------------------

    def start(self, handler: MessageHandler) -> None:
        """Blocking long-poll loop. Pass a handler that sees every message."""
        log.info("Telegram adapter polling as bot token=…%s", self.token[-4:])
        while not self._stop.is_set():
            try:
                updates = self._transport("getUpdates", {
                    "offset": self._offset,
                    "timeout": self.poll_timeout,
                })
            except Exception as e:
                log.warning("getUpdates failed: %s — retrying", e)
                time.sleep(2)
                continue

            if not updates.get("ok", True):
                log.warning("getUpdates not ok: %s", updates)
                time.sleep(2)
                continue

            for upd in updates.get("result", []) or []:
                try:
                    self._dispatch(upd, handler)
                except Exception as e:  # pragma: no cover
                    log.exception("dispatch failed: %s", e)
                self._offset = max(self._offset, int(upd.get("update_id", 0)) + 1)

    def send(self, msg: OutgoingMessage) -> None:
        params: dict[str, Any] = {"chat_id": msg.chat_id, "text": msg.text}
        if msg.reply_to_message_id:
            params["reply_to_message_id"] = msg.reply_to_message_id
        self._transport("sendMessage", params)

    # -- helpers --------------------------------------------------------------

    def parse_update(self, upd: dict[str, Any]) -> Optional[IncomingMessage]:
        """Convert a raw Telegram Update dict → :class:`IncomingMessage`."""
        msg = (upd.get("message") or upd.get("edited_message")
               or upd.get("channel_post"))
        if not msg:
            return None
        text = msg.get("text") or msg.get("caption") or ""
        if not text:
            return None
        user = msg.get("from") or {}
        chat = msg.get("chat") or {}
        display = (user.get("username")
                   or (f"{user.get('first_name', '')} {user.get('last_name', '')}"
                       .strip()))
        return IncomingMessage(
            platform=self.platform,
            platform_user_id=str(user.get("id") or chat.get("id") or ""),
            text=text,
            chat_id=str(chat.get("id") or ""),
            message_id=str(msg.get("message_id") or ""),
            user_display_name=display,
            raw=upd,
        )

    def _dispatch(self, upd: dict[str, Any], handler: MessageHandler) -> None:
        incoming = self.parse_update(upd)
        if incoming is None:
            return
        # Handler looks up the bound Ome path itself (so business logic stays
        # in the runner, not the adapter).
        reply = handler(incoming, None)
        if reply:
            self.send(reply)

    # -- default HTTP client --------------------------------------------------

    def _default_transport(self, method: str,
                           params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.api_base}/bot{self.token}/{method}"
        data = urllib.parse.urlencode(params).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req, timeout=self.poll_timeout + 5) as resp:
            return json.loads(resp.read().decode("utf-8"))
