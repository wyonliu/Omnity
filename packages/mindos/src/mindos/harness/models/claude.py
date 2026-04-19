"""Claude backend — Anthropic Messages API with explicit cache TTL.

Why we pass `cache_ttl` on every call:

    On 2026-03-06 Anthropic silently reverted the default prompt-cache TTL
    from 1h back to 5m, causing a 20-32% cost inflation for long-running
    Claude Code sessions. Using the Messages API's `cache_control.ttl: "1h"`
    explicitly (at 2x write price but 0.1x read price) beats that regression
    whenever the same system prompt / skills schema is reused within an hour.

The default here is "1h" for the system prompt + tools schema. Per-message
cache blocks default to "5m" because message history churns.

Network is injectable via `transport` so tests stay offline.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Callable, Optional

from mindos.harness.models.base import (
    CompletionResult,
    ModelBackend,
    TokenStats,
    ToolCallRequest,
)

log = logging.getLogger("mindos.harness.claude")

_API_VERSION = "2023-06-01"
_DEFAULT_URL = "https://api.anthropic.com/v1/messages"
_DEFAULT_MODEL = "claude-opus-4-6"


class ClaudeBackend(ModelBackend):
    """Anthropic Claude backend.

    Args:
        api_key: Anthropic key; falls back to ANTHROPIC_API_KEY env.
        model: model id (default: claude-opus-4-6).
        transport: optional `fn(url, payload, headers) -> dict` for tests.
        url: API endpoint override.
    """

    name = "claude"
    supports_cache = True
    default_cache_ttl = "1h"

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        model: str = _DEFAULT_MODEL,
        transport: Optional[Callable[[str, dict, dict], dict]] = None,
        url: str = _DEFAULT_URL,
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self._transport = transport
        self.url = url

    # -- public ----------------------------------------------------------

    def complete(
        self,
        *,
        system: str,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        cache_ttl: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> CompletionResult:
        ttl = cache_ttl or self.default_cache_ttl
        if ttl not in ("none", "5m", "1h"):
            log.warning("unrecognised cache_ttl=%r, falling back to 5m", ttl)
            ttl = "5m"

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": _system_blocks(system, ttl),
            "messages": _normalise_messages(messages),
        }
        if tools:
            payload["tools"] = _tools_with_cache(tools, ttl)

        raw = self._post(payload)
        return _parse_response(raw, model=self.model, cache_ttl=ttl)

    # -- internals -------------------------------------------------------

    def _post(self, payload: dict) -> dict:
        if self._transport is not None:
            return self._transport(self.url, payload, self._headers())
        if not self.api_key:
            raise RuntimeError(
                "ClaudeBackend has no api_key and no injected transport; "
                "set ANTHROPIC_API_KEY or pass transport=... for tests.",
            )
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            log.error("anthropic HTTP %s: %s", e.code, body[:400])
            raise

    def _headers(self) -> dict:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": _API_VERSION,
            "content-type": "application/json",
        }


# -- helpers ----------------------------------------------------------------

def _system_blocks(system: str, ttl: str) -> list[dict]:
    """System prompt as a cached content block (if TTL != 'none')."""
    block = {"type": "text", "text": system or ""}
    if ttl != "none":
        block["cache_control"] = {"type": "ephemeral", "ttl": ttl}
    return [block]


def _tools_with_cache(tools: list[dict], ttl: str) -> list[dict]:
    """Attach cache_control to the LAST tool so the whole tools array is cached."""
    if not tools:
        return tools
    out = [dict(t) for t in tools]
    if ttl != "none":
        out[-1] = dict(out[-1])
        out[-1]["cache_control"] = {"type": "ephemeral", "ttl": ttl}
    return out


def _normalise_messages(messages: list[dict]) -> list[dict]:
    """Pass-through; the harness builds Anthropic-shaped messages already."""
    return [dict(m) for m in messages]


def _parse_response(raw: dict, *, model: str, cache_ttl: str) -> CompletionResult:
    """Parse Anthropic Messages API response into CompletionResult."""
    text_parts: list[str] = []
    tool_calls: list[ToolCallRequest] = []
    for block in raw.get("content", []) or []:
        btype = block.get("type")
        if btype == "text":
            text_parts.append(block.get("text", ""))
        elif btype == "tool_use":
            tool_calls.append(ToolCallRequest(
                id=block.get("id", ""),
                name=block.get("name", ""),
                arguments=block.get("input", {}) or {},
            ))

    usage = raw.get("usage", {}) or {}
    tokens = TokenStats(
        input=int(usage.get("input_tokens", 0) or 0),
        output=int(usage.get("output_tokens", 0) or 0),
        cached_read=int(usage.get("cache_read_input_tokens", 0) or 0),
        cached_write=int(usage.get("cache_creation_input_tokens", 0) or 0),
    )

    return CompletionResult(
        text="".join(text_parts),
        tool_calls=tool_calls,
        tokens=tokens,
        stop_reason=raw.get("stop_reason", "end_turn") or "end_turn",
        model=raw.get("model", model),
        cache_ttl_used=cache_ttl,
        raw=raw,
    )
