"""W3 tests — MCP Apps SEP-1865 builders.

Pure grammar tests: every builder returns the JSON shape the spec requires,
without touching a transport. That's deliberate — the harness's job is to
speak the protocol correctly; wiring to stdin/stdout is mcp_server.py's job.
"""

from __future__ import annotations

import sys
from pathlib import Path

_here = Path(__file__).resolve()
sys.path.insert(0, str(_here.parent.parent / "src"))

from mindos.harness import ContextBuilder, ContextLoader
from mindos.harness.mcp_apps import (
    LEGACY_PROTOCOL_VERSION,
    PROTOCOL_VERSION_SEP1865,
    ElicitationField,
    ResourceTemplate,
    ServerInfo,
    UIComponent,
    elicitation_request,
    initialize_response,
    list_resource_templates_response,
    parse_elicitation_response,
    stable_json,
    tool_result_with_ui,
)


# -- handshake -------------------------------------------------------------

def test_initialize_response_advertises_sep1865_and_legacy():
    r = initialize_response()
    assert r["protocolVersion"] == PROTOCOL_VERSION_SEP1865
    assert LEGACY_PROTOCOL_VERSION in r["supportedProtocolVersions"]
    caps = r["capabilities"]
    assert caps["ui"]["components"] is True
    assert "elicitation" in caps
    assert "resourceTemplates" in caps
    assert r["serverInfo"]["name"] == "mindos"
    print("  PASSED")


def test_initialize_response_can_drop_legacy_and_caps():
    r = initialize_response(
        server_info=ServerInfo(name="ome", version="1.2.3"),
        supports_ui=False, supports_elicitation=False,
        supports_resource_templates=False, supports_legacy=False,
    )
    assert r["supportedProtocolVersions"] == [PROTOCOL_VERSION_SEP1865]
    assert "ui" not in r["capabilities"]
    assert "elicitation" not in r["capabilities"]
    assert "resourceTemplates" not in r["capabilities"]
    assert r["serverInfo"] == {"name": "ome", "version": "1.2.3"}
    print("  PASSED")


# -- UI components ---------------------------------------------------------

def test_ui_component_html_resource_and_read():
    ui = UIComponent(id="memory-card-42", title="Memory",
                     html="<div>hi</div>", width=400, height=300)
    assert ui.uri() == "ui://memory-card-42"
    res = ui.as_resource()
    assert res["uri"] == "ui://memory-card-42"
    assert res["mimeType"] == "text/html"
    assert res["annotations"]["mindos.ui"]["width"] == 400
    read = ui.as_read_result()
    assert read["contents"][0]["text"] == "<div>hi</div>"
    assert read["contents"][0]["mimeType"] == "text/html"
    print("  PASSED")


def test_ui_component_iframe_read_returns_uri_list():
    ui = UIComponent(id="dash", title="Dashboard",
                     iframe_url="https://example.com/dash")
    read = ui.as_read_result()
    assert read["contents"][0]["mimeType"] == "text/uri-list"
    assert read["contents"][0]["text"].strip() == "https://example.com/dash"
    print("  PASSED")


def test_ui_component_rejects_bad_inputs():
    # both html and iframe_url → error
    import pytest
    try:
        UIComponent(id="x", title="t", html="<p/>", iframe_url="https://e.com")
        assert False, "expected ValueError"
    except ValueError:
        pass
    # non-https iframe rejected
    try:
        UIComponent(id="x", title="t", iframe_url="http://evil.com")
        assert False, "expected ValueError"
    except ValueError:
        pass
    # invalid slug rejected
    try:
        UIComponent(id="../bad", title="t", html="<p/>")
        assert False, "expected ValueError"
    except ValueError:
        pass
    print("  PASSED")


def test_tool_result_with_ui_wraps_text_and_resource_link():
    ui = UIComponent(id="x", title="X", html="<p/>")
    r = tool_result_with_ui("here's your card", ui)
    assert len(r["content"]) == 2
    assert r["content"][0]["type"] == "text"
    assert r["content"][1]["type"] == "resource_link"
    assert r["content"][1]["uri"] == "ui://x"
    print("  PASSED")


# -- elicitation -----------------------------------------------------------

def test_elicitation_request_shape():
    fs = [
        ElicitationField("name", "string", "Your name"),
        ElicitationField("age", "integer", "Age in years"),
        ElicitationField("env", "enum", "Environment",
                         required=False, default="prod",
                         enum=["dev", "prod"]),
    ]
    req = elicitation_request(prompt="who are you?", fields=fs,
                              request_id="r1")
    assert req["jsonrpc"] == "2.0"
    assert req["id"] == "r1"
    assert req["method"] == "elicitation/create"
    s = req["params"]["schema"]
    assert s["properties"]["name"]["type"] == "string"
    assert s["properties"]["age"]["type"] == "integer"
    assert s["properties"]["env"]["enum"] == ["dev", "prod"]
    assert s["required"] == ["name", "age"]  # env not required
    print("  PASSED")


def test_elicitation_response_parse_and_validate():
    fs = [
        ElicitationField("name", "string", required=True),
        ElicitationField("age", "integer", required=True),
        ElicitationField("env", "enum", required=False, default="prod",
                         enum=["dev", "prod"]),
    ]
    # happy path
    vals, err = parse_elicitation_response(
        {"result": {"values": {"name": "Cap", "age": 40}}}, fs)
    assert err is None
    assert vals == {"name": "Cap", "age": 40, "env": "prod"}
    # direct result (some clients)
    vals, err = parse_elicitation_response(
        {"result": {"name": "C", "age": 1, "env": "dev"}}, fs)
    assert err is None and vals["env"] == "dev"
    # missing required
    vals, err = parse_elicitation_response({"result": {"name": "x"}}, fs)
    assert vals == {} and "age" in err
    # type mismatch
    vals, err = parse_elicitation_response(
        {"result": {"name": "x", "age": "forty"}}, fs)
    assert vals == {} and "type mismatch" in err
    # enum reject
    vals, err = parse_elicitation_response(
        {"result": {"name": "x", "age": 1, "env": "staging"}}, fs)
    assert vals == {} and "env" in err
    # jsonrpc error propagates
    vals, err = parse_elicitation_response(
        {"error": {"code": -32603, "message": "user cancelled"}}, fs)
    assert vals == {} and "cancelled" in err
    print("  PASSED")


# -- resource templates ----------------------------------------------------

def test_resource_template_expand_and_list():
    t = ResourceTemplate(uri_template="mindos://memory/{id}",
                         name="memory", description="One memory",
                         mime_type="application/json")
    assert t.expand(id="abc-42") == "mindos://memory/abc-42"
    # URL-encoded
    assert t.expand(id="hello world") == "mindos://memory/hello%20world"
    # missing param
    try:
        t.expand()
        assert False
    except ValueError as e:
        assert "missing" in str(e)
    # extra param
    try:
        t.expand(id="x", y="z")
        assert False
    except ValueError as e:
        assert "unknown" in str(e)

    body = list_resource_templates_response([t])
    assert body["resourceTemplates"][0]["uriTemplate"] == "mindos://memory/{id}"
    assert body["resourceTemplates"][0]["mimeType"] == "application/json"
    print("  PASSED")


# -- stable json -----------------------------------------------------------

def test_stable_json_sorts_keys_and_unicode():
    s = stable_json({"b": 1, "a": {"z": 2, "y": "米莱"}})
    assert s == '{"a": {"y": "米莱", "z": 2}, "b": 1}'
    print("  PASSED")


# -- ContextLoader hook (Ome365 ASK) ---------------------------------------

class _InMemLoader:
    """Fake PG+RLS-ish loader: no disk at all."""
    def __init__(self, files: dict[str, str], journal_order: list[str] = None):
        self.files = files
        self.journal_order = journal_order or []
        self.read_calls: list[str] = []

    def read_text(self, relpath: str) -> str:
        self.read_calls.append(relpath)
        return self.files.get(relpath, "")

    def list_journal(self, *, limit: int) -> list[str]:
        return list(self.journal_order)[:limit]


def test_context_builder_accepts_context_loader():
    loader = _InMemLoader({
        "IDENTITY.md": "---\nname: X\n---\n# I am X\n",
        "MEMORY.md":   "# mem\n- a\n",
        "FACTS.md":    "# facts\n- f1\n",
        "Journal/2026-04-19.md": "---\nd: 19\n---\n# today\nship W4\n",
        "Journal/2026-04-18.md": "# yesterday\n",
    }, journal_order=["Journal/2026-04-19.md", "Journal/2026-04-18.md"])
    ctx = ContextBuilder(loader).build("hello")
    # All four sections picked up without touching disk
    assert "I am X" in ctx.system_prompt
    assert "mem" in ctx.system_prompt
    assert "facts" in ctx.system_prompt
    assert "ship W4" in ctx.system_prompt
    assert "IDENTITY.md" in ctx.files_used
    assert "MEMORY.md" in ctx.files_used
    assert "FACTS.md" in ctx.files_used
    assert any(f.endswith("/recent") for f in ctx.files_used)
    # Loader's read_text was actually invoked (no disk fallback)
    assert "IDENTITY.md" in loader.read_calls
    assert "Journal/2026-04-19.md" in loader.read_calls
    print("  PASSED")


def test_context_builder_loader_soft_fails_on_raise():
    class _Broken:
        def read_text(self, relpath):
            raise RuntimeError("db down")
        def list_journal(self, *, limit):
            raise RuntimeError("db down")
    ctx = ContextBuilder(_Broken()).build("hi")
    # Builder returns empty system prompt, doesn't explode
    assert ctx.system_prompt == ""
    assert ctx.files_used == []
    assert ctx.truncated is False
    print("  PASSED")


def test_context_builder_rejects_bad_source():
    try:
        ContextBuilder(42)  # type: ignore[arg-type]
    except TypeError as e:
        assert "ContextLoader" in str(e) or "path" in str(e)
        print("  PASSED")
        return
    raise AssertionError("expected TypeError")


def test_context_loader_protocol_runtime_checkable():
    # The duck-typed path (no explicit Protocol inheritance) also works.
    l = _InMemLoader({"IDENTITY.md": "# I"})
    assert isinstance(l, ContextLoader)  # runtime_checkable Protocol
    print("  PASSED")


if __name__ == "__main__":
    test_initialize_response_advertises_sep1865_and_legacy()
    test_initialize_response_can_drop_legacy_and_caps()
    test_ui_component_html_resource_and_read()
    test_ui_component_iframe_read_returns_uri_list()
    test_ui_component_rejects_bad_inputs()
    test_tool_result_with_ui_wraps_text_and_resource_link()
    test_elicitation_request_shape()
    test_elicitation_response_parse_and_validate()
    test_resource_template_expand_and_list()
    test_stable_json_sorts_keys_and_unicode()
    test_context_builder_accepts_context_loader()
    test_context_builder_loader_soft_fails_on_raise()
    test_context_builder_rejects_bad_source()
    test_context_loader_protocol_runtime_checkable()
    print("\n✔ harness W3: 14 tests passed")
