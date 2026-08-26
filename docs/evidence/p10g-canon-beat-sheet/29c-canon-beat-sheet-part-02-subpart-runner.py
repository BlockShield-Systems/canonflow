#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types


PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
PROJECT_SLUG = "yd-when-paradise-glitches"
MODEL = "gemini-3.1-pro-preview"
TEMPERATURE = 0.15
MAXIMUM_OUTPUT_TOKENS = 65_536
REQUEST_TIMEOUT_MS = 3_600_000

BASE_RUNNER_FILENAME = (
    "29b-canon-beat-sheet-multipart-runner.py"
)

FINAL_OUTPUT_FILENAME = (
    "30b-second-revision-part-02-beats-012-022.md"
)
FINAL_METADATA_FILENAME = (
    "31b-second-revision-part-02.json"
)

SUBPARTS: dict[str, dict[str, Any]] = {
    "2a": {
        "pseudo_part_number": 2,
        "first_beat": 12,
        "last_beat": 17,
        "output_filename": (
            "30b1-second-revision-subpart-02a-beats-012-017.md"
        ),
        "metadata_filename": (
            "31b1-second-revision-subpart-02a.json"
        ),
    },
    "2b": {
        "pseudo_part_number": 3,
        "first_beat": 18,
        "last_beat": 22,
        "output_filename": (
            "30b2-second-revision-subpart-02b-beats-018-022.md"
        ),
        "metadata_filename": (
            "31b2-second-revision-subpart-02b.json"
        ),
    },
}

PSEUDO_PARTS = {
    1: (1, 11),
    2: (12, 17),
    3: (18, 22),
    4: (23, 44),
}


def load_base_runner(root: Path) -> Any:
    path = root / BASE_RUNNER_FILENAME

    if not path.is_file():
        raise RuntimeError(
            f"Base multipart runner is absent: {path}"
        )

    specification = importlib.util.spec_from_file_location(
        "p10g_multipart_base",
        path,
    )

    if specification is None or specification.loader is None:
        raise RuntimeError(
            "Could not create base-runner import specification"
        )

    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)

    required = {
        "PARTS",
        "PART_SYSTEM_INSTRUCTION",
        "load_original_runner",
        "assert_common_preflight",
        "structural_template",
        "section_headings",
        "validate_part",
        "sha256_bytes",
        "sha256_file",
        "utc_now",
        "EXPECTED_PARENT_RUN_ID",
        "EXPECTED_PARENT_DRAFT_SHA256",
        "WORKFLOW",
        "OPERATION",
    }

    missing = sorted(
        name for name in required
        if not hasattr(module, name)
    )

    if missing:
        raise RuntimeError(
            "Base multipart runner contract is incomplete: "
            + ", ".join(missing)
        )

    return module


def configure_pseudo_parts(base_runner: Any) -> None:
    base_runner.PARTS = dict(PSEUDO_PARTS)


def generate_subpart(root: Path, subpart_id: str) -> None:
    configuration = SUBPARTS[subpart_id]
    base_runner = load_base_runner(root)

    if base_runner.PROJECT_ID != PROJECT_ID:
        raise RuntimeError("Base-runner PROJECT_ID mismatch")

    if base_runner.MODEL != MODEL:
        raise RuntimeError("Base-runner MODEL mismatch")

    if base_runner.MAXIMUM_OUTPUT_TOKENS != MAXIMUM_OUTPUT_TOKENS:
        raise RuntimeError(
            "Base-runner MAXIMUM_OUTPUT_TOKENS mismatch"
        )

    if base_runner.REQUEST_TIMEOUT_MS != REQUEST_TIMEOUT_MS:
        raise RuntimeError(
            "Base-runner REQUEST_TIMEOUT_MS mismatch"
        )

    original_runner = base_runner.load_original_runner(root)
    preflight = base_runner.assert_common_preflight(
        root,
        original_runner,
    )

    output_path = root / configuration["output_filename"]
    metadata_path = root / configuration["metadata_filename"]

    if output_path.exists() or metadata_path.exists():
        raise RuntimeError(
            f"Refusing to overwrite Subpart {subpart_id} artifacts"
        )

    configure_pseudo_parts(base_runner)

    pseudo_part_number = configuration["pseudo_part_number"]
    first_beat = configuration["first_beat"]
    last_beat = configuration["last_beat"]

    template = base_runner.structural_template(
        preflight["parent_draft"],
        pseudo_part_number,
    )

    expected_ids = [
        f"P10G-BEAT-{number:03d}"
        for number in range(first_beat, last_beat + 1)
    ]

    actual_template_ids = [
        beat_id
        for beat_id, _ in original_runner.beat_blocks(template)
    ]

    if actual_template_ids != expected_ids:
        raise RuntimeError(
            f"Subpart {subpart_id} template Beat range mismatch: "
            f"expected {expected_ids}, got {actual_template_ids}"
        )

    required_sections = base_runner.section_headings(template)

    multipart_directive = f"""
# Binding Part-02 Subdivision Directive

Generate only controlled Part-02 Subpart {subpart_id}.

This is a transport subdivision of multipart package 2 of 4.
It is not an independent final multipart package.

Required Beat range:
P10G-BEAT-{first_beat:03d} through P10G-BEAT-{last_beat:03d}

Return no Beat outside that range.

Required top-level section headings in this subpart, preserved in this order:
{json.dumps(required_sections, ensure_ascii=False, indent=2)}

Minimum characters for this subpart:
{len(template)}

Do not include any Beat Sheet end marker.

# Structural Template for Part-02 Subpart {subpart_id}

{template}
""".strip()

    prompt = (
        preflight["generation_input"].rstrip()
        + "\n\n"
        + multipart_directive
        + "\n"
    )

    run_id = str(uuid.uuid4())
    started_at = base_runner.utc_now()

    print(
        f"Starting controlled Part-02 Subpart {subpart_id}..."
    )
    print(
        f"Beat range: "
        f"P10G-BEAT-{first_beat:03d}.."
        f"P10G-BEAT-{last_beat:03d}"
    )
    print(f"Minimum subpart characters: {len(template)}")
    print(f"Model: {MODEL}")
    print("AFC route: Chat.send_message_stream")
    print("Streaming: enabled")
    print(f"Maximum output tokens: {MAXIMUM_OUTPUT_TOKENS}")
    print(f"Request timeout: {REQUEST_TIMEOUT_MS} ms")
    print("Database mutation: disabled")
    print("Automatic canon release: disabled")
    print("Human review required: True")

    client = genai.Client(
        api_key=preflight["api_key"],
        http_options=types.HttpOptions(
            timeout=REQUEST_TIMEOUT_MS,
        ),
    )

    chat = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=(
                base_runner.PART_SYSTEM_INSTRUCTION
            ),
            temperature=TEMPERATURE,
            max_output_tokens=MAXIMUM_OUTPUT_TOKENS,
        ),
    )

    response_chunks = chat.send_message_stream(prompt)
    response_text_chunks: list[str] = []

    for response_chunk in response_chunks:
        chunk_text = response_chunk.text

        if isinstance(chunk_text, str) and chunk_text:
            response_text_chunks.append(chunk_text)

    raw_text = "".join(response_text_chunks)

    if not raw_text.strip():
        raise RuntimeError(
            f"Provider returned no usable text for "
            f"Subpart {subpart_id}"
        )

    cleaned = original_runner.clean_provider_text(raw_text)

    metrics = base_runner.validate_part(
        original_runner,
        cleaned,
        template,
        pseudo_part_number,
    )

    validated_ids = [
        beat_id
        for beat_id, _ in original_runner.beat_blocks(cleaned)
    ]

    if validated_ids != expected_ids:
        raise RuntimeError(
            f"Validated Subpart {subpart_id} Beat range mismatch"
        )

    persisted_text = cleaned.rstrip() + "\n"
    output_path.write_text(
        persisted_text,
        encoding="utf-8",
    )

    persisted_hash = base_runner.sha256_file(output_path)
    expected_hash = base_runner.sha256_bytes(
        persisted_text.encode("utf-8")
    )

    if persisted_hash != expected_hash:
        output_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Persisted SHA-256 mismatch for "
            f"Subpart {subpart_id}"
        )

    completed_at = base_runner.utc_now()

    metadata = {
        "schema_version": 1,
        "workflow": base_runner.WORKFLOW,
        "operation": (
            "controlled_second_beat_sheet_revision_part_02_subpart"
        ),
        "project_id": PROJECT_ID,
        "project_slug": PROJECT_SLUG,
        "multipart": True,
        "parent_part_number": 2,
        "parent_part_count": 4,
        "subdivision": True,
        "subpart_id": subpart_id,
        "subpart_run_id": run_id,
        "parent_revision_run_id": (
            base_runner.EXPECTED_PARENT_RUN_ID
        ),
        "parent_revised_draft_sha256": (
            base_runner.EXPECTED_PARENT_DRAFT_SHA256
        ),
        "model": MODEL,
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "transport": {
            "route": "Chat.send_message_stream",
            "streaming": True,
            "external_tools": False,
            "temperature": TEMPERATURE,
            "maximum_output_tokens": (
                MAXIMUM_OUTPUT_TOKENS
            ),
            "timeout_ms": REQUEST_TIMEOUT_MS,
        },
        "output": {
            "filename": output_path.name,
            **metrics,
            "logical_first_beat_id": expected_ids[0],
            "logical_last_beat_id": expected_ids[-1],
            "logical_beat_ids": expected_ids,
            "persisted_sha256": persisted_hash,
        },
        "controls": {
            "database_access": False,
            "database_mutation": False,
            "automatic_canon_release": False,
            "human_review_required": True,
            "strict_validation_required": True,
            "frozen_inputs_modified": False,
        },
        "status": (
            "part_02_subpart_generated_and_locally_validated"
        ),
    }

    try:
        metadata_path.write_text(
            json.dumps(
                metadata,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    except Exception:
        output_path.unlink(missing_ok=True)
        raise

    print(f"Subpart Run ID: {run_id}")
    print(f"Subpart characters: {metrics['characters']}")
    print(
        f"Subpart Beat headings: "
        f"{metrics['beat_heading_count']}"
    )
    print(f"Subpart SHA-256: {persisted_hash}")
    print(f"P10G PART-02 SUBPART {subpart_id}: OK")


def verify_subpart(
    root: Path,
    base_runner: Any,
    subpart_id: str,
) -> tuple[str, dict[str, Any]]:
    configuration = SUBPARTS[subpart_id]

    output_path = root / configuration["output_filename"]
    metadata_path = root / configuration["metadata_filename"]

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise RuntimeError(
            f"Subpart {subpart_id} output is absent or empty"
        )

    if (
        not metadata_path.is_file()
        or metadata_path.stat().st_size == 0
    ):
        raise RuntimeError(
            f"Subpart {subpart_id} metadata is absent or empty"
        )

    text = output_path.read_text(encoding="utf-8")
    metadata = json.loads(
        metadata_path.read_text(encoding="utf-8")
    )

    expected_ids = [
        f"P10G-BEAT-{number:03d}"
        for number in range(
            configuration["first_beat"],
            configuration["last_beat"] + 1,
        )
    ]

    actual_ids = [
        beat_id
        for beat_id, _ in base_runner.beat_blocks(text)
    ]

    failures: list[str] = []

    if metadata.get("subpart_id") != subpart_id:
        failures.append("subpart_id")

    if metadata.get("parent_part_number") != 2:
        failures.append("parent_part_number")

    if actual_ids != expected_ids:
        failures.append("ordered Beat IDs")

    output_metadata = metadata.get("output", {})

    if output_metadata.get("persisted_sha256") != (
        base_runner.sha256_file(output_path)
    ):
        failures.append("persisted_sha256")

    if output_metadata.get(
        "immediate_part_validation_passed"
    ) is not True:
        failures.append("immediate_part_validation_passed")

    controls = metadata.get("controls", {})

    if controls.get("database_mutation") is not False:
        failures.append("database_mutation")

    if controls.get("automatic_canon_release") is not False:
        failures.append("automatic_canon_release")

    if failures:
        raise RuntimeError(
            f"Subpart {subpart_id} verification failed: "
            + ", ".join(failures)
        )

    return text, metadata


def merge_subparts(root: Path) -> None:
    base_runner = load_base_runner(root)
    original_runner = base_runner.load_original_runner(root)

    preflight = base_runner.assert_common_preflight(
        root,
        original_runner,
    )

    final_output_path = root / FINAL_OUTPUT_FILENAME
    final_metadata_path = root / FINAL_METADATA_FILENAME

    if final_output_path.exists() or final_metadata_path.exists():
        raise RuntimeError(
            "Refusing to overwrite final Part-02 artifacts"
        )

    text_2a, metadata_2a = verify_subpart(
        root,
        original_runner,
        "2a",
    )
    text_2b, metadata_2b = verify_subpart(
        root,
        original_runner,
        "2b",
    )

    base_runner.PARTS = {
        1: (1, 11),
        2: (12, 22),
        3: (23, 33),
        4: (34, 44),
    }

    full_template = base_runner.structural_template(
        preflight["parent_draft"],
        2,
    )

    assembled = (
        text_2a.rstrip()
        + "\n\n"
        + text_2b.lstrip()
    )

    cleaned = original_runner.clean_provider_text(assembled)

    metrics = base_runner.validate_part(
        original_runner,
        cleaned,
        full_template,
        2,
    )

    expected_ids = [
        f"P10G-BEAT-{number:03d}"
        for number in range(12, 23)
    ]

    actual_ids = [
        beat_id
        for beat_id, _ in original_runner.beat_blocks(cleaned)
    ]

    if actual_ids != expected_ids:
        raise RuntimeError(
            "Merged Part-02 Beat sequence is invalid"
        )

    persisted_text = cleaned.rstrip() + "\n"

    final_output_path.write_text(
        persisted_text,
        encoding="utf-8",
    )

    persisted_hash = base_runner.sha256_file(
        final_output_path
    )

    expected_hash = base_runner.sha256_bytes(
        persisted_text.encode("utf-8")
    )

    if persisted_hash != expected_hash:
        final_output_path.unlink(missing_ok=True)
        raise RuntimeError(
            "Merged Part-02 persisted SHA-256 mismatch"
        )

    merge_run_id = str(uuid.uuid4())
    completed_at = base_runner.utc_now()

    final_metadata = {
        "schema_version": 1,
        "workflow": base_runner.WORKFLOW,
        "operation": base_runner.OPERATION,
        "project_id": PROJECT_ID,
        "project_slug": PROJECT_SLUG,
        "multipart": True,
        "part_number": 2,
        "part_count": 4,
        "part_run_id": merge_run_id,
        "parent_revision_run_id": (
            base_runner.EXPECTED_PARENT_RUN_ID
        ),
        "parent_revised_draft_sha256": (
            base_runner.EXPECTED_PARENT_DRAFT_SHA256
        ),
        "model": MODEL,
        "started_at_utc": min(
            metadata_2a["started_at_utc"],
            metadata_2b["started_at_utc"],
        ),
        "completed_at_utc": completed_at,
        "transport": {
            "route": "Chat.send_message_stream",
            "streaming": True,
            "external_tools": False,
            "temperature": TEMPERATURE,
            "maximum_output_tokens": (
                MAXIMUM_OUTPUT_TOKENS
            ),
            "timeout_ms": REQUEST_TIMEOUT_MS,
            "subdivision": True,
            "provider_request_count": 2,
        },
        "output": {
            "filename": final_output_path.name,
            **metrics,
            "persisted_sha256": persisted_hash,
        },
        "subparts": [
            {
                "subpart_id": "2a",
                "run_id": metadata_2a["subpart_run_id"],
                "filename": (
                    SUBPARTS["2a"]["output_filename"]
                ),
                "sha256": metadata_2a["output"][
                    "persisted_sha256"
                ],
            },
            {
                "subpart_id": "2b",
                "run_id": metadata_2b["subpart_run_id"],
                "filename": (
                    SUBPARTS["2b"]["output_filename"]
                ),
                "sha256": metadata_2b["output"][
                    "persisted_sha256"
                ],
            },
        ],
        "controls": {
            "database_access": False,
            "database_mutation": False,
            "automatic_canon_release": False,
            "human_review_required": True,
            "strict_validation_required": True,
            "frozen_inputs_modified": False,
        },
        "status": (
            "multipart_segment_generated_subdivided_"
            "assembled_and_locally_validated"
        ),
    }

    try:
        final_metadata_path.write_text(
            json.dumps(
                final_metadata,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    except Exception:
        final_output_path.unlink(missing_ok=True)
        raise

    print(f"Part-02 Merge Run ID: {merge_run_id}")
    print(f"Part-02 characters: {metrics['characters']}")
    print(
        f"Part-02 Beat headings: "
        f"{metrics['beat_heading_count']}"
    )
    print(f"Part-02 SHA-256: {persisted_hash}")
    print("Provider requests represented: 2")
    print("Database mutation: False")
    print("Automatic canon release: False")
    print("P10G PART-02 SUBPART MERGE: OK")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    operation = parser.add_mutually_exclusive_group(
        required=True
    )

    operation.add_argument(
        "--subpart",
        choices=("2a", "2b"),
    )
    operation.add_argument(
        "--merge",
        action="store_true",
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    root = Path(__file__).resolve().parent

    if arguments.merge:
        merge_subparts(root)
    else:
        generate_subpart(root, arguments.subpart)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(
            "P10G Part-02 subdivision process: FAILED",
            file=sys.stderr,
        )
        raise
    else:
        print("P10G Part-02 subdivision process: COMPLETED")
