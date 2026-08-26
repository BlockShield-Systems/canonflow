#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types


PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
PROJECT_SLUG = "yd-when-paradise-glitches"
WORKFLOW = "P10G Canon Beat Sheet"
OPERATION = "controlled_second_beat_sheet_revision"

MODEL = "gemini-3.1-pro-preview"
TEMPERATURE = 0.15
MAXIMUM_OUTPUT_TOKENS = 65_536
REQUEST_TIMEOUT_MS = 3_600_000

PARENT_DRAFT_FILENAME = "19-canon-beat-sheet-revised-draft.md"
GENERATION_INPUT_FILENAME = "29-second-revision-generation-input.md"
ORIGINAL_RUNNER_FILENAME = (
    "29a-canon-beat-sheet-second-revision-runner.py"
)

OUTPUT_FILENAME = "30-canon-beat-sheet-second-revised-draft.md"
SUMMARY_FILENAME = "31-second-revision-summary.json"

EXPECTED_PARENT_DRAFT_SHA256 = (
    "5e5db9a12e4f87dfa457be414fcc3b14f6ac565ff5e71a3b40ca4c8a3e89c6d0"
)
EXPECTED_PARENT_RUN_ID = (
    "ad024e98-f8b0-495b-be64-0fe9d408f1f0"
)

END_MARKER = "P10G CANON BEAT SHEET SECOND REVISED DRAFT END"

PARTS = {
    1: (1, 11),
    2: (12, 22),
    3: (23, 33),
    4: (34, 44),
}

PART_FILENAMES = {
    1: "30a-second-revision-part-01-beats-001-011.md",
    2: "30b-second-revision-part-02-beats-012-022.md",
    3: "30c-second-revision-part-03-beats-023-033.md",
    4: "30d-second-revision-part-04-beats-034-044.md",
}

PART_METADATA_FILENAMES = {
    1: "31a-second-revision-part-01.json",
    2: "31b-second-revision-part-02.json",
    3: "31c-second-revision-part-03.json",
    4: "31d-second-revision-part-04.json",
}

PART_SYSTEM_INSTRUCTION = """
You are generating exactly one controlled partial replacement package for the
P10G Canon Beat Sheet for the feature film Y.D. When Paradise Glitches.

Return only the requested partial Markdown document. Do not return the complete
44-beat document. Do not add analysis, explanation, preamble, apology, JSON,
Markdown code fences, or an end marker.

The multipart instruction in the final section of the user message overrides
any embedded instruction asking for one complete document.

Preserve exactly:
- only the explicitly assigned ordered P10G Beat IDs;
- every top-level numbered section heading present in the supplied structural
  template, in the same order and with the same section number;
- all sixteen required fields exactly once in every assigned beat;
- the structural placement and continuity represented by the template.

Apply all embedded human-review authority, Canon Decisions, correction
findings, Story Bible facts, and detailed creative direction relevant to the
assigned Beats.

Write a complete, detailed feature-film Beat Sheet segment. The segment must
be at least as long as its supplied structural template. It remains pending
strict local validation, deterministic assembly, and final human approval.
""".strip()


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_required(path: Path) -> str:
    if not path.is_file():
        raise RuntimeError(f"Required file is absent: {path.name}")

    text = path.read_text(encoding="utf-8")

    if not text.strip():
        raise RuntimeError(f"Required file is empty: {path.name}")

    return text


def load_original_runner(root: Path):
    path = root / ORIGINAL_RUNNER_FILENAME

    if not path.is_file():
        raise RuntimeError(
            f"Original validator runner is absent: {path.name}"
        )

    spec = importlib.util.spec_from_file_location(
        "p10g_original_second_revision_runner",
        path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load original P10G runner")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def remove_end_markers(text: str) -> str:
    lines = []

    for line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        if re.fullmatch(
            r"\s*P10G CANON BEAT SHEET(?: SECOND)? REVISED DRAFT END\s*",
            line,
            flags=re.IGNORECASE,
        ):
            continue

        lines.append(line)

    return "\n".join(lines).strip()


def beat_position(text: str, beat_number: int) -> int:
    beat_id = f"P10G-BEAT-{beat_number:03d}"
    match = re.search(
        rf"^##\s+{re.escape(beat_id)}\b",
        text,
        flags=re.MULTILINE,
    )

    if not match:
        raise RuntimeError(
            f"Parent draft is missing required heading: {beat_id}"
        )

    return match.start()


def calculate_part_boundaries(
    parent_draft: str,
) -> dict[int, tuple[int, int]]:
    starts: dict[int, int] = {1: 0}

    for part_number in (2, 3, 4):
        first_beat = PARTS[part_number][0]
        previous_beat = first_beat - 1

        previous_position = beat_position(
            parent_draft,
            previous_beat,
        )
        current_position = beat_position(
            parent_draft,
            first_beat,
        )

        section_matches = list(
            re.finditer(
                r"^#\s+\d+\.\s+.*$",
                parent_draft[previous_position:current_position],
                flags=re.MULTILINE,
            )
        )

        if section_matches:
            starts[part_number] = (
                previous_position + section_matches[0].start()
            )
        else:
            starts[part_number] = current_position

    boundaries = {}

    for part_number in (1, 2, 3, 4):
        start = starts[part_number]

        if part_number < 4:
            end = starts[part_number + 1]
        else:
            end = len(parent_draft)

        boundaries[part_number] = (start, end)

    return boundaries


def structural_template(
    parent_draft: str,
    part_number: int,
) -> str:
    boundaries = calculate_part_boundaries(parent_draft)
    start, end = boundaries[part_number]
    template = parent_draft[start:end].strip()

    if not template:
        raise RuntimeError(
            f"Structural template for part {part_number} is empty"
        )

    return template


def expected_beat_ids(part_number: int) -> list[str]:
    first, last = PARTS[part_number]

    return [
        f"P10G-BEAT-{number:03d}"
        for number in range(first, last + 1)
    ]


def section_numbers(text: str) -> list[str]:
    return re.findall(
        r"^#\s+(\d+)\.\s+",
        text,
        flags=re.MULTILINE,
    )


def section_headings(text: str) -> list[str]:
    return re.findall(
        r"^#\s+\d+\.\s+.*$",
        text,
        flags=re.MULTILINE,
    )


def validate_part(
    base: Any,
    text: str,
    template: str,
    part_number: int,
) -> dict[str, Any]:
    failures: list[str] = []

    expected_ids = expected_beat_ids(part_number)

    headings = re.findall(
        r"^##\s+(P10G-BEAT-\d{3})\b",
        text,
        flags=re.MULTILINE,
    )

    if headings != expected_ids:
        failures.append(
            "Beat headings do not match exact assigned range: "
            + ", ".join(expected_ids)
        )

    expected_sections = section_numbers(template)
    actual_sections = section_numbers(text)

    if actual_sections != expected_sections:
        failures.append(
            "Top-level section-number sequence differs from template: "
            f"expected {expected_sections}, got {actual_sections}"
        )

    if "```" in text:
        failures.append("Markdown code fence is present")

    if END_MARKER in text:
        failures.append(
            "Final assembled-document end marker is present in a part"
        )

    if re.search(
        r"P10G CANON BEAT SHEET(?: SECOND)? REVISED DRAFT END",
        text,
        flags=re.IGNORECASE,
    ):
        failures.append("A legacy or final end marker is present")

    if len(text) < len(template):
        failures.append(
            f"Part is shorter than its structural template: "
            f"{len(text)} < {len(template)}"
        )

    blocks = base.beat_blocks(text)

    if len(blocks) != len(expected_ids):
        failures.append(
            f"Expected {len(expected_ids)} Beat blocks, "
            f"found {len(blocks)}"
        )

    malformed: list[str] = []

    for beat_id, block in blocks:
        beat_failed = False

        for label in base.BEAT_FIELDS:
            count = base.field_occurrences(block, label)

            if count != 1:
                failures.append(
                    f"{beat_id}: field {label!r} occurs {count} times"
                )
                beat_failed = True

        if beat_failed:
            malformed.append(beat_id)

    if failures:
        raise RuntimeError(
            f"Multipart provider response {part_number} failed validation:\n- "
            + "\n- ".join(failures)
        )

    return {
        "part_number": part_number,
        "characters": len(text),
        "sha256": sha256_bytes(text.encode("utf-8")),
        "first_beat_id": headings[0],
        "last_beat_id": headings[-1],
        "beat_heading_count": len(headings),
        "numbered_section_count": len(actual_sections),
        "numbered_section_ids": actual_sections,
        "numbered_section_headings": section_headings(text),
        "beat_field_count": len(base.BEAT_FIELDS),
        "malformed_beat_blocks": malformed,
        "immediate_part_validation_passed": True,
    }


def assert_common_preflight(root: Path, base: Any) -> dict[str, Any]:
    preflight = base.assert_preflight(root)

    parent_path = root / PARENT_DRAFT_FILENAME
    input_path = root / GENERATION_INPUT_FILENAME

    parent_draft = remove_end_markers(read_required(parent_path))
    generation_input = read_required(input_path)

    parent_hash = sha256_file(parent_path)

    if parent_hash != EXPECTED_PARENT_DRAFT_SHA256:
        raise RuntimeError(
            "Parent revised draft SHA-256 mismatch: "
            f"{parent_hash}"
        )

    return {
        **preflight,
        "parent_draft": parent_draft,
        "generation_input": generation_input,
        "parent_sha256": parent_hash,
    }


def generate_part(root: Path, part_number: int) -> None:
    base = load_original_runner(root)
    preflight = assert_common_preflight(root, base)

    output_path = root / PART_FILENAMES[part_number]
    metadata_path = root / PART_METADATA_FILENAMES[part_number]

    if output_path.exists() or metadata_path.exists():
        raise RuntimeError(
            f"Refusing to overwrite multipart artifacts for part "
            f"{part_number}"
        )

    template = structural_template(
        preflight["parent_draft"],
        part_number,
    )

    first_beat, last_beat = PARTS[part_number]
    required_sections = section_headings(template)

    multipart_directive = f"""
# Binding Multipart Generation Directive

Generate only multipart package {part_number} of 4.

Required Beat range:
P10G-BEAT-{first_beat:03d} through P10G-BEAT-{last_beat:03d}

Return no Beat outside that range.

Required top-level section headings in this part, preserved in this order:
{json.dumps(required_sections, ensure_ascii=False, indent=2)}

Minimum characters for this part:
{len(template)}

Do not include any Beat Sheet end marker.

# Structural Template for Multipart Package {part_number}

{template}
""".strip()

    prompt = (
        preflight["generation_input"].rstrip()
        + "\n\n"
        + multipart_directive
        + "\n"
    )

    run_id = str(uuid.uuid4())
    started_at = utc_now()

    print(
        f"Starting controlled multipart package {part_number} of 4..."
    )
    print(
        f"Beat range: "
        f"P10G-BEAT-{first_beat:03d}..P10G-BEAT-{last_beat:03d}"
    )
    print(f"Minimum part characters: {len(template)}")
    print(f"Model: {MODEL}")
    print("AFC route: Chat.send_message_stream")
    print("Streaming: enabled")
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
            system_instruction=PART_SYSTEM_INSTRUCTION,
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

    if not isinstance(raw_text, str) or not raw_text.strip():
        raise RuntimeError(
            f"Provider returned no usable text for part {part_number}"
        )

    cleaned = base.clean_provider_text(raw_text)
    metrics = validate_part(
        base,
        cleaned,
        template,
        part_number,
    )

    output_path.write_text(
        cleaned.rstrip() + "\n",
        encoding="utf-8",
    )

    persisted_hash = sha256_file(output_path)

    expected_persisted_hash = sha256_bytes(
        (cleaned.rstrip() + "\n").encode("utf-8")
    )

    if persisted_hash != expected_persisted_hash:
        output_path.unlink(missing_ok=True)
        raise RuntimeError(
            f"Persisted SHA-256 mismatch for part {part_number}"
        )

    completed_at = utc_now()

    metadata = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "operation": OPERATION,
        "project_id": PROJECT_ID,
        "project_slug": PROJECT_SLUG,
        "multipart": True,
        "part_number": part_number,
        "part_count": 4,
        "part_run_id": run_id,
        "parent_revision_run_id": EXPECTED_PARENT_RUN_ID,
        "parent_revised_draft_sha256": (
            EXPECTED_PARENT_DRAFT_SHA256
        ),
        "model": MODEL,
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "transport": {
            "route": "Chat.send_message_stream",
            "streaming": True,
            "external_tools": False,
            "temperature": TEMPERATURE,
            "maximum_output_tokens": MAXIMUM_OUTPUT_TOKENS,
            "timeout_ms": REQUEST_TIMEOUT_MS,
        },
        "output": {
            "filename": output_path.name,
            **metrics,
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
        "status": "multipart_segment_generated_and_locally_validated",
    }

    metadata_path.write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Part Run ID: {run_id}")
    print(f"Part characters: {metrics['characters']}")
    print(f"Part Beat headings: {metrics['beat_heading_count']}")
    print(f"Part SHA-256: {persisted_hash}")
    print(
        f"P10G MULTIPART PACKAGE {part_number}: OK"
    )


def assemble(root: Path) -> None:
    base = load_original_runner(root)
    preflight = assert_common_preflight(root, base)

    output_path = root / OUTPUT_FILENAME
    summary_path = root / SUMMARY_FILENAME

    if output_path.exists() or summary_path.exists():
        raise RuntimeError(
            "Refusing to overwrite final second-revision artifacts"
        )

    part_texts: list[str] = []
    part_metadata: list[dict[str, Any]] = []

    for part_number in (1, 2, 3, 4):
        part_path = root / PART_FILENAMES[part_number]
        metadata_path = root / PART_METADATA_FILENAMES[part_number]

        part_text = remove_end_markers(read_required(part_path))
        metadata = json.loads(
            read_required(metadata_path)
        )

        template = structural_template(
            preflight["parent_draft"],
            part_number,
        )

        validate_part(
            base,
            part_text,
            template,
            part_number,
        )

        persisted_hash = sha256_file(part_path)

        if (
            metadata.get("output", {}).get("persisted_sha256")
            != persisted_hash
        ):
            raise RuntimeError(
                f"Part {part_number} metadata SHA-256 mismatch"
            )

        part_texts.append(part_text.strip())
        part_metadata.append(metadata)

    assembled = (
        "\n\n".join(part_texts).rstrip()
        + "\n\n"
        + END_MARKER
    )

    assembled = base.clean_provider_text(assembled)
    metrics = base.validate_candidate(assembled)

    persisted_bytes = assembled.encode("utf-8")
    persisted_hash = sha256_bytes(persisted_bytes)

    if persisted_hash != metrics["sha256"]:
        raise RuntimeError(
            "Assembled in-memory SHA-256 mismatch"
        )

    output_path.write_bytes(persisted_bytes)

    if sha256_file(output_path) != persisted_hash:
        output_path.unlink(missing_ok=True)
        raise RuntimeError(
            "Persisted assembled draft SHA-256 mismatch"
        )

    run_id = str(uuid.uuid4())
    completed_at = utc_now()

    started_values = [
        item["started_at_utc"]
        for item in part_metadata
    ]

    summary = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "operation": OPERATION,
        "project_id": PROJECT_ID,
        "project_slug": PROJECT_SLUG,
        "revision_run_id": run_id,
        "parent_revision_run_id": EXPECTED_PARENT_RUN_ID,
        "parent_revised_draft_sha256": (
            EXPECTED_PARENT_DRAFT_SHA256
        ),
        "model": MODEL,
        "started_at_utc": min(started_values),
        "completed_at_utc": completed_at,
        "transport": {
            "route": "Chat.send_message_stream",
            "direct_models_generate_content": False,
            "streaming": True,
            "external_tools": False,
            "temperature": TEMPERATURE,
            "maximum_output_tokens": MAXIMUM_OUTPUT_TOKENS,
            "timeout_ms": REQUEST_TIMEOUT_MS,
            "multipart": True,
            "part_count": 4,
        },
        "generation_input": {
            "filename": GENERATION_INPUT_FILENAME,
            "sha256": preflight["input_sha256"],
        },
        "multipart_parts": [
            {
                "part_number": item["part_number"],
                "part_run_id": item["part_run_id"],
                "filename": item["output"]["filename"],
                "sha256": item["output"]["persisted_sha256"],
                "characters": item["output"]["characters"],
                "first_beat_id": item["output"]["first_beat_id"],
                "last_beat_id": item["output"]["last_beat_id"],
            }
            for item in part_metadata
        ],
        "output": {
            "filename": OUTPUT_FILENAME,
            **metrics,
        },
        "controls": {
            "database_access": False,
            "database_mutation": False,
            "automatic_canon_release": False,
            "human_review_required": True,
            "strict_validation_required": True,
            "frozen_inputs_modified": False,
        },
        "status": "generated_strict_local_validation_pending",
    }

    try:
        summary_path.write_text(
            json.dumps(
                summary,
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    except Exception:
        output_path.unlink(missing_ok=True)
        raise

    print(f"Second Revision Run ID: {run_id}")
    print(f"Parent Revision Run ID: {EXPECTED_PARENT_RUN_ID}")
    print(f"Model: {MODEL}")
    print(f"Second Revised Draft characters: {metrics['characters']}")
    print(f"Second Revised Draft SHA-256: {metrics['sha256']}")
    print(f"Beat headings: {metrics['beat_heading_count']}")
    print(f"First Beat ID: {metrics['first_beat_id']}")
    print(f"Last Beat ID: {metrics['last_beat_id']}")
    print(f"Numbered sections: {metrics['numbered_section_count']}")
    print(
        "Canon decision references: "
        f"{metrics['canon_decision_references_found']}"
    )
    print("Multipart provider calls: 4")
    print("Database mutation: disabled")
    print("Automatic canon release: disabled")
    print("Human review required: True")
    print("P10G MULTIPART ASSEMBLY AND STRICT VALIDATION: OK")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    operation = parser.add_mutually_exclusive_group(
        required=True
    )

    operation.add_argument(
        "--part",
        type=int,
        choices=(1, 2, 3, 4),
    )

    operation.add_argument(
        "--assemble",
        action="store_true",
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    root = Path(__file__).resolve().parent

    if arguments.assemble:
        assemble(root)
    else:
        generate_part(root, arguments.part)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(
            "P10G multipart second revision process: FAILED",
            file=sys.stderr,
        )
        raise
    else:
        print(
            "P10G multipart second revision process: COMPLETED"
        )
