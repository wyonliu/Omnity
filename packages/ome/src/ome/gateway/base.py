"""Shared types for OmeGate adapters.

Keeping these tiny and stdlib-only so any adapter (Telegram, Slack, SMS…)
can depend on them without pulling in transport libraries.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger("ome.gateway")


# ---------------------------------------------------------------------------
# Message dataclasses
# ---------------------------------------------------------------------------

@dataclass
class IncomingMessage:
    """A normalised message arriving from any platform."""
    platform: str                       # "telegram" | "slack" | ...
    platform_user_id: str               # stringified so any ID type survives
    text: str
    chat_id: str = ""                   # group / DM where to reply
    message_id: str = ""                # for reply / reaction hooks
    user_display_name: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutgoingMessage:
    """What an adapter should post back to the platform."""
    chat_id: str
    text: str
    reply_to_message_id: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


# A handler receives the incoming message + the bound Ome root (or None if
# the user isn't bound yet) and returns at most one outgoing message.
MessageHandler = Callable[[IncomingMessage, Optional[Path]], Optional[OutgoingMessage]]


# ---------------------------------------------------------------------------
# User-binding registry
# ---------------------------------------------------------------------------

class BindingRegistry:
    """Persistent map of (platform, platform_user_id) → local Ome root.

    Stored as a single JSON file so it round-trips nicely with ``mindos dump``
    and other human-readable tools. Thread-safe via a local RLock.
    """

    def __init__(self, path: str | Path = "~/.ome/gateway/bindings.json") -> None:
        self.path = Path(path).expanduser()
        self._lock = threading.RLock()
        self._data: dict[str, dict[str, str]] = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as e:  # pragma: no cover
                log.warning("Bindings file corrupt (%s) — starting fresh", e)
                self._data = {}

    # -- CRUD -----------------------------------------------------------------

    def bind(self, platform: str, user_id: str, ome_path: str | Path) -> None:
        ome_path = str(Path(ome_path).expanduser())
        with self._lock:
            self._data.setdefault(platform, {})[str(user_id)] = ome_path
            self._flush()

    def unbind(self, platform: str, user_id: str) -> bool:
        with self._lock:
            plat = self._data.get(platform, {})
            if str(user_id) not in plat:
                return False
            del plat[str(user_id)]
            if not plat:
                self._data.pop(platform, None)
            self._flush()
            return True

    def resolve(self, platform: str, user_id: str) -> Optional[Path]:
        with self._lock:
            p = self._data.get(platform, {}).get(str(user_id))
        return Path(p) if p else None

    def list(self, platform: str | None = None) -> list[tuple[str, str, str]]:
        with self._lock:
            out: list[tuple[str, str, str]] = []
            platforms = [platform] if platform else list(self._data.keys())
            for plat in platforms:
                for uid, path in sorted((self._data.get(plat) or {}).items()):
                    out.append((plat, uid, path))
        return out

    # -- internals ------------------------------------------------------------

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, self.path)


# ---------------------------------------------------------------------------
# Adapter base class
# ---------------------------------------------------------------------------

class GatewayAdapter:
    """Subclass per platform. Responsibilities: fetch updates, dispatch to
    the shared ``handler``, send out replies."""

    platform: str = "generic"

    def __init__(self) -> None:
        self._stop = threading.Event()

    # -- public lifecycle -----------------------------------------------------

    def start(self, handler: MessageHandler) -> None:
        """Block until :meth:`stop` is called. Override per adapter."""
        raise NotImplementedError

    def send(self, msg: OutgoingMessage) -> None:
        """Post an :class:`OutgoingMessage` to the platform."""
        raise NotImplementedError

    def stop(self) -> None:
        self._stop.set()
