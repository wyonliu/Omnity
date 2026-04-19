"""Kimi K2 Thinking backend — OpenAI-compatible Moonshot API.

Why K2 Thinking specifically: Moonshot's 2025-11 release can sustain
200-300 sequential tool calls without drift on a 256K context window.
For the harness's tool loop this is the single most important Chinese
model to support.

This is a W1 **stub** — interface identical to ClaudeBackend.complete(),
real call uses the OpenAI-compat endpoint:
    POST https://api.moonshot.ai/v1/chat/completions

Keeping the shape locked now means W2 just fills in `_post`.
"""

from __future__ import annotations

import logging
import os
from typing import Callable, Optional

from mindos.harness.models.base import (
    CompletionResult,
    ModelBackend,
    TokenStats,
    ToolCallRequest,
)

log = logging.getLogger("mindos.harness.kimi")

_DEFAULT_URL = "https://api.moonshot.ai/v1/chat/completions"
_DEFAULT_MODEL = "kimi-k2-thinking"


class KimiBackend(ModelBackend):
    """Moonshot Kimi K2 Thinking backend (OpenAI-compatible)."""

    name = "kimi"
    # K2 uses OpenAI-compat; no first-class cache control. We still surface a
    # cache_ttl value in the result for consistency, but mark it "none".
    supports_cache = False
    default_cache_ttl = "none"

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        model: str = _DEFAULT_MODEL,
        transport: Optional[Callable[[str, dict, dict], dict]] = None,
        url: str = _DEFAULT_URL,
    ):
        self.api_key = api_key or os.environ.get("MOONSHOT_API_KEY", "")
        self.model = model
        self._transport = transport
        self.url = url

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
        oai_messages = _to_openai_messages(system, messages)
        payload = {
            "model": self.model,
            "messages": oai_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = _to_openai_tools(tools)

        if self._transport is None:
            raise NotImplementedError(
                "KimiBackend real transport lands W2; pass transport=... "
                "for now (stub present to lock the interface).",
            )
        raw = self._transport(self.url, payload, self._headers())
        return _parse_openai(raw, model=self.model)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }


# -- helpers ----------------------------------------------------------------

def _to_openai_messages(system: str, messages: list[dict]) -> list[dict]:
    """Convert Anthropic-shaped messages → OpenAI-shaped messages."""
    out: list[dict] = []
    if system:
        out.append({"role": "system", "content": system})
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        # Anthropic-style list-of-blocks → flatten text; tool use/results ignored
        # in this stub — filled in W2 when we wire K2's real tool protocol.
        if isinstance(content, list):
            text_parts = [
                b.get("text", "") for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            ]
            content = "\n".join(text_parts)
        out.append({"role": role, "content": content})
    return out


def _to_openai_tools(tools: list[dict]) -> list[dict]:
    """Anthropic tools → OpenAI tools format."""
    out = []
    for t in tools:
        out.append({
            "type": "function",
            "function": {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {}),
            },
        })
    return out


def _parse_openai(raw: dict, *, model: str) -> CompletionResult:
    choices = raw.get("choices") or []
    msg = (choices[0] or {}).get("message", {}) if choices else {}
    text = msg.get("content") or ""

    tool_calls: list[ToolCallRequest] = []
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function", {}) or {}
        import json as _json
        args = fn.get("arguments", "{}")
        try:
            parsed = _json.loads(args) if isinstance(args, str) else args
        except Exception:
            parsed = {"_raw": args}
        tool_calls.append(ToolCallRequest(
            id=tc.get("id", ""),
            name=fn.get("name", ""),
            arguments=parsed or {},
        ))

    usage = raw.get("usage", {}) or {}
    tokens = TokenStats(
        input=int(usage.get("prompt_tokens", 0) or 0),
        output=int(usage.get("completion_tokens", 0) or 0),
    )
    stop = (choices[0] or {}).get("finish_reason", "stop") if choices else "stop"

    return CompletionResult(
        text=text,
        tool_calls=tool_calls,
        tokens=tokens,
        stop_reason="tool_use" if tool_calls else "end_turn",
        model=raw.get("model", model),
        cache_ttl_used="none",
        raw=raw,
    )
