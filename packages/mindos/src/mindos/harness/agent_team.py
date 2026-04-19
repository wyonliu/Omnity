"""Agent Team — opt-in multi-agent dispatch.

We default to single-agent for good reason (Cognition 2025-06 "Don't Build
Multi-Agents" and Anthropic 2025-09 follow-up). Multi-agent systems fail
mostly from **diverging state** and **unstructured branches**. Teams here
are useful only if they:

1. **Share the lead's context** — every sub-agent sees the full context the
   lead just built. No parallel discovery, no hidden state.
2. **Run one-shot, not as a loop** — the lead delegates, collects results,
   then decides. Sub-agents don't talk to each other.
3. **Branch only with structure** — if parallel, each sub-agent gets a
   disjoint role with explicit output contract. No "figure it out together."

This module wires that discipline. `agent_team=["reviewer", "fact-checker"]`
fans out to two sub-agents, each prepended with its role, each running one
turn (no tool loop), and folds their outputs back into the lead's next
prompt. The lead then keeps running as a normal single-agent loop.

If you want real sub-agents with their own tool loops, build it on top —
but accept the failure mode you're opting into.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from mindos.harness.models.base import CompletionResult, ModelBackend, TokenStats

log = logging.getLogger("mindos.harness.agent_team")


# --- public types ---------------------------------------------------------

@dataclass
class SubAgentRole:
    """One branch of a team delegation.

    `system` is the role-specific prefix (appended to the lead's system
    prompt). `instruction` is the task the lead hands to this sub-agent.
    """
    name: str
    system: str = ""
    instruction: str = ""
    model: Optional[ModelBackend] = None  # defaults to lead's model


@dataclass
class SubAgentOutput:
    """What one sub-agent turn produced."""
    name: str
    text: str = ""
    tokens: TokenStats = field(default_factory=TokenStats)
    error: Optional[str] = None
    model: str = ""


@dataclass
class TeamResult:
    """Aggregate of one delegation round."""
    outputs: list[SubAgentOutput] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(o.error is None for o in self.outputs)

    def as_tool_result_block(self) -> str:
        """Format outputs as a markdown block the lead agent reads next."""
        parts = ["# Sub-agent report\n"]
        for o in self.outputs:
            parts.append(f"## {o.name}")
            if o.error:
                parts.append(f"_error: {o.error}_\n")
            else:
                parts.append(o.text.strip() + "\n")
        return "\n".join(parts)


# --- dispatcher -----------------------------------------------------------

def normalize_team(team: Any, *, default_model: Optional[ModelBackend] = None
                   ) -> list[SubAgentRole]:
    """Accept the common shapes: list[str] | list[dict] | list[SubAgentRole]."""
    roles: list[SubAgentRole] = []
    if team is None:
        return roles
    if not isinstance(team, (list, tuple)):
        raise ValueError("agent_team must be a list")
    for i, item in enumerate(team):
        if isinstance(item, SubAgentRole):
            roles.append(item if item.model else SubAgentRole(
                name=item.name, system=item.system, instruction=item.instruction,
                model=default_model,
            ))
        elif isinstance(item, str):
            roles.append(SubAgentRole(name=item, model=default_model))
        elif isinstance(item, dict):
            roles.append(SubAgentRole(
                name=item.get("name") or f"agent{i}",
                system=item.get("system") or "",
                instruction=item.get("instruction") or "",
                model=item.get("model") or default_model,
            ))
        else:
            raise ValueError(f"unsupported team member: {item!r}")
    return roles


def dispatch_team(
    *,
    roles: list[SubAgentRole],
    lead_system: str,
    lead_user_message: str,
    default_model: ModelBackend,
) -> TeamResult:
    """Run each sub-agent for exactly one turn. No tool loop.

    Sequential by default. Shared context: every sub-agent sees the lead's
    system prompt + the lead's user message. They never see each other.
    """
    result = TeamResult()
    for role in roles:
        model = role.model or default_model
        full_system = _merge_role(lead_system, role)
        user_msg = role.instruction.strip() or lead_user_message
        try:
            completion: CompletionResult = model.complete(
                system=full_system,
                messages=[{
                    "role": "user",
                    "content": [{"type": "text", "text": user_msg}],
                }],
                tools=None,        # sub-agents don't get tools — lead owns dispatch
                cache_ttl=None,    # each backend uses its own default
            )
            result.outputs.append(SubAgentOutput(
                name=role.name,
                text=completion.text,
                tokens=completion.tokens,
                model=completion.model or model.name,
            ))
        except Exception as e:
            log.exception("sub-agent %s failed", role.name)
            result.outputs.append(SubAgentOutput(
                name=role.name,
                error=f"{type(e).__name__}: {e}",
                model=model.name,
            ))
    return result


# --- helpers --------------------------------------------------------------

def _merge_role(lead_system: str, role: SubAgentRole) -> str:
    """Prepend the lead's system prompt to the role-specific directives."""
    role_block = role.system.strip()
    if not role_block:
        role_block = f"You are the sub-agent **{role.name}**. Respond with your focused contribution."
    return f"{lead_system}\n\n---\n# Sub-agent role\n{role_block}".strip()
