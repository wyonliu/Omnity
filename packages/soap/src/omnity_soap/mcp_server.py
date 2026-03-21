"""soap-mcp: MCP Server — 外部 Agent（OpenClaw / Claude / 自定义）通过此接口进入 SOAP 空间。

读取工具：soap_get_scene_summary / soap_list_objects / soap_get_object / soap_list_regions
动作工具：soap_observe / soap_navigate / soap_manipulate（写入 Runtime 事件流）
事件工具：soap_get_events（查看历史动作与结果）
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from omnity_soap.paths import default_scene_path
from omnity_soap.runtime import SOAPRuntime


def _load_runtime() -> SOAPRuntime:
    path = default_scene_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"SOAP scene not found: {path}. Set SOAP_SCENE_PATH or add examples/minimal-scene.json."
        )
    return SOAPRuntime.load(path)


def main() -> None:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:
        raise SystemExit(
            "The 'mcp' package is required. Install with: pip install 'omnity-soap[mcp]'"
        ) from e

    rt = _load_runtime()
    mcp = FastMCP(
        "SOAP Spatial Agent Environment",
        instructions=(
            "SOAP (Spatial Omnity Agentic Protocol) environment. "
            "Use READ tools to understand the space, then ACTION tools to interact. "
            "Every action is logged — the user can observe your behavior in soap-view.\n\n"
            "Verbs: OBSERVE (perceive), NAVIGATE (move), MANIPULATE (interact with affordances).\n"
            "Always provide your agent_id so actions are attributed correctly."
        ),
    )

    # ── READ tools ──────────────────────────────────────────────

    @mcp.tool()
    def soap_get_scene_summary() -> str:
        """Return scene metadata: soap_version, space_id, title, object/region/event counts."""
        return json.dumps(rt.summary(), indent=2, ensure_ascii=False)

    @mcp.tool()
    def soap_list_objects() -> str:
        """List all objects with id, uri, type, reality, affordances, and current state."""
        out = []
        for o in rt.list_objects():
            out.append({
                "id": o.get("id"),
                "uri": o.get("uri"),
                "type": o.get("type"),
                "reality": o.get("reality"),
                "affordances": o.get("affordances", []),
                "state": o.get("state"),
            })
        return json.dumps(out, indent=2, ensure_ascii=False)

    @mcp.tool()
    def soap_get_object(object_id: str) -> str:
        """Get full detail of one object by id (including bounds, bindings, state)."""
        o = rt.get_object(object_id)
        if o is None:
            return json.dumps({"error": "not_found", "object_id": object_id})
        return json.dumps(o, indent=2, ensure_ascii=False)

    @mcp.tool()
    def soap_list_regions() -> str:
        """List regions with id, name, purpose_tags, contained_object_ids."""
        out = []
        for r in rt.list_regions():
            out.append({
                "id": r.get("id"),
                "uri": r.get("uri"),
                "name": r.get("name"),
                "purpose_tags": r.get("purpose_tags", []),
                "contained_object_ids": r.get("contained_object_ids", []),
            })
        return json.dumps(out, indent=2, ensure_ascii=False)

    # ── ACTION tools ────────────────────────────────────────────

    @mcp.tool()
    def soap_observe(agent_id: str, target_id: str) -> str:
        """OBSERVE a target (object or region). Returns its perceivable state.

        Args:
            agent_id: Your agent identifier (e.g. "openclaw_agent_1", "claude_explorer").
            target_id: The id of the object or region to observe.
        """
        result = rt.observe(agent_id, target_id)
        return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)

    @mcp.tool()
    def soap_navigate(agent_id: str, object_id: str, target_uri: str) -> str:
        """NAVIGATE — move an object/NPC/robot to a target location.

        Args:
            agent_id: Your agent identifier.
            object_id: The id of the entity to move (can be yourself, an NPC, or a robot).
            target_uri: Destination as soap:// URI (e.g. "soap://mall_01/cafe_201/counter").
        """
        result = rt.navigate(agent_id, object_id, target_uri)
        return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)

    @mcp.tool()
    def soap_manipulate(agent_id: str, object_id: str, action: str,
                        message: str = "", damage: int = 0) -> str:
        """MANIPULATE — perform an affordance action on an object.

        Args:
            agent_id: Your agent identifier.
            object_id: The target object id.
            action: The affordance to invoke (must be in the object's affordances list).
            message: For 'speak' action — what to say to an NPC.
            damage: For 'attack_target' action — damage amount.
        """
        params = {}
        if message:
            params["message"] = message
        if damage:
            params["damage"] = damage
        result = rt.manipulate(agent_id, object_id, action, params)
        return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)

    # ── EVENT tools ─────────────────────────────────────────────

    @mcp.tool()
    def soap_get_events(after_seq: int = 0) -> str:
        """Get the action event log (all events after the given sequence number).

        Args:
            after_seq: Only return events with seq > this value. Use 0 for all events.
        """
        events = rt.get_events_since(after_seq)
        return json.dumps(events, indent=2, ensure_ascii=False)

    _ = os.environ.get("SOAP_SCENE_PATH", "")
    mcp.run()
