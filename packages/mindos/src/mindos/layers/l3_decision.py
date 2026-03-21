"""L3 Prefrontal — Decision layer: deep reasoning, planning, behavior orchestration.

Handles complex requests that require multi-step reasoning, strategic planning,
or creative synthesis. Uses the most capable LLM available via ModelRouter.
"""

from __future__ import annotations

from typing import Any, Optional

from mindos.config import ModelRouter


_PLANNING_SYSTEM = """You are the decision-making center of a personal AI identity called Mindos.
You have access to the person's personality, memories, and knowledge graph.
Your role:
1. Break complex requests into actionable steps
2. Resolve conflicts between competing priorities
3. Orchestrate multi-step behaviors
4. Apply strategic reasoning with the person's values and goals in mind

Always respond with structured, actionable output."""


class Prefrontal:
    """L3: strategic reasoning and behavior orchestration."""

    def __init__(self, model_router: Optional[ModelRouter] = None) -> None:
        self.router = model_router

    def reason(self, query: str, identity_context: str = "",
               memory_context: str = "") -> Optional[str]:
        """Deep reasoning with full context."""
        if self.router is None:
            return None

        user_msg = f"""Identity context:
{identity_context}

Relevant memories:
{memory_context}

Request: {query}"""

        return self.router.call_llm(
            system=_PLANNING_SYSTEM, user=user_msg,
            task="reasoning", max_tokens=2048,
        )

    def plan(self, goal: str, constraints: list[str] | None = None,
             identity_context: str = "") -> Optional[str]:
        """Generate a structured plan for a complex goal."""
        if self.router is None:
            return None

        constraint_block = ""
        if constraints:
            constraint_block = "\nConstraints:\n" + "\n".join(f"- {c}" for c in constraints)

        user_msg = f"""Identity context:
{identity_context}

Goal: {goal}
{constraint_block}

Generate a step-by-step plan with clear milestones."""

        return self.router.call_llm(
            system=_PLANNING_SYSTEM, user=user_msg,
            task="reasoning", max_tokens=2048,
        )

    def resolve_conflict(self, option_a: str, option_b: str,
                         values: list[str] | None = None) -> Optional[str]:
        """Resolve a conflict between two options using the person's values."""
        if self.router is None:
            return None

        values_block = ""
        if values:
            values_block = "\nCore values: " + ", ".join(values)

        user_msg = f"""A conflict needs resolution:
Option A: {option_a}
Option B: {option_b}
{values_block}

Analyze both options considering the person's values, and recommend one with reasoning."""

        return self.router.call_llm(
            system=_PLANNING_SYSTEM, user=user_msg,
            task="deep_reasoning", max_tokens=1024,
        )
