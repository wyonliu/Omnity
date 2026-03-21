"""Mindos CLI — mindos init / status / serve / forget."""

from __future__ import annotations

import argparse
import json
import sys


def cmd_init(args: argparse.Namespace) -> None:
    from mindos.core import Mindos
    traits = [t.strip() for t in args.traits.split(",")] if args.traits else []
    m = Mindos.init(path=args.path, name=args.name, traits=traits, style=args.style)
    s = m.status()
    print(f"✓ Mindos 已创建：{m.root}")
    print(f"  identity.yaml — 编辑它来描述你自己")
    print(f"  memory.db     — 记忆存储")
    print(f"  名称：{s['name']}  人格：{', '.join(s['personality']) or '(空)'}")


def cmd_status(args: argparse.Namespace) -> None:
    from mindos.core import Mindos
    m = Mindos.load(args.path)
    s = m.status()
    print("🧠 Mindos Status")
    print("─" * 30)
    print(f"  名称：      {s['name']}")
    print(f"  灵魂年龄：  创建于 {s['soul_age']}")
    print(f"  人格特征：  {', '.join(s['personality']) or '(空)'}")
    print(f"  沟通风格：  {s['style'] or '(未设定)'}")
    print(f"  记忆总量：  {s['total_memories']} 条")
    for t, c in s.get("by_type", {}).items():
        print(f"    {t}: {c}")
    print(f"  知识图谱：  {s['knowledge_graph_triples']} 条三元组")


def cmd_forget(args: argparse.Namespace) -> None:
    from mindos.core import Mindos
    m = Mindos.load(args.path)
    count = m.forget(args.pattern, scope=args.scope)
    print(f"✓ 已擦除 {count} 条匹配 '{args.pattern}' 的记忆（scope={args.scope}）")


def cmd_serve(args: argparse.Namespace) -> None:
    from mindos.dashboard import run_dashboard
    from mindos.core import Mindos
    m = Mindos.load(args.path)
    if args.dashboard:
        run_dashboard(m, port=args.port)
    else:
        print(f"mindos serve: 请指定 --dashboard 或 --mcp")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(prog="mindos", description="Portable Digital Soul Protocol")
    parser.add_argument("--path", default="~/.mindos", help="Mindos 数据目录")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="创建新的 Mindos")
    p_init.add_argument("--name", default="User")
    p_init.add_argument("--traits", default="", help="逗号分隔的性格特征")
    p_init.add_argument("--style", default="", help="沟通风格")

    sub.add_parser("status", help="查看灵魂状态")

    p_forget = sub.add_parser("forget", help="物理擦除记忆")
    p_forget.add_argument("pattern", help="要擦除的内容关键词")
    p_forget.add_argument("--scope", default="all", choices=["all", "fact", "episode", "preference"])

    p_serve = sub.add_parser("serve", help="启动服务")
    p_serve.add_argument("--dashboard", action="store_true", help="启动可视化面板")
    p_serve.add_argument("--port", type=int, default=3456)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    {"init": cmd_init, "status": cmd_status, "forget": cmd_forget, "serve": cmd_serve}[args.command](args)


if __name__ == "__main__":
    main()
