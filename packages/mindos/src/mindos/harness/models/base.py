"""Model backend abstract base + a deterministic StubBackend for tests.

A backend is the thinnest possible wrapper over a chat-completion API:
system prompt + messages + tools → text / tool_calls / tokens.

It is the **only** place in the harness that speaks to a remote model.
Everything upstream (ContextBuilder, ToolRegistry, HarnessEngine) is pure
python.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class TokenStats:
    """Token accounting for one completion call."""
    input: int = 0
    output: int = 0
    cached_read: int = 0   # tokens that hit an existing cache entry
    cached_write: int = 0  # tokens written into a new cache entry

    @property
    def total(self) -> int:
        return self.input + self.output

    def add(self, other: "TokenStats") -> None:
        self.input += other.input
        self.output += other.output
        self.cached_read += other.cached_read
        self.cached_write += other.cached_write


@dataclass
class ToolCallRequest:
    """A tool the model wants us to execute. Raw from the backend."""
    id: str
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class CompletionResult:
    """One round-trip with the model."""
    text: str = ""
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    tokens: TokenStats = field(default_factory=TokenStats)
    stop_reason: str = "end_turn"  # "end_turn" | "tool_use" | "max_tokens" | "error"
    model: str = ""
    cache_ttl_used: str = ""  # what TTL the backend actually asked for
    raw: dict = field(default_factory=dict)


class ModelBackend:
    """Abstract model backend."""

    name: str = "abstract"
    supports_cache: bool = False
    # Policy: each backend declares the TTL it wants when the caller does
    # not override. Claude explicitly picks "1h" to beat the 2026-03-06 default
    # regression; stubs just echo "none".
    default_cache_ttl: str = "none"

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
        raise NotImplementedError


# ---------------------------------------------------------------------------

class StubBackend(ModelBackend):
    """Deterministic no-network backend for tests & `harness run --stub`.

    Echoes the last user message, optionally invoking a scripted sequence of
    tool calls so we can exercise the tool loop end-to-end.
    """

    name = "stub"
    default_cache_ttl = "none"

    def __init__(
        self,
        *,
        reply: Optional[str] = None,
        reply_fn: Optional[Callable[[list[dict]], str]] = None,
        tool_script: Optional[list[list[ToolCallRequest]]] = None,
    ):
        self._reply = reply
        self._reply_fn = reply_fn
        self._tool_script = list(tool_script or [])
        self.calls: list[dict] = []  # inspect in tests

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
        self.calls.append({
            "system": system, "messages": list(messages),
            "tools": tools, "cache_ttl": cache_ttl,
        })

        # Pop a scripted tool batch if any remain
        if self._tool_script:
            batch = self._tool_script.pop(0)
            return CompletionResult(
                text="",
                tool_calls=list(batch),
                tokens=TokenStats(input=len(str(messages)), output=0),
                stop_reason="tool_use",
                model=self.name,
                cache_ttl_used=cache_ttl or "none",
            )

        # Otherwise produce a final text reply
        if self._reply_fn:
            text = self._reply_fn(messages)
        elif self._reply is not None:
            text = self._reply
        else:
            last_user = next(
                (m["content"] for m in reversed(messages)
                 if m.get("role") == "user"),
                "",
            )
            if isinstance(last_user, list):  # tool_result blocks, text blocks, etc.
                text_from_blocks = next(
                    (b.get("text", "") for b in last_user
                     if isinstance(b, dict) and b.get("type") == "text"),
                    None,
                )
                if text_from_blocks is None:
                    # Fallback: tool_result blocks carry content on a different key
                    text_from_blocks = next(
                        (str(b.get("content", "")) for b in last_user
                         if isinstance(b, dict) and b.get("type") == "tool_result"),
                        "",
                    )
                last_user = text_from_blocks
            text = f"[stub] {last_user}".strip()

        return CompletionResult(
            text=text,
            tokens=TokenStats(input=len(str(messages)), output=len(text)),
            stop_reason="end_turn",
            model=self.name,
            cache_ttl_used=cache_ttl or "none",
        )
