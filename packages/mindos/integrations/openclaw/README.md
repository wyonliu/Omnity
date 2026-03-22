# Mindos × OpenClaw Integration

Give every Claw a persistent memory and personality layer.

## Quick Start

```python
from mindos import Mindos

# Load or create the user's soul
soul = Mindos.load()  # reads from ~/.mindos/

# At the start of every Claw session: hydrate
identity_context = soul.hydrate(context="the task your claw is working on")

# Inject into the Claw's system prompt
system_prompt = f"""
{identity_context}

---
You are a helpful assistant. Use the identity context above to personalize
your responses. Remember the user's preferences and communication style.
"""

# After the Claw session: commit the conversation
soul.commit(conversation_text, source="openclaw")
```

## As an OpenClaw Plugin

```python
# openclaw_mindos_plugin.py
"""Mindos plugin for OpenClaw — persistent memory across all Claws."""

from mindos import Mindos
from mindos.client import MindosClient


class MindosPlugin:
    """Drop-in plugin: hydrate before, commit after every Claw run."""

    def __init__(self, soul_path: str = "~/.mindos"):
        # Try server first (supports multi-Claw concurrency)
        self.client = MindosClient.discover(soul_path)
        if not self.client:
            self._soul = Mindos.load(soul_path)
        else:
            self._soul = None

    def before_run(self, task_description: str = "") -> str:
        """Call before each Claw run. Returns identity context for system prompt."""
        if self.client:
            return self.client.hydrate(context=task_description)
        return self._soul.hydrate(context=task_description)

    def after_run(self, conversation: str, source: str = "openclaw") -> dict:
        """Call after each Claw run. Digests conversation into memories."""
        if self.client:
            return self.client.commit(conversation, source=source)
        return self._soul.commit(conversation, source=source)

    def recall(self, query: str, top_k: int = 10) -> list:
        """Search the user's memories."""
        if self.client:
            return self.client.recall(query, top_k=top_k)
        return self._soul.recall(query, top_k=top_k)

    def status(self) -> dict:
        if self.client:
            return self.client.status()
        return self._soul.status()


# Usage in an OpenClaw Claw:
#
#   plugin = MindosPlugin()
#   context = plugin.before_run("code review for my project")
#   # ... run claw with context in system prompt ...
#   plugin.after_run(conversation_text)
```

## Multi-Claw Concurrency

When multiple Claws run simultaneously, use server mode:

```bash
# Terminal 1: start Mindos server
mindos serve

# Now any number of Claws can connect via MindosClient
# The server handles concurrent access safely
```

The `MindosPlugin` automatically detects the server via lockfile.

## What Gets Remembered

After each conversation, Mindos extracts:
- **Facts**: biographical info, knowledge, stated facts
- **Preferences**: likes, dislikes, habits
- **Skills**: things the user knows or can do
- **Relations**: people and organizations mentioned
- **Episodes**: conversation summaries

All data stays local in `~/.mindos/`. No cloud, no telemetry.
