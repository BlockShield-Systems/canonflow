#!/usr/bin/env python3
"""Compile the deterministic offline Gemini request-descriptor package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AGENTS_ROOT = REPOSITORY_ROOT / "agents"

if str(AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTS_ROOT))

from canonflow_agent.gemini_direction_request_builder import (  # noqa: E402
    build_gemini_direction_request_package,
)


def parse_args(
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compile the deterministic offline Gemini Interactions API "
            "direction-request descriptor package. This command does not "
            "read credentials or perform provider/network calls."
        )
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New output directory; it must not already exist.",
    )
    parser.add_argument(
        "--repository-root",
        type=Path,
        default=REPOSITORY_ROOT,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        result = build_gemini_direction_request_package(
            args.output,
            repository_root=args.repository_root,
        )
    except (FileExistsError, ValueError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    summary = {
        **result,
        "output_path": str(args.output.resolve()),
        "credentials_environment_inspected": False,
        "credentials_read": False,
        "credentials_persisted": False,
        "client_initialized": False,
        "provider_calls": False,
        "http_requests": False,
        "network_access": False,
        "reference_images_transmitted": False,
        "media_generation_authorized": False,
        "media_generation_performed": False,
    }

    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
