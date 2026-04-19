"""Built-in harness tools — the first-class moves every Ome can make.

Four tools, wired straight to the harness:

    recall(query, limit=5)       → MemoryStore.search_text
    commit(content, type='fact') → MemoryStore.add  (no LLM, just write)
    read_file(path)              → sandboxed file read
    write_file(path, content)    → sandboxed file write

Every fs tool is clamped to a sandbox root; there is no path that can escape
via `..` or absolute prefixes. If no `sandbox_root` is provided, the fs tools
are simply not registered (vs. registered with a silent loophole) — that is
intentional: **no sandbox, no write_file**.

Usage:

    from mindos.harness import ToolRegistry
    from mindos.harness.builtins import register_builtins

    reg = ToolRegistry()
    register_builtins(reg, mindos=m, sandbox_root="./scratch")
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

from mindos.harness.tools import ToolRegistry

log = logging.getLogger("mindos.harness.builtins")


# --- public API -----------------------------------------------------------

def register_builtins(
    registry: ToolRegistry,
    *,
    mindos: Optional[Any] = None,
    sandbox_root: Optional[str | Path] = None,
    allow: Optional[set[str]] = None,
) -> int:
    """Register built-in tools on `registry`. Returns number registered.

    - `mindos`: if given, `recall` and `commit` are wired to it.
    - `sandbox_root`: if given (must exist or be creatable), `read_file` and
      `write_file` are registered with a jail.
    - `allow`: optional allowlist of builtin names to register. If None, all
      eligible ones are registered.
    """
    want = lambda name: (allow is None) or (name in allow)
    count = 0

    if mindos is not None and want("recall"):
        _register_recall(registry, mindos)
        count += 1
    if mindos is not None and want("commit"):
        _register_commit(registry, mindos)
        count += 1

    if sandbox_root is not None:
        root = Path(sandbox_root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        if want("read_file"):
            _register_read_file(registry, root)
            count += 1
        if want("write_file"):
            _register_write_file(registry, root)
            count += 1

    return count


# --- recall ---------------------------------------------------------------

def _register_recall(registry: ToolRegistry, mindos: Any) -> None:
    def _handler(args: dict) -> dict:
        query = str(args.get("query") or "").strip()
        limit = _clamp_int(args.get("limit"), default=5, low=1, high=25)
        if not query:
            return {"ok": False, "error": "query is required"}
        rows = mindos.store.search_text(query, limit=limit) or []
        # MemoryStore may return Memory objects or dicts; normalize to dicts.
        hits = [_mem_to_dict(m) for m in rows]
        return {"ok": True, "query": query, "count": len(hits), "hits": hits}

    registry.register(
        name="recall",
        description=(
            "Search the user's personal memory store (MEMORY.md + FACTS.md) "
            "by free-text query. Returns top-k matches with content + type."
        ),
        handler=_handler,
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "Natural-language query."},
                "limit": {"type": "integer", "default": 5,
                          "description": "Max hits (1–25)."},
            },
            "required": ["query"],
        },
        source="builtin",
    )


# --- commit ---------------------------------------------------------------

def _register_commit(registry: ToolRegistry, mindos: Any) -> None:
    def _handler(args: dict) -> dict:
        content = str(args.get("content") or "").strip()
        if not content:
            return {"ok": False, "error": "content is required"}
        mtype = str(args.get("type") or "fact").strip().lower()
        if mtype not in {"fact", "episode", "preference", "relation",
                         "insight", "narrative", "skill"}:
            return {"ok": False, "error": f"unsupported memory type: {mtype}"}
        source = str(args.get("source") or "harness.builtin")
        # Avoid LLM pipeline — direct store write, deterministic.
        from mindos.store import Memory
        mem = Memory(id="", type=mtype, content=content,
                     source=source, confidence=1.0)
        mindos.store.add(mem)
        return {"ok": True, "type": mtype, "stored": content[:120]}

    registry.register(
        name="commit",
        description=(
            "Write one memory straight into the store (no LLM digest). "
            "Use when the user says something worth remembering."
        ),
        handler=_handler,
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string",
                            "description": "The memory text."},
                "type": {"type": "string", "default": "fact",
                         "enum": ["fact", "episode", "preference", "relation",
                                  "insight", "narrative", "skill"]},
                "source": {"type": "string", "default": "harness.builtin"},
            },
            "required": ["content"],
        },
        source="builtin",
    )


# --- read_file ------------------------------------------------------------

def _register_read_file(registry: ToolRegistry, root: Path) -> None:
    def _handler(args: dict) -> dict:
        rel = str(args.get("path") or "").strip()
        if not rel:
            return {"ok": False, "error": "path is required"}
        try:
            target = _resolve_in_sandbox(root, rel)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        if not target.exists():
            return {"ok": False, "error": f"not found: {rel}"}
        if not target.is_file():
            return {"ok": False, "error": f"not a file: {rel}"}
        try:
            data = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return {"ok": False, "error": "binary file; refuse to read"}
        # Cap at ~200KB so the model doesn't blow its context.
        if len(data) > 200_000:
            return {"ok": True, "path": rel, "truncated": True,
                    "content": data[:200_000]}
        return {"ok": True, "path": rel, "truncated": False, "content": data}

    registry.register(
        name="read_file",
        description=(
            f"Read a UTF-8 text file inside the sandbox ({root}). "
            "Paths are relative; `..` and absolute paths are rejected."
        ),
        handler=_handler,
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
        source="builtin",
    )


# --- write_file -----------------------------------------------------------

def _register_write_file(registry: ToolRegistry, root: Path) -> None:
    def _handler(args: dict) -> dict:
        rel = str(args.get("path") or "").strip()
        content = args.get("content")
        if not rel:
            return {"ok": False, "error": "path is required"}
        if not isinstance(content, str):
            return {"ok": False, "error": "content must be a string"}
        try:
            target = _resolve_in_sandbox(root, rel)
        except ValueError as e:
            return {"ok": False, "error": str(e)}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"ok": True, "path": rel, "bytes": len(content.encode("utf-8"))}

    registry.register(
        name="write_file",
        description=(
            f"Write a UTF-8 text file inside the sandbox ({root}). "
            "Creates parent dirs. Paths are relative; escapes are rejected."
        ),
        handler=_handler,
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
        source="builtin",
    )


# --- helpers --------------------------------------------------------------

def _resolve_in_sandbox(root: Path, rel: str) -> Path:
    """Join `rel` onto `root` and refuse anything that escapes.

    Uses `os.path.commonpath` on resolved paths — symlinks get resolved, so
    a symlink pointing outside the jail will also be rejected.
    """
    if os.path.isabs(rel):
        raise ValueError("absolute paths not allowed")
    candidate = (root / rel).resolve()
    try:
        common = Path(os.path.commonpath([str(root), str(candidate)]))
    except ValueError:  # different drives on Windows
        raise ValueError("path outside sandbox")
    if common != root:
        raise ValueError("path outside sandbox")
    return candidate


def _mem_to_dict(m: Any) -> dict:
    if isinstance(m, dict):
        return {k: m.get(k) for k in ("id", "type", "content", "source", "confidence")}
    return {
        "id": getattr(m, "id", None),
        "type": getattr(m, "type", None),
        "content": getattr(m, "content", None),
        "source": getattr(m, "source", None),
        "confidence": getattr(m, "confidence", None),
    }


def _clamp_int(val: Any, *, default: int, low: int, high: int) -> int:
    try:
        n = int(val) if val is not None else default
    except (TypeError, ValueError):
        n = default
    return max(low, min(high, n))
