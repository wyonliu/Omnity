from __future__ import annotations

import json
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

from omnity_soap.paths import schema_dir


def build_scene_validator() -> jsonschema.Draft202012Validator:
    """Validator for SOAPScene documents (resolves cross-schema $ref by $id)."""
    sdir = schema_dir()
    registry: Registry = Registry()
    for path in sorted(sdir.glob("*.schema.json")):
        contents = json.loads(path.read_text(encoding="utf-8"))
        rid = contents.get("$id")
        if not rid:
            raise ValueError(f"Schema missing $id: {path}")
        registry = registry.with_resource(rid, Resource.from_contents(contents))
    scene_path = sdir / "scene.schema.json"
    scene_schema = json.loads(scene_path.read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(scene_schema, registry=registry)


def validate_scene_file(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    v = build_scene_validator()
    v.validate(data)


def build_action_validator() -> jsonschema.Draft202012Validator:
    sdir = schema_dir()
    registry: Registry = Registry()
    for path in sorted(sdir.glob("*.schema.json")):
        contents = json.loads(path.read_text(encoding="utf-8"))
        rid = contents.get("$id")
        if rid:
            registry = registry.with_resource(rid, Resource.from_contents(contents))
    action_path = sdir / "agent-action.schema.json"
    action_schema = json.loads(action_path.read_text(encoding="utf-8"))
    return jsonschema.Draft202012Validator(action_schema, registry=registry)


def validate_action_file(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    v = build_action_validator()
    v.validate(data)
