"""Mindos MCP Server — expose Mindos as MCP tools + resources for Claude/Cursor.

Protocol: JSON-RPC 2.0 over stdio (stdin/stdout).
Implements MCP 2024-11-05 spec.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Optional

from mindos.router import LayerRouter

PROTOCOL_VERSION = "2024-11-05"

_TOOLS = [
    {
        "name": "mindos_hydrate",
        "description": (
            "Assemble the user's identity context for the current conversation. "
            "Call this at the start of a session to load personality, relevant memories, "
            "and knowledge graph into the LLM context."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "context": {
                    "type": "string",
                    "description": "Optional topic/query to retrieve relevant memories for",
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Max tokens for identity context (default 2000)",
                    "default": 2000,
                },
            },
        },
    },
    {
        "name": "mindos_commit",
        "description": (
            "Digest a conversation into long-term memories. Extracts facts, preferences, "
            "skills, relations, and episode summaries. Filters sensitive content."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "conversation": {
                    "type": "string",
                    "description": "The conversation text to digest",
                },
                "source": {
                    "type": "string",
                    "description": "Source label (e.g. 'claude', 'cursor', 'chatgpt')",
                    "default": "mcp",
                },
            },
            "required": ["conversation"],
        },
    },
    {
        "name": "mindos_recall",
        "description": (
            "Search memories by query. Returns relevant memories ranked by "
            "recency × importance × access frequency × decay."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "top_k": {"type": "integer", "description": "Max results (default 10)", "default": 10},
            },
            "required": ["query"],
        },
    },
    {
        "name": "mindos_forget",
        "description": (
            "Physically erase memories matching a pattern. GDPR-compliant hard delete "
            "from both memory store and knowledge graph."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Pattern to match for deletion"},
                "scope": {
                    "type": "string",
                    "description": "Limit to memory type: fact, episode, preference, skill, relation",
                    "enum": ["fact", "episode", "preference", "skill", "relation"],
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "mindos_status",
        "description": "Get current Mindos status: identity, memory stats, emotion state.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "mindos_reflect",
        "description": (
            "Trigger a reflection cycle. Reviews recent episodes, detects personality drift, "
            "and proposes identity updates."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
]

_RESOURCES = [
    {
        "uri": "mindos://identity",
        "name": "Mindos Identity",
        "description": "Current identity profile (name, traits, style, capabilities)",
        "mimeType": "application/json",
    },
    {
        "uri": "mindos://memories/recent",
        "name": "Recent Memories",
        "description": "The 20 most recent memories",
        "mimeType": "application/json",
    },
    {
        "uri": "mindos://knowledge_graph",
        "name": "Knowledge Graph",
        "description": "All knowledge graph triples",
        "mimeType": "application/json",
    },
]


class McpServer:
    """MCP server that wraps LayerRouter over JSON-RPC stdio."""

    def __init__(self, layer_router: LayerRouter) -> None:
        self.router = layer_router

    def run(self) -> None:
        """Main loop: read JSON-RPC from stdin, write responses to stdout."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            response = self._handle(msg)
            if response is not None:
                self._send(response)

    def _handle(self, msg: dict[str, Any]) -> Optional[dict[str, Any]]:
        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        handler = {
            "initialize": self._on_initialize,
            "initialized": lambda _: None,
            "tools/list": self._on_tools_list,
            "tools/call": self._on_tools_call,
            "resources/list": self._on_resources_list,
            "resources/read": self._on_resources_read,
            "ping": self._on_ping,
        }.get(method)

        if handler is None:
            if msg_id is not None:
                return self._error(msg_id, -32601, f"Method not found: {method}")
            return None

        result = handler(params)
        if result is None and method == "initialized":
            return None  # notification, no response
        if msg_id is not None:
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        return None

    def _on_initialize(self, params: dict) -> dict:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {
                "tools": {},
                "resources": {},
            },
            "serverInfo": {
                "name": "mindos",
                "version": "0.2.0",
            },
        }

    def _on_ping(self, params: dict) -> dict:
        return {}

    def _on_tools_list(self, params: dict) -> dict:
        return {"tools": _TOOLS}

    def _on_tools_call(self, params: dict) -> dict:
        name = params.get("name", "")
        args = params.get("arguments", {})

        try:
            if name == "mindos_hydrate":
                text = self.router.hydrate(
                    context=args.get("context", ""),
                    max_tokens=args.get("max_tokens", 2000),
                )
                return {"content": [{"type": "text", "text": text}]}

            elif name == "mindos_commit":
                result = self.router.commit(
                    conversation=args["conversation"],
                    source=args.get("source", "mcp"),
                )
                return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

            elif name == "mindos_recall":
                results = self.router.recall(
                    query=args["query"],
                    top_k=args.get("top_k", 10),
                )
                return {"content": [{"type": "text", "text": json.dumps(results, ensure_ascii=False)}]}

            elif name == "mindos_forget":
                result = self.router.forget(
                    pattern=args["pattern"],
                    scope=args.get("scope"),
                )
                return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}]}

            elif name == "mindos_status":
                status = self.router.status()
                return {"content": [{"type": "text", "text": json.dumps(status, ensure_ascii=False)}]}

            elif name == "mindos_reflect":
                result = self.router.reflect()
                text = json.dumps(result, ensure_ascii=False) if result else '{"message": "No episodes to reflect on"}'
                return {"content": [{"type": "text", "text": text}]}

            else:
                return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True}

        except Exception as e:
            return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}

    def _on_resources_list(self, params: dict) -> dict:
        return {"resources": _RESOURCES}

    def _on_resources_read(self, params: dict) -> dict:
        uri = params.get("uri", "")

        if uri == "mindos://identity":
            snapshot = self.router.l4.personality_snapshot()
            return {"contents": [{"uri": uri, "mimeType": "application/json",
                                  "text": json.dumps(snapshot, ensure_ascii=False)}]}

        elif uri == "mindos://memories/recent":
            memories = self.router.recall("", top_k=20)
            return {"contents": [{"uri": uri, "mimeType": "application/json",
                                  "text": json.dumps(memories, ensure_ascii=False)}]}

        elif uri == "mindos://knowledge_graph":
            triples = self.router.store.triples()
            data = [{"subject": t.subject, "predicate": t.predicate, "object": t.object}
                    for t in triples]
            return {"contents": [{"uri": uri, "mimeType": "application/json",
                                  "text": json.dumps(data, ensure_ascii=False)}]}

        return {"contents": []}

    def _send(self, msg: dict) -> None:
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()

    def _error(self, msg_id: Any, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def run_mcp_server(soul_dir: str) -> None:
    """Entry point for `mindos serve --mcp`."""
    from pathlib import Path
    from mindos.config import MindosConfig
    from mindos.store import MemoryStore

    root = Path(soul_dir).expanduser()
    if not root.exists():
        print(f"Soul directory not found: {root}", file=sys.stderr)
        sys.exit(1)

    config = MindosConfig.load(root)
    store = MemoryStore(root / "memory.db")

    identity_path = root / "identity.yaml"
    identity: dict[str, Any] = {}
    if identity_path.exists():
        try:
            import yaml
            identity = yaml.safe_load(identity_path.read_text(encoding="utf-8")) or {}
        except ImportError:
            identity = json.loads(identity_path.read_text(encoding="utf-8"))

    router = LayerRouter(store, identity, config)
    server = McpServer(router)

    print("Mindos MCP server started", file=sys.stderr)
    server.run()
