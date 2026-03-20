from __future__ import annotations

import argparse
import sys
from pathlib import Path

from omnity_soap.validate import validate_action_file, validate_scene_file


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Validate SOAP JSON documents against v0.1 schemas.")
    parser.add_argument(
        "path",
        type=Path,
        help="Path to a SOAPScene .json or AgentAction .json",
    )
    parser.add_argument(
        "--kind",
        choices=("auto", "scene", "action"),
        default="auto",
        help="Document kind (default: infer from structure)",
    )
    args = parser.parse_args(argv)
    path = args.path.expanduser().resolve()
    if not path.is_file():
        print(f"error: not a file: {path}", file=sys.stderr)
        sys.exit(1)

    kind = args.kind
    if kind == "auto":
        data = path.read_text(encoding="utf-8")
        if '"space_id"' in data and '"objects"' in data:
            kind = "scene"
        elif '"verb"' in data and '"target_uri"' in data:
            kind = "action"
        else:
            print("error: could not infer --kind; specify --kind scene|action", file=sys.stderr)
            sys.exit(1)

    try:
        if kind == "scene":
            validate_scene_file(path)
        else:
            validate_action_file(path)
    except Exception as e:
        print(f"validation failed: {e}", file=sys.stderr)
        sys.exit(2)
    print(f"OK ({kind}): {path}")


if __name__ == "__main__":
    main()
