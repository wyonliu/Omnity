from __future__ import annotations

import os
from pathlib import Path


def package_root() -> Path:
    """Root of the `packages/soap` tree (parent of `src/`)."""
    return Path(__file__).resolve().parent.parent.parent


def schema_dir() -> Path:
    """JSON Schema files: bundled in wheel under `omnity_soap/schemas`, else `spec/schemas`."""
    bundled = Path(__file__).resolve().parent / "schemas"
    if bundled.is_dir() and list(bundled.glob("*.schema.json")):
        return bundled
    return package_root() / "spec" / "schemas"


def default_scene_path() -> Path:
    p = os.environ.get("SOAP_SCENE_PATH")
    if p:
        return Path(p).expanduser().resolve()
    # 与 soap-explore 默认一致：活商场样例便于演示；单元测试仍显式指定路径。
    return package_root() / "examples" / "mall-mixed-reality.json"


def viewer_static_dir() -> Path:
    """`soap-view` 静态资源：wheel 内 `viewer_static/`（Vite `dist/` 的拷贝），开发时优先用 `web/viewer/dist/`。"""
    bundled = Path(__file__).resolve().parent / "viewer_static"
    if bundled.is_dir() and (bundled / "index.html").is_file():
        return bundled
    return package_root() / "web" / "viewer" / "dist"
