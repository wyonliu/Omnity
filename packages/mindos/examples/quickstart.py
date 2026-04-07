#!/usr/bin/env python3
"""Mindos Quick Start — create a 5-layer brain and store/recall memories.

Usage:
    export DEEPSEEK_API_KEY="sk-..."   # optional, for LLM-powered layers
    python quickstart.py
"""

import tempfile, os
from mindos import Mindos, MindosConfig

# --- Method 1: from_env() auto-detects your API keys ---
home = os.path.join(tempfile.mkdtemp(), "brain-demo")
config = MindosConfig.from_env()
brain = Mindos(home, config)

print(f"Brain created at {home}")
print(f"Router providers: {[p.name for p in config.router.config.providers]}")
print()

# Store memories
brain.l0.store.add("I'm working on a Rust compiler", category="fact", importance=0.8)
brain.l0.store.add("Met Alice at the AI conference", category="episode", importance=0.7)
brain.l0.store.add("I prefer vim over emacs", category="preference", importance=0.5)

# Recall
results = brain.l0.recall("compiler", limit=5)
print(f"Recall 'compiler': {len(results)} results")
for m in results:
    print(f"  - [{m.category}] {m.content[:60]}")
print()

# --- Method 2: from_dict() for programmatic config ---
config2 = MindosConfig.from_dict({
    "providers": [
        {"name": "deepseek", "api_key": os.getenv("DEEPSEEK_API_KEY", "sk-test"),
         "model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"},
    ]
})
print(f"from_dict providers: {[p.name for p in config2.router.config.providers]}")
print()

# L1: Instinct (emotion detection)
emotion = brain.l1.detect_emotion("I'm so excited about this project!")
print(f"Emotion: {emotion}")

# Commit to memory (goes through all layers)
brain.commit("Just finished the lexer module for my compiler", "episode", {"mood": "proud"})
print("Committed new memory through all layers.")
print(f"Total memories: {brain.l0.store.count()}")
