"""soap-view：本地 HTTP 服务，浏览器可视化 SOAP 场景 + 实时动作事件流。

端点：
  /api/scene  — 当前场景快照（含被 Agent 修改后的最新状态）
  /api/roles  — 角色视角
  /api/events?after=N — 事件日志（轮询）
  /api/act    — POST 执行动作（也可从浏览器 / curl 触发，与 soap-mcp 同一 Runtime）
  其余       — 静态文件（dist/）
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote, urlparse

from omnity_soap.explore import load_scene, viewer_roles_payload
from omnity_soap.paths import default_scene_path, viewer_static_dir, package_root
from omnity_soap.runtime import SOAPRuntime

_runtime: Optional[SOAPRuntime] = None


def _get_runtime() -> SOAPRuntime:
    global _runtime
    if _runtime is None:
        _runtime = SOAPRuntime.load(default_scene_path())
    return _runtime


def _safe_file_under_root(root: Path, rel: str) -> Optional[Path]:
    if not rel or rel == "/":
        rel = "index.html"
    rel = rel.replace("\\", "/").lstrip("/")
    for part in rel.split("/"):
        if part == "..":
            return None
    root = root.resolve()
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


class _Handler(BaseHTTPRequestHandler):
    server_version = "SOAP-View/0.2"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj: Any, code: int = 200) -> None:
        data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        self._send(code, data, "application/json; charset=utf-8")

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(length) if length > 0 else b""

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path, encoding="utf-8") or "/"

        if path == "/api/act":
            try:
                body = json.loads(self._read_body())
            except Exception:
                self._send_json({"error": "invalid_json"}, 400)
                return
            rt = _get_runtime()
            agent_id = body.get("agent_id", "anonymous")
            verb = body.get("verb", "")
            target_id = body.get("target_id", "")
            params = body.get("params", {})
            result = rt.execute_action(agent_id, verb, target_id, params)
            self._send_json(result.to_dict())
            return

        self._send(404, b"not found", "text/plain; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path, encoding="utf-8") or "/"
        qs = parse_qs(parsed.query)

        rt = _get_runtime()

        if path == "/api/scene":
            self._send_json({"meta": {"scene_path": str(default_scene_path())},
                             "scene": rt.raw})
            return

        if path == "/api/roles":
            try:
                self._send_json({"roles": viewer_roles_payload(rt.raw),
                                 "scene_path": str(default_scene_path())})
            except Exception as e:
                self._send_json({"error": "roles_failed", "detail": str(e)}, 500)
            return

        if path == "/api/events":
            after = int(qs.get("after", ["0"])[0])
            events = rt.get_events_since(after)
            self._send_json({"events": events, "latest_seq": rt._seq})
            return

        if path == "/api/summary":
            self._send_json(rt.summary())
            return

        static_root = viewer_static_dir()
        rel = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
        file_path = _safe_file_under_root(static_root, rel)
        if file_path is None:
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        ctype, _ = mimetypes.guess_type(str(file_path))
        self._send(200, file_path.read_bytes(), ctype or "application/octet-stream")


def main() -> None:
    parser = argparse.ArgumentParser(description="SOAP scene web viewer + action server.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    args = parser.parse_args()

    p = default_scene_path()
    if not p.is_file():
        print(f"场景文件不存在: {p}\n请设置 SOAP_SCENE_PATH。", file=sys.stderr)
        sys.exit(1)

    global _runtime
    _runtime = SOAPRuntime.load(p)

    static = viewer_static_dir()
    if not (static / "index.html").is_file():
        dist = package_root() / "web" / "viewer" / "dist"
        print(
            f"未找到前端构建产物: {static}/index.html\n"
            f"请在仓库内执行:\n"
            f"  cd {package_root() / 'web' / 'viewer'} && npm ci && npm run build\n"
            f"（期望生成 {dist}/index.html）",
            file=sys.stderr,
        )
        sys.exit(1)

    httpd = ThreadingHTTPServer((args.host, args.port), _Handler)
    print(f"SOAP-View → http://{args.host}:{args.port}/")
    print(f"场景: {p}")
    print(f"API: /api/scene · /api/roles · /api/events · /api/act (POST)")
    print("Ctrl+C 停止")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
