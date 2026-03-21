"""Demo: seed a Mindos with rich data, then launch the Dashboard."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mindos.core import Mindos
from mindos.store import Triple

DEMO_PATH = Path(__file__).resolve().parent.parent / ".demo-mindos"


def seed():
    m = Mindos.init(
        path=str(DEMO_PATH),
        name="Wyon",
        traits=["curious", "efficient", "creative", "direct"],
        style="简洁技术风，偶尔幽默，喜欢用类比解释复杂概念",
    )

    # Add capabilities to identity
    m.identity["capabilities"] = [
        {"domain": "AI 开发", "level": "expert"},
        {"domain": "产品设计", "level": "proficient"},
        {"domain": "分布式系统", "level": "advanced"},
        {"domain": "写作", "level": "intermediate"},
    ]
    m.identity["personality"]["values"] = ["创新", "效率", "开源", "简洁"]
    m.identity["personality"]["boundaries"] = ["不讨论政治", "拒绝生成有害内容"]
    m.save_identity()

    # Simulate multiple conversations across platforms
    conversations = [
        {
            "source": "claude",
            "messages": [
                {"role": "user", "content": "我住在上海浦东，是一名 AI 工程师，在做一个叫 Omnity 的开源项目"},
                {"role": "assistant", "content": "了解！你在上海浦东做 Omnity 开源项目，这是一个什么样的项目？"},
                {"role": "user", "content": "Omnity 是一个把 AI 智能体带入真实 3D 空间的生态系统，包含 SOAP 协议和 Mindos 数字灵魂"},
                {"role": "assistant", "content": "非常有野心的项目！SOAP 协议负责空间交互，Mindos 负责记忆和身份。"},
            ],
        },
        {
            "source": "gpt",
            "messages": [
                {"role": "user", "content": "我喜欢喝冰美式，加双份浓缩，最好是浅烘的豆子"},
                {"role": "assistant", "content": "记住了！冰美式、双份浓缩、浅烘豆子。看来你对咖啡很讲究。"},
                {"role": "user", "content": "我不喜欢太酸的咖啡，偏好巧克力调的风味"},
                {"role": "assistant", "content": "了解，你更喜欢巧克力风味而非果酸风味的咖啡。"},
            ],
        },
        {
            "source": "claude",
            "messages": [
                {"role": "user", "content": "我计划下周去东京出差，顺便参加一个 AI 开发者大会"},
                {"role": "assistant", "content": "东京出差+AI 开发者大会，需要帮你规划行程吗？"},
                {"role": "user", "content": "我擅长 Python 和 TypeScript，最近在学 Rust"},
                {"role": "assistant", "content": "Python/TypeScript 是主力，Rust 在学习中。这和你的分布式系统背景很搭。"},
            ],
        },
        {
            "source": "cursor",
            "messages": [
                {"role": "user", "content": "我决定用 Apache-2.0 协议开源 Omnity"},
                {"role": "assistant", "content": "Apache-2.0 是个好选择，对企业友好且专利条款清晰。"},
                {"role": "user", "content": "我想把 SOAP 做成空间 AI 的 HTTP，让所有 Agent 都能用"},
                {"role": "assistant", "content": "把 SOAP 打造成空间智能体的通用协议，这个定位很清晰。"},
            ],
        },
        {
            "source": "claude",
            "messages": [
                {"role": "user", "content": "我最近对 3D Gaussian Splatting 很感兴趣，觉得它能改变空间重建"},
                {"role": "assistant", "content": "3DGS 确实是空间重建领域的突破。和 SOAP 结合很有潜力。"},
            ],
        },
        {
            "source": "gpt",
            "messages": [
                {"role": "user", "content": "张三是我的同事，技术很强但沟通风格比较直接"},
                {"role": "assistant", "content": "了解，张三是你的同事，技术强但沟通直接。"},
                {"role": "user", "content": "李四是我大学室友，现在在深圳做前端"},
                {"role": "assistant", "content": "李四——大学室友，在深圳做前端开发。"},
            ],
        },
    ]

    for conv in conversations:
        r = m.commit(conv["messages"], source=conv["source"])
        print(f"  commit [{conv['source']}]: +{r['memories_added']} memories")

    # Add knowledge graph triples
    triples = [
        Triple("Wyon", "住在", "上海浦东"),
        Triple("Wyon", "职业", "AI 工程师"),
        Triple("Wyon", "创建了", "Omnity"),
        Triple("Omnity", "包含", "SOAP"),
        Triple("Omnity", "包含", "Mindos"),
        Triple("SOAP", "是", "空间智能体协议"),
        Triple("Mindos", "是", "数字灵魂协议"),
        Triple("Wyon", "擅长", "Python"),
        Triple("Wyon", "擅长", "TypeScript"),
        Triple("Wyon", "在学", "Rust"),
        Triple("Wyon", "喜欢喝", "冰美式"),
        Triple("张三", "是", "Wyon 的同事"),
        Triple("李四", "是", "Wyon 的大学室友"),
        Triple("李四", "在", "深圳做前端"),
    ]
    for t in triples:
        m.store.add_triple(t)
    print(f"  知识图谱：+{len(triples)} 条三元组")

    s = m.status()
    print(f"\n🧠 灵魂已就绪：{s['total_memories']} 条记忆，{s['knowledge_graph_triples']} 条图谱")
    return m


def main():
    ap = argparse.ArgumentParser(description="Mindos demo: seed data + Dashboard")
    ap.add_argument("--port", type=int, default=3456, help="Dashboard 端口（占用时自动递增）")
    ap.add_argument("--no-serve", action="store_true", help="只灌数据，不启动 Web")
    args = ap.parse_args()

    print("=" * 50)
    print("  Mindos Demo — 创建灵魂 + 启动 Dashboard")
    print("=" * 50)
    print()

    # Clean previous demo
    import shutil
    if DEMO_PATH.exists():
        shutil.rmtree(DEMO_PATH)
    print(f"📂 数据目录：{DEMO_PATH}")

    m = seed()
    print()

    # Test hydrate
    ctx = m.hydrate(situation="讨论 AI 开发和旅行计划")
    print("💧 hydrate（场景：讨论 AI 开发和旅行计划）:")
    print(ctx)
    print()

    if args.no_serve:
        print("（--no-serve）已跳过 Dashboard。可用：")
        print(f"  PYTHONPATH=src python3 -m mindos.cli serve --dashboard --port {args.port} --path {DEMO_PATH}")
        return

    from mindos.dashboard import run_dashboard
    print("=" * 50)
    run_dashboard(m, port=args.port)


if __name__ == "__main__":
    main()
