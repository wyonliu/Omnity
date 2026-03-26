# omnity-soap

**SOAP -- Spatial Omnity Agentic Protocol: the HTTP for spatial AI agents.**

An open protocol + reference implementation for AI agents to understand, query, and manipulate real 3D environments. Four verbs: **OBSERVE**, **NAVIGATE**, **MANIPULATE**, **REARRANGE**.

## Install

```bash
pip install omnity-soap                   # core (validation + CLI)
pip install "omnity-soap[mcp]"            # + MCP server (Python >=3.10)
pip install "omnity-soap[server]"         # + HTTP server + soap-view visualizer
```

## Quick Start

```bash
# Validate a scene file against the SOAP spec
soap-validate examples/mall-mixed-reality.json

# Interactive walkthrough — explore a scene from 6 different roles
soap-explore examples/mall-mixed-reality.json

# Launch browser visualizer with autonomous agent demo
pip install "omnity-soap[server]"
export SOAP_SCENE_PATH=examples/mall-mixed-reality.json
soap-view
# Open http://127.0.0.1:8765/
```

### Python API

```python
from omnity_soap.runtime import SOAPRuntime

# Load a scene into the mutable runtime
rt = SOAPRuntime.from_file("scene.json")

# Execute an agent action
result = rt.act(
    agent_id="my_bot",
    verb="OBSERVE",
    target_id="atrium",
    params={},
)
print(result.ok, result.detail)

# Navigate to a store
rt.act("my_bot", "NAVIGATE", "store_102",
       {"target_uri": "soap://mall_01/store_102"})
```

### HTTP API (with soap-view running)

```bash
# Observe the atrium
curl -X POST http://127.0.0.1:8765/api/act \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"my_bot","verb":"OBSERVE","target_id":"atrium","params":{}}'

# Navigate to a store
curl -X POST http://127.0.0.1:8765/api/act \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"my_bot","verb":"NAVIGATE","target_id":"store_102","params":{"target_uri":"soap://mall_01/store_102"}}'
```

### MCP (Claude Desktop / Cursor)

```json
{
  "mcpServers": {
    "soap": { "command": "soap-mcp" }
  }
}
```

## API Overview

| Class / CLI | What it does |
|-------------|-------------|
| **`SOAPRuntime`** | In-memory mutable scene graph. Load a scene JSON, execute agent actions (OBSERVE/NAVIGATE/MANIPULATE/REARRANGE), track events. The core runtime that powers all other tools. |
| **`soap-validate`** | CLI that checks whether a scene JSON conforms to the SOAP v0.1 JSON Schema. |
| **`soap-explore`** | Interactive CLI to walk through a scene from six different role perspectives, testing visibility and access. |
| **`soap-view`** | Browser-based Canvas 2D visualizer: floor plan + agent avatars + thought bubbles + smooth movement + autonomous exploration demo. Also exposes an HTTP API at `/api/act`. |
| **`soap-mcp`** | MCP server exposing SOAP spatial tools to Claude Desktop, Cursor, or any MCP-compatible host. |

## Part of Omnity

```
SOAP         <-- you are here
  Mindos        persistent multi-layer brain
    Ome           individual AI agent (persona, skills, growth)
      Maxim         multi-agent society + economy
        OmeTown       the integrated world
```

`pip install omnity-soap omnity-mindos omnity-ome omnity-maxim`

## Docs

- [SOAP Spec v0.1](./spec/SOAP-v0.1.md)
- [soap-mcp README](./soap-mcp/README.md)

## License

[Apache-2.0](../../LICENSE)
