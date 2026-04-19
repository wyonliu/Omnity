"""HarnessEngine — the Personal Harness tool loop.

One call = one `HarnessResult`:

    engine.run(user_message="...")
      → ContextBuilder builds system prompt from MemoryDoc files
      → ModelBackend.complete(...)  (may request tool calls)
      → for each tool call: ToolRegistry.invoke(...)
      → feed tool_results back to model
      → repeat until end_turn / max_steps
      → return HarnessResult with full provenance

Design invariants (ratified 2026-04-19):
- Default single-agent. `run(..., agent_team=...)` is gated (W4).
- Explicit prompt-cache TTL. Engine delegates to backend; backend chooses
  "1h" by default where supported (beats Anthropic's 03-06 regression).
- File-first context. Reads IDENTITY.md / MEMORY.md / FACTS.md directly.
- Fail-soft tools. A failing tool becomes a tool_result with `is_error=True`
  rather than aborting the run.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from mindos.harness.context import AssembledContext, ContextBuilder
from mindos.harness.models.base import (
    CompletionResult,
    ModelBackend,
    TokenStats,
    ToolCallRequest,
)
from mindos.harness.tools import ToolCall, ToolRegistry

log = logging.getLogger("mindos.harness.engine")


@dataclass
class HarnessResult:
    """Everything one user turn produced. Fully auditable."""
    response: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    context_files: list[str] = field(default_factory=list)
    tokens: TokenStats = field(default_factory=TokenStats)
    steps: int = 0
    model: str = ""
    cache_ttl_used: str = ""
    truncated_context: bool = False
    stop_reason: str = "end_turn"

    # Reserved, disabled by default — Agent Team (W4)
    sub_agent_delegations: list = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "response_chars": len(self.response),
            "tool_calls": [{"name": c.name, "ok": c.error is None} for c in self.tool_calls],
            "steps": self.steps,
            "model": self.model,
            "cache_ttl": self.cache_ttl_used,
            "tokens": {
                "in": self.tokens.input, "out": self.tokens.output,
                "cache_r": self.tokens.cached_read,
                "cache_w": self.tokens.cached_write,
            },
            "context_files": list(self.context_files),
            "truncated_context": self.truncated_context,
            "stop_reason": self.stop_reason,
        }


class HarnessEngine:
    """Personal Harness Runtime — context + tools + model, looped."""

    def __init__(
        self,
        *,
        context_source: Path | str,
        model: ModelBackend,
        tools: Optional[ToolRegistry] = None,
        max_steps: int = 20,
        max_chars: int = 48_000,
        recent_days: int = 3,
        cache_ttl: Optional[str] = None,
    ):
        self.context_builder = ContextBuilder(
            source=context_source,
            max_chars=max_chars,
            recent_days=recent_days,
        )
        self.model = model
        self.tools = tools or ToolRegistry()
        self.max_steps = int(max_steps)
        self.cache_ttl = cache_ttl  # None → backend default

    # -- public ---------------------------------------------------------

    def run(
        self,
        user_message: str,
        *,
        agent_team: Any = None,
        extra_system: Optional[str] = None,
    ) -> HarnessResult:
        if agent_team is not None:
            raise NotImplementedError(
                "agent_team= is gated until W4. Default single-agent only "
                "(Cognition 2025-06 principle still applies to general tasks).",
            )

        ctx = self.context_builder.build(user_message)
        system = _merge_system(ctx, extra_system)

        messages: list[dict] = [{
            "role": "user",
            "content": [{"type": "text", "text": ctx.user_message}],
        }]

        result = HarnessResult(
            context_files=list(ctx.files_used),
            truncated_context=ctx.truncated,
            cache_ttl_used=self.cache_ttl or self.model.default_cache_ttl,
        )

        tool_schema = self.tools.as_anthropic_schema() if len(self.tools) else None

        for step in range(1, self.max_steps + 1):
            completion = self.model.complete(
                system=system,
                messages=messages,
                tools=tool_schema,
                cache_ttl=self.cache_ttl,
            )
            result.tokens.add(completion.tokens)
            result.steps = step
            result.model = completion.model or self.model.name
            result.cache_ttl_used = completion.cache_ttl_used or result.cache_ttl_used
            result.stop_reason = completion.stop_reason

            if completion.tool_calls:
                # Record assistant message with tool_use blocks
                messages.append({
                    "role": "assistant",
                    "content": _assistant_tool_blocks(completion),
                })
                # Invoke each tool; append a single user turn with tool_results
                tool_results: list[dict] = []
                for req in completion.tool_calls:
                    call = self._invoke(req)
                    result.tool_calls.append(call)
                    tool_results.append(_tool_result_block(call))
                messages.append({"role": "user", "content": tool_results})
                continue  # next step — give the model tool outputs

            # No more tool calls: end of turn
            result.response = completion.text
            break
        else:
            # Hit max_steps without end_turn
            result.stop_reason = "max_steps"
            log.warning("harness run hit max_steps=%d", self.max_steps)

        return result

    # -- internals ------------------------------------------------------

    def _invoke(self, req: ToolCallRequest) -> ToolCall:
        start = time.time()
        value, err = self.tools.invoke(req.name, req.arguments)
        ms = int((time.time() - start) * 1000)
        return ToolCall(
            id=req.id,
            name=req.name,
            arguments=dict(req.arguments or {}),
            result=value,
            error=err,
            ms=ms,
        )


# -- helpers ---------------------------------------------------------------

def _merge_system(ctx: AssembledContext, extra: Optional[str]) -> str:
    if not extra:
        return ctx.system_prompt
    return f"{ctx.system_prompt}\n\n# Session directives\n\n{extra}".strip()


def _assistant_tool_blocks(completion: CompletionResult) -> list[dict]:
    """Rebuild the assistant message Anthropic sent, preserving any text + tool_use."""
    blocks: list[dict] = []
    if completion.text:
        blocks.append({"type": "text", "text": completion.text})
    for tc in completion.tool_calls:
        blocks.append({
            "type": "tool_use",
            "id": tc.id or f"tc-{tc.name}",
            "name": tc.name,
            "input": tc.arguments,
        })
    return blocks


def _tool_result_block(call: ToolCall) -> dict:
    """Shape a single tool_result content block for the user message."""
    if call.error:
        return {
            "type": "tool_result",
            "tool_use_id": call.id or f"tc-{call.name}",
            "is_error": True,
            "content": [{"type": "text", "text": f"error: {call.error}"}],
        }
    content = call.result
    if not isinstance(content, str):
        import json as _json
        try:
            content = _json.dumps(content, ensure_ascii=False, default=str)
        except Exception:
            content = str(content)
    return {
        "type": "tool_result",
        "tool_use_id": call.id or f"tc-{call.name}",
        "content": [{"type": "text", "text": content}],
    }
