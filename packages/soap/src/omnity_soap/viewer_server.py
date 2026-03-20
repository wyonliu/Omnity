"""soap-view：本地 HTTP 服务，浏览器内可视化 SOAP 场景（平面图 + 关系图）。"""
from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from omnity_soap.explore import load_scene, viewer_roles_payload
from omnity_soap.paths import default_scene_path, viewer_static_dir, package_root


def _scene_path() -> Path:
    return default_scene_path()


def _load_scene_dict(path: Path) -> Dict[str, Any]:
    return load_scene(path)


def _safe_file_under_root(root: Path, rel: str) -> Optional[Path]:
    """解析 root 下的相对路径；禁止越界与路径遍历。存在且为文件则返回。"""
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
    server_version = "SOAP-View/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, obj: Any, code: int = 200) -> None:
        data = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
        self._send(code, data, "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path or "/"

        if path == "/api/scene":
            p = _scene_path()
            if not p.is_file():
                self._send_json({"error": "scene_not_found", "path": str(p)}, 404)
                return
            try:
                scene = _load_scene_dict(p)
            except Exception as e:
                self._send_json({"error": "scene_invalid", "detail": str(e)}, 500)
                return
            self._send_json({"meta": {"scene_path": str(p)}, "scene": scene})
            return

        if path == "/api/roles":
            p = _scene_path()
            if not p.is_file():
                self._send_json({"error": "scene_not_found", "path": str(p)}, 404)
                return
            try:
                scene = _load_scene_dict(p)
            except Exception as e:
                self._send_json({"error": "scene_invalid", "detail": str(e)}, 500)
                return
            self._send_json({"roles": viewer_roles_payload(scene), "scene_path": str(p)})
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
    parser = argparse.ArgumentParser(description="SOAP scene web viewer (local only by default).")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    args = parser.parse_args()

    p = _scene_path()
    if not p.is_file():
        print(f"场景文件不存在: {p}\n请设置 SOAP_SCENE_PATH。", file=sys.stderr)
        sys.exit(1)
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
    print("Ctrl+C 停止")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
