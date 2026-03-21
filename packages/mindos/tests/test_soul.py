"""Integration test: create a soul, commit conversations, hydrate, forget, inspect."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mindos.core import Mindos


def test_full_lifecycle():
    with tempfile.TemporaryDirectory() as tmp:
        # 1. Init
        m = Mindos.init(path=tmp, name="TestUser", traits=["curious", "efficient"], style="简洁直接")
        assert (Path(tmp) / "identity.yaml").exists()
        assert (Path(tmp) / "memory.db").exists()

        s = m.status()
        assert s["name"] == "TestUser"
        assert s["total_memories"] == 0
        print(f"✓ Init: {s}")

        # 2. Commit conversations
        r1 = m.commit([
            {"role": "user", "content": "我住在上海，是一名 AI 工程师"},
            {"role": "assistant", "content": "好的，了解了！你住在上海，从事 AI 工程。"},
        ], source="test-claude")
        print(f"✓ Commit #1: {r1}")
        assert r1["memories_added"] >= 1

        r2 = m.commit([
            {"role": "user", "content": "我喜欢喝冰美式，加双份浓缩"},
            {"role": "assistant", "content": "记住了，冰美式加双份浓缩。"},
        ], source="test-gpt")
        print(f"✓ Commit #2: {r2}")

        r3 = m.commit([
            {"role": "user", "content": "我计划下周去东京出差"},
            {"role": "assistant", "content": "东京出差，需要帮你做行程规划吗？"},
        ], source="test-claude")
        print(f"✓ Commit #3: {r3}")

        r4 = m.commit([
            {"role": "user", "content": "我擅长 Python 和分布式系统"},
            {"role": "assistant", "content": "Python 和分布式系统是你的核心技能。"},
        ], source="test-cursor")
        print(f"✓ Commit #4: {r4}")

        # Sensitive info should be blocked
        r5 = m.commit([
            {"role": "user", "content": "我的API密钥是 sk-abc123def456ghi789jkl012mno"},
            {"role": "assistant", "content": "收到。"},
        ], source="test")
        print(f"✓ Commit #5 (sensitive): skipped={r5['skipped_sensitive']}")
        assert r5["skipped_sensitive"] >= 1

        s = m.status()
        print(f"✓ Status after commits: {s['total_memories']} memories")

        # 3. Hydrate
        ctx = m.hydrate(situation="讨论旅行计划", max_tokens=2000)
        print(f"✓ Hydrate:\n{ctx}\n")
        assert "TestUser" in ctx

        # 4. Search
        results = m.store.search_text("上海", limit=5)
        print(f"✓ Search '上海': {len(results)} results")
        assert len(results) >= 1

        # 5. Forget
        count = m.forget("东京")
        print(f"✓ Forget '东京': erased {count} memories")
        remaining = m.store.search_text("东京")
        assert len(remaining) == 0

        s = m.status()
        print(f"\n🧠 Final Status:")
        print(f"  记忆: {s['total_memories']}")
        print(f"  知识图谱: {s['knowledge_graph_triples']}")
        print(f"  人格: {', '.join(s['personality'])}")

    print("\n✅ All tests passed!")


def test_commit_deduplicates():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="D")
        m.commit([{"role": "user", "content": "我住在杭州"}], source="t1")
        r2 = m.commit([{"role": "user", "content": "我住在杭州"}], source="t2")
        assert r2.get("skipped_duplicate", 0) >= 1, "second commit should skip duplicate fact"


def test_forget_knowledge_graph():
    from mindos.store import Triple
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="K")
        m.store.add_triple(Triple("User", "visited", "东京"))
        m.store.add_triple(Triple("User", "likes", "coffee"))
        before = len(m.store.triples())
        assert before == 2
        m.forget("东京")
        triples = m.store.triples()
        assert len(triples) == 1
        assert triples[0].object == "coffee"


def test_reload_identity():
    with tempfile.TemporaryDirectory() as tmp:
        m = Mindos.init(path=tmp, name="Stale")
        m.identity["name"] = "Fresh"
        m.save_identity()
        m.identity["name"] = "Stale"  # simulate outdated in-memory copy
        m.reload_identity()
        assert m.identity["name"] == "Fresh"


if __name__ == "__main__":
    test_full_lifecycle()
    test_commit_deduplicates()
    test_forget_knowledge_graph()
    test_reload_identity()
    print("✅ Extended tests passed!")
