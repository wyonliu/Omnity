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
    return package_root() / "examples" / "minimal-scene.json"
