"""Mindos CLI — auto-discovers running server, falls back to direct DB access.

When a server is running (detected via lockfile), all commands proxy to it.
Otherwise, commands open the SQLite DB directly.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


def _get_client(path: str) -> Optional["MindosClient"]:
    """Try to discover a running server."""
    try:
        from mindos.client import MindosClient
        return MindosClient.discover(path)
    except Exception:
        return None


def _get_mindos(path: str) -> "Mindos":
    from mindos.core import Mindos
    return Mindos.load(path)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> None:
    from mindos.core import Mindos
    traits = [t.strip() for t in args.traits.split(",")] if args.traits else []
    values = [v.strip() for v in args.values.split(",")] if args.values else []
    m = Mindos.init(path=args.path, name=args.name, traits=traits,
                    style=args.style, values=values)
    s = m.status()
    ident = s.get("identity", {})
    print(f"Mindos created: {m.root}")
    print(f"  identity.yaml — edit to describe yourself")
    print(f"  config.yaml   — configure LLM providers")
    print(f"  memory.db     — memory storage")
    print(f"  Name: {ident.get('name', '')}  Traits: {', '.join(ident.get('traits', [])) or '(empty)'}")
    print(f"\nStart the server:  mindos serve --path {args.path}")


def cmd_status(args: argparse.Namespace) -> None:
    client = _get_client(args.path)
    if client:
        s = client.status()
        _print_status(s, via="server")
    else:
        m = _get_mindos(args.path)
        s = m.status()
        _print_status(s, via="direct")


def _print_status(s: dict, via: str) -> None:
    ident = s.get("identity", {})
    mem = s.get("memory", {})
    emotion = s.get("emotion", {})
    print(f"Mindos Status (via {via})")
    print("─" * 40)
    print(f"  Name:        {ident.get('name', '')}")
    print(f"  Soul age:    {s.get('soul_age', '?')}")
    print(f"  Traits:      {', '.join(ident.get('traits', [])) or '(empty)'}")
    print(f"  Style:       {ident.get('style', '') or '(not set)'}")
    print(f"  Mood:        {emotion.get('mood', '?')} ({emotion.get('energy', '?')})")
    print(f"  Memories:    {mem.get('total_memories', 0)}")
    for t, c in mem.get("by_type", {}).items():
        print(f"    {t}: {c}")
    print(f"  KG triples:  {mem.get('knowledge_graph_triples', 0)}")
    print(f"  Reflection:  {s.get('commits_since_reflection', 0)}/20 commits")


def cmd_recall(args: argparse.Namespace) -> None:
    client = _get_client(args.path)
    if client:
        results = client.recall(args.query, top_k=args.top_k)
    else:
        m = _get_mindos(args.path)
        results = m.recall(args.query, top_k=args.top_k)

    if not results:
        print("No memories found.")
        return
    for r in results:
        print(f"  [{r['type']}] (conf={r['confidence']:.1f}) {r['content']}")


def cmd_commit(args: argparse.Namespace) -> None:
    text = args.text
    if text == "-":
        text = sys.stdin.read()

    client = _get_client(args.path)
    if client:
        result = client.commit(text, source=args.source)
    else:
        m = _get_mindos(args.path)
        result = m.commit(text, source=args.source)

    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_forget(args: argparse.Namespace) -> None:
    client = _get_client(args.path)
    if client:
        result = client.forget(args.pattern, scope=args.scope)
    else:
        m = _get_mindos(args.path)
        result = m.forget(args.pattern, scope=args.scope)

    deleted = result.get("deleted", 0)
    print(f"Erased {deleted} memories matching '{args.pattern}' (scope={args.scope})")


def cmd_memories(args: argparse.Namespace) -> None:
    """Memory management: list, export, import, stats, consolidate."""
    if args.export:
        _do_export(args)
    elif args.import_file:
        _do_import(args)
    elif args.stats:
        _do_stats(args)
    elif args.consolidate:
        _do_consolidate(args)
    else:
        _do_list(args)


def _do_list(args: argparse.Namespace) -> None:
    client = _get_client(args.path)
    if client:
        data = client.memories(query=args.query or "", limit=args.limit)
        mems = data.get("memories", [])
        total = data.get("total", len(mems))
    else:
        m = _get_mindos(args.path)
        if args.query:
            from mindos.store import Memory
            raw = m.store.search_text(args.query, limit=args.limit)
        else:
            raw = m.store.list_recent(limit=args.limit)
        mems = [{"type": x.type, "content": x.content, "source": x.source,
                 "confidence": x.confidence, "access_count": x.access_count}
                for x in raw]
        total = m.store.count()

    print(f"Memories ({len(mems)} of {total} total):")
    for m in mems:
        print(f"  [{m['type']}] {m['content'][:80]}")
        print(f"         src={m.get('source','')} conf={m.get('confidence',0):.1f} accessed={m.get('access_count',0)}")


def _do_export(args: argparse.Namespace) -> None:
    client = _get_client(args.path)
    if client:
        data = client.export_memories()
    else:
        m = _get_mindos(args.path)
        all_mems = m.store.list_recent(limit=100000)
        triples = m.store.triples()
        data = {
            "version": 1,
            "identity": m.identity,
            "memories": [
                {"id": x.id, "type": x.type, "content": x.content,
                 "source": x.source, "confidence": x.confidence,
                 "created_at": x.created_at, "access_count": x.access_count,
                 "decay_weight": x.decay_weight}
                for x in all_mems
            ],
            "knowledge_graph": [
                {"subject": t.subject, "predicate": t.predicate,
                 "object": t.object, "source": t.source}
                for t in triples
            ],
            "stats": m.store.stats(),
        }

    output = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        n = len(data.get("memories", []))
        print(f"Exported {n} memories to {args.output}")
    else:
        print(output)


def _do_import(args: argparse.Namespace) -> None:
    import_path = Path(args.import_file)
    if not import_path.exists():
        print(f"File not found: {args.import_file}", file=sys.stderr)
        sys.exit(1)
    data = json.loads(import_path.read_text(encoding="utf-8"))

    client = _get_client(args.path)
    if client:
        result = client.import_memories(data)
    else:
        from mindos.server import _import_memories
        m = _get_mindos(args.path)
        result = _import_memories(m, data)

    print(f"Imported: {result.get('memories_imported', 0)} memories, "
          f"{result.get('triples_imported', 0)} triples "
          f"(skipped {result.get('skipped_duplicate', 0)} duplicates)")


def _do_stats(args: argparse.Namespace) -> None:
    client = _get_client(args.path)
    if client:
        stats = client.stats()
    else:
        m = _get_mindos(args.path)
        stats = m.store.stats()
        sources: dict[str, int] = {}
        for mem in m.store.list_recent(limit=10000):
            sources[mem.source] = sources.get(mem.source, 0) + 1
        stats["by_source"] = sources

    print("Memory Statistics")
    print("─" * 40)
    print(f"  Total:      {stats.get('total_memories', 0)}")
    for t, c in stats.get("by_type", {}).items():
        print(f"    {t}: {c}")
    print(f"  KG triples: {stats.get('knowledge_graph_triples', 0)}")
    if stats.get("by_source"):
        print("  By source:")
        for src, cnt in sorted(stats["by_source"].items(), key=lambda x: -x[1]):
            print(f"    {src}: {cnt}")


def _do_consolidate(args: argparse.Namespace) -> None:
    client = _get_client(args.path)
    if client:
        result = client.consolidate()
    else:
        m = _get_mindos(args.path)
        result = m.consolidate()

    print(f"Consolidated: merged {result.get('merged', 0)} similar memories, "
          f"kept {result.get('kept', 0)}, total after: {result.get('total_after', '?')}")


def cmd_serve(args: argparse.Namespace) -> None:
    if args.mcp:
        from mindos.mcp_server import run_mcp_server
        run_mcp_server(args.path)
    else:
        from mindos.core import Mindos
        from mindos.server import run_server
        m = Mindos.load(args.path)
        run_server(m, port=args.port)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mindos",
        description="Mindos — Portable Digital Soul Protocol",
    )
    parser.add_argument("--path", default="~/.mindos", help="Mindos data directory")
    parser.add_argument("--version", action="store_true", help="Show version")

    # Shared --path argument for all subcommands
    path_parent = argparse.ArgumentParser(add_help=False)
    path_parent.add_argument("--path", default="~/.mindos", help="Mindos data directory")

    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init", help="Create a new Mindos", parents=[path_parent])
    p_init.add_argument("--name", default="User")
    p_init.add_argument("--traits", default="", help="Comma-separated traits")
    p_init.add_argument("--style", default="", help="Communication style")
    p_init.add_argument("--values", default="", help="Comma-separated core values")

    # status
    sub.add_parser("status", help="Show soul status", parents=[path_parent])

    # recall
    p_recall = sub.add_parser("recall", help="Search memories", parents=[path_parent])
    p_recall.add_argument("query", help="Search query")
    p_recall.add_argument("--top-k", type=int, default=10)

    # commit
    p_commit = sub.add_parser("commit", help="Digest text into memories", parents=[path_parent])
    p_commit.add_argument("text", help="Conversation text (use '-' for stdin)")
    p_commit.add_argument("--source", default="cli", help="Source label")

    # forget
    p_forget = sub.add_parser("forget", help="Erase memories", parents=[path_parent])
    p_forget.add_argument("pattern", help="Pattern to erase")
    p_forget.add_argument("--scope", default="all",
                          choices=["all", "fact", "episode", "preference", "skill", "relation"])

    # memories (management)
    p_mem = sub.add_parser("memories", help="Memory management", parents=[path_parent])
    p_mem.add_argument("--query", "-q", default="", help="Search filter")
    p_mem.add_argument("--limit", type=int, default=20, help="Max results")
    p_mem.add_argument("--export", action="store_true", help="Export all memories as JSON")
    p_mem.add_argument("--output", "-o", default="", help="Export output file")
    p_mem.add_argument("--import-file", default="", help="Import memories from JSON file")
    p_mem.add_argument("--stats", action="store_true", help="Show memory statistics")
    p_mem.add_argument("--consolidate", action="store_true", help="Merge similar memories")

    # serve
    p_serve = sub.add_parser("serve", help="Start Mindos server", parents=[path_parent])
    p_serve.add_argument("--mcp", action="store_true", help="MCP Server (stdio)")
    p_serve.add_argument("--port", type=int, default=3456, help="HTTP port")

    args = parser.parse_args()
    if getattr(args, "version", False):
        from mindos import __version__
        print(f"mindos {__version__}")
        sys.exit(0)
    if not args.command:
        parser.print_help()
        sys.exit(0)

    cmds = {
        "init": cmd_init, "status": cmd_status, "recall": cmd_recall,
        "commit": cmd_commit, "forget": cmd_forget, "memories": cmd_memories,
        "serve": cmd_serve,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
