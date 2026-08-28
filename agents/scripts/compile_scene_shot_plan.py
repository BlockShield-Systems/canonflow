#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AGENTS_ROOT = Path(__file__).resolve().parents[1]

if str(AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTS_ROOT))

from canonflow_agent.scene_shot_compiler import (  # noqa: E402
    SceneShotCompilerError,
    build_scene_shot_plan,
    write_scene_shot_plan,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compile frozen canon into an offline narrative-context and "
            "scene-shot planning contract."
        )
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        required=True,
        help="CanonFlow repository root.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Non-overwritable JSON output path.",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Write the compiled plan to standard output.",
    )

    args = parser.parse_args()

    if bool(args.output) == bool(args.stdout):
        parser.error("Specify exactly one of --output or --stdout.")

    return args


def main() -> int:
    args = parse_args()

    try:
        plan = build_scene_shot_plan(args.repository_root)

        if args.stdout:
            json.dump(
                plan,
                sys.stdout,
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            )
            sys.stdout.write("\n")
        else:
            write_scene_shot_plan(args.output, plan)

        return 0
    except (OSError, ValueError, SceneShotCompilerError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
