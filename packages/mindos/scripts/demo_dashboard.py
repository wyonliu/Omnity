"""Demo: seed a Mindos with rich data, then launch the server."""

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mindos.core import Mindos
from mindos.store import Triple

DEMO_PATH = Path(__file__).resolve().parent.parent / ".demo-mindos"


def seed():
    m = Mindos.init(
        path=str(DEMO_PATH), name="Wyon",
        traits=["curious", "efficient", "creative", "direct"],
        style="concise technical, occasional humor, likes analogies",
        values=["innovation", "efficiency", "open-source", "simplicity"],
        capabilities=[
            {"domain": "AI engineering", "level": "expert"},
            {"domain": "Product design", "level": "proficient"},
            {"domain": "Distributed systems", "level": "advanced"},
        ],
    )

    conversations = [
        ("claude", "user: 我住在上海浦东，是一名 AI 工程师，在做一个叫 Omnity 的开源项目\nassistant: 了解！你在上海浦东做 Omnity 开源项目"),
        ("gpt", "user: 我喜欢喝冰美式，加双份浓缩\nassistant: 记住了！\nuser: 我不喜欢太酸的咖啡\nassistant: 了解"),
        ("claude", "user: 我计划下周去东京出差\nassistant: 需要帮你规划行程吗？\nuser: 我擅长 Python 和 TypeScript，最近在学 Rust\nassistant: Python/TypeScript 主力"),
        ("cursor", "user: 我决定用 Apache-2.0 协议开源 Omnity\nassistant: 对企业友好"),
        ("claude", "user: 我最近对 3D Gaussian Splatting 很感兴趣\nassistant: 空间重建突破"),
    ]

    for source, text in conversations:
        r = m.commit(text, source=source)
        print(f"  commit [{source}]: added={r['facts_added']}, method={r['method']}")

    triples = [
        Triple("Wyon", "lives_in", "Shanghai"), Triple("Wyon", "created", "Omnity"),
        Triple("Omnity", "contains", "SOAP"), Triple("Omnity", "contains", "Mindos"),
        Triple("Wyon", "skilled_at", "Python"), Triple("Wyon", "skilled_at", "TypeScript"),
        Triple("Wyon", "learning", "Rust"), Triple("Wyon", "prefers", "iced_americano"),
    ]
    for t in triples:
        m.store.add_triple(t)
    print(f"  KG: +{len(triples)} triples")

    s = m.status()
    mem = s["memory"]
    print(f"\nSoul ready: {mem['total_memories']} memories, {mem['knowledge_graph_triples']} triples")
    return m


def main():
    ap = argparse.ArgumentParser(description="Mindos demo: seed + server")
    ap.add_argument("--port", type=int, default=3456)
    ap.add_argument("--no-serve", action="store_true", help="Seed data only")
    args = ap.parse_args()

    if DEMO_PATH.exists():
        shutil.rmtree(DEMO_PATH)
    print(f"Data: {DEMO_PATH}\n")

    m = seed()
    ctx = m.hydrate(context="AI development")
    print(f"\nhydrate ({len(ctx)} chars):\n{ctx}\n")

    if args.no_serve:
        print("Done. Start server with:")
        print(f"  PYTHONPATH=src python3 -m mindos serve --path {DEMO_PATH}")
        return

    from mindos.server import run_server
    run_server(m, port=args.port)


if __name__ == "__main__":
    main()
