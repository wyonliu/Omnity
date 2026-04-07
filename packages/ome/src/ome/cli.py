"""Ome CLI — create your AI twin in 5 minutes.

Commands:
    ome create              Interactive guided setup
    ome create --import     Import persona from chat export
    ome chat                Talk to your Ome (terminal)
    ome chat "message"      One-shot chat
    ome recall <query>      What does your Ome remember?
    ome remember <text>     Teach your Ome something
    ome forget <pattern>    Make your Ome forget
    ome status              What does your Ome know?
    ome dashboard           Full life dashboard (bond, skills, emotion)
    ome events              Check proactive events
    ome export              Export portable persona (JSON)
    ome export --prompt     Export as system prompt (text)
    ome serve               Start MCP server for Claude/Cursor
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
        # If --import is specified on existing Ome, just import persona
        if getattr(args, "import_file", None):
            ome = Ome.load(path)
            source = Path(args.import_file).expanduser()
            if not source.exists():
                print(f"  File not found: {source}")
                return
            profile = ome.import_persona(source)
            _print_persona_result(profile)
            return

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

    # If --import was specified, import persona immediately
    if getattr(args, "import_file", None):
        source = Path(args.import_file).expanduser()
        if source.exists():
            print("  Importing your voice...")
            profile = ome.import_persona(source)
            _print_persona_result(profile)

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
    print("    ome create --import FILE — Import your voice from chat logs")
    print("    ome serve                — Connect to Claude/Cursor (MCP)")
    print("    ome export --prompt      — Copy system prompt for any AI")
    print()


def _print_persona_result(profile):
    """Print persona import results."""
    from ome.life.persona import PersonaProfile
    print()
    print("  Persona imported!")
    if profile.tone_tags:
        print(f"    Tone:         {', '.join(profile.tone_tags)}")
    if profile.catchphrases:
        print(f"    Catchphrases: {'、'.join(profile.catchphrases[:5])}")
    if profile.emoji_habits:
        print(f"    Emoji:        {''.join(profile.emoji_habits[:8])}")
    if profile.topics:
        print(f"    Topics:       {', '.join(profile.topics[:5])}")
    print(f"    Msg length:   {profile.avg_msg_length:.0f} chars (avg)")
    print()


def cmd_chat(args):
    """Chat with your Ome — interactive or one-shot."""
    ome = _get_ome(args.path)

    # Check proactive events on chat launch
    events = ome.check_events()
    for ev in events:
        if not ev.needs_approval:
            print(f"  [{ev.event_name}] {ev.message}")
            print()

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


def cmd_dashboard(args):
    """Show full life dashboard."""
    ome = _get_ome(args.path)
    d = ome.life_dashboard()

    print(f"\n  {ome.name}'s Life Dashboard")
    print(f"  {'═' * 40}")

    # Bond
    bond = d["bond"]
    print(f"\n  Bond: Lv.{bond['level']} {bond['name']} ({bond.get('name_en', '')})")
    print(f"  Interactions: {bond['total_interactions']}")
    if "next_level" in bond:
        print(f"  Next: {bond['next_level']} "
              f"(need {bond['interactions_needed']} more chats, {bond['days_needed']} more days)")

    # Streak
    streak = d["streak"]
    print(f"\n  Streak: {streak['current']} days (max: {streak['max']})")

    # Emotion
    emotion = d.get("emotion", {})
    if emotion:
        print(f"\n  Mood: {emotion.get('mood_emoji', '😌')} {emotion.get('mood', 'neutral')}")
        print(f"  Energy: {'█' * int(emotion.get('energy', 0.5) * 10)}{'░' * (10 - int(emotion.get('energy', 0.5) * 10))} "
              f"{emotion.get('energy', 0.5):.0%}")
        print(f"  Warmth: {'█' * int(emotion.get('warmth', 0.5) * 10)}{'░' * (10 - int(emotion.get('warmth', 0.5) * 10))} "
              f"{emotion.get('warmth', 0.5):.0%}")

    # Skills
    skills = d["skills"]
    print(f"\n  Skills:")
    for name, skill in skills.items():
        comp = skill["competence"]
        bar = "█" * int(comp * 10) + "░" * (10 - int(comp * 10))
        lock = "" if skill.get("min_bond_level", 0) <= bond["level"] else " 🔒"
        print(f"    {name:10s} {bar} {comp:.0%}  ({skill['uses']} uses){lock}")

    # Achievements
    achs = d["achievements"]
    print(f"\n  Achievements: {achs['count']}")
    for a in achs["unlocked"]:
        print(f"    {a['icon']} {a['name']} — {a['description']}")
    for a in achs["locked"][:3]:
        print(f"    🔒 {a['name']} — ???")

    # Permissions
    perm = d.get("permissions", {})
    if perm:
        trust_names = {0: "Locked", 1: "Observer", 2: "Assistant",
                       3: "Deputy", 4: "Autonomous", 5: "Full Trust"}
        tl = perm.get("trust_level", 1)
        print(f"\n  Trust: Level {tl} ({trust_names.get(tl, '?')})")

    print()


def cmd_events(args):
    """Check proactive events."""
    ome = _get_ome(args.path)
    events = ome.check_events()

    if not events:
        print("  No events right now. All quiet.")
        return

    for ev in events:
        status = "⏳ needs approval" if ev.needs_approval else "✅"
        print(f"  [{ev.event_name}] {status} {ev.message}")


def cmd_mirror(args):
    """Mirror chat — talk to "yourself". Ome responds in your voice."""
    ome = _get_ome(args.path)

    # One-shot mode
    if args.message:
        message = " ".join(args.message)
        reply = ome.mirror_chat(message)
        print(reply)
        return

    # Interactive mode
    print(f"\n  Mirror mode: talking to {ome.name} (yourself). Type 'quit' to exit.\n")
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
        reply = ome.mirror_chat(message)
        print(f"{ome.name}: {reply}\n")


def cmd_calibrate(args):
    """Calibrate your Ome's persona by giving feedback on responses."""
    ome = _get_ome(args.path)

    print(f"\n  Calibration mode for {ome.name}'s Ome.")
    print("  I'll say something, you tell me if it sounds like you.\n")

    test_prompts = [
        "你最近在忙什么？",
        "今天心情怎么样？",
        "有什么想聊的吗？",
    ]

    for prompt in test_prompts:
        print(f"  Prompt: {prompt}")
        reply = ome.mirror_chat(prompt)
        print(f"  Ome: {reply}")
        print()

        try:
            feedback = input("  Feedback (完美/不像我/具体修改): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Calibration ended.")
            return

        if not feedback:
            continue

        result = ome.calibrate(prompt, reply, feedback)
        action = result.get("action", "")
        if action == "reinforced":
            print("  ✅ Got it, reinforcing this style.\n")
        else:
            print("  📝 Noted, adjusting...\n")

    print("  Calibration complete! Your Ome will keep learning.\n")


def cmd_skill(args):
    """List or use Ome skills."""
    ome = _get_ome(args.path)

    if args.action == "list":
        skills = ome.list_skills()
        print(f"\n  {ome.name}'s Skills")
        print(f"  {'─' * 40}")
        for s in skills:
            available = "✅" if s.get("available") else "🔒"
            comp = s.get("competence", 0)
            uses = s.get("uses", 0)
            print(f"  {available} {s['name']:12s} [{s['tier']}] "
                  f"competence={comp:.0%} uses={uses}")
            print(f"     {s['description']}")
        print()
    elif args.action == "use":
        if not args.skill_args:
            print("  Usage: ome skill use <skill_name> [kwargs...]")
            return
        skill_name = args.skill_args[0]
        # Parse remaining args as key=value pairs
        kwargs: dict[str, str] = {}
        for arg in args.skill_args[1:]:
            if "=" in arg:
                k, v = arg.split("=", 1)
                kwargs[k] = v
            else:
                # Treat as the main argument (message/task/topic/query)
                kwargs["message"] = arg
                kwargs["task"] = arg
                kwargs["topic"] = arg
                kwargs["query"] = arg
        result = ome.use_skill(skill_name, **kwargs)
        if result.success:
            print(result.output)
        else:
            print(f"  Error: {result.output}")
    else:
        print("  Usage: ome skill list | ome skill use <name> [args]")


def cmd_identity(args):
    """Show Ome identity card."""
    ome = _get_ome(args.path)
    card = ome.identity_card(protocol=args.protocol)
    print(json.dumps(card, ensure_ascii=False, indent=2))


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
    parser.add_argument("--version", action="version", version="ome 0.5.0")
    sub = parser.add_subparsers(dest="command")

    def _add_path(p):
        p.add_argument("--path", default=DEFAULT_PATH,
                        help=f"Ome data directory (default: {DEFAULT_PATH})")

    # create
    p_create = sub.add_parser("create", help="Create your Ome (start here!)")
    p_create.add_argument("--import", dest="import_file", default=None,
                          help="Import persona from chat export file")
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

    # dashboard
    p_dash = sub.add_parser("dashboard", help="Full life dashboard")
    _add_path(p_dash)

    # events
    p_events = sub.add_parser("events", help="Check proactive events")
    _add_path(p_events)

    # mirror
    p_mirror = sub.add_parser("mirror", help="Talk to yourself (mirror chat)")
    p_mirror.add_argument("message", nargs="*", help="Message (omit for interactive mode)")
    _add_path(p_mirror)

    # calibrate
    p_calibrate = sub.add_parser("calibrate", help="Calibrate your Ome's voice")
    _add_path(p_calibrate)

    # skill
    p_skill = sub.add_parser("skill", help="List or use skills")
    p_skill.add_argument("action", choices=["list", "use"], nargs="?", default="list",
                         help="list or use")
    p_skill.add_argument("skill_args", nargs="*", help="Skill name and arguments")
    _add_path(p_skill)

    # identity
    p_identity = sub.add_parser("identity", help="Show Ome identity card")
    p_identity.add_argument("--protocol", default="generic",
                            choices=["generic", "mcp", "http", "soap"],
                            help="Protocol format (default: generic)")
    _add_path(p_identity)

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
        "dashboard": cmd_dashboard,
        "events": cmd_events,
        "mirror": cmd_mirror,
        "calibrate": cmd_calibrate,
        "skill": cmd_skill,
        "identity": cmd_identity,
        "export": cmd_export,
        "serve": cmd_serve,
    }

    if args.command in handlers:
        handlers[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
