"""Integration tests for Mindos — five-layer architecture, server, client, memory mgmt."""

import json
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mindos.core import Mindos
from mindos.store import Triple


def test_full_lifecycle():
    """Init → commit → hydrate → recall → forget → status."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="TestUser", traits=["curious", "efficient"],
                        style="concise", values=["honesty", "growth"])
        assert (Path(tmp) / "identity.yaml").exists()
        assert (Path(tmp) / "config.yaml").exists()

        r1 = m.commit("user: 我住在上海，是一名 AI 工程师\nassistant: 了解了！", source="claude")
        assert r1["facts_added"] >= 1 or r1["episode"] != ""

        m.commit("user: 我喜欢喝冰美式\nassistant: 记住了", source="gpt")
        m.commit("user: 我计划下周去东京出差\nassistant: 行程规划？", source="claude")
        m.commit("user: 我擅长 Python 和分布式系统\nassistant: 核心技能", source="cursor")

        r5 = m.commit("user: 我的API密钥是 sk-abc123def456ghi789jkl012mno\nassistant: 收到", source="test")
        assert r5.get("skipped_sensitive", 0) >= 1 or r5.get("method") == "blocked"

        ctx = m.hydrate(context="旅行计划")
        assert "TestUser" in ctx

        results = m.recall("上海", top_k=5)
        assert len(results) >= 1

        result = m.forget("东京")
        assert len(m.store.search_text("东京")) == 0
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
        assert len(triples) == 1 and triples[0].object == "coffee"
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
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="Router", traits=["analytical"])
        assert m.layers.l1.classify_request("你好") == "l1"
        assert m.layers.l1.classify_request("你是谁") == "l4"
        assert m.layers.l1.classify_request("帮我分析一下") == "l3"
        assert m.layers.l1.classify_request("今天学了Python") == "l2"
    print("  PASSED")


def test_relevance_scoring():
    from mindos.store import Memory
    from mindos.layers.l0_memory import relevance_score

    now = time.time()
    recent = Memory(id="r", type="fact", content="recent", created_at=now,
                    confidence=1.0, access_count=0, decay_weight=1.0)
    old = Memory(id="o", type="fact", content="old", created_at=now - 86400 * 60,
                 confidence=1.0, access_count=0, decay_weight=1.0)
    important = Memory(id="i", type="fact", content="important", created_at=now - 86400 * 60,
                       confidence=1.0, access_count=50, decay_weight=1.0)

    assert relevance_score(recent, now) > relevance_score(old, now)
    assert relevance_score(important, now) > relevance_score(old, now)
    print("  PASSED")


def test_emotion_state():
    from mindos.layers.l1_instinct import EmotionState, Mood
    e = EmotionState()
    e.tick()
    assert e.energy > 0
    e.boost(0.5)
    assert e.mood == Mood.ENGAGED
    print("  PASSED")


def test_mcp_protocol():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="MCP")
        from mindos.mcp_server import McpServer
        server = McpServer(m.layers)

        init_resp = server._handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        assert init_resp["result"]["protocolVersion"] == "2024-11-05"

        tools_resp = server._handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        tool_names = {t["name"] for t in tools_resp["result"]["tools"]}
        assert {"mindos_hydrate", "mindos_commit", "mindos_recall", "mindos_forget", "mindos_reflect"} <= tool_names

        commit_resp = server._handle({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "mindos_commit", "arguments": {"conversation": "user: 我住在北京", "source": "mcp"}}
        })
        result = json.loads(commit_resp["result"]["content"][0]["text"])
        assert "facts_added" in result

        res_resp = server._handle({"jsonrpc": "2.0", "id": 4, "method": "resources/list", "params": {}})
        uris = {r["uri"] for r in res_resp["result"]["resources"]}
        assert "mindos://identity" in uris
    print("  PASSED")


def test_server_client():
    """Start HTTP server, connect with client, verify round-trip."""
    from http.server import HTTPServer
    from mindos.server import MindosHandler, _write_lockfile, _remove_lockfile
    import mindos.server as srv

    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="ServerTest", traits=["smart"])
        m.commit("user: 我住在深圳\nassistant: 好的", source="setup")

        srv._mindos = m
        srv._serve_port = 0  # will be set after bind
        srv._start_time = time.time()

        httpd = HTTPServer(("127.0.0.1", 0), MindosHandler)
        port = httpd.server_address[1]
        srv._serve_port = port
        _write_lockfile(Path(tmp), port)

        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()

        try:
            from mindos.client import MindosClient
            client = MindosClient(f"http://127.0.0.1:{port}")

            assert client.health()

            s = client.status()
            assert s["identity"]["name"] == "ServerTest"

            ctx = client.hydrate(context="深圳")
            assert "ServerTest" in ctx

            r = client.commit("user: 我喜欢骑行\nassistant: 好的", source="client-test")
            assert r.get("facts_added", 0) >= 0

            results = client.recall("深圳")
            assert len(results) >= 1

            stats = client.stats()
            assert stats["total_memories"] >= 1

            export = client.export_memories()
            assert len(export["memories"]) >= 1

            # Auto-discover via lockfile
            discovered = MindosClient.discover(tmp)
            assert discovered is not None
            assert discovered.health()
        finally:
            httpd.shutdown()
            _remove_lockfile(Path(tmp))

    print("  PASSED")


def test_memory_export_import():
    """Export from one soul, import into another."""
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        m1 = Mindos.init(path=tmp1, name="Exporter")
        m1.commit("user: 我住在广州\nassistant: 好的", source="test")
        m1.store.add_triple(Triple("User", "lives_in", "Guangzhou"))

        all_mems = m1.store.list_recent(limit=10000)
        triples = m1.store.triples()
        export_data = {
            "version": 1,
            "memories": [
                {"type": x.type, "content": x.content, "source": x.source,
                 "confidence": x.confidence, "decay_weight": x.decay_weight}
                for x in all_mems
            ],
            "knowledge_graph": [
                {"subject": t.subject, "predicate": t.predicate,
                 "object": t.object, "source": t.source}
                for t in triples
            ],
        }

        m2 = Mindos.init(path=tmp2, name="Importer")
        from mindos.server import _import_memories
        result = _import_memories(m2, export_data)
        assert result["memories_imported"] >= 1
        assert result["triples_imported"] >= 1

        assert len(m2.store.search_text("广州")) >= 1
        assert any(t.object == "Guangzhou" for t in m2.store.triples())
    print("  PASSED")


def test_lockfile():
    """Lockfile is created/removed and stale locks are cleaned up."""
    from mindos.server import read_lockfile, _write_lockfile, _remove_lockfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        assert read_lockfile(root) is None

        _write_lockfile(root, 3456)
        lock = read_lockfile(root)
        assert lock is not None
        assert lock["port"] == 3456

        _remove_lockfile(root)
        assert read_lockfile(root) is None

        # Stale lockfile (PID doesn't exist)
        lf = root / "server.lock"
        lf.write_text(json.dumps({"pid": 999999999, "port": 3456, "url": "http://127.0.0.1:3456"}))
        assert read_lockfile(root) is None  # should clean up stale lock
        assert not lf.exists()
    print("  PASSED")


def test_consolidate():
    """Similar memories should be merged."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="C")
        from mindos.store import Memory
        # Add near-identical memories
        m.store.add(Memory(id="", type="fact", content="我住在上海浦东新区"))
        m.store.add(Memory(id="", type="fact", content="我住在上海浦东新区附近"))
        m.store.add(Memory(id="", type="fact", content="我喜欢咖啡"))
        assert m.store.count() == 3

        result = m.consolidate()
        # "上海浦东新区" and "上海浦东新区附近" are similar enough to merge
        assert result["merged"] >= 1
        assert m.store.count() < 3
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
        ("server_client", test_server_client),
        ("memory_export_import", test_memory_export_import),
        ("lockfile", test_lockfile),
        ("consolidate", test_consolidate),
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
