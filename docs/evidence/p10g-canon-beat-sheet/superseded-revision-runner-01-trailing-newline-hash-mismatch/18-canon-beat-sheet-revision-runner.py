#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types


WORKFLOW = "P10G Canon Beat Sheet"
OPERATION = "controlled_beat_sheet_revision"
EXPECTED_MODEL = "gemini-3.1-pro-preview"

EXPECTED_STORY_BIBLE_SHA256 = (
    "b53c6e01afeb38abf91e8b523cd5237b9d9cf64a949bc0d02713aae05a1e655c"
)
EXPECTED_ORIGINAL_DRAFT_SHA256 = (
    "f31eb0a475100755e82676dde16d5075a044eea35f426d0e56eab71fcba7e1d8"
)
PARENT_GENERATION_RUN_ID = "002a27d3-a414-4a25-b21e-d3c924b2a391"

CONTRACT_FILENAME = "15-beat-sheet-revision-generation-contract.json"
REQUEST_FILENAME = "16-beat-sheet-revision-generation-request.md"
INPUT_FILENAME = "17-beat-sheet-revision-generation-input.md"

DRAFT_FILENAME = "19-canon-beat-sheet-revised-draft.md"
SUMMARY_FILENAME = "20-beat-sheet-revision-summary.json"

MINIMUM_CHARACTERS = 75_000
EXACT_BEAT_COUNT = 44
EXACT_NUMBERED_SECTIONS = 24
MAXIMUM_OUTPUT_TOKENS = 32_768
TEMPERATURE = 0.15
END_MARKER = "P10G CANON BEAT SHEET REVISED DRAFT END"

EXPECTED_BEAT_IDS = [
    f"P10G-BEAT-{number:03d}"
    for number in range(1, 45)
]
EXPECTED_CANON_IDS = [
    f"YD-CANON-{number:04d}"
    for number in range(1, 12)
]
BEAT_BODY_FIELDS = [
    "Act / structural position",
    "Sequence",
    "Narrative purpose",
    "Location",
    "Participating characters",
    "Action",
    "Conflict or pressure",
    "Emotional movement",
    "Reversal, reveal, or turn",
    "Demian knowledge state",
    "Y.D. state and voice stage",
    "Canon decision references",
    "Source references or verified locators",
    "Fact classification",
    "Continuity consequences",
    "Production or staging considerations",
]

SYSTEM_INSTRUCTION = """
You are performing a controlled revision of a feature-length Canon Beat Sheet.

Follow the authority precedence and revision requirements contained in the
provided input package. Return only the complete revised Markdown document.

Do not return analysis, commentary, a revision summary, XML, JSON, or Markdown
code fences. Do not use external tools. Do not access any database. Do not
claim that the result is approved canon. Human review remains mandatory.

Every required Beat ID must appear exactly once as a level-two Markdown
heading. Preserve the required structure, source traceability, knowledge-state
boundaries, Canon Decision references, and final end marker.
""".strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require_file(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Missing or empty required artifact: {path}")


def load_json(path: Path) -> dict[str, Any]:
    require_file(path)

    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")

    return payload


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )

    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def field_pattern(field: str) -> re.Pattern[str]:
    return re.compile(
        rf"^\s*[-*]\s+\*{{0,2}}{re.escape(field)}\*{{0,2}}\s*:",
        flags=re.MULTILINE | re.IGNORECASE,
    )


def extract_beat_blocks(
    text: str,
) -> list[tuple[str, str, str]]:
    heading_pattern = re.compile(
        r"^##\s+(P10G-BEAT-\d{3})\s+[–-]\s+(.+?)\s*$",
        flags=re.MULTILINE,
    )
    matches = list(heading_pattern.finditer(text))
    blocks: list[tuple[str, str, str]] = []

    for index, match in enumerate(matches):
        start = match.start()
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(text)
        )

        blocks.append(
            (
                match.group(1),
                match.group(2).strip(),
                text[start:end],
            )
        )

    return blocks


def validate_revised_draft(text: str) -> dict[str, Any]:
    failures: list[str] = []

    if len(text) < MINIMUM_CHARACTERS:
        failures.append(
            f"Draft has {len(text)} characters; "
            f"minimum is {MINIMUM_CHARACTERS}"
        )

    if not text.endswith(END_MARKER):
        failures.append("Required end marker is absent or not final")

    if text.startswith("```") or text.endswith("```"):
        failures.append("Markdown code fence detected around output")

    if re.search(r"^```", text, flags=re.MULTILINE):
        failures.append("Markdown code fences are forbidden")

    blocks = extract_beat_blocks(text)
    beat_ids = [beat_id for beat_id, _, _ in blocks]

    if len(blocks) != EXACT_BEAT_COUNT:
        failures.append(
            f"Found {len(blocks)} Beat headings; "
            f"expected {EXACT_BEAT_COUNT}"
        )

    if beat_ids != EXPECTED_BEAT_IDS:
        failures.append(
            "Beat headings are missing, duplicated, malformed, or out of order"
        )

    field_failures: dict[str, list[str]] = {}

    for beat_id, _, block in blocks:
        missing_fields = [
            field
            for field in BEAT_BODY_FIELDS
            if len(field_pattern(field).findall(block)) != 1
        ]

        if missing_fields:
            field_failures[beat_id] = missing_fields

    if field_failures:
        failures.append(
            "One or more Beat blocks do not contain every required field "
            "exactly once"
        )

    numbered_sections = re.findall(
        r"^#\s+\d+\.\s+.+$",
        text,
        flags=re.MULTILINE,
    )

    if len(numbered_sections) != EXACT_NUMBERED_SECTIONS:
        failures.append(
            f"Found {len(numbered_sections)} numbered top-level sections; "
            f"expected {EXACT_NUMBERED_SECTIONS}"
        )

    missing_canon_ids = [
        canon_id
        for canon_id in EXPECTED_CANON_IDS
        if canon_id not in text
    ]

    if missing_canon_ids:
        failures.append(
            "Missing Canon Decision references: "
            + ", ".join(missing_canon_ids)
        )

    required_literal_markers = [
        "2385",
        "2425",
        "2666",
        "281",
        "Neuro-Somatic Continuity Lattice",
        "The Long Build",
        "Green Force",
        "Rich Elite",
        "Poor Communities",
        "High-Tech-Future Force",
        "fractured dual-state AI entity",
    ]

    missing_markers = [
        marker
        for marker in required_literal_markers
        if marker.lower() not in text.lower()
    ]

    if missing_markers:
        failures.append(
            "Missing mandatory revision markers: "
            + ", ".join(missing_markers)
        )

    if not re.search(
        r"\bfirst-person\b|\bsubjective\b",
        text,
        flags=re.IGNORECASE,
    ):
        failures.append(
            "Controlled subjective first-person direction is absent"
        )

    if not (
        re.search(r"\brecover", text, flags=re.IGNORECASE)
        and re.search(
            r"\bseismic hammer\b",
            text,
            flags=re.IGNORECASE,
        )
        and re.search(r"\bdrag", text, flags=re.IGNORECASE)
    ):
        failures.append(
            "Seismic-hammer recovery and dragging continuity is absent"
        )

    forbidden_countdown_phrases = [
        "below two minutes",
        "under two minutes",
        "less than two minutes",
        "sub-two-minute",
    ]

    present_forbidden_countdown = [
        phrase
        for phrase in forbidden_countdown_phrases
        if phrase.lower() in text.lower()
    ]

    if present_forbidden_countdown:
        failures.append(
            "Physically implausible countdown wording remains: "
            + ", ".join(present_forbidden_countdown)
        )

    if re.search(
        r"\bschizophrenic AI entity\b",
        text,
        flags=re.IGNORECASE,
    ):
        failures.append("Forbidden AI terminology remains")

    if not re.search(
        r"\bambiguous\b|\bambiguity\b|"
        r"\bmultiple plausible causes\b",
        text,
        flags=re.IGNORECASE,
    ):
        failures.append("Corruption-cause ambiguity is not explicit")

    if not re.search(
        r"\bEpilogue\b",
        text,
        flags=re.IGNORECASE,
    ):
        failures.append("Required Epilogue is absent")

    if not re.search(
        r"\bopen ending\b|\bunresolved\b|"
        r"\bwithout being guaranteed\b|"
        r"\bno definitive answer\b",
        text,
        flags=re.IGNORECASE,
    ):
        failures.append(
            "Open philosophical ending is not sufficiently explicit"
        )

    if not re.search(
        r"human-approved-canon-amendment",
        text,
        flags=re.IGNORECASE,
    ):
        failures.append(
            "Human-approved amendment fact classification is absent"
        )

    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "characters": len(text),
        "beat_heading_count": len(blocks),
        "beat_ids": beat_ids,
        "first_beat_id": beat_ids[0] if beat_ids else None,
        "last_beat_id": beat_ids[-1] if beat_ids else None,
        "numbered_section_count": len(numbered_sections),
        "canon_decisions_found": [
            canon_id
            for canon_id in EXPECTED_CANON_IDS
            if canon_id in text
        ],
        "missing_canon_decisions": missing_canon_ids,
        "missing_mandatory_markers": missing_markers,
        "field_failures": field_failures,
        "end_marker_present": text.endswith(END_MARKER),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p10g", required=True)
    args = parser.parse_args()

    p10g = Path(args.p10g).expanduser().resolve()

    if not p10g.is_dir():
        raise RuntimeError(f"P10G directory not found: {p10g}")

    contract_path = p10g / CONTRACT_FILENAME
    request_path = p10g / REQUEST_FILENAME
    input_path = p10g / INPUT_FILENAME
    draft_path = p10g / DRAFT_FILENAME
    summary_path = p10g / SUMMARY_FILENAME

    for path in [
        contract_path,
        request_path,
        input_path,
    ]:
        require_file(path)

    existing_outputs = [
        path.name
        for path in [draft_path, summary_path]
        if path.exists()
    ]

    if existing_outputs:
        raise RuntimeError(
            "Refusing to overwrite existing revision output: "
            + ", ".join(existing_outputs)
        )

    api_key = os.environ.get("GOOGLE_API_KEY", "")

    if len(api_key) < 20:
        raise RuntimeError(
            "GOOGLE_API_KEY is missing or unexpectedly short"
        )

    configured_model = os.environ.get("CANONFLOW_MODEL", "")

    if configured_model != EXPECTED_MODEL:
        raise RuntimeError(
            f"CANONFLOW_MODEL must be {EXPECTED_MODEL}, "
            f"got {configured_model!r}"
        )

    contract = load_json(contract_path)

    if contract.get("workflow") != WORKFLOW:
        raise RuntimeError("Unexpected workflow")

    if contract.get("operation") != OPERATION:
        raise RuntimeError("Unexpected operation")

    if contract.get("status") != "ready_for_afc_chat_revision":
        raise RuntimeError("Unexpected contract status")

    if contract.get("model") != EXPECTED_MODEL:
        raise RuntimeError("Unexpected contract model")

    transport = contract.get("transport", {})

    if transport.get("route") != "Chat.send_message":
        raise RuntimeError("AFC Chat.send_message route is required")

    if transport.get("chat_required") is not True:
        raise RuntimeError("Chat transport must be required")

    if (
        transport.get("direct_models_generate_content_allowed")
        is not False
    ):
        raise RuntimeError("Direct model generation must remain disabled")

    if transport.get("streaming_allowed") is not False:
        raise RuntimeError("Streaming must remain disabled")

    if transport.get("external_tools_allowed") is not False:
        raise RuntimeError("External tools must remain disabled")

    controls = contract.get("controls", {})

    if controls.get("database_access_allowed") is not False:
        raise RuntimeError("Database access must remain disabled")

    if controls.get("database_mutation_allowed") is not False:
        raise RuntimeError("Database mutation must remain disabled")

    if controls.get("automatic_canon_release_allowed") is not False:
        raise RuntimeError("Automatic canon release must remain disabled")

    immutable_identity = contract.get(
        "immutable_input_identity",
        {},
    )

    if (
        immutable_identity.get("approved_story_bible_sha256")
        != EXPECTED_STORY_BIBLE_SHA256
    ):
        raise RuntimeError("Story Bible identity mismatch")

    if (
        immutable_identity.get("original_beat_sheet_sha256")
        != EXPECTED_ORIGINAL_DRAFT_SHA256
    ):
        raise RuntimeError("Original Beat Sheet identity mismatch")

    request_text = request_path.read_text(encoding="utf-8")
    input_text = input_path.read_text(encoding="utf-8")

    if len(input_text) < 100_000:
        raise RuntimeError("Revision input bundle is unexpectedly short")

    input_hashes_before = {
        path.name: sha256(path)
        for path in [contract_path, request_path, input_path]
    }

    revision_run_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc)

    client = genai.Client(api_key=api_key)

    chat = client.chats.create(
        model=EXPECTED_MODEL,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=TEMPERATURE,
            max_output_tokens=MAXIMUM_OUTPUT_TOKENS,
            response_mime_type="text/plain",
        ),
    )

    response = chat.send_message(input_text)

    if response is None or not getattr(response, "text", None):
        raise RuntimeError("Provider returned no textual revision")

    revised_text = response.text.strip()

    validation = validate_revised_draft(revised_text)

    if not validation["passed"]:
        failure_lines = "\n".join(
            f"- {failure}"
            for failure in validation["failures"]
        )

        raise RuntimeError(
            "Provider response failed immediate revision validation:\n"
            + failure_lines
        )

    input_hashes_after = {
        path.name: sha256(path)
        for path in [contract_path, request_path, input_path]
    }

    if input_hashes_after != input_hashes_before:
        raise RuntimeError(
            "One or more immutable revision inputs changed during generation"
        )

    completed_at = datetime.now(timezone.utc)
    draft_hash = sha256_text(revised_text)

    summary_payload = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "operation": OPERATION,
        "status": "revised_generated_awaiting_strict_validation",
        "revision_run_id": revision_run_id,
        "parent_generation_run_id": PARENT_GENERATION_RUN_ID,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_seconds": (
            completed_at - started_at
        ).total_seconds(),
        "model": EXPECTED_MODEL,
        "transport": {
            "client": "genai.Client",
            "route": "Chat.send_message",
            "direct_models_generate_content_used": False,
            "streaming_used": False,
            "external_tools_used": False,
        },
        "sampling": {
            "temperature": TEMPERATURE,
            "maximum_output_tokens": MAXIMUM_OUTPUT_TOKENS,
        },
        "input_identity": {
            "contract_filename": contract_path.name,
            "contract_sha256": input_hashes_before[contract_path.name],
            "request_filename": request_path.name,
            "request_sha256": input_hashes_before[request_path.name],
            "input_filename": input_path.name,
            "input_sha256": input_hashes_before[input_path.name],
            "approved_story_bible_sha256": (
                EXPECTED_STORY_BIBLE_SHA256
            ),
            "original_beat_sheet_sha256": (
                EXPECTED_ORIGINAL_DRAFT_SHA256
            ),
        },
        "output": {
            "filename": DRAFT_FILENAME,
            "sha256": draft_hash,
            "characters": validation["characters"],
            "beat_heading_count": validation["beat_heading_count"],
            "first_beat_id": validation["first_beat_id"],
            "last_beat_id": validation["last_beat_id"],
            "numbered_section_count": (
                validation["numbered_section_count"]
            ),
            "canon_decision_references_found": len(
                validation["canon_decisions_found"]
            ),
            "end_marker_present": validation["end_marker_present"],
        },
        "immediate_validation": validation,
        "controls": {
            "original_story_bible_modified": False,
            "original_beat_sheet_modified": False,
            "database_access_performed": False,
            "database_mutation_performed": False,
            "automatic_canon_release_performed": False,
            "strict_validation_required": True,
            "human_review_required": True,
        },
    }

    summary_text = (
        json.dumps(
            summary_payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )

    atomic_write_text(
        draft_path,
        revised_text + "\n",
    )

    try:
        atomic_write_text(
            summary_path,
            summary_text,
        )
    except BaseException:
        draft_path.unlink(missing_ok=True)
        raise

    print(f"Revision Run ID: {revision_run_id}")
    print(f"Parent Run ID: {PARENT_GENERATION_RUN_ID}")
    print(f"Model: {EXPECTED_MODEL}")
    print(f"Revised Draft characters: {validation['characters']}")
    print(f"Revised Draft SHA-256: {draft_hash}")
    print(f"Beat headings: {validation['beat_heading_count']}")
    print(f"First Beat ID: {validation['first_beat_id']}")
    print(f"Last Beat ID: {validation['last_beat_id']}")
    print(
        "Numbered sections: "
        f"{validation['numbered_section_count']}"
    )
    print(
        "Canon decision references: "
        f"{len(validation['canon_decisions_found'])}"
    )
    print("AFC route: Chat.send_message")
    print("Direct Models.generate_content: disabled")
    print("Streaming: disabled")
    print("External tools: disabled")
    print("Database mutation: disabled")
    print("Automatic canon release: disabled")
    print("Human review required: True")
    print("P10G CONTROLLED BEAT SHEET REVISION: OK")


if __name__ == "__main__":
    main()
