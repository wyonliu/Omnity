"""Ome CLI — create your AI twin in 5 minutes.

Commands:
    ome create          Interactive guided setup
    ome chat            Talk to your Ome (terminal)
    ome chat "message"  One-shot chat
    ome recall <query>  What does your Ome remember?
    ome remember <text> Teach your Ome something
    ome forget <pattern> Make your Ome forget
    ome status          What does your Ome know?
    ome export          Export portable persona (JSON)
    ome export --prompt Export as system prompt (text)
    ome serve           Start MCP server for Claude/Cursor
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


DEFAULT_PATH = os.environ.get("OME_PATH", "~/.ome")


def _get_ome(path: str = DEFAULT_PATH):
    """Load Ome, exit with helpful message if not found."""
    from ome.core import Ome
    root = Path(path).expanduser()
    if not root.exists():
        print(f"No Ome found at {root}")
        print(f"Create one first:  ome create")
        sys.exit(1)
    return Ome.load(root)


def cmd_create(args):
    """Interactive Ome creation — friendly, no jargon."""
    from ome.core import Ome

    path = Path(args.path).expanduser()
    if path.exists() and (path / "identity.yaml").exists():
        print(f"You already have an Ome at {path}")
        print(f"To start fresh:  rm -rf {path} && ome create")
        return

    print()
    print("  Let's create your Ome — your AI twin.")
    print("  It will remember everything you tell it,")
    print("  speak in your voice, and work for you.")
    print()

    name = input("  What's your name? ").strip() or "User"

    print()
    print("  What are you like? Pick a few words.")
    print("  (e.g., curious, direct, creative, analytical, warm)")
    traits_raw = input("  Traits: ").strip()
    traits = [t.strip() for t in traits_raw.split(",") if t.strip()] or ["curious"]

    print()
    print("  How do you communicate?")
    print("  (e.g., concise and technical, warm and storytelling, direct no-BS)")
    style = input("  Style: ").strip() or "direct and clear"

    print()
    print("  What matters most to you?")
    print("  (e.g., honesty, efficiency, creativity, helping others)")
    values_raw = input("  Values: ").strip()
    values = [v.strip() for v in values_raw.split(",") if v.strip()] or []

    print()
    print("  What are you good at? (optional)")
    print("  (e.g., Python, design, marketing, writing)")
    skills_raw = input("  Skills: ").strip()
    capabilities = []
    if skills_raw:
        for s in skills_raw.split(","):
            s = s.strip()
            if s:
                capabilities.append({"domain": s, "level": "proficient"})

    print()
    print("  Creating your Ome...")

    ome = Ome.create(
        path=path,
        name=name,
        traits=traits,
        style=style,
        values=values,
        capabilities=capabilities,
    )

    # Seed with a self-introduction
    intro = f"user: My name is {name}. I'm {', '.join(traits)}. I communicate in a {style} way."
    if values:
        intro += f" I value {', '.join(values)}."
    if capabilities:
        domains = [c["domain"] for c in capabilities]
        intro += f" I'm skilled in {', '.join(domains)}."
    ome.remember(intro, source="ome-create")

    print()
    print(f"  Your Ome is alive at {path}")
    print()
    print(f"    Name:   {name}")
    print(f"    Traits: {', '.join(traits)}")
    print(f"    Style:  {style}")
    if values:
        print(f"    Values: {', '.join(values)}")
    if capabilities:
        print(f"    Skills: {', '.join(c['domain'] for c in capabilities)}")
    print()
    print("  What's next:")
    print("    ome chat                 — Talk to your Ome")
    print("    ome serve                — Connect to Claude/Cursor (MCP)")
    print("    ome export --prompt      — Copy system prompt for any AI")
    print()


def cmd_chat(args):
    """Chat with your Ome — interactive or one-shot."""
    ome = _get_ome(args.path)

    # One-shot mode
    if args.message:
        message = " ".join(args.message)
        reply = ome.chat(message)
        print(reply)
        return

    # Interactive mode
    print(f"\n  Chatting with {ome.name}'s Ome. Type 'quit' to exit.\n")
    while True:
        try:
            message = input("you: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Bye!")
            break
        if not message:
            continue
        if message.lower() in ("quit", "exit", "bye", "/quit", "/exit"):
            print("  Bye!")
            break
        reply = ome.chat(message)
        print(f"ome: {reply}\n")


def cmd_recall(args):
    """Search your Ome's memories."""
    ome = _get_ome(args.path)
    query = " ".join(args.query) if args.query else ""
    results = ome.recall(query, top_k=args.top_k)
    if not results:
        print("  No memories found.")
        return
    for m in results:
        mtype = m.get("type", "?")
        content = m.get("content", "")
        conf = m.get("confidence", 0)
        print(f"  [{mtype}] (conf={conf:.1f}) {content}")


def cmd_remember(args):
    """Teach your Ome something."""
    ome = _get_ome(args.path)
    text = " ".join(args.text)
    result = ome.remember(text)
    print(f"  Remembered. ({result.get('facts_added', 0)} facts, "
          f"{result.get('triples_added', 0)} relations)")


def cmd_forget(args):
    """Make your Ome forget something."""
    ome = _get_ome(args.path)
    pattern = " ".join(args.pattern)
    result = ome.forget(pattern)
    deleted = result.get("deleted_memories", 0) + result.get("deleted_triples", 0)
    print(f"  Forgotten. ({deleted} items erased)")


def cmd_status(args):
    """Show Ome status."""
    ome = _get_ome(args.path)
    s = ome.status()
    print(f"\n  {ome.name}'s Ome")
    print(f"  {'─' * 40}")
    print(f"  Traits:    {', '.join(ome.traits)}")
    style = ome.soul.identity.get("personality", {}).get("style", "")
    if style:
        print(f"  Style:     {style}")
    print(f"  Mood:      {s.get('emotion', {}).get('mood', 'neutral')}")
    mem = s.get("memory", {})
    total = mem.get("total", 0)
    print(f"  Memories:  {total}")
    by_type = mem.get("by_type", {})
    if by_type:
        parts = [f"{k}: {v}" for k, v in by_type.items() if v > 0]
        if parts:
            print(f"             {', '.join(parts)}")
    print(f"  KG:        {mem.get('kg_triples', 0)} triples")
    print(f"  Soul age:  {s.get('soul_age', 'unknown')}")
    print()


def cmd_export(args):
    """Export Ome as portable persona."""
    ome = _get_ome(args.path)
    context = args.context or ""

    if args.prompt:
        # Export as system prompt text
        prompt = ome.export_system_prompt(context)
        if args.output:
            Path(args.output).write_text(prompt, encoding="utf-8")
            print(f"  System prompt saved to {args.output}")
        else:
            print(prompt)
    else:
        # Export as full JSON persona
        persona = ome.export(context)
        text = json.dumps(persona, ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
            print(f"  Persona saved to {args.output}")
        else:
            print(text)


def cmd_serve(args):
    """Start Ome as MCP server (for Claude/Cursor) or HTTP server."""
    path = Path(args.path).expanduser()
    if not path.exists():
        print(f"No Ome found at {path}. Run: ome create")
        sys.exit(1)

    if args.mcp:
        from mindos.mcp_server import run_mcp_server
        run_mcp_server(str(path))
    else:
        from mindos.core import Mindos
        from mindos.server import run_server
        mindos = Mindos.load(path)
        run_server(mindos, port=args.port)


def main():
    parser = argparse.ArgumentParser(
        prog="ome",
        description="Ome — your AI twin that remembers everything.",
    )
    parser.add_argument("--version", action="version", version="ome 0.1.0")
    sub = parser.add_subparsers(dest="command")

    def _add_path(p):
        p.add_argument("--path", default=DEFAULT_PATH,
                        help=f"Ome data directory (default: {DEFAULT_PATH})")

    # create
    p_create = sub.add_parser("create", help="Create your Ome (start here!)")
    _add_path(p_create)

    # chat
    p_chat = sub.add_parser("chat", help="Talk to your Ome")
    p_chat.add_argument("message", nargs="*", help="Message (omit for interactive mode)")
    _add_path(p_chat)

    # recall
    p_recall = sub.add_parser("recall", help="Search your Ome's memories")
    p_recall.add_argument("query", nargs="*", help="Search query")
    p_recall.add_argument("-k", "--top-k", type=int, default=10)
    _add_path(p_recall)

    # remember
    p_remember = sub.add_parser("remember", help="Teach your Ome something")
    p_remember.add_argument("text", nargs="+", help="What to remember")
    _add_path(p_remember)

    # forget
    p_forget = sub.add_parser("forget", help="Make your Ome forget")
    p_forget.add_argument("pattern", nargs="+", help="What to forget")
    _add_path(p_forget)

    # status
    p_status = sub.add_parser("status", help="What does your Ome know?")
    _add_path(p_status)

    # export
    p_export = sub.add_parser("export", help="Export portable persona")
    p_export.add_argument("--prompt", action="store_true",
                          help="Export as system prompt text (instead of JSON)")
    p_export.add_argument("--context", default="",
                          help="Topic to bias memory selection")
    p_export.add_argument("-o", "--output", help="Output file path")
    _add_path(p_export)

    # serve
    p_serve = sub.add_parser("serve", help="Start MCP/HTTP server")
    p_serve.add_argument("--mcp", action="store_true",
                         help="MCP stdio mode (for Claude/Cursor)")
    p_serve.add_argument("--port", type=int, default=3456,
                         help="HTTP port (default: 3456)")
    _add_path(p_serve)

    args = parser.parse_args()

    handlers = {
        "create": cmd_create,
        "chat": cmd_chat,
        "recall": cmd_recall,
        "remember": cmd_remember,
        "forget": cmd_forget,
        "status": cmd_status,
        "export": cmd_export,
        "serve": cmd_serve,
    }

    if args.command in handlers:
        handlers[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
