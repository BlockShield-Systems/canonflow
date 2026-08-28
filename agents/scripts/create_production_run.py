#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


AGENTS_ROOT = Path(__file__).resolve().parents[1]

if str(AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTS_ROOT))

from canonflow_agent.production_run import (
    PROFILE_SEGMENTS,
    SEGMENT_ORDER,
    ProductionRunError,
    build_production_run,
    write_production_run,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create an offline SHA-256-bound CanonFlow production run."
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
        required=True,
    )

    selection = parser.add_mutually_exclusive_group(
        required=True
    )
    selection.add_argument(
        "--profile",
        choices=tuple(PROFILE_SEGMENTS),
    )
    selection.add_argument(
        "--segment",
        action="append",
        choices=SEGMENT_ORDER,
        dest="segments",
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_args()

    try:
        production_run = build_production_run(
            arguments.repository_root,
            profile=arguments.profile,
            segments=arguments.segments,
        )
        write_production_run(
            arguments.output,
            production_run,
        )
    except (OSError, ProductionRunError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": production_run["status"],
                "contract_id": production_run["contract_id"],
                "production_run_id": (
                    production_run["production_run_id"]
                ),
                "selection_id": production_run["selection_id"],
                "selection": production_run["selection"]["name"],
                "segments": production_run["selection"]["segments"],
                "selected_beat_count": (
                    production_run["selection"][
                        "selected_beat_count"
                    ]
                ),
                "output": str(arguments.output.resolve()),
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
