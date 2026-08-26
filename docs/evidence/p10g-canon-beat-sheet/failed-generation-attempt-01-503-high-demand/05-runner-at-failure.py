#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types


WORKFLOW = "P10G Canon Beat Sheet"
EXPECTED_MODEL = "gemini-3.1-pro-preview"

EXPECTED_STORY_BIBLE_SHA256 = (
    "b53c6e01afeb38abf91e8b523cd5237b9d9cf64a949bc0d02713aae05a1e655c"
)

EXPECTED_CANON_IDS = [
    f"YD-CANON-{number:04d}"
    for number in range(1, 7)
]

EXPECTED_SECTIONS = [
    "1. Authority, Scope, and Precedence",
    "2. Feature-Film Structural Overview",
    "3. Character and Relationship Arc Baseline",
    "4. Prologue",
    "5. Act 1 – Setup",
    "6. Inciting Incident",
    "7. Act 1 – Doll and Seismic Hammer Sequence",
    "8. First Act Turning Point",
    "9. Act 2A – Escalation and Dependency",
    "10. Midpoint",
    "11. Act 2B – Systemic Escalation",
    "12. Amusement Park of Illusions",
    "13. Transition into the Mirror Room",
    "14. Act 2 Crisis and Lowest Point",
    "15. Act 3 – Mirror Room and Final Confrontation",
    "16. Climax and Resolution",
    "17. Epilogue",
    "18. Demian Character Arc",
    "19. Y.D. Character and Voice Progression",
    "20. Corruption Mystery and Ambiguity Control",
    "21. Dialogue, Dark Humor, Satire, and Performance",
    "22. Source Traceability",
    "23. Canon Decision Compliance Matrix",
    "24. Open Questions and Non-Canon Proposals",
]

MINIMUM_CHARACTERS = 30_000
MINIMUM_BEAT_ENTRIES = 40
MAX_OUTPUT_TOKENS = 32_768
TEMPERATURE = 0.2

END_MARKER = "P10G CANON BEAT SHEET DRAFT END"

DRAFT_FILENAME = "06-canon-beat-sheet-draft.md"
SUMMARY_FILENAME = "07-canon-beat-sheet-generation-summary.json"


def abort(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def require_file(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        abort(f"Missing or empty input file: {path}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        abort(f"Invalid JSON file {path}: {error}")

    if not isinstance(value, dict):
        abort(f"Expected JSON object in {path}")

    return value


def normalize_finish_reason(value: Any) -> str | None:
    if value is None:
        return None

    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return str(enum_value)

    return str(value)


def usage_value(usage: Any, field: str) -> int | None:
    if usage is None:
        return None

    value = getattr(usage, field, None)

    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def atomic_write_text(path: Path, text: str) -> None:
    temporary_path = path.with_name(
        f".{path.name}.{uuid.uuid4().hex}.tmp"
    )

    try:
        temporary_path.write_text(text, encoding="utf-8")
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def atomic_write_json(
    path: Path,
    value: dict[str, Any],
) -> None:
    serialized = (
        json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    )
    atomic_write_text(path, serialized)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the P10G Canon Beat Sheet through "
            "Google Gen AI Chat.send_message."
        )
    )

    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Authoritative generation input Markdown",
    )

    parser.add_argument(
        "--contract",
        required=True,
        type=Path,
        help="Generation contract JSON",
    )

    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="P10G evidence directory",
    )

    parser.add_argument(
        "--model",
        required=True,
        help="Required Gemini model",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    input_path = args.input.expanduser().resolve()
    contract_path = args.contract.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    model = args.model.strip()

    require_file(input_path)
    require_file(contract_path)

    if not output_dir.is_dir():
        abort(f"Output directory does not exist: {output_dir}")

    if model != EXPECTED_MODEL:
        abort(
            "Unexpected model:\n"
            f"Actual:   {model}\n"
            f"Expected: {EXPECTED_MODEL}"
        )

    api_key = os.environ.get("GOOGLE_API_KEY", "")

    if len(api_key) < 20:
        abort(
            "GOOGLE_API_KEY is not exported or is unexpectedly short"
        )

    contract = load_json(contract_path)

    if contract.get("workflow") != WORKFLOW:
        abort("Unexpected contract workflow")

    if (
        contract.get("status")
        != "ready_for_afc_chat_generation"
    ):
        abort("Contract is not ready_for_afc_chat_generation")

    generation = contract.get("generation", {})
    afc = generation.get("automatic_function_calling", {})
    output_contract = contract.get("output", {})
    validation = contract.get("validation", {})

    if generation.get("model") != model:
        abort("Contract model does not match requested model")

    if generation.get("streaming") is not False:
        abort("Contract does not disable streaming")

    if generation.get("external_tools_enabled") is not False:
        abort("Contract does not disable external tools")

    if afc.get("required_transport") != "Chat.send_message":
        abort("Contract does not require Chat.send_message")

    if (
        afc.get("direct_models_generate_content_allowed")
        is not False
    ):
        abort("Contract permits direct Models.generate_content")

    if (
        afc.get("automatic_function_tools_configured")
        is not False
    ):
        abort("Contract unexpectedly configures function tools")

    if validation.get("database_mutation_allowed") is not False:
        abort("Contract permits database mutation")

    if validation.get("automatic_canon_release_allowed") is not False:
        abort("Contract permits automatic canon release")

    if validation.get("human_review_required") is not True:
        abort("Contract does not require human review")

    if output_contract.get("minimum_characters") != MINIMUM_CHARACTERS:
        abort("Unexpected minimum-character requirement")

    if (
        output_contract.get("minimum_beat_entries")
        != MINIMUM_BEAT_ENTRIES
    ):
        abort("Unexpected minimum beat-entry requirement")

    if (
        output_contract.get("required_sections")
        != EXPECTED_SECTIONS
    ):
        abort("Contract required sections do not match runner")

    if (
        output_contract.get("required_canon_decision_ids")
        != EXPECTED_CANON_IDS
    ):
        abort("Contract Canon Decision IDs do not match runner")

    if output_contract.get("end_marker") != END_MARKER:
        abort("Contract end marker does not match runner")

    authority = contract.get("input_authority", {})
    story_bible_authority = authority.get(
        "approved_story_bible",
        {},
    )

    if (
        story_bible_authority.get("sha256")
        != EXPECTED_STORY_BIBLE_SHA256
    ):
        abort("Unexpected approved Story Bible SHA-256")

    generation_input = input_path.read_text(encoding="utf-8")

    if len(generation_input) <= MINIMUM_CHARACTERS:
        abort(
            "Generation input is unexpectedly short: "
            f"{len(generation_input)} characters"
        )

    for decision_id in EXPECTED_CANON_IDS:
        if decision_id not in generation_input:
            abort(
                f"Generation input is missing {decision_id}"
            )

    for section in EXPECTED_SECTIONS:
        if section not in generation_input:
            abort(
                f"Generation input is missing section: {section}"
            )

    draft_path = output_dir / DRAFT_FILENAME
    summary_path = output_dir / SUMMARY_FILENAME

    for path in (draft_path, summary_path):
        if path.exists():
            abort(f"Refusing to overwrite existing output: {path}")

    run_id = str(uuid.uuid4())
    started_at = utc_now()

    generation_config = types.GenerateContentConfig(
        temperature=TEMPERATURE,
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    client = genai.Client(api_key=api_key)

    chat = client.chats.create(
        model=model,
        config=generation_config,
    )

    response = chat.send_message(generation_input)

    completed_at = utc_now()

    response_text = response.text

    if not isinstance(response_text, str):
        abort("Gemini response does not contain text")

    draft = response_text.strip()

    if len(draft) < MINIMUM_CHARACTERS:
        abort(
            "Generated Beat Sheet is too short:\n"
            f"Actual:   {len(draft)}\n"
            f"Required: {MINIMUM_CHARACTERS}"
        )

    if not draft.endswith(END_MARKER):
        abort(
            "Generated Beat Sheet does not end with the "
            "required marker"
        )

    missing_sections = [
        section
        for section in EXPECTED_SECTIONS
        if section not in draft
    ]

    if missing_sections:
        abort(
            "Generated Beat Sheet is missing required sections:\n"
            + "\n".join(missing_sections)
        )

    missing_canon_ids = [
        decision_id
        for decision_id in EXPECTED_CANON_IDS
        if decision_id not in draft
    ]

    if missing_canon_ids:
        abort(
            "Generated Beat Sheet is missing Canon Decision IDs:\n"
            + "\n".join(missing_canon_ids)
        )

    beat_ids = [
        f"P10G-BEAT-{number:03d}"
        for number in range(1, 1000)
        if f"P10G-BEAT-{number:03d}" in draft
    ]

    if len(beat_ids) < MINIMUM_BEAT_ENTRIES:
        abort(
            "Generated Beat Sheet contains too few unique beat IDs:\n"
            f"Actual:   {len(beat_ids)}\n"
            f"Required: {MINIMUM_BEAT_ENTRIES}"
        )

    expected_prefix = [
        f"P10G-BEAT-{number:03d}"
        for number in range(1, len(beat_ids) + 1)
    ]

    if beat_ids != expected_prefix:
        abort(
            "Generated Beat IDs are not a contiguous sequence "
            "starting with P10G-BEAT-001"
        )

    candidate = None

    if response.candidates:
        candidate = response.candidates[0]

    finish_reason = normalize_finish_reason(
        getattr(candidate, "finish_reason", None)
    )

    usage = getattr(response, "usage_metadata", None)

    draft_with_newline = draft + "\n"
    draft_sha256 = sha256_text(draft_with_newline)

    summary = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "status": "generated_awaiting_strict_validation",
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "model": model,
        "sdk": {
            "package": "google-genai",
            "version": version("google-genai"),
        },
        "transport": {
            "client": "genai.Client",
            "chat_creation": "client.chats.create",
            "message_method": "Chat.send_message",
            "automatic_function_calling_route": "chat",
            "direct_models_generate_content": False,
            "streaming": False,
            "external_tools": False,
        },
        "generation_config": {
            "temperature": TEMPERATURE,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        },
        "input": {
            "path": str(input_path),
            "sha256": sha256_file(input_path),
            "characters": len(generation_input),
            "contract_path": str(contract_path),
            "contract_sha256": sha256_file(contract_path),
            "approved_story_bible_sha256":
                EXPECTED_STORY_BIBLE_SHA256,
        },
        "output": {
            "path": str(draft_path),
            "sha256": draft_sha256,
            "characters": len(draft),
            "required_sections_found":
                len(EXPECTED_SECTIONS),
            "canon_decision_references_found":
                len(EXPECTED_CANON_IDS),
            "unique_beat_ids_found": len(beat_ids),
            "first_beat_id": beat_ids[0],
            "last_beat_id": beat_ids[-1],
            "end_marker_found": True,
        },
        "response": {
            "finish_reason": finish_reason,
            "prompt_token_count": usage_value(
                usage,
                "prompt_token_count",
            ),
            "candidates_token_count": usage_value(
                usage,
                "candidates_token_count",
            ),
            "total_token_count": usage_value(
                usage,
                "total_token_count",
            ),
        },
        "controls": {
            "database_access_performed": False,
            "database_mutation_performed": False,
            "automatic_canon_release_performed": False,
            "human_review_required": True,
        },
    }

    atomic_write_text(draft_path, draft_with_newline)
    atomic_write_json(summary_path, summary)

    if sha256_file(draft_path) != draft_sha256:
        abort("Written draft SHA-256 verification failed")

    print(f"Run ID: {run_id}")
    print(f"Model: {model}")
    print(f"Draft characters: {len(draft)}")
    print(f"Required sections: {len(EXPECTED_SECTIONS)}")
    print(f"Canon decision references: {len(EXPECTED_CANON_IDS)}")
    print(f"Unique beat IDs: {len(beat_ids)}")
    print(f"First beat ID: {beat_ids[0]}")
    print(f"Last beat ID: {beat_ids[-1]}")
    print(f"Draft: {draft_path}")
    print(f"Summary: {summary_path}")
    print("Transport: Chat.send_message")
    print("Direct Models.generate_content: disabled")
    print("Streaming: disabled")
    print("External tools: disabled")
    print("Database mutation: disabled")
    print("P10G CANON BEAT SHEET GENERATION: OK")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
