"""MCP Apps (SEP-1865) — UI components, elicitation, resource templates.

Why this module exists
----------------------
The legacy ``mindos.mcp_server`` speaks the 2024-11-05 MCP spec: tools +
resources only. SEP-1865 (accepted 2026-01-26) adds three things the harness
wants:

1. **UI components in chat** — a tool can return an ``ui://`` resource URL
   whose body is HTML (or an iframe source). The client renders it inline.
2. **Elicitation** — mid-tool-call request for user input, structured like a
   tool call going the other direction. Lets a tool ask "which branch?"
   without bailing and restarting.
3. **Resource templates** — URI patterns the server advertises; the client
   fills in parameters to resolve concrete resources. Enables tool handlers
   to return templated links rather than static ones.

This module is **grammar-only**: it builds the JSON objects that comply with
the spec. Wiring them into a transport is left to ``mcp_server.py`` or any
embedder. Every builder is pure python and unit-testable without a network.

References:
- SEP-1865 — https://github.com/modelcontextprotocol/specification (2026-01-26)
- Protocol version constant below is the one SEP-1865 advertises.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import quote

# SEP-1865 landed in the 2026-03-15 protocol revision.
PROTOCOL_VERSION_SEP1865 = "2026-03-15"
LEGACY_PROTOCOL_VERSION = "2024-11-05"


# --- capability handshake -------------------------------------------------

@dataclass
class ServerInfo:
    name: str = "mindos"
    version: str = "0.9"


def initialize_response(
    *,
    server_info: Optional[ServerInfo] = None,
    supports_ui: bool = True,
    supports_elicitation: bool = True,
    supports_resource_templates: bool = True,
    supports_legacy: bool = True,
) -> dict:
    """Build an ``initialize`` response advertising SEP-1865 capabilities.

    The response is drop-in for the JSON-RPC ``result`` of an
    ``initialize`` method call.
    """
    caps: dict[str, Any] = {
        "tools": {"listChanged": True},
        "resources": {"listChanged": True, "subscribe": False},
        "prompts": {"listChanged": False},
    }
    if supports_ui:
        caps["ui"] = {"components": True}
    if supports_elicitation:
        caps["elicitation"] = {}
    if supports_resource_templates:
        caps["resourceTemplates"] = {}

    info = server_info or ServerInfo()
    return {
        "protocolVersion": PROTOCOL_VERSION_SEP1865,
        "supportedProtocolVersions": (
            [PROTOCOL_VERSION_SEP1865, LEGACY_PROTOCOL_VERSION]
            if supports_legacy else [PROTOCOL_VERSION_SEP1865]
        ),
        "capabilities": caps,
        "serverInfo": {"name": info.name, "version": info.version},
    }


# --- UI components --------------------------------------------------------

_SAFE_SCHEMES = frozenset({"https"})


@dataclass
class UIComponent:
    """One UI block the server exposes under a ``ui://`` resource URI."""
    id: str
    title: str
    # Exactly one of `html` or `iframe_url` is set.
    html: Optional[str] = None
    iframe_url: Optional[str] = None
    # Display hints for the client — all optional.
    width: Optional[int] = None
    height: Optional[int] = None
    sandbox: list[str] = field(
        default_factory=lambda: ["allow-scripts", "allow-same-origin"]
    )

    def __post_init__(self) -> None:
        if (self.html is None) == (self.iframe_url is None):
            raise ValueError("UIComponent needs exactly one of html / iframe_url")
        if self.iframe_url is not None and not _is_safe_https(self.iframe_url):
            raise ValueError(f"iframe_url must be https:// — got {self.iframe_url}")
        if not _slug_ok(self.id):
            raise ValueError(f"invalid component id: {self.id}")

    def uri(self) -> str:
        return f"ui://{self.id}"

    def as_resource(self) -> dict:
        """Serialize as an MCP resource descriptor (listResources shape)."""
        mime = "text/html" if self.html is not None else "text/uri-list"
        resource: dict[str, Any] = {
            "uri": self.uri(),
            "name": self.title,
            "mimeType": mime,
        }
        if self.width or self.height:
            resource["annotations"] = {
                "mindos.ui": {
                    k: v for k, v in
                    (("width", self.width), ("height", self.height),
                     ("sandbox", self.sandbox))
                    if v is not None
                }
            }
        return resource

    def as_read_result(self) -> dict:
        """Serialize as a ``resources/read`` response body."""
        if self.html is not None:
            return {"contents": [{
                "uri": self.uri(),
                "mimeType": "text/html",
                "text": self.html,
            }]}
        # iframe: return the URL in a text/uri-list body (standard)
        return {"contents": [{
            "uri": self.uri(),
            "mimeType": "text/uri-list",
            "text": self.iframe_url + "\n",
        }]}


def tool_result_with_ui(text: str, component: UIComponent) -> dict:
    """Build a SEP-1865 ``tools/call`` result that embeds a UI component.

    The client renders `text` as the assistant message and inlines the UI
    resource referenced by ``resource_link``.
    """
    return {
        "content": [
            {"type": "text", "text": text},
            {"type": "resource_link", "uri": component.uri(),
             "name": component.title, "mimeType":
                ("text/html" if component.html is not None else "text/uri-list")},
        ],
    }


# --- elicitation ----------------------------------------------------------

@dataclass
class ElicitationField:
    name: str
    type: str  # "string" | "integer" | "number" | "boolean" | "enum"
    description: str = ""
    required: bool = True
    default: Any = None
    enum: Optional[list[Any]] = None

    def as_schema_property(self) -> dict:
        if self.type == "enum":
            return {"type": "string", "enum": list(self.enum or []),
                    "description": self.description}
        p: dict[str, Any] = {"type": self.type, "description": self.description}
        if self.default is not None:
            p["default"] = self.default
        return p


def elicitation_request(
    *,
    prompt: str,
    fields: list[ElicitationField],
    request_id: Optional[str] = None,
) -> dict:
    """Build a JSON-RPC request that asks the user for structured input.

    The client should render `prompt` and collect values matching the
    schema, then send them back as the response result.
    """
    properties = {f.name: f.as_schema_property() for f in fields}
    required = [f.name for f in fields if f.required]
    return {
        "jsonrpc": "2.0",
        "id": request_id or f"elicit-{uuid.uuid4().hex[:8]}",
        "method": "elicitation/create",
        "params": {
            "prompt": prompt,
            "schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def parse_elicitation_response(
    response: dict,
    fields: list[ElicitationField],
) -> tuple[dict, Optional[str]]:
    """Validate an elicitation response. Returns (values, error_or_None)."""
    if "error" in response:
        err = response["error"]
        return {}, f"{err.get('code')}: {err.get('message', '')}".strip()
    result = response.get("result") or {}
    values = result.get("values") if isinstance(result, dict) else None
    if values is None:
        values = result  # some clients return the object directly
    if not isinstance(values, dict):
        return {}, "elicitation result must be an object"
    # type/required checks
    out: dict[str, Any] = {}
    for f in fields:
        if f.name not in values:
            if f.required and f.default is None:
                return {}, f"missing required field: {f.name}"
            if f.default is not None:
                out[f.name] = f.default
            continue
        v = values[f.name]
        if not _type_ok(v, f):
            return {}, f"type mismatch for {f.name}: want {f.type}"
        out[f.name] = v
    return out, None


# --- resource templates ---------------------------------------------------

@dataclass
class ResourceTemplate:
    uri_template: str  # e.g. "mindos://memory/{id}"
    name: str
    description: str = ""
    mime_type: Optional[str] = None

    def as_dict(self) -> dict:
        out: dict[str, Any] = {
            "uriTemplate": self.uri_template,
            "name": self.name,
            "description": self.description,
        }
        if self.mime_type:
            out["mimeType"] = self.mime_type
        return out

    def expand(self, **params: Any) -> str:
        """Fill in template parameters. Rejects unknown/missing params."""
        needed = set(re.findall(r"\{([^{}]+)\}", self.uri_template))
        missing = needed - set(params)
        if missing:
            raise ValueError(f"missing template params: {sorted(missing)}")
        extra = set(params) - needed
        if extra:
            raise ValueError(f"unknown template params: {sorted(extra)}")
        out = self.uri_template
        for k, v in params.items():
            out = out.replace("{" + k + "}", quote(str(v), safe=""))
        return out


def list_resource_templates_response(templates: list[ResourceTemplate]) -> dict:
    return {"resourceTemplates": [t.as_dict() for t in templates]}


# --- helpers --------------------------------------------------------------

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{0,63}$")


def _slug_ok(s: str) -> bool:
    return bool(s and _SLUG_RE.match(s))


def _is_safe_https(url: str) -> bool:
    return url.lower().startswith("https://") and " " not in url


def _type_ok(v: Any, f: ElicitationField) -> bool:
    if f.type == "string":
        return isinstance(v, str)
    if f.type == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if f.type == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if f.type == "boolean":
        return isinstance(v, bool)
    if f.type == "enum":
        return v in (f.enum or [])
    return False


# Tiny helper so callers can json.dumps the output and get stable keys.
def stable_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)
