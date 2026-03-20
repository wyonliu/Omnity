# soap-mcp

MCP server that exposes a **static SOAP scene** (JSON) as tools.

## Install

Requires **Python 3.10+** (MCP SDK).

```bash
cd packages/soap
pip install -e ".[mcp]"
```

## Run

```bash
export SOAP_SCENE_PATH=/absolute/path/to/scene.json   # optional; default = examples/minimal-scene.json
soap-mcp
```

## Cursor / Claude Code

Add an MCP server entry pointing at `soap-mcp` (stdio). Example:

```json
{
  "mcpServers": {
    "soap": {
      "command": "soap-mcp",
      "env": {
        "SOAP_SCENE_PATH": "/Users/you/Omnity/packages/soap/examples/mall-mixed-reality.json"
      }
    }
  }
}
```

## Tools

| Tool | Purpose |
|------|---------|
| `soap_get_scene_summary` | Version, space_id, counts |
| `soap_list_objects` | All objects (id, uri, type, reality, affordances) |
| `soap_get_object` | One object by `object_id` |
| `soap_list_regions` | Regions and contained objects |
| `soap_simulate_navigate` | Stub validity check (no planner) |
