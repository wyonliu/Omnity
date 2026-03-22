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
from mindos.sync import SyncHub


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


def test_export_ome():
    """Ome export produces a valid persona package."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="OmeTest", traits=["creative", "bold"],
                        style="direct", values=["truth", "beauty"])
        m.commit("user: 我住在火星\nassistant: 酷！", source="test")
        m.store.add_triple(Triple("OmeTest", "lives_on", "Mars"))

        ome = m.export_ome(context="火星")
        assert ome["ome_version"] == "0.1.0"
        assert ome["identity"]["name"] == "OmeTest"
        assert "creative" in ome["identity"]["traits"]
        assert "OmeTest" in ome["anchor"]
        assert isinstance(ome["hydrated_context"], str)
        assert len(ome["hydrated_context"]) > 0
        assert isinstance(ome["memories"], list)
        assert isinstance(ome["knowledge_graph"], list)
        assert ome["emotion"]["mood"] is not None
    print("  PASSED")


def test_content_hash_dedup():
    """Content-hash dedup catches minor variations."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="Hash")
        m.commit("user: 我住在上海", source="t1")
        r = m.commit("user: 我住在 上海。", source="t2")
        # The hash-normalized version should catch this as duplicate
        assert r.get("skipped_duplicate", 0) >= 1 or r.get("facts_added", 0) == 0
    print("  PASSED")


def test_fts_search():
    """FTS5 full-text search works."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="FTS")
        from mindos.store import Memory
        m.store.add(Memory(id="", type="fact", content="我喜欢在北京三里屯喝咖啡"))
        m.store.add(Memory(id="", type="fact", content="上海外滩的夜景很美"))
        m.store.add(Memory(id="", type="fact", content="杭州西湖是世界文化遗产"))

        results = m.store.search_text("北京")
        assert len(results) >= 1
        assert "北京" in results[0].content
    print("  PASSED")


def test_soul_state_persistence():
    """Soul state (emotion) persists across reloads."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="Emotion")
        m.layers.l1.emotion.boost(0.5)
        m.layers.l1.save_emotion()

        # Reload
        m2 = Mindos.load(tmp)
        assert m2.layers.l1.emotion.mood.value == "engaged"
        assert m2.layers.l1.emotion.energy > 0.5
    print("  PASSED")


def test_mcp_ome_tool():
    """MCP server exposes mindos_ome tool."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="McpOme", traits=["wise"])
        from mindos.mcp_server import McpServer
        server = McpServer(m.layers, mindos=m)

        tools_resp = server._handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        tool_names = {t["name"] for t in tools_resp["result"]["tools"]}
        assert "mindos_ome" in tool_names

        ome_resp = server._handle({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "mindos_ome", "arguments": {"context": ""}}
        })
        ome = json.loads(ome_resp["result"]["content"][0]["text"])
        assert ome["identity"]["name"] == "McpOme"
    print("  PASSED")


def test_sync_journal():
    """Sync journal records mutations and supports push/pull."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="SyncTest")
        store = m.store

        # Commit should auto-journal
        m.commit("user: 我喜欢火锅", source="test")
        events = store.journal_since(0)
        assert len(events) >= 1
        # At least one add_memory event
        ops = [e["op"] for e in events]
        assert "add_memory" in ops

        # Journal tracks sequence
        latest = store.journal_latest_seq()
        assert latest > 0

        # Unsynced events
        unsynced = store.journal_unsynced()
        assert len(unsynced) >= 1

        # Mark synced
        store.journal_mark_synced(latest)
        unsynced_after = store.journal_unsynced()
        assert len(unsynced_after) == 0

        # Device ID was set
        assert len(store.device_id) == 8
    print("  PASSED")


def test_sync_hub_push_pull():
    """Sync Hub accepts pushes and serves pulls to other devices."""
    from mindos.sync import SyncHub

    hub = SyncHub()

    # Device A pushes events
    push_result = hub.push([
        {"event_id": "evt1", "device_id": "dev_a", "op": "add_memory",
         "payload": {"type": "fact", "content": "我住在北京"}, "created_at": time.time()},
        {"event_id": "evt2", "device_id": "dev_a", "op": "add_triple",
         "payload": {"subject": "User", "predicate": "lives_in", "object": "Beijing"},
         "created_at": time.time()},
    ], device_id="dev_a")
    assert push_result["accepted"] == 2

    # Dedup — push same events again
    push_result2 = hub.push([
        {"event_id": "evt1", "device_id": "dev_a", "op": "add_memory",
         "payload": {"type": "fact", "content": "我住在北京"}, "created_at": time.time()},
    ], device_id="dev_a")
    assert push_result2["accepted"] == 0

    # Device B pulls — should get Device A's events
    pull_result = hub.pull("dev_b", after_seq=0)
    assert len(pull_result["events"]) == 2
    assert pull_result["events"][0]["op"] == "add_memory"

    # Device A pulls — should NOT get its own events
    pull_a = hub.pull("dev_a", after_seq=0)
    assert len(pull_a["events"]) == 0

    # Status
    status = hub.status()
    assert status["total_events"] == 2
    print("  PASSED")


def test_sync_apply_remote():
    """Applying remote events to local store creates memories."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="RemoteApply")
        store = m.store

        # Apply a remote add_memory event
        applied = store.journal_apply_remote({
            "event_id": "remote_evt_1",
            "device_id": "phone_01",
            "op": "add_memory",
            "payload": {"type": "fact", "content": "我在手机上说过这句话"},
            "created_at": time.time(),
        })
        assert applied is True

        # Memory should exist
        results = store.search_text("手机")
        assert len(results) >= 1

        # Applying same event again should be deduped
        applied2 = store.journal_apply_remote({
            "event_id": "remote_evt_1",
            "device_id": "phone_01",
            "op": "add_memory",
            "payload": {"type": "fact", "content": "我在手机上说过这句话"},
            "created_at": time.time(),
        })
        assert applied2 is False

        # Apply a remote forget
        store.journal_apply_remote({
            "event_id": "remote_evt_2",
            "device_id": "phone_01",
            "op": "forget",
            "payload": {"pattern": "手机", "mem_type": None},
            "created_at": time.time(),
        })
        assert len(store.search_text("手机")) == 0
    print("  PASSED")


def test_sync_hub_persistence():
    """Sync Hub persists and reloads state."""
    with tempfile.TemporaryDirectory() as tmp:
        persist_path = Path(tmp) / "hub.json"
        hub1 = SyncHub(persist_path=persist_path)
        hub1.push([
            {"event_id": "p1", "device_id": "d1", "op": "add_memory",
             "payload": {"type": "fact", "content": "test"}, "created_at": time.time()},
        ], device_id="d1")
        assert persist_path.exists()

        # Reload
        hub2 = SyncHub(persist_path=persist_path)
        assert hub2.status()["total_events"] == 1
        pull = hub2.pull("d2", after_seq=0)
        assert len(pull["events"]) == 1
    print("  PASSED")


def test_anthropic_router_selection():
    """ModelRouter correctly selects Anthropic provider type."""
    from mindos.config import MindosConfig, ModelRouter, ModelProvider
    import os

    config_data = {
        "models": [
            {"name": "claude", "type": "anthropic", "api_key_env": "TEST_ANTHROPIC_KEY",
             "model": "claude-sonnet-4-20250514", "priority": 1, "for": ["reasoning"]},
        ],
        "fallback": "claude",
    }
    # Set fake key
    os.environ["TEST_ANTHROPIC_KEY"] = "test-key-123"
    try:
        config = MindosConfig(config_data)
        router = ModelRouter(config)
        provider = router.select("reasoning")
        assert provider is not None
        assert provider.type == "anthropic"
        assert provider.name == "claude"
    finally:
        del os.environ["TEST_ANTHROPIC_KEY"]
    print("  PASSED")


def test_process_unified_entry():
    """process() routes L1 requests through quick_reply, L2/L3/L4 through layers."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="ProcessTest", traits=["smart"])
        # L1: greeting
        r = m.process("你好")
        assert r["layer"] == "l1"
        assert "你好" in r["response"]
        assert r.get("cost", 0) == 0

        # L1: thanks
        r = m.process("谢谢")
        assert r["layer"] == "l1"

        # L1: status
        r = m.process("状态")
        assert r["layer"] == "l1"
        assert "记忆" in r["response"]

        # L2: general conversation (no LLM, fallback)
        r = m.process("今天学了Python")
        assert r["layer"] == "l2"

        # L3: planning
        r = m.process("帮我分析一下这个问题")
        assert r["layer"] == "l3"

        # L4: reflection
        r = m.process("你是谁")
        assert r["layer"] == "l4"
    print("  PASSED")


def test_l1_quick_reply():
    """L1 quick_reply handles various simple queries."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="QuickTest")
        b = m.layers.l1

        assert "你好" in b.quick_reply("你好")
        assert "不客气" in b.quick_reply("谢谢")
        assert "记忆" in b.quick_reply("状态")
        assert "还没有记忆" in b.quick_reply("你记得吗")
    print("  PASSED")


def test_event_bus():
    """EventBus on/emit/off work correctly."""
    from mindos.event_bus import EventBus, MEMORY_COMMITTED
    bus = EventBus()
    received = []
    handler = lambda e: received.append(e)
    bus.on(MEMORY_COMMITTED, handler)

    bus.emit(MEMORY_COMMITTED, {"facts_added": 3})
    assert len(received) == 1
    assert received[0].data["facts_added"] == 3

    bus.off(MEMORY_COMMITTED, handler)
    bus.emit(MEMORY_COMMITTED, {"facts_added": 1})
    assert len(received) == 1  # handler removed, not called

    # History
    events = bus.recent_events(MEMORY_COMMITTED)
    assert len(events) == 2
    print("  PASSED")


def test_commit_emits_event():
    """commit() emits MEMORY_COMMITTED event."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="EventTest")
        received = []
        m.event_bus.on("memory.committed", lambda e: received.append(e))

        m.commit("user: 我住在上海\nassistant: 好的", source="test")
        assert len(received) == 1
        assert received[0].data["source"] == "test"
    print("  PASSED")


def test_l4_writeback_anchors():
    """L4 reflect with trait_updates respects anchors and writes back."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="AnchorTest", traits=["curious"])
        # Set anchors
        m.identity["personality"]["anchors"] = ["说话简洁直接"]
        m.save_identity()
        m.reload_identity()

        l4 = m.layers.l4
        # Simulate trait update (what reflect() would return)
        changed = l4._apply_trait_updates(["creative", "verbose"])
        assert changed
        assert "creative" in l4.identity["traits"]
        # "verbose" contradicts anchor "简洁" — should be dropped
        assert "verbose" not in l4.identity["traits"]
    print("  PASSED")


def test_insight_daily_digest():
    """InsightEngine daily_digest produces correct structure."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="InsightTest")
        from mindos.store import Memory
        m.store.add(Memory(id="", type="fact", content="我喜欢喝咖啡", source="claude"))
        m.store.add(Memory(id="", type="fact", content="我住在上海浦东", source="cursor"))
        m.store.add(Memory(id="", type="episode", content="讨论了Python项目架构", source="claude"))

        from mindos.insight import InsightEngine
        engine = InsightEngine(m.store)
        digest = engine.daily_digest(hours=24)

        assert digest["total_memories"] == 3
        assert "claude" in digest["by_source"]
        assert len(digest["highlights"]) >= 1
        assert len(digest["top_topics"]) >= 1
    print("  PASSED")


def test_insight_contradiction():
    """InsightEngine detects contradictory facts."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="ContraTest")
        from mindos.store import Memory
        m.store.add(Memory(id="", type="fact", content="我住在上海"))
        m.store.add(Memory(id="", type="fact", content="我住在北京"))

        from mindos.insight import InsightEngine
        engine = InsightEngine(m.store)
        contradictions = engine.contradiction_alert()
        assert len(contradictions) >= 1
        assert "地点矛盾" in contradictions[0]["reason"]
    print("  PASSED")


def test_insight_patterns():
    """InsightEngine pattern_discovery finds source dominance."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="PatternTest")
        from mindos.store import Memory
        # Add 10 memories from claude, 2 from cursor
        for i in range(10):
            m.store.add(Memory(id="", type="fact", content=f"事实{i}", source="claude"))
        for i in range(2):
            m.store.add(Memory(id="", type="fact", content=f"代码{i}", source="cursor"))

        from mindos.insight import InsightEngine
        engine = InsightEngine(m.store)
        patterns = engine.pattern_discovery()
        # Should detect claude as dominant source
        source_patterns = [p for p in patterns if "claude" in p.get("pattern", "")]
        assert len(source_patterns) >= 1
    print("  PASSED")


def test_memory_compressor():
    """MemoryCompressor compress/merge/archive work."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="CompressTest")
        from mindos.store import Memory

        # compress_old_episodes: add old episodes
        old_time = time.time() - 100 * 86400  # 100 days ago
        m.store.add(Memory(id="", type="episode", content="A" * 200,
                           created_at=old_time, confidence=0.5))
        m.store.add(Memory(id="", type="episode", content="B" * 200,
                           created_at=old_time, confidence=0.95))  # high confidence, should be preserved

        result = m.store.compress_old_episodes(older_than_days=90)
        assert result["compressed"] >= 1
        assert result["preserved"] >= 1

        # merge_redundant_facts
        m.store.add(Memory(id="", type="fact", content="我喜欢喝咖啡"))
        m.store.add(Memory(id="", type="fact", content="我喜欢喝咖啡呢"))
        result = m.store.merge_redundant_facts(similarity_threshold=0.7)
        assert result["merged"] >= 1

        # archive_stale
        stale_time = time.time() - 200 * 86400
        m.store.add(Memory(id="", type="fact", content="很久以前的事",
                           created_at=stale_time, confidence=0.5))
        # Manually set accessed_at to be old
        m.store._conn.execute(
            "UPDATE memories SET accessed_at=? WHERE content=?",
            (stale_time, "很久以前的事")
        )
        m.store._conn.commit()
        result = m.store.archive_stale(inactive_days=180, min_access=2)
        assert result["archived"] >= 1
    print("  PASSED")


def test_scheduler():
    """Scheduler check_and_run executes due jobs."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="SchedTest")
        from mindos.store import Memory
        m.store.add(Memory(id="", type="fact", content="测试数据", source="test"))

        scheduler = m.get_scheduler()
        # All jobs should be overdue (never run before)
        status = scheduler.job_status()
        assert all(j["overdue"] for j in status)

        # Run all due jobs
        results = scheduler.check_and_run()
        assert len(results) >= 1
        assert all(r.success for r in results)

        # Run again — nothing should be due
        results2 = scheduler.check_and_run()
        assert len(results2) == 0

        # Force run specific job
        result = scheduler.force_run("daily_digest")
        assert result is not None
        assert result.success
    print("  PASSED")


def test_update_embedding():
    """store.update_embedding() stores and caches vectors."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="EmbTest")
        from mindos.store import Memory
        mem = Memory(id="", type="fact", content="embedding test")
        mid = m.store.add(mem)

        try:
            import numpy as np
            vec = np.random.randn(384).astype(np.float32)
            ok = m.store.update_embedding(mid, vec.tolist())
            assert ok
            assert mid in m.store._embeddings_cache
        except ImportError:
            pass  # numpy not available, skip
    print("  PASSED")


def test_identity_anchors_in_default():
    """Default identity includes anchors field."""
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="AnchorDefault")
        p = m.identity.get("personality", {})
        assert "anchors" in p
        assert isinstance(p["anchors"], list)
    print("  PASSED")


def test_server_process_endpoint():
    """HTTP /api/process endpoint works."""
    from http.server import HTTPServer
    from mindos.server import MindosHandler, _write_lockfile, _remove_lockfile
    import mindos.server as srv
    import urllib.request

    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="APITest")
        srv._mindos = m
        srv._start_time = time.time()

        httpd = HTTPServer(("127.0.0.1", 0), MindosHandler)
        port = httpd.server_address[1]
        srv._serve_port = port

        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()

        try:
            # Test /api/process
            data = json.dumps({"text": "你好"}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/process",
                data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read())
            assert result["layer"] == "l1"
            assert "你好" in result["response"]

            # Test /api/insights
            req = urllib.request.Request(f"http://127.0.0.1:{port}/api/insights")
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read())
            assert "total_memories" in result

            # Test /api/maintenance
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/api/maintenance",
                data=b"{}",
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req) as resp:
                result = json.loads(resp.read())
            assert "jobs_run" in result

        finally:
            httpd.shutdown()
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
        ("export_ome", test_export_ome),
        ("content_hash_dedup", test_content_hash_dedup),
        ("fts_search", test_fts_search),
        ("soul_state_persistence", test_soul_state_persistence),
        ("mcp_ome_tool", test_mcp_ome_tool),
        ("anthropic_router_selection", test_anthropic_router_selection),
        ("sync_journal", test_sync_journal),
        ("sync_hub_push_pull", test_sync_hub_push_pull),
        ("sync_apply_remote", test_sync_apply_remote),
        ("sync_hub_persistence", test_sync_hub_persistence),
        # v0.4.0 Phase 0 tests
        ("process_unified_entry", test_process_unified_entry),
        ("l1_quick_reply", test_l1_quick_reply),
        ("event_bus", test_event_bus),
        ("commit_emits_event", test_commit_emits_event),
        ("l4_writeback_anchors", test_l4_writeback_anchors),
        ("insight_daily_digest", test_insight_daily_digest),
        ("insight_contradiction", test_insight_contradiction),
        ("insight_patterns", test_insight_patterns),
        ("memory_compressor", test_memory_compressor),
        ("scheduler", test_scheduler),
        ("update_embedding", test_update_embedding),
        ("identity_anchors_in_default", test_identity_anchors_in_default),
        ("server_process_endpoint", test_server_process_endpoint),
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
