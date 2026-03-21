"""Mindos CLI — mindos init / status / serve / forget / recall / commit."""

from __future__ import annotations

import argparse
import json
import sys


def cmd_init(args: argparse.Namespace) -> None:
    from mindos.core import Mindos
    traits = [t.strip() for t in args.traits.split(",")] if args.traits else []
    values = [v.strip() for v in args.values.split(",")] if args.values else []
    m = Mindos.init(path=args.path, name=args.name, traits=traits,
                    style=args.style, values=values)
    s = m.status()
    ident = s.get("identity", {})
    print(f"✓ Mindos created: {m.root}")
    print(f"  identity.yaml — edit to describe yourself")
    print(f"  config.yaml   — configure LLM providers")
    print(f"  memory.db     — memory storage")
    print(f"  Name: {ident.get('name', '')}  Traits: {', '.join(ident.get('traits', [])) or '(empty)'}")


def cmd_status(args: argparse.Namespace) -> None:
    from mindos.core import Mindos
    m = Mindos.load(args.path)
    s = m.status()
    ident = s.get("identity", {})
    mem = s.get("memory", {})
    emotion = s.get("emotion", {})
    print("🧠 Mindos Status")
    print("─" * 40)
    print(f"  Name:         {ident.get('name', '')}")
    print(f"  Soul age:     created {s.get('soul_age', '?')}")
    print(f"  Traits:       {', '.join(ident.get('traits', [])) or '(empty)'}")
    print(f"  Style:        {ident.get('style', '') or '(not set)'}")
    print(f"  Mood:         {emotion.get('mood', '?')} (energy: {emotion.get('energy', '?')})")
    print(f"  Memories:     {mem.get('total_memories', 0)}")
    for t, c in mem.get("by_type", {}).items():
        print(f"    {t}: {c}")
    print(f"  KG triples:   {mem.get('knowledge_graph_triples', 0)}")
    print(f"  Commits→reflection: {s.get('commits_since_reflection', 0)}/20")


def cmd_recall(args: argparse.Namespace) -> None:
    from mindos.core import Mindos
    m = Mindos.load(args.path)
    results = m.recall(args.query, top_k=args.top_k)
    if not results:
        print("No memories found.")
        return
    for r in results:
        print(f"  [{r['type']}] (conf={r['confidence']:.1f}) {r['content']}")


def cmd_commit(args: argparse.Namespace) -> None:
    from mindos.core import Mindos
    m = Mindos.load(args.path)
    text = args.text
    if text == "-":
        text = sys.stdin.read()
    result = m.commit(text, source=args.source)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_forget(args: argparse.Namespace) -> None:
    from mindos.core import Mindos
    m = Mindos.load(args.path)
    result = m.forget(args.pattern, scope=args.scope)
    print(f"✓ Erased {result.get('deleted', 0)} memories matching '{args.pattern}' (scope={args.scope})")


def cmd_serve(args: argparse.Namespace) -> None:
    if args.mcp:
        from mindos.mcp_server import run_mcp_server
        run_mcp_server(args.path)
    elif args.dashboard:
        from mindos.core import Mindos
        from mindos.dashboard import run_dashboard
        m = Mindos.load(args.path)
        run_dashboard(m, port=args.port)
    else:
        print("mindos serve: specify a mode:")
        print("  --mcp         MCP Server (for Claude Desktop, Cursor, etc.)")
        print("  --dashboard   Local visualization dashboard (port 3456)")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(prog="mindos", description="Portable Digital Soul Protocol")
    parser.add_argument("--path", default="~/.mindos", help="Mindos data directory")
    parser.add_argument("--version", action="store_true", help="Show version")
    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Create a new Mindos")
    p_init.add_argument("--name", default="User")
    p_init.add_argument("--traits", default="", help="Comma-separated personality traits")
    p_init.add_argument("--style", default="", help="Communication style")
    p_init.add_argument("--values", default="", help="Comma-separated core values")

    sub.add_parser("status", help="Show soul status")

    p_recall = sub.add_parser("recall", help="Search memories")
    p_recall.add_argument("query", help="Search query")
    p_recall.add_argument("--top-k", type=int, default=10)

    p_commit = sub.add_parser("commit", help="Digest text into memories")
    p_commit.add_argument("text", help="Conversation text (use '-' to read from stdin)")
    p_commit.add_argument("--source", default="cli", help="Source label")

    p_forget = sub.add_parser("forget", help="Physically erase memories")
    p_forget.add_argument("pattern", help="Content keyword to erase")
    p_forget.add_argument(
        "--scope", default="all",
        choices=["all", "fact", "episode", "preference", "skill", "relation"],
    )

    p_serve = sub.add_parser("serve", help="Start a server")
    p_serve.add_argument("--mcp", action="store_true", help="MCP Server (stdio, for Claude/Cursor)")
    p_serve.add_argument("--dashboard", action="store_true", help="Web dashboard")
    p_serve.add_argument("--port", type=int, default=3456)

    args = parser.parse_args()
    if getattr(args, "version", False):
        from mindos import __version__
        print(__version__)
        sys.exit(0)
    if not args.command:
        parser.print_help()
        sys.exit(0)

    cmds = {
        "init": cmd_init, "status": cmd_status, "recall": cmd_recall,
        "commit": cmd_commit, "forget": cmd_forget, "serve": cmd_serve,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
