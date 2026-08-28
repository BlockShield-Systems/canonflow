#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


AGENTS_ROOT = Path(__file__).resolve().parents[1]

if str(AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTS_ROOT))


from canonflow_agent.direction_package_builder import (  # noqa: E402
    DirectionPackageError,
    build_direction_package,
    serialized_sha256,
    write_direction_package,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compile the deterministic multipart Gemini direction-input "
            "package without provider execution, network access, reference-"
            "image transmission, or media generation."
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        package_files = build_direction_package(
            args.repository_root
        )
        write_direction_package(
            args.output,
            package_files,
        )

        global_contract = package_files[
            "00-global-contract.json"
        ]
        merge_manifest = package_files[
            "07-merge-manifest.json"
        ]

        summary = {
            "global_contract_id": global_contract[
                "global_contract_id"
            ],
            "merge_manifest_id": merge_manifest[
                "merge_manifest_id"
            ],
            "output_path": str(args.output.resolve()),
            "package_file_count": len(package_files),
            "segment_package_count": 6,
            "shot_direction_input_count": (
                merge_manifest["merge_contract"][
                    "expected_shot_direction_count"
                ]
            ),
            "narrative_runtime_seconds": (
                merge_manifest["merge_contract"][
                    "expected_narrative_runtime_seconds"
                ]
            ),
            "file_sha256s": {
                filename: serialized_sha256(value)
                for filename, value in sorted(
                    package_files.items()
                )
            },
            "provider_calls": False,
            "network_access": False,
            "reference_images_transmitted": False,
            "media_generation_authorized": False,
        }

        json.dump(
            summary,
            sys.stdout,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        sys.stdout.write("\n")
        return 0

    except (
        OSError,
        ValueError,
        KeyError,
        DirectionPackageError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
