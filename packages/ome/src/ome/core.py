"""Ome core — your AI twin, powered by Mindos.

Ome is the consumer-facing wrapper around Mindos. It adds:
  - Conversational chat with automatic memory commit/recall
  - Persona-aware response generation (your Ome speaks like you)
  - Simple create/chat/export interface (no brain-layer jargon)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

from mindos.core import Mindos

log = logging.getLogger("ome")


class Ome:
    """Your AI twin — remembers everything, speaks like you, works for you.

    Usage:
        ome = Ome.create("~/.ome", name="Alice", traits=["curious", "direct"])
        ome = Ome.load("~/.ome")

        # Chat (auto-remembers everything)
        reply = ome.chat("What do you know about my Python projects?")

        # Export portable persona for any platform
        persona = ome.export()
    """

    def __init__(self, soul: Mindos, root: Path) -> None:
        self.soul = soul
        self.root = root
        self._chat_history: list[dict[str, str]] = []

    @classmethod
    def create(
        cls,
        path: str | Path = "~/.ome",
        name: str = "User",
        traits: Optional[list[str]] = None,
        style: str = "",
        values: Optional[list[str]] = None,
        capabilities: Optional[list[dict]] = None,
    ) -> "Ome":
        """Create a new Ome (your digital twin)."""
        root = Path(path).expanduser()
        soul = Mindos.init(
            root, name=name, traits=traits, style=style,
            values=values, capabilities=capabilities,
        )
        return cls(soul, root)

    @classmethod
    def load(cls, path: str | Path = "~/.ome") -> "Ome":
        """Load an existing Ome."""
        root = Path(path).expanduser()
        soul = Mindos.load(root)
        return cls(soul, root)

    # -- Chat (the main interface) -------------------------------------------

    def chat(self, message: str, provider: str = "") -> str:
        """Talk to your Ome. It remembers everything you've ever said.

        1. Recalls relevant memories based on your message
        2. Assembles identity + context
        3. Generates a response (via LLM)
        4. Commits the exchange to long-term memory

        Returns the Ome's response text.
        """
        # Step 1: Recall relevant context
        memories = self.soul.recall(message, top_k=5)
        memory_context = "\n".join(
            f"- [{m.get('type', '?')}] {m.get('content', '')}"
            for m in memories
        ) if memories else "(no relevant memories yet)"

        # Step 2: Build identity context
        identity = self.soul.hydrate(context=message, max_tokens=1500)

        # Step 3: Generate response via LLM
        system_prompt = self._build_system_prompt(identity, memory_context)
        reply = self._generate(system_prompt, message, provider)

        # Step 4: Commit to memory
        conversation = f"user: {message}\nassistant: {reply}"
        self._chat_history.append({"role": "user", "content": message})
        self._chat_history.append({"role": "assistant", "content": reply})

        try:
            self.soul.commit(conversation, source="ome-chat")
        except Exception as e:
            log.warning("Failed to commit chat: %s", e)

        return reply

    def remember(self, text: str, source: str = "manual") -> dict[str, Any]:
        """Teach your Ome something directly."""
        return self.soul.commit(f"user: {text}", source=source)

    def recall(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Ask your Ome what it remembers about a topic."""
        return self.soul.recall(query, top_k=top_k)

    def forget(self, pattern: str) -> dict[str, Any]:
        """Make your Ome forget something. Permanent."""
        return self.soul.forget(pattern)

    # -- Export (portable persona) -------------------------------------------

    def export(self, context: str = "") -> dict[str, Any]:
        """Export your Ome as a portable persona package.

        The exported JSON can be injected into any AI platform:
        Claude, ChatGPT, Gemini, local models, OpenClaw agents.
        """
        return self.soul.export_ome(context=context)

    def export_system_prompt(self, context: str = "") -> str:
        """Export your Ome as a system prompt string.

        Simpler than full export — just paste into any AI's system prompt.
        """
        return self.soul.hydrate(context=context, max_tokens=3000)

    # -- Status --------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """What does your Ome know?"""
        s = self.soul.status()
        s["ome_version"] = "0.1.0"
        return s

    @property
    def name(self) -> str:
        return self.soul.identity.get("name", "Ome")

    @property
    def traits(self) -> list[str]:
        p = self.soul.identity.get("personality", {})
        return p.get("traits", [])

    # -- Internal ------------------------------------------------------------

    def _build_system_prompt(self, identity: str, memory_context: str) -> str:
        """Assemble the system prompt for chat."""
        name = self.name
        return (
            f"You are {name}'s Ome — their AI twin. "
            f"You speak in their voice, know their history, and represent them.\n\n"
            f"## Identity\n{identity}\n\n"
            f"## Relevant Memories\n{memory_context}\n\n"
            f"## Instructions\n"
            f"- Respond as {name} would — match their style, values, and knowledge.\n"
            f"- Be direct and authentic. Don't be generic.\n"
            f"- If you don't know something, say so honestly.\n"
            f"- Keep responses concise unless detail is needed.\n"
        )

    def _generate(self, system: str, user_message: str, provider: str = "") -> str:
        """Generate a response using the configured LLM."""
        router = getattr(self.soul.layers.l2, "router", None)
        if router:
            try:
                result = router.call_llm(
                    task="chat",
                    system=system,
                    user=user_message,
                    max_tokens=1024,
                    provider_name=provider or None,
                )
                if result:
                    return result
            except Exception as e:
                log.warning("LLM generation failed: %s", e)

        # Fallback: return a helpful message instead of crashing
        return (
            f"[Ome needs an LLM to chat. "
            f"Set DEEPSEEK_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY "
            f"in your environment, then try again.]\n\n"
            f"In the meantime, I remembered what you said. "
            f"Try: ome recall \"{user_message[:30]}...\""
        )
