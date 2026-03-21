"""Mindos HTTP Server — unified entry point for multi-terminal access.

Serves:
  - REST API (hydrate, commit, recall, forget, reflect, status, memories, KG)
  - Dashboard web UI (served at /)
  - Lockfile for automatic client discovery

Usage:
  mindos serve                  # HTTP server (default port 3456)
  mindos serve --mcp            # MCP stdio (separate process)
  mindos serve --port 8080      # custom port

Multiple terminals on the same machine automatically discover the running
server via ~/.mindos/server.lock and proxy all CLI commands to it.
"""

from __future__ import annotations

import atexit
import json
import os
import signal
import socket
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse, parse_qs

if TYPE_CHECKING:
    from mindos.core import Mindos

_mindos: "Mindos | None" = None
_serve_port: int = 3456
_start_time: float = 0.0


# ---------------------------------------------------------------------------
# Lockfile management
# ---------------------------------------------------------------------------

def _lockfile_path(soul_root: Path) -> Path:
    return soul_root / "server.lock"


def _write_lockfile(soul_root: Path, port: int) -> None:
    lf = _lockfile_path(soul_root)
    lf.write_text(json.dumps({
        "pid": os.getpid(),
        "port": port,
        "started_at": time.time(),
        "url": f"http://127.0.0.1:{port}",
    }), encoding="utf-8")


def _remove_lockfile(soul_root: Path) -> None:
    lf = _lockfile_path(soul_root)
    try:
        lf.unlink(missing_ok=True)
    except Exception:
        pass


def read_lockfile(soul_root: Path | str = "~/.mindos") -> dict[str, Any] | None:
    """Read lockfile to discover a running server. Returns None if none found."""
    root = Path(soul_root).expanduser()
    lf = _lockfile_path(root)
    if not lf.exists():
        return None
    try:
        data = json.loads(lf.read_text(encoding="utf-8"))
        pid = data.get("pid")
        if pid and _pid_alive(pid):
            return data
        lf.unlink(missing_ok=True)
        return None
    except Exception:
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


# ---------------------------------------------------------------------------
# Dashboard HTML (embedded)
# ---------------------------------------------------------------------------

def _get_dashboard_html() -> str:
    try:
        from mindos.dashboard import _HTML
        return _HTML
    except ImportError:
        return "<html><body><h1>Mindos is running</h1><p>Dashboard unavailable.</p></body></html>"


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

class MindosHandler(BaseHTTPRequestHandler):
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

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        assert _mindos is not None
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            body = _get_dashboard_html().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/config":
            from mindos import __version__
            self._json({
                "port": _serve_port,
                "version": __version__,
                "data_root": str(_mindos.root),
                "uptime_seconds": round(time.time() - _start_time),
                "pid": os.getpid(),
            })
            return

        if path == "/api/health":
            self._json({"status": "ok", "pid": os.getpid()})
            return

        if path == "/api/status":
            self._json(_mindos.status())
            return

        if path == "/api/memories":
            q = qs.get("q", [""])[0]
            mem_type = qs.get("type", [""])[0] or None
            limit = int(qs.get("limit", ["50"])[0])
            if q:
                mems = _mindos.store.search_text(q, limit=limit)
            else:
                mems = _mindos.store.list_recent(limit=limit, mem_type=mem_type)
            self._json({"memories": [
                {"id": m.id, "type": m.type, "content": m.content,
                 "source": m.source, "confidence": m.confidence,
                 "created_at": m.created_at, "access_count": m.access_count}
                for m in mems
            ], "total": _mindos.store.count()})
            return

        if path == "/api/memories/export":
            all_mems = _mindos.store.list_recent(limit=100000)
            triples = _mindos.store.triples()
            export_data = {
                "version": 1,
                "exported_at": time.time(),
                "identity": _mindos.identity,
                "memories": [
                    {"id": m.id, "type": m.type, "content": m.content,
                     "source": m.source, "confidence": m.confidence,
                     "created_at": m.created_at, "access_count": m.access_count,
                     "decay_weight": m.decay_weight}
                    for m in all_mems
                ],
                "knowledge_graph": [
                    {"subject": t.subject, "predicate": t.predicate,
                     "object": t.object, "source": t.source, "confidence": t.confidence}
                    for t in triples
                ],
                "stats": _mindos.store.stats(),
            }
            self._json(export_data)
            return

        if path == "/api/memories/stats":
            stats = _mindos.store.stats()
            sources: dict[str, int] = {}
            for m in _mindos.store.list_recent(limit=10000):
                sources[m.source] = sources.get(m.source, 0) + 1
            stats["by_source"] = sources
            self._json(stats)
            return

        if path == "/api/knowledge_graph":
            triples = _mindos.store.triples()
            self._json({"triples": [
                {"subject": t.subject, "predicate": t.predicate, "object": t.object,
                 "source": t.source, "confidence": t.confidence}
                for t in triples
            ]})
            return

        self.send_error(404)

    def do_POST(self) -> None:
        assert _mindos is not None
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_body()

        if path == "/api/hydrate":
            ctx = _mindos.hydrate(
                context=body.get("context", ""),
                max_tokens=body.get("max_tokens", 2000),
            )
            self._json({"context": ctx})
            return

        if path == "/api/commit":
            conv = body.get("conversation", "")
            if not conv and body.get("messages"):
                conv = "\n".join(
                    f"{m.get('role', '?')}: {m.get('content', '')}"
                    for m in body["messages"]
                )
            result = _mindos.commit(conv, source=body.get("source", "api"))
            self._json(result)
            return

        if path == "/api/recall":
            results = _mindos.recall(
                body.get("query", ""),
                top_k=body.get("top_k", 10),
            )
            self._json({"results": results})
            return

        if path == "/api/forget":
            result = _mindos.forget(
                body.get("pattern", ""),
                scope=body.get("scope", "all"),
            )
            self._json(result)
            return

        if path == "/api/reflect":
            result = _mindos.reflect()
            self._json(result or {"message": "No episodes to reflect on"})
            return

        if path == "/api/memories/import":
            imported = _import_memories(_mindos, body)
            self._json(imported)
            return

        if path == "/api/memories/consolidate":
            result = _mindos.consolidate()
            self._json(result)
            return

        self.send_error(404)


def _import_memories(mindos: "Mindos", data: dict) -> dict:
    """Import memories from an export JSON."""
    from mindos.store import Memory, Triple

    added = 0
    skipped = 0
    for m in data.get("memories", []):
        if mindos.store.content_exists(m["content"]):
            skipped += 1
            continue
        mem = Memory(
            id="", type=m.get("type", "fact"), content=m["content"],
            source=m.get("source", "import"), confidence=m.get("confidence", 0.8),
            decay_weight=m.get("decay_weight", 1.0),
        )
        mindos.store.add(mem)
        added += 1

    kg_added = 0
    for t in data.get("knowledge_graph", []):
        mindos.store.add_triple(Triple(
            subject=t["subject"], predicate=t["predicate"],
            object=t["object"], source=t.get("source", "import"),
            confidence=t.get("confidence", 1.0),
        ))
        kg_added += 1

    return {"memories_imported": added, "skipped_duplicate": skipped, "triples_imported": kg_added}


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------

def _pick_port(preferred: int = 3456, max_attempts: int = 32) -> int:
    for p in range(preferred, preferred + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise OSError(f"Cannot bind port {preferred}-{preferred + max_attempts - 1}")


def run_server(mindos_instance: "Mindos", port: int = 3456) -> None:
    """Start the unified Mindos HTTP server."""
    global _mindos, _serve_port, _start_time
    _mindos = mindos_instance
    actual = _pick_port(port)
    _serve_port = actual
    _start_time = time.time()

    _write_lockfile(mindos_instance.root, actual)
    atexit.register(lambda: _remove_lockfile(mindos_instance.root))

    def _signal_handler(sig, frame):
        _remove_lockfile(mindos_instance.root)
        sys.exit(0)
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    if actual != port:
        print(f"Port {port} busy, using {actual}")

    server = HTTPServer(("127.0.0.1", actual), MindosHandler)
    print(f"Mindos server running at http://localhost:{actual}")
    print(f"  Dashboard:  http://localhost:{actual}")
    print(f"  API:        http://localhost:{actual}/api/")
    print(f"  Data:       {mindos_instance.root}")
    print(f"  PID:        {os.getpid()}")
    print(f"  Lockfile:   {_lockfile_path(mindos_instance.root)}")
    print()
    print("Other terminals will auto-discover this server.")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        _remove_lockfile(mindos_instance.root)
        server.server_close()
        print("\nServer stopped.")
