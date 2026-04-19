"""mindos.harness — Personal Harness Runtime.

`Agent = Model + Harness`. This package is the *harness*: everything around
a model that makes it actually useful for one person — context assembly,
skills-as-tools, prompt cache policy, tool-loop recovery, optional sub-agents.

Design rules (ratified 2026-04-19):
- Default **single-agent**. Agent Teams are gated behind an explicit flag —
  Cognition's 2025-06 "Don't Build Multi-Agents" critique still applies to
  general tasks; we only spin up sub-agents when the user asks for it.
- **Explicit prompt-cache TTL** on every request. Anthropic silently flipped
  the default from 1h back to 5m on 2026-03-06; blindly riding defaults
  burns money. Backends that support caching must accept a `cache_ttl`
  parameter ("5m" | "1h") and surface what they actually used.
- **File-first context**: MemoryDoc markdown is the source of truth. The
  harness reads IDENTITY.md / MEMORY.md / FACTS.md directly rather than
  going through a bespoke memory API.
- **Pluggable models**: Claude, Kimi K2 Thinking, Qwen3 — one interface.
  Backends are injectable for tests (no network required).
"""

from __future__ import annotations

from mindos.harness.engine import HarnessEngine, HarnessResult
from mindos.harness.context import AssembledContext, ContextBuilder, ContextLoader
from mindos.harness.tools import ToolRegistry, ToolCall, ToolSpec
from mindos.harness.builtins import register_builtins
from mindos.harness.overnight import (
    OvernightConfig,
    OvernightReport,
    OvernightSoulSync,
)
from mindos.harness.skills_package import (
    load_skill_package,
    load_skill_dir,
    shipped_skills_dir,
)
from mindos.harness.models.base import (
    ModelBackend,
    CompletionResult,
    TokenStats,
    StubBackend,
)

__all__ = [
    "HarnessEngine",
    "HarnessResult",
    "ContextBuilder",
    "AssembledContext",
    "ContextLoader",
    "ToolRegistry",
    "ToolCall",
    "ToolSpec",
    "register_builtins",
    "OvernightSoulSync",
    "OvernightConfig",
    "OvernightReport",
    "load_skill_package",
    "load_skill_dir",
    "shipped_skills_dir",
    "ModelBackend",
    "CompletionResult",
    "TokenStats",
    "StubBackend",
]
