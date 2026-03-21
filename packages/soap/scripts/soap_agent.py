#!/usr/bin/env python3
"""soap-agent — LLM-driven autonomous agent for SOAP environments.

Usage:
    # With built-in heuristic brain (no API key needed):
    python scripts/soap_agent.py

    # With Claude:
    ANTHROPIC_API_KEY=sk-... python scripts/soap_agent.py --brain claude

    # With OpenAI:
    OPENAI_API_KEY=sk-... python scripts/soap_agent.py --brain openai

    # With DeepSeek:
    DEEPSEEK_API_KEY=sk-... python scripts/soap_agent.py --brain deepseek

The agent connects to a running soap-view server, perceives the environment,
thinks about what to do, and acts — a complete sense-think-act loop.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from typing import Any, Dict, List, Optional

import urllib.request

CFG = {"server": "http://127.0.0.1:8765"}
AGENT_ID = "llm_agent"

# ─── HTTP helpers ───────────────────────────────────────────────

def api_get(path: str) -> Dict[str, Any]:
    req = urllib.request.Request(f"{CFG['server']}{path}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def api_post(path: str, body: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{CFG['server']}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def act(verb: str, target_id: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return api_post("/api/act", {
        "agent_id": AGENT_ID, "verb": verb,
        "target_id": target_id, "params": params or {}})


# ─── Scene perception ──────────────────────────────────────────

def perceive() -> Dict[str, Any]:
    """Build a perception summary from the scene API."""
    scene_data = api_get("/api/scene")
    scene = scene_data.get("scene", {})
    regions = scene.get("regions", [])
    objects = scene.get("objects", [])

    region_summaries = []
    for r in regions:
        oids = r.get("contained_object_ids", [])
        region_summaries.append({
            "id": r["id"], "name": r.get("name", r["id"]),
            "objects": oids, "tags": r.get("purpose_tags", [])
        })

    object_summaries = []
    for o in objects:
        object_summaries.append({
            "id": o["id"], "type": o.get("type", ""),
            "reality": o.get("reality", ""),
            "affordances": o.get("affordances", []),
            "hp": o.get("state", {}).get("hp"),
            "status": o.get("state", {}).get("status"),
        })

    events_data = api_get("/api/events?after=0")
    recent = events_data.get("events", [])[-5:]

    return {
        "title": scene.get("title", ""),
        "regions": region_summaries,
        "objects": object_summaries,
        "recent_events": recent,
    }


# ─── Brain interface ───────────────────────────────────────────

SYSTEM_PROMPT = """You are an autonomous agent exploring a SOAP (Spatial Omnity Agentic Protocol) environment — a mixed-reality shopping mall.

Available actions (respond with exactly ONE JSON object):
- OBSERVE a region or object: {"verb":"OBSERVE","target_id":"<id>","params":{},"thought":"<why>"}
- NAVIGATE to a region: {"verb":"NAVIGATE","target_id":"<region_id>","params":{"target_uri":"soap://mall_01/<region_id>"},"thought":"<why>"}
- MANIPULATE an object: {"verb":"MANIPULATE","target_id":"<object_id>","params":{"action":"<affordance>","message":"<text>"},"thought":"<why>"}

Rules:
- Always include a "thought" field explaining your reasoning in Chinese
- Explore systematically: observe first, then navigate, then interact
- Talk to NPCs, try different affordances, visit all regions
- Be curious and creative — you're exploring a mixed-reality world!
- Only use affordances listed for each object
- Respond with ONLY the JSON object, no markdown or extra text
"""


def build_user_prompt(perception: Dict, memory: List[Dict], step: int) -> str:
    lines = [f"=== Step {step} ===", "", "Current perception:"]
    lines.append(f"Scene: {perception['title']}")
    lines.append(f"\nRegions ({len(perception['regions'])}):")
    for r in perception["regions"]:
        lines.append(f"  - {r['id']} ({r['name']}): {len(r['objects'])} objects, tags={r['tags']}")
    lines.append(f"\nObjects ({len(perception['objects'])}):")
    for o in perception["objects"]:
        extra = ""
        if o["hp"] is not None:
            extra += f" HP={o['hp']}"
        if o["status"]:
            extra += f" status={o['status']}"
        lines.append(f"  - {o['id']} [{o['type']}] reality={o['reality']} affordances={o['affordances']}{extra}")

    if memory:
        lines.append(f"\nYour action history (last {min(len(memory), 8)}):")
        for m in memory[-8:]:
            ok = "✓" if m.get("ok") else "✗"
            lines.append(f"  {m['verb']} {m['target_id']} → {ok} {m.get('detail','')[:80]}")

    if perception["recent_events"]:
        lines.append("\nRecent events in the world:")
        for ev in perception["recent_events"][-3:]:
            lines.append(f"  {ev['verb']} {ev['target_id']} by {ev['agent_id']}")

    lines.append("\nWhat do you want to do next? Respond with ONE JSON action.")
    return "\n".join(lines)


def think_claude(perception: Dict, memory: List[Dict], step: int) -> Dict[str, Any]:
    """Use Claude API for reasoning."""
    try:
        import anthropic
    except ImportError:
        print("ERROR: pip install anthropic", file=sys.stderr)
        sys.exit(1)
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(perception, memory, step)}],
    )
    text = msg.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def think_openai(perception: Dict, memory: List[Dict], step: int) -> Dict[str, Any]:
    """Use OpenAI API for reasoning."""
    try:
        import openai
    except ImportError:
        print("ERROR: pip install openai", file=sys.stderr)
        sys.exit(1)
    client = openai.OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=512,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(perception, memory, step)},
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def think_deepseek(perception: Dict, memory: List[Dict], step: int) -> Dict[str, Any]:
    """Use DeepSeek API (OpenAI-compatible) for reasoning.

    Set DEEPSEEK_API_KEY env var before running.
    """
    try:
        import openai
    except ImportError:
        print("ERROR: pip install openai", file=sys.stderr)
        sys.exit(1)
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("ERROR: set DEEPSEEK_API_KEY environment variable", file=sys.stderr)
        sys.exit(1)
    client = openai.OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    resp = client.chat.completions.create(
        model="deepseek-chat",
        max_tokens=512,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(perception, memory, step)},
        ],
        response_format={"type": "json_object"},
    )
    text = resp.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


def think_heuristic(perception: Dict, memory: List[Dict], step: int) -> Dict[str, Any]:
    """Built-in heuristic brain — no API key needed.

    Simulates intelligent exploration with a structured plan:
    1. Observe current region
    2. Interact with objects in the region
    3. Navigate to next unvisited region
    4. Repeat until all regions explored
    """
    regions = perception["regions"]
    objects = perception["objects"]
    visited_regions = set()
    observed_ids = set()
    talked_to = set()
    attacked = set()

    for m in memory:
        if m["verb"] == "NAVIGATE" and m.get("ok"):
            visited_regions.add(m["target_id"])
        if m["verb"] == "OBSERVE" and m.get("ok"):
            observed_ids.add(m["target_id"])
        if m["verb"] == "MANIPULATE" and m.get("ok"):
            a = m.get("params", {}).get("action", "")
            if a == "speak":
                talked_to.add(m["target_id"])
            if a == "attack_target":
                attacked.add(m["target_id"])

    region_order = ["atrium", "store_102", "cafe_201", "service_lane", "virtual_twin"]
    current_region = None
    if memory:
        for m in reversed(memory):
            if m["verb"] == "NAVIGATE" and m.get("ok"):
                current_region = m["target_id"]
                break
    if current_region is None:
        current_region = "atrium"

    # Phase 1: observe current region if not yet
    if current_region not in observed_ids:
        r = next((r for r in regions if r["id"] == current_region), None)
        name = r["name"] if r else current_region
        return {"verb": "OBSERVE", "target_id": current_region, "params": {},
                "thought": f"我刚到{name}，先观察一下环境"}

    # Phase 2: interact with objects in current region
    cur_region_data = next((r for r in regions if r["id"] == current_region), None)
    if cur_region_data:
        for oid in cur_region_data["objects"]:
            obj = next((o for o in objects if o["id"] == oid), None)
            if not obj:
                continue

            # Observe unobserved objects
            if oid not in observed_ids:
                return {"verb": "OBSERVE", "target_id": oid, "params": {},
                        "thought": f"看看{oid}是什么"}

            # Talk to NPCs
            if "speak" in obj.get("affordances", []) and oid not in talked_to:
                phrases = {
                    "store_102_ai_clerk": "有什么推荐的商品吗？",
                    "npc_merchant_lin": "今天有什么新鲜事？",
                    "npc_barista_chen": "来杯拿铁吧",
                }
                msg = phrases.get(oid, "你好，能聊聊吗？")
                return {"verb": "MANIPULATE", "target_id": oid,
                        "params": {"action": "speak", "message": msg},
                        "thought": f"和{oid}聊聊看"}

            # Attack monsters
            if "attack_target" in obj.get("affordances", []):
                hp = obj.get("hp")
                if hp is not None and hp > 0 and oid not in attacked:
                    return {"verb": "MANIPULATE", "target_id": oid,
                            "params": {"action": "attack_target", "damage": 40},
                            "thought": f"试试攻击{oid}！它还有{hp}HP"}

            # Scan QR codes
            if "scan_qr" in obj.get("affordances", []) and oid not in set(
                    m["target_id"] for m in memory if m.get("params", {}).get("action") == "scan_qr"):
                return {"verb": "MANIPULATE", "target_id": oid,
                        "params": {"action": "scan_qr"},
                        "thought": f"扫一下{oid}的二维码看看"}

            # Make coffee
            if "make_coffee" in obj.get("affordances", []) and oid not in set(
                    m["target_id"] for m in memory if m.get("params", {}).get("action") == "make_coffee"):
                return {"verb": "MANIPULATE", "target_id": oid,
                        "params": {"action": "make_coffee"},
                        "thought": f"让{oid}做杯咖啡"}

    # Phase 3: navigate to next unvisited region
    for rid in region_order:
        if rid not in visited_regions or rid not in observed_ids:
            r = next((r for r in regions if r["id"] == rid), None)
            name = r["name"] if r else rid
            return {"verb": "NAVIGATE", "target_id": rid,
                    "params": {"target_uri": f"soap://mall_01/{rid}"},
                    "thought": f"还没去过{name}，去探索一下"}

    # Phase 4: revisit for second-round interactions
    # Attack monster again if still alive
    for o in objects:
        if "attack_target" in o.get("affordances", []):
            hp = o.get("hp")
            if hp is not None and hp > 0:
                return {"verb": "MANIPULATE", "target_id": o["id"],
                        "params": {"action": "attack_target", "damage": 60},
                        "thought": f"{o['id']}还有{hp}HP，再打一次！"}

    # Final: just observe a random object for fun
    obj = random.choice(objects)
    return {"verb": "OBSERVE", "target_id": obj["id"], "params": {},
            "thought": f"再仔细看看{obj['id']}"}


BRAINS = {
    "heuristic": think_heuristic,
    "claude": think_claude,
    "openai": think_openai,
    "deepseek": think_deepseek,
}


# ─── Main loop ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SOAP autonomous agent")
    parser.add_argument("--brain", choices=BRAINS.keys(), default="heuristic",
                        help="Reasoning backend (default: heuristic)")
    parser.add_argument("--steps", type=int, default=20,
                        help="Max number of actions (default: 20)")
    parser.add_argument("--delay", type=float, default=2.5,
                        help="Seconds between actions (default: 2.5)")
    parser.add_argument("--server", default=CFG["server"],
                        help="soap-view server URL")
    args = parser.parse_args()

    CFG["server"] = args.server
    think = BRAINS[args.brain]
    memory: List[Dict] = []

    srv = CFG["server"]
    print(f"╔══════════════════════════════════════════════════╗")
    print(f"║  SOAP Agent — {args.brain} brain                ║")
    print(f"║  Server: {srv:<39s} ║")
    print(f"║  Max steps: {args.steps:<36d} ║")
    print(f"╚══════════════════════════════════════════════════╝")
    print()

    try:
        info = api_get("/api/scene")
        title = info.get("scene", {}).get("title", "?")
        print(f"✓ Connected — scene: {title}")
    except Exception as e:
        print(f"✗ Cannot reach {srv}: {e}")
        print("  Start soap-view first: soap-view")
        sys.exit(1)

    print()

    for step in range(1, args.steps + 1):
        perception = perceive()
        decision = think(perception, memory, step)

        thought = decision.get("thought", "")
        verb = decision["verb"]
        target = decision["target_id"]
        params = decision.get("params", {})

        print(f"── Step {step}/{args.steps} ──────────────────────────────")
        print(f"💭 {thought}")
        print(f"▶  {verb} → {target}" + (f"  params={params}" if params else ""))

        try:
            result = act(verb, target, params)
            ok = result.get("ok", False)
            detail = result.get("detail", "")
            data = result.get("data", {})
            print(f"{'✓' if ok else '✗'}  {detail}")

            if data.get("reply"):
                print(f"💬 {data['reply']}")
            if data.get("hp_remaining") is not None:
                hp = data["hp_remaining"]
                print(f"⚔  HP={hp}" + (" 💀 击败!" if data.get("defeated") else ""))
            if data.get("digital_twin_url"):
                print(f"🔗 {data['digital_twin_url']}")

            memory.append({
                "verb": verb, "target_id": target, "params": params,
                "ok": ok, "detail": detail,
            })
        except Exception as e:
            print(f"✗  Error: {e}")
            memory.append({"verb": verb, "target_id": target, "params": params, "ok": False, "detail": str(e)})

        print()

        if step < args.steps:
            time.sleep(args.delay)

    print("═══ Agent finished ═══")
    print(f"Completed {len(memory)} actions, {sum(1 for m in memory if m['ok'])} succeeded.")


if __name__ == "__main__":
    main()
