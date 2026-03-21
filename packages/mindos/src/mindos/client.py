"""Mindos HTTP Client — connect to a running Mindos server.

Auto-discovers server via lockfile. Falls back to direct DB access when
no server is running.

Usage:
    from mindos.client import MindosClient

    # Auto-discover (reads ~/.mindos/server.lock)
    client = MindosClient.discover()

    # Or connect directly
    client = MindosClient("http://localhost:3456")

    ctx = client.hydrate(context="discussing Python")
    result = client.commit("user: I like Rust\\nassistant: Nice!", source="cli")
    memories = client.recall("Rust", top_k=5)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError


class MindosClient:
    """HTTP client for a running Mindos server."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    @classmethod
    def discover(cls, soul_dir: str | Path = "~/.mindos") -> Optional["MindosClient"]:
        """Auto-discover a running server via lockfile. Returns None if no server."""
        from mindos.server import read_lockfile
        lock = read_lockfile(soul_dir)
        if lock and lock.get("url"):
            client = cls(lock["url"])
            if client.health():
                return client
        return None

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"

        req = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except URLError as e:
            raise ConnectionError(f"Cannot reach Mindos server at {self.base_url}: {e}") from e

    def health(self) -> bool:
        try:
            r = self._request("GET", "/api/health")
            return r.get("status") == "ok"
        except Exception:
            return False

    def status(self) -> dict[str, Any]:
        return self._request("GET", "/api/status")

    def hydrate(self, context: str = "", max_tokens: int = 2000) -> str:
        r = self._request("POST", "/api/hydrate", {"context": context, "max_tokens": max_tokens})
        return r.get("context", "")

    def commit(self, conversation: str, source: str = "api") -> dict[str, Any]:
        return self._request("POST", "/api/commit", {"conversation": conversation, "source": source})

    def recall(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        r = self._request("POST", "/api/recall", {"query": query, "top_k": top_k})
        return r.get("results", [])

    def forget(self, pattern: str, scope: str = "all") -> dict[str, Any]:
        return self._request("POST", "/api/forget", {"pattern": pattern, "scope": scope})

    def reflect(self) -> dict[str, Any]:
        return self._request("POST", "/api/reflect", {})

    def memories(self, query: str = "", mem_type: str = "", limit: int = 50) -> dict[str, Any]:
        params = []
        if query:
            params.append(f"q={query}")
        if mem_type:
            params.append(f"type={mem_type}")
        params.append(f"limit={limit}")
        qs = "&".join(params)
        return self._request("GET", f"/api/memories?{qs}")

    def export_memories(self) -> dict[str, Any]:
        return self._request("GET", "/api/memories/export")

    def import_memories(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/memories/import", data)

    def stats(self) -> dict[str, Any]:
        return self._request("GET", "/api/memories/stats")

    def consolidate(self) -> dict[str, Any]:
        return self._request("POST", "/api/memories/consolidate", {})

    def config(self) -> dict[str, Any]:
        return self._request("GET", "/api/config")
