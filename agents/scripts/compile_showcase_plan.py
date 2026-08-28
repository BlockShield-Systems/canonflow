#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


AGENTS_ROOT = Path(__file__).resolve().parents[1]

if str(AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTS_ROOT))

from canonflow_agent.showcase_selector import (  # noqa: E402
    ShowcaseSelectionError,
    build_showcase_plan,
    write_showcase_plan,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compile the approved six-segment 600-second showcase plan "
            "without provider execution or media generation."
        )
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output",
        type=Path,
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
    )

    args = parser.parse_args()

    if bool(args.output) == bool(args.stdout):
        parser.error("Specify exactly one of --output or --stdout.")

    return args


def main() -> int:
    args = parse_args()

    try:
        plan = build_showcase_plan(args.repository_root)

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
            write_showcase_plan(args.output, plan)

        return 0
    except (
        OSError,
        ValueError,
        KeyError,
        ShowcaseSelectionError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
