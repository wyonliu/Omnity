"""Mindos Sync — cross-device soul synchronization.

Architecture:
  - Each device has a full local SQLite (fast reads, offline-capable)
  - Every mutation is recorded in sync_journal (append-only event log)
  - Sync Hub relays events between devices (push/pull REST API)
  - Conflict resolution: memories are append-only (no conflict),
    identity edits use last-writer-wins with timestamps

Sync Hub options:
  1. Self-hosted: `mindos serve --sync` on a VPS/NAS
  2. Omnity Cloud: managed service (future)
  3. File-based: shared folder (iCloud Drive, Dropbox)

Protocol:
  POST /sync/push   — device pushes unsynced events to hub
  POST /sync/pull   — device pulls new events from hub since last_seq
  GET  /sync/status — sync state for all devices
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import URLError

from mindos.store import MemoryStore

log = logging.getLogger("mindos.sync")


# ---------------------------------------------------------------------------
# Sync Hub (Server-side) — lightweight event relay
# ---------------------------------------------------------------------------

@dataclass
class SyncEvent:
    """A single sync event as stored in the hub."""
    hub_seq: int
    event_id: str
    device_id: str
    op: str
    payload: dict
    created_at: float
    received_at: float = 0.0


class SyncHub:
    """In-memory event relay for Mindos sync.

    For production, back with SQLite or Redis. This implementation
    uses a simple in-memory list suitable for self-hosted single-user.
    """

    def __init__(self, persist_path: Optional[Path] = None) -> None:
        self._events: list[SyncEvent] = []
        self._seq = 0
        self._device_cursors: dict[str, int] = {}  # device_id → last_pulled_hub_seq
        self._persist_path = persist_path
        self._auth_token = os.environ.get("MINDOS_SYNC_TOKEN", "")
        if persist_path:
            self._load()

    def push(self, events: list[dict], device_id: str) -> dict:
        """Receive events from a device. Returns count accepted."""
        accepted = 0
        for e in events:
            # Dedup by event_id
            if any(x.event_id == e["event_id"] for x in self._events):
                continue
            self._seq += 1
            self._events.append(SyncEvent(
                hub_seq=self._seq,
                event_id=e["event_id"],
                device_id=e.get("device_id", device_id),
                op=e["op"],
                payload=e["payload"],
                created_at=e["created_at"],
                received_at=time.time(),
            ))
            accepted += 1
        if accepted > 0 and self._persist_path:
            self._save()
        return {"accepted": accepted, "hub_seq": self._seq}

    def pull(self, device_id: str, after_seq: int = 0, limit: int = 500) -> dict:
        """Return events after a given hub sequence, excluding the device's own events."""
        events = []
        for e in self._events:
            if e.hub_seq <= after_seq:
                continue
            if e.device_id == device_id:
                continue  # Don't send device its own events back
            events.append({
                "hub_seq": e.hub_seq,
                "event_id": e.event_id,
                "device_id": e.device_id,
                "op": e.op,
                "payload": e.payload,
                "created_at": e.created_at,
            })
            if len(events) >= limit:
                break
        # Update cursor
        if events:
            self._device_cursors[device_id] = events[-1]["hub_seq"]
        elif after_seq > 0:
            self._device_cursors[device_id] = after_seq
        return {"events": events, "hub_seq": self._seq}

    def status(self) -> dict:
        return {
            "total_events": len(self._events),
            "hub_seq": self._seq,
            "devices": self._device_cursors,
        }

    def _save(self) -> None:
        if not self._persist_path:
            return
        data = {
            "seq": self._seq,
            "events": [
                {"hub_seq": e.hub_seq, "event_id": e.event_id, "device_id": e.device_id,
                 "op": e.op, "payload": e.payload, "created_at": e.created_at,
                 "received_at": e.received_at}
                for e in self._events
            ],
            "cursors": self._device_cursors,
        }
        self._persist_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def _load(self) -> None:
        if not self._persist_path or not self._persist_path.exists():
            return
        try:
            data = json.loads(self._persist_path.read_text(encoding="utf-8"))
            self._seq = data.get("seq", 0)
            self._device_cursors = data.get("cursors", {})
            for e in data.get("events", []):
                self._events.append(SyncEvent(
                    hub_seq=e["hub_seq"], event_id=e["event_id"],
                    device_id=e["device_id"], op=e["op"],
                    payload=e["payload"], created_at=e["created_at"],
                    received_at=e.get("received_at", 0),
                ))
        except Exception as ex:
            log.warning("Failed to load sync hub state: %s", ex)


# ---------------------------------------------------------------------------
# Sync Hub HTTP Server
# ---------------------------------------------------------------------------

_hub: SyncHub | None = None


class SyncHubHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        pass

    def _json(self, data: dict, code: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def _check_auth(self) -> bool:
        assert _hub is not None
        if not _hub._auth_token:
            return True
        auth = self.headers.get("Authorization", "")
        if auth == f"Bearer {_hub._auth_token}":
            return True
        self._json({"error": "Unauthorized"}, 401)
        return False

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self) -> None:
        assert _hub is not None
        path = urlparse(self.path).path

        if path == "/sync/status":
            if not self._check_auth():
                return
            self._json(_hub.status())
            return

        if path == "/sync/health":
            self._json({"status": "ok"})
            return

        self.send_error(404)

    def do_POST(self) -> None:
        assert _hub is not None
        if not self._check_auth():
            return
        path = urlparse(self.path).path
        body = self._read_body()

        if path == "/sync/push":
            device_id = body.get("device_id", "unknown")
            events = body.get("events", [])
            result = _hub.push(events, device_id)
            self._json(result)
            return

        if path == "/sync/pull":
            device_id = body.get("device_id", "unknown")
            after_seq = body.get("after_seq", 0)
            result = _hub.pull(device_id, after_seq)
            self._json(result)
            return

        self.send_error(404)


def run_sync_hub(port: int = 3457, persist_dir: str = "~/.mindos") -> None:
    """Start the Mindos Sync Hub server."""
    global _hub
    root = Path(persist_dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    _hub = SyncHub(persist_path=root / "sync_hub.json")

    server = HTTPServer(("0.0.0.0", port), SyncHubHandler)
    print(f"Mindos Sync Hub running at http://0.0.0.0:{port}")
    print(f"  Push:   POST http://localhost:{port}/sync/push")
    print(f"  Pull:   POST http://localhost:{port}/sync/pull")
    print(f"  Status: GET  http://localhost:{port}/sync/status")
    print(f"  Data:   {root / 'sync_hub.json'}")
    if os.environ.get("MINDOS_SYNC_TOKEN"):
        print("  Auth:   Bearer token enabled")
    print("\nPress Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("\nSync Hub stopped.")


# ---------------------------------------------------------------------------
# Sync Client (runs on each device)
# ---------------------------------------------------------------------------

class SyncClient:
    """Client-side sync: push local events to hub, pull remote events.

    Usage:
        sync = SyncClient(store, hub_url="http://my-vps:3457")
        sync.push()    # Push unsynced local events to hub
        sync.pull()    # Pull new events from hub and apply locally
        sync.sync()    # Push then pull (full round-trip)
    """

    def __init__(self, store: MemoryStore, hub_url: str = "",
                 auth_token: str = "") -> None:
        self.store = store
        self.hub_url = hub_url.rstrip("/") or os.environ.get("MINDOS_SYNC_URL", "")
        self._auth_token = auth_token or os.environ.get("MINDOS_SYNC_TOKEN", "")
        # Track where we are in the hub's sequence
        self._hub_cursor_key = "sync_hub_cursor"

    @property
    def hub_cursor(self) -> int:
        """Last hub_seq we've pulled up to."""
        raw = self.store.get_state(self._hub_cursor_key)
        return int(raw) if raw else 0

    @hub_cursor.setter
    def hub_cursor(self, value: int) -> None:
        self.store.set_state(self._hub_cursor_key, str(value))

    def push(self) -> dict:
        """Push unsynced local events to the hub."""
        if not self.hub_url:
            return {"error": "No hub URL configured"}

        events = self.store.journal_unsynced()
        if not events:
            return {"pushed": 0, "message": "Nothing to push"}

        result = self._request("POST", "/sync/push", {
            "device_id": self.store.device_id,
            "events": events,
        })

        if "hub_seq" in result:
            # Mark local events as synced
            max_seq = max(e["seq"] for e in events)
            self.store.journal_mark_synced(max_seq)

        return {"pushed": len(events), **result}

    def pull(self) -> dict:
        """Pull new events from the hub and apply locally."""
        if not self.hub_url:
            return {"error": "No hub URL configured"}

        result = self._request("POST", "/sync/pull", {
            "device_id": self.store.device_id,
            "after_seq": self.hub_cursor,
        })

        applied = 0
        skipped = 0
        for event in result.get("events", []):
            if self.store.journal_apply_remote(event):
                applied += 1
            else:
                skipped += 1

        # Update cursor
        if result.get("events"):
            self.hub_cursor = result["events"][-1]["hub_seq"]
        elif "hub_seq" in result:
            self.hub_cursor = result["hub_seq"]

        return {"applied": applied, "skipped": skipped, "hub_seq": result.get("hub_seq", 0)}

    def sync(self) -> dict:
        """Full round-trip: push then pull."""
        push_result = self.push()
        pull_result = self.pull()
        return {
            "push": push_result,
            "pull": pull_result,
            "device_id": self.store.device_id,
        }

    def _request(self, method: str, path: str, body: dict) -> dict:
        url = f"{self.hub_url}{path}"
        data = json.dumps(body).encode()
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"

        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except URLError as e:
            log.error("Sync request failed: %s %s — %s", method, path, e)
            return {"error": str(e)}
