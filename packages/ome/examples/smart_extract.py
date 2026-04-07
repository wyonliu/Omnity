#!/usr/bin/env python3
"""Ome Smart Extraction — parse contacts, tasks, and notes from natural language.

Usage:
    export DEEPSEEK_API_KEY="sk-..."
    python smart_extract.py
"""

import tempfile, os, json
from ome import Ome

home = os.path.join(tempfile.mkdtemp(), "extract-demo")
twin = Ome.create(home, name="Assistant", traits=["organized"])

# Chinese input
result = twin.smart_extract("帮我记住张三的电话 13800138000，明天下午两点开会讨论新项目")
print("Input: 帮我记住张三的电话 13800138000，明天下午两点开会讨论新项目")
print(f"Result: {json.dumps(result, ensure_ascii=False, indent=2)}")
print()

# English input
result = twin.smart_extract("Remind me to call John at 5pm, his email is john@example.com")
print("Input: Remind me to call John at 5pm, his email is john@example.com")
print(f"Result: {json.dumps(result, ensure_ascii=False, indent=2)}")
print()

# Verify it was remembered
memories = twin.recall("张三")
print(f"Recalled {len(memories)} memories about '张三'")
for m in memories:
    print(f"  - {m.content[:80]}")
