"""Mindos plugin for OpenClaw — persistent memory across all Claws.

Usage:
    from mindos_plugin import MindosPlugin

    plugin = MindosPlugin()

    # Before each Claw run
    context = plugin.before_run("task description")
    # → inject context into system prompt

    # After each Claw run
    plugin.after_run(conversation_text, source="my-claw")
"""

from __future__ import annotations

from typing import Any, Optional


class MindosPlugin:
    """Drop-in Mindos integration. Auto-discovers server, falls back to direct DB."""

    def __init__(self, soul_path: str = "~/.mindos") -> None:
        self._soul_path = soul_path
        self._client: Any = None
        self._soul: Any = None
        self._init()

    def _init(self) -> None:
        try:
            from mindos.client import MindosClient
            self._client = MindosClient.discover(self._soul_path)
        except Exception:
            pass
        if not self._client:
            try:
                from mindos import Mindos
                self._soul = Mindos.load(self._soul_path)
            except Exception:
                pass

    @property
    def available(self) -> bool:
        return self._client is not None or self._soul is not None

    def before_run(self, task_description: str = "", max_tokens: int = 2000) -> str:
        """Load identity context. Call before each Claw/agent run."""
        if self._client:
            return self._client.hydrate(context=task_description, max_tokens=max_tokens)
        if self._soul:
            return self._soul.hydrate(context=task_description, max_tokens=max_tokens)
        return ""

    def after_run(self, conversation: str, source: str = "openclaw") -> dict[str, Any]:
        """Digest conversation. Call after each Claw/agent run."""
        if self._client:
            return self._client.commit(conversation, source=source)
        if self._soul:
            return self._soul.commit(conversation, source=source)
        return {}

    def recall(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Search the user's memories by relevance."""
        if self._client:
            return self._client.recall(query, top_k=top_k)
        if self._soul:
            return self._soul.recall(query, top_k=top_k)
        return []

    def forget(self, pattern: str, scope: str = "all") -> dict[str, Any]:
        """Physical erasure of memories."""
        if self._client:
            return self._client.forget(pattern, scope=scope)
        if self._soul:
            return self._soul.forget(pattern, scope=scope)
        return {}

    def status(self) -> dict[str, Any]:
        if self._client:
            return self._client.status()
        if self._soul:
            return self._soul.status()
        return {}
