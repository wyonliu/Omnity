from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from omnity_soap.validate import validate_scene_file


@dataclass
class SOAPRuntime:
    """Minimal in-memory scene graph (read-only)."""

    raw: dict[str, Any]
    space_id: str

    @classmethod
    def load(cls, path: Path) -> SOAPRuntime:
        validate_scene_file(path)
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls(raw=raw, space_id=raw["space_id"])

    def summary(self) -> dict[str, Any]:
        return {
            "soap_version": self.raw.get("soap_version"),
            "space_id": self.space_id,
            "title": self.raw.get("title"),
            "object_count": len(self.raw.get("objects", [])),
            "region_count": len(self.raw.get("regions", [])),
        }

    def list_objects(self) -> list[dict[str, Any]]:
        return list(self.raw.get("objects", []))

    def get_object(self, obj_id: str) -> dict[str, Any] | None:
        for o in self.list_objects():
            if o.get("id") == obj_id:
                return o
        return None

    def list_regions(self) -> list[dict[str, Any]]:
        return list(self.raw.get("regions", []))

    def get_region(self, region_id: str) -> dict[str, Any] | None:
        for r in self.list_regions():
            if r.get("id") == region_id:
                return r
        return None
