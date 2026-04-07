#!/usr/bin/env python3
"""Ome Quick Start — create a twin and have a conversation.

Usage:
    export DEEPSEEK_API_KEY="sk-..."   # or OPENAI_API_KEY / OPENROUTER_API_KEY
    python quickstart.py
"""

import tempfile, os
from ome import Ome

# Create a twin in a temp directory (use a real path for persistence)
home = os.path.join(tempfile.mkdtemp(), "my-twin")
twin = Ome.create(home, name="Alice", traits=["curious", "direct"])

print(f"Twin created at {home}")
print(f"Phase: {twin.life_dashboard()['phase']}")
print()

# Simple chat
reply = twin.chat("Hi! I'm a Python developer working on a compiler.")
print(f"Alice: {reply}")
print()

# Rich chat — get memories, emotion, bond info
result = twin.chat_rich("What do you know about me?")
print(f"Alice: {result['reply']}")
print(f"Memories recalled: {len(result['memories_recalled'])}")
print(f"Emotion: {result['emotion']}")
print(f"Bond level: {result['bond']['level']}")
print()

# Recall memories
memories = twin.recall("compiler")
print(f"Found {len(memories)} memories about 'compiler'")
for m in memories:
    print(f"  - [{m.category}] {m.content[:80]}")
print()

# Life dashboard
dash = twin.life_dashboard()
print(f"Bond: {dash['bond']['label']} (level {dash['bond']['level']})")
print(f"Phase: {dash['phase']}")
print(f"Achievements: {dash['achievements_unlocked']}/{dash['achievements_total']}")
