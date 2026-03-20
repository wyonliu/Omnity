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
        "SOAP Spatial Context",
        instructions=(
            "Tools expose a static SOAP scene (JSON). Use them to answer questions about "
            "objects, regions, and URIs in the space. Set env SOAP_SCENE_PATH to override the scene file."
        ),
    )

    @mcp.tool()
    def soap_get_scene_summary() -> str:
        """Return soap_version, space_id, title, and counts of objects and regions."""
        return json.dumps(rt.summary(), indent=2)

    @mcp.tool()
    def soap_list_objects() -> str:
        """List all objects with id, uri, type, reality, and affordances."""
        out = []
        for o in rt.list_objects():
            out.append(
                {
                    "id": o.get("id"),
                    "uri": o.get("uri"),
                    "type": o.get("type"),
                    "reality": o.get("reality"),
                    "affordances": o.get("affordances", []),
                }
            )
        return json.dumps(out, indent=2)

    @mcp.tool()
    def soap_get_object(object_id: str) -> str:
        """Get one object by its id, or {\"error\":\"not_found\"}."""
        o = rt.get_object(object_id)
        if o is None:
            return json.dumps({"error": "not_found", "object_id": object_id})
        return json.dumps(o, indent=2)

    @mcp.tool()
    def soap_list_regions() -> str:
        """List regions with id, uri, name, purpose_tags, contained_object_ids."""
        out = []
        for r in rt.list_regions():
            out.append(
                {
                    "id": r.get("id"),
                    "uri": r.get("uri"),
                    "name": r.get("name"),
                    "purpose_tags": r.get("purpose_tags", []),
                    "contained_object_ids": r.get("contained_object_ids", []),
                }
            )
        return json.dumps(out, indent=2)

    @mcp.tool()
    def soap_simulate_navigate(object_id: str, target_uri: str) -> str:
        """Stub: check object exists and target_uri looks like soap:// (no path planning)."""
        o = rt.get_object(object_id)
        if o is None:
            return json.dumps({"ok": False, "code": "UNKNOWN_OBJECT", "object_id": object_id})
        if not target_uri.startswith("soap://"):
            return json.dumps({"ok": False, "code": "INVALID_URI", "detail": "must start with soap://"})
        return json.dumps(
            {
                "ok": True,
                "code": "STUB_OK",
                "detail": "No geometry planner in v0.1; object and URI are structurally valid.",
                "object_id": object_id,
                "target_uri": target_uri,
            },
            indent=2,
        )

    # Reload scene if env changes (optional); for MVP load once at startup is enough.
    _ = os.environ.get("SOAP_SCENE_PATH", "")
    mcp.run()
