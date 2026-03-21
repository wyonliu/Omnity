"""Integration tests for the Mindos five-layer architecture."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mindos.core import Mindos
from mindos.store import Triple


def test_full_lifecycle():
    """Init → commit × N → hydrate → recall → forget → status."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="TestUser", traits=["curious", "efficient"],
                        style="concise", values=["honesty", "growth"])
        assert (Path(tmp) / "identity.yaml").exists()
        assert (Path(tmp) / "memory.db").exists()
        assert (Path(tmp) / "config.yaml").exists()

        s = m.status()
        assert s["identity"]["name"] == "TestUser"
        print(f"  init: {s['identity']}")

        r1 = m.commit("user: 我住在上海，是一名 AI 工程师\nassistant: 好的，了解了！", source="claude")
        print(f"  commit#1: {r1}")
        assert r1["facts_added"] >= 1 or r1["episode"] != ""

        r2 = m.commit("user: 我喜欢喝冰美式\nassistant: 记住了", source="gpt")
        print(f"  commit#2: {r2}")

        r3 = m.commit("user: 我计划下周去东京出差\nassistant: 需要帮你做行程规划吗？", source="claude")
        print(f"  commit#3: {r3}")

        r4 = m.commit("user: 我擅长 Python 和分布式系统\nassistant: 核心技能。", source="cursor")
        print(f"  commit#4: {r4}")

        # Sensitive info must be blocked
        r5 = m.commit("user: 我的API密钥是 sk-abc123def456ghi789jkl012mno\nassistant: 收到。", source="test")
        print(f"  commit#5 (sensitive): skipped={r5.get('skipped_sensitive', 0)}")
        assert r5.get("skipped_sensitive", 0) >= 1 or r5.get("method") == "blocked"

        s = m.status()
        mem = s["memory"]
        print(f"  memories: {mem['total_memories']}, KG: {mem['knowledge_graph_triples']}")

        # Hydrate
        ctx = m.hydrate(context="旅行计划")
        assert "TestUser" in ctx
        print(f"  hydrate: {len(ctx)} chars")

        # Recall
        results = m.recall("上海", top_k=5)
        print(f"  recall '上海': {len(results)} results")
        assert len(results) >= 1

        # Forget
        result = m.forget("东京")
        print(f"  forget '东京': {result}")
        remaining = m.store.search_text("东京")
        assert len(remaining) == 0

    print("  PASSED")


def test_commit_dedup():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="D")
        m.commit("user: 我住在杭州", source="t1")
        r2 = m.commit("user: 我住在杭州", source="t2")
        assert r2.get("skipped_duplicate", 0) >= 1
    print("  PASSED")


def test_forget_kg():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="K")
        m.store.add_triple(Triple("User", "visited", "东京"))
        m.store.add_triple(Triple("User", "likes", "coffee"))
        m.forget("东京")
        triples = m.store.triples()
        assert len(triples) == 1
        assert triples[0].object == "coffee"
    print("  PASSED")


def test_reload_identity():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="OldName")
        m.identity["name"] = "NewName"
        m.save_identity()
        m.identity["name"] = "StaleCache"
        m.reload_identity()
        assert m.identity["name"] == "NewName"
    print("  PASSED")


def test_layer_router():
    """Verify LayerRouter wiring."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="Router", traits=["analytical"])
        assert m.layers.l1.classify_request("你好") == "l1"
        assert m.layers.l1.classify_request("你是谁") == "l4"
        assert m.layers.l1.classify_request("帮我分析一下这个方案") == "l3"
        assert m.layers.l1.classify_request("我今天学了Python") == "l2"
    print("  PASSED")


def test_relevance_scoring():
    """Verify memories are ranked by composite relevance score."""
    import time
    from mindos.store import Memory
    from mindos.layers.l0_memory import relevance_score

    now = time.time()
    recent = Memory(id="r", type="fact", content="recent", created_at=now, confidence=1.0, access_count=0, decay_weight=1.0)
    old = Memory(id="o", type="fact", content="old", created_at=now - 86400 * 60, confidence=1.0, access_count=0, decay_weight=1.0)
    important = Memory(id="i", type="fact", content="important", created_at=now - 86400 * 60, confidence=1.0, access_count=50, decay_weight=1.0)

    assert relevance_score(recent, now) > relevance_score(old, now)
    assert relevance_score(important, now) > relevance_score(old, now)
    print("  PASSED")


def test_emotion_state():
    """Verify brainstem emotion tracking."""
    from mindos.layers.l1_instinct import EmotionState, Mood
    e = EmotionState()
    e.tick()
    assert e.energy > 0
    e.boost(0.5)
    assert e.mood == Mood.ENGAGED
    assert e.energy <= 1.0
    print("  PASSED")


def test_mcp_protocol():
    """Verify MCP server handles initialize and tools/list."""
    import json
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="MCP")
        from mindos.mcp_server import McpServer
        server = McpServer(m.layers)

        init_resp = server._handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert init_resp["result"]["protocolVersion"] == "2024-11-05"

        tools_resp = server._handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tool_names = {t["name"] for t in tools_resp["result"]["tools"]}
        assert "mindos_hydrate" in tool_names
        assert "mindos_commit" in tool_names
        assert "mindos_recall" in tool_names
        assert "mindos_forget" in tool_names
        assert "mindos_reflect" in tool_names

        # Test tool call
        hydrate_resp = server._handle({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "mindos_hydrate", "arguments": {"context": "test"}}
        })
        assert hydrate_resp["result"]["content"][0]["type"] == "text"

        # Test commit via MCP
        commit_resp = server._handle({
            "jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "mindos_commit", "arguments": {"conversation": "user: 我住在北京", "source": "mcp-test"}}
        })
        result = json.loads(commit_resp["result"]["content"][0]["text"])
        assert "facts_added" in result

        # Test resources
        res_resp = server._handle({"jsonrpc": "2.0", "id": 5, "method": "resources/list", "params": {}})
        uris = {r["uri"] for r in res_resp["result"]["resources"]}
        assert "mindos://identity" in uris

    print("  PASSED")


if __name__ == "__main__":
    tests = [
        ("full_lifecycle", test_full_lifecycle),
        ("commit_dedup", test_commit_dedup),
        ("forget_kg", test_forget_kg),
        ("reload_identity", test_reload_identity),
        ("layer_router", test_layer_router),
        ("relevance_scoring", test_relevance_scoring),
        ("emotion_state", test_emotion_state),
        ("mcp_protocol", test_mcp_protocol),
    ]
    failed = 0
    for name, fn in tests:
        print(f"test_{name}...")
        try:
            fn()
        except Exception as e:
            print(f"  FAILED: {e}")
            import traceback; traceback.print_exc()
            failed += 1

    print(f"\n{'FAILED' if failed else 'ALL PASSED'}: {len(tests) - failed}/{len(tests)} tests")
    sys.exit(1 if failed else 0)
