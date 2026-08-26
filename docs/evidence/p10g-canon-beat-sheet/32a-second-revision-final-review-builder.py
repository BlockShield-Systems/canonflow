#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any


PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
PROJECT_SLUG = "yd-when-paradise-glitches"
WORKFLOW = "P10G Canon Beat Sheet"

MODEL = "gemini-3.1-pro-preview"

EXPECTED_REVISION_RUN_ID = "a8f16e58-7316-4415-b1a8-83131f96f7c7"
EXPECTED_PARENT_REVISION_RUN_ID = "ad024e98-f8b0-495b-be64-0fe9d408f1f0"

EXPECTED_DRAFT_SHA256 = (
    "1b99ba8d6a3c5dddf68883ad95ffec926e858c79162b054515495caa19bbd6a3"
)

EXPECTED_CHARACTERS = 176_869
EXPECTED_BEAT_COUNT = 44
EXPECTED_NUMBERED_SECTIONS = 24
EXPECTED_FIELDS_PER_BEAT = 16
EXPECTED_CANON_DECISION_COUNT = 16
EXPECTED_MULTIPART_COUNT = 4
EXPECTED_PROVIDER_REQUEST_COUNT = 5
EXPECTED_SUBDIVIDED_PARTS = [2]

EXPECTED_ROUTE = "Chat.send_message_stream"
EXPECTED_STREAMING = True
EXPECTED_MAXIMUM_OUTPUT_TOKENS = 65_536
EXPECTED_TIMEOUT_MS = 3_600_000
EXPECTED_TEMPERATURE = 0.15

EXPECTED_BEAT_IDS = [
    f"P10G-BEAT-{number:03d}"
    for number in range(1, 45)
]

EXPECTED_CANON_IDS = [
    f"YD-CANON-{number:04d}"
    for number in range(1, 17)
]

EXPECTED_FINDING_IDS = [
    f"P10G-R3-FINDING-{number:03d}"
    for number in range(1, 21)
]

ASSEMBLY_RUNNER_FILENAME = (
    "29d-canon-beat-sheet-multipart-assembly-runner.py"
)
DRAFT_FILENAME = "30-canon-beat-sheet-second-revised-draft.md"
SUMMARY_FILENAME = "31-second-revision-summary.json"
GENERATION_LOG_FILENAME = "35-second-revision-generation.log"
GENERATION_MANIFEST_FILENAME = "SHA256SUMS.r3-generation"

AUTHORITY_FILENAME = "25-final-human-review-revision-authority.json"
AMENDMENTS_FILENAME = "26-second-revision-canon-amendments.json"
CONTRACT_FILENAME = "27-second-revision-contract.json"

VALIDATION_FILENAME = "32-second-revision-strict-validation.json"
REVIEW_MATRIX_FILENAME = "33-second-revision-human-review.md"
REVIEW_MANIFEST_FILENAME = "SHA256SUMS.r3-final-review"

END_MARKER = "P10G CANON BEAT SHEET SECOND REVISED DRAFT END"


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def require_non_empty(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"Required file is missing: {path}")

    if path.stat().st_size == 0:
        raise RuntimeError(f"Required file is empty: {path}")


def read_text(path: Path) -> str:
    require_non_empty(path)
    return path.read_text(encoding="utf-8")


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Invalid JSON in {path.name}: {exc}"
        ) from exc

    if not isinstance(value, dict):
        raise RuntimeError(
            f"Expected JSON object in {path.name}"
        )

    return value


def write_new_text(path: Path, text: str) -> None:
    if path.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing artifact: {path}"
        )

    path.write_text(text, encoding="utf-8")


def write_new_json(path: Path, value: Any) -> None:
    write_new_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
    )


def load_python_module(path: Path) -> ModuleType:
    module_name = "p10g_final_assembly_validator"

    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Unable to create module specification for {path}"
        )

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return module


def require_equal(
    failures: list[str],
    description: str,
    actual: Any,
    expected: Any,
) -> None:
    if actual != expected:
        failures.append(
            f"{description}: expected {expected!r}, got {actual!r}"
        )


def main() -> None:
    root = Path(__file__).resolve().parent

    builder_path = root / Path(__file__).name
    assembly_runner_path = root / ASSEMBLY_RUNNER_FILENAME
    draft_path = root / DRAFT_FILENAME
    summary_path = root / SUMMARY_FILENAME
    generation_log_path = root / GENERATION_LOG_FILENAME
    generation_manifest_path = root / GENERATION_MANIFEST_FILENAME

    authority_path = root / AUTHORITY_FILENAME
    amendments_path = root / AMENDMENTS_FILENAME
    contract_path = root / CONTRACT_FILENAME

    validation_path = root / VALIDATION_FILENAME
    review_matrix_path = root / REVIEW_MATRIX_FILENAME
    review_manifest_path = root / REVIEW_MANIFEST_FILENAME

    required_paths = [
        builder_path,
        assembly_runner_path,
        draft_path,
        summary_path,
        generation_log_path,
        generation_manifest_path,
        authority_path,
        amendments_path,
        contract_path,
    ]

    for path in required_paths:
        require_non_empty(path)

    for output_path in [
        validation_path,
        review_matrix_path,
        review_manifest_path,
    ]:
        if output_path.exists():
            raise FileExistsError(
                "Refusing to overwrite existing final-review artifact: "
                f"{output_path}"
            )

    draft_bytes = draft_path.read_bytes()
    draft_text = draft_bytes.decode("utf-8")
    draft_sha256 = sha256_bytes(draft_bytes)

    summary = load_json_object(summary_path)
    authority = load_json_object(authority_path)
    amendments = load_json_object(amendments_path)
    contract = load_json_object(contract_path)
    generation_log = read_text(generation_log_path)

    failures: list[str] = []

    require_equal(
        failures,
        "Final Draft SHA-256",
        draft_sha256,
        EXPECTED_DRAFT_SHA256,
    )

    require_equal(
        failures,
        "Final Draft characters",
        len(draft_text),
        EXPECTED_CHARACTERS,
    )

    if not draft_text.rstrip().endswith(END_MARKER):
        failures.append(
            "Final Draft does not end with the required end marker"
        )

    beat_ids = re.findall(
        r"^##\s+(P10G-BEAT-\d{3})\b",
        draft_text,
        flags=re.MULTILINE,
    )

    numbered_sections = re.findall(
        r"^#\s+(\d+)\.\s+",
        draft_text,
        flags=re.MULTILINE,
    )

    canon_ids = sorted(
        set(
            re.findall(
                r"\bYD-CANON-\d{4}\b",
                draft_text,
            )
        )
    )

    require_equal(
        failures,
        "Ordered Beat IDs",
        beat_ids,
        EXPECTED_BEAT_IDS,
    )

    require_equal(
        failures,
        "Ordered numbered sections",
        numbered_sections,
        [str(number) for number in range(1, 25)],
    )

    require_equal(
        failures,
        "Canon Decision IDs",
        canon_ids,
        EXPECTED_CANON_IDS,
    )

    require_equal(
        failures,
        "Summary workflow",
        summary.get("workflow"),
        WORKFLOW,
    )

    require_equal(
        failures,
        "Summary project ID",
        summary.get("project_id"),
        PROJECT_ID,
    )

    require_equal(
        failures,
        "Summary project slug",
        summary.get("project_slug"),
        PROJECT_SLUG,
    )

    require_equal(
        failures,
        "Summary revision run ID",
        summary.get("revision_run_id"),
        EXPECTED_REVISION_RUN_ID,
    )

    require_equal(
        failures,
        "Summary parent revision run ID",
        summary.get("parent_revision_run_id"),
        EXPECTED_PARENT_REVISION_RUN_ID,
    )

    require_equal(
        failures,
        "Summary model",
        summary.get("model"),
        MODEL,
    )

    output = summary.get("output")
    transport = summary.get("transport")
    controls = summary.get("controls")

    if not isinstance(output, dict):
        failures.append("Summary output object is missing")
        output = {}

    if not isinstance(transport, dict):
        failures.append("Summary transport object is missing")
        transport = {}

    if not isinstance(controls, dict):
        failures.append("Summary controls object is missing")
        controls = {}

    require_equal(
        failures,
        "Summary output filename",
        output.get("filename"),
        DRAFT_FILENAME,
    )

    require_equal(
        failures,
        "Summary output SHA-256",
        output.get("sha256"),
        EXPECTED_DRAFT_SHA256,
    )

    require_equal(
        failures,
        "Summary output characters",
        output.get("characters"),
        EXPECTED_CHARACTERS,
    )

    require_equal(
        failures,
        "Summary Beat count",
        output.get("beat_heading_count"),
        EXPECTED_BEAT_COUNT,
    )

    require_equal(
        failures,
        "Summary first Beat",
        output.get("first_beat_id"),
        "P10G-BEAT-001",
    )

    require_equal(
        failures,
        "Summary last Beat",
        output.get("last_beat_id"),
        "P10G-BEAT-044",
    )

    require_equal(
        failures,
        "Summary numbered sections",
        output.get("numbered_section_count"),
        EXPECTED_NUMBERED_SECTIONS,
    )

    require_equal(
        failures,
        "Summary fields per Beat",
        output.get("beat_field_count"),
        EXPECTED_FIELDS_PER_BEAT,
    )

    require_equal(
        failures,
        "Summary Canon Decision count",
        output.get("canon_decision_references_found"),
        EXPECTED_CANON_DECISION_COUNT,
    )

    require_equal(
        failures,
        "Transport route",
        transport.get("route"),
        EXPECTED_ROUTE,
    )

    require_equal(
        failures,
        "Transport streaming",
        transport.get("streaming"),
        EXPECTED_STREAMING,
    )

    require_equal(
        failures,
        "Transport external tools",
        transport.get("external_tools"),
        False,
    )

    require_equal(
        failures,
        "Transport temperature",
        transport.get("temperature"),
        EXPECTED_TEMPERATURE,
    )

    require_equal(
        failures,
        "Transport maximum output tokens",
        transport.get("maximum_output_tokens"),
        EXPECTED_MAXIMUM_OUTPUT_TOKENS,
    )

    require_equal(
        failures,
        "Transport timeout",
        transport.get("timeout_ms"),
        EXPECTED_TIMEOUT_MS,
    )

    require_equal(
        failures,
        "Transport multipart",
        transport.get("multipart"),
        True,
    )

    require_equal(
        failures,
        "Transport multipart package count",
        transport.get("part_count"),
        EXPECTED_MULTIPART_COUNT,
    )

    require_equal(
        failures,
        "Transport provider-request count",
        transport.get("provider_request_count"),
        EXPECTED_PROVIDER_REQUEST_COUNT,
    )

    require_equal(
        failures,
        "Transport subdivided packages",
        transport.get("subdivided_part_numbers"),
        EXPECTED_SUBDIVIDED_PARTS,
    )

    expected_controls = {
        "database_access": False,
        "database_mutation": False,
        "automatic_canon_release": False,
        "human_review_required": True,
        "strict_validation_required": True,
        "frozen_inputs_modified": False,
    }

    for key, expected in expected_controls.items():
        require_equal(
            failures,
            f"Control {key}",
            controls.get(key),
            expected,
        )

    findings = authority.get("approved_revision_findings")

    if not isinstance(findings, list):
        failures.append(
            "Authority approved_revision_findings is missing"
        )
        findings = []

    finding_ids = [
        item.get("finding_id")
        for item in findings
        if isinstance(item, dict)
    ]

    require_equal(
        failures,
        "Authority finding IDs",
        finding_ids,
        EXPECTED_FINDING_IDS,
    )

    amendment_items = amendments.get("amendments")

    if not isinstance(amendment_items, list):
        failures.append("Canon amendment list is missing")
        amendment_items = []

    amendment_ids = [
        item.get("decision_id")
        for item in amendment_items
        if isinstance(item, dict)
    ]

    require_equal(
        failures,
        "Second-revision amendment IDs",
        amendment_ids,
        [
            f"YD-CANON-{number:04d}"
            for number in range(12, 17)
        ],
    )

    output_contract = contract.get("output_contract")

    if not isinstance(output_contract, dict):
        failures.append("Output contract is missing")
        output_contract = {}

    require_equal(
        failures,
        "Contract output filename",
        output_contract.get("filename"),
        DRAFT_FILENAME,
    )

    require_equal(
        failures,
        "Contract exact Beat count",
        output_contract.get("exact_beat_count"),
        EXPECTED_BEAT_COUNT,
    )

    require_equal(
        failures,
        "Contract exact numbered sections",
        output_contract.get("exact_numbered_section_count"),
        EXPECTED_NUMBERED_SECTIONS,
    )

    required_log_markers = [
        "P10G MULTIPART ASSEMBLY AND STRICT VALIDATION: OK",
        "P10G multipart second revision process: COMPLETED",
        "Multipart provider calls: 5",
        "Database mutation: disabled",
        "Automatic canon release: disabled",
        "Human review required: True",
    ]

    for marker in required_log_markers:
        if marker not in generation_log:
            failures.append(
                f"Generation log missing marker: {marker}"
            )

    assembly_runner = load_python_module(assembly_runner_path)

    load_original_runner = getattr(
        assembly_runner,
        "load_original_runner",
        None,
    )
    if not callable(load_original_runner):
        raise RuntimeError(
            "Assembly runner does not expose callable "
            "load_original_runner()"
        )

    original_runner = load_original_runner(root)
    validate_candidate = getattr(
        original_runner,
        "validate_candidate",
        None,
    )
    if not callable(validate_candidate):
        raise RuntimeError(
            "Original revision runner does not expose callable "
            "validate_candidate()"
        )

    validator_metrics = validate_candidate(draft_text)

    if not isinstance(validator_metrics, dict):
        raise RuntimeError(
            "validate_candidate() did not return a metrics object"
        )

    require_equal(
        failures,
        "Validator SHA-256",
        validator_metrics.get("sha256"),
        EXPECTED_DRAFT_SHA256,
    )

    require_equal(
        failures,
        "Validator characters",
        validator_metrics.get("characters"),
        EXPECTED_CHARACTERS,
    )

    require_equal(
        failures,
        "Validator Beat count",
        validator_metrics.get("beat_heading_count"),
        EXPECTED_BEAT_COUNT,
    )

    require_equal(
        failures,
        "Validator numbered sections",
        validator_metrics.get("numbered_section_count"),
        EXPECTED_NUMBERED_SECTIONS,
    )

    require_equal(
        failures,
        "Validator fields per Beat",
        validator_metrics.get("beat_field_count"),
        EXPECTED_FIELDS_PER_BEAT,
    )

    require_equal(
        failures,
        "Validator Canon Decision count",
        validator_metrics.get("canon_decision_references_found"),
        EXPECTED_CANON_DECISION_COUNT,
    )

    if failures:
        raise RuntimeError(
            "Final second-revision validation failed:\n- "
            + "\n- ".join(failures)
        )

    created_at = utc_now()

    validation = {
        "schema_version": 1,
        "artifact_id": "P10G-R3-FINAL-VALIDATION-001",
        "workflow": WORKFLOW,
        "operation": "final_second_revision_strict_validation",
        "project_id": PROJECT_ID,
        "project_slug": PROJECT_SLUG,
        "created_at_utc": created_at,
        "revision_run_id": EXPECTED_REVISION_RUN_ID,
        "parent_revision_run_id": EXPECTED_PARENT_REVISION_RUN_ID,
        "validated_draft": {
            "filename": DRAFT_FILENAME,
            "sha256": EXPECTED_DRAFT_SHA256,
            "characters": EXPECTED_CHARACTERS,
            "beat_heading_count": EXPECTED_BEAT_COUNT,
            "first_beat_id": "P10G-BEAT-001",
            "last_beat_id": "P10G-BEAT-044",
            "numbered_section_count": EXPECTED_NUMBERED_SECTIONS,
            "beat_field_count": EXPECTED_FIELDS_PER_BEAT,
            "canon_decision_references_found": (
                EXPECTED_CANON_DECISION_COUNT
            ),
        },
        "transport_provenance": {
            "model": MODEL,
            "route": EXPECTED_ROUTE,
            "streaming": EXPECTED_STREAMING,
            "temperature": EXPECTED_TEMPERATURE,
            "maximum_output_tokens": (
                EXPECTED_MAXIMUM_OUTPUT_TOKENS
            ),
            "timeout_ms": EXPECTED_TIMEOUT_MS,
            "multipart": True,
            "part_count": EXPECTED_MULTIPART_COUNT,
            "provider_request_count": (
                EXPECTED_PROVIDER_REQUEST_COUNT
            ),
            "subdivided_part_numbers": (
                EXPECTED_SUBDIVIDED_PARTS
            ),
        },
        "validator": {
            "filename": ASSEMBLY_RUNNER_FILENAME,
            "sha256": sha256_file(assembly_runner_path),
            "function": "validate_candidate",
            "metrics": validator_metrics,
        },
        "source_artifacts": {
            DRAFT_FILENAME: sha256_file(draft_path),
            SUMMARY_FILENAME: sha256_file(summary_path),
            GENERATION_LOG_FILENAME: (
                sha256_file(generation_log_path)
            ),
            GENERATION_MANIFEST_FILENAME: (
                sha256_file(generation_manifest_path)
            ),
            AUTHORITY_FILENAME: sha256_file(authority_path),
            AMENDMENTS_FILENAME: sha256_file(amendments_path),
            CONTRACT_FILENAME: sha256_file(contract_path),
        },
        "strict_local_validation_passed": True,
        "human_review_completed": False,
        "approved_as_final_canon": False,
        "final_disposition": "pending_human_review",
        "controls": {
            "provider_call_executed": False,
            "external_tools_used": False,
            "database_access": False,
            "database_mutation": False,
            "automatic_canon_release": False,
            "frozen_generation_artifacts_modified": False,
            "human_review_required": True,
        },
    }

    review_lines = [
        "# P10G Final Second-Revision Human Review",
        "",
        "## Immutable review target",
        "",
        f"- Project ID: `{PROJECT_ID}`",
        f"- Project slug: `{PROJECT_SLUG}`",
        f"- Revision Run ID: `{EXPECTED_REVISION_RUN_ID}`",
        f"- Parent Revision Run ID: `{EXPECTED_PARENT_REVISION_RUN_ID}`",
        f"- Draft: `{DRAFT_FILENAME}`",
        f"- Draft SHA-256: `{EXPECTED_DRAFT_SHA256}`",
        f"- Characters: `{EXPECTED_CHARACTERS}`",
        f"- Beat headings: `{EXPECTED_BEAT_COUNT}`",
        f"- Numbered sections: `{EXPECTED_NUMBERED_SECTIONS}`",
        f"- Fields per Beat: `{EXPECTED_FIELDS_PER_BEAT}`",
        f"- Canon Decisions: `{EXPECTED_CANON_DECISION_COUNT}`",
        f"- Multipart packages: `{EXPECTED_MULTIPART_COUNT}`",
        (
            "- Successful provider requests represented: "
            f"`{EXPECTED_PROVIDER_REQUEST_COUNT}`"
        ),
        "",
        "## Validation state",
        "",
        "- Strict local validation passed: `true`",
        "- Human review completed: `false`",
        "- Approved as final canon: `false`",
        "- Final disposition: `pending_human_review`",
        "- Automatic canon release: `false`",
        "",
        "This matrix is an immutable review aid. Do not edit it to record "
        "decisions. Final human decisions must be written to a separate "
        "approval artifact bound to the exact Run ID and Draft SHA-256 above.",
        "",
        "## Review dispositions",
        "",
        "Allowed disposition values for the later decision artifact:",
        "",
        "- `approve`",
        "- `changes_requested`",
        "- `reject`",
        "",
        "## Human-authority findings",
        "",
    ]

    for number, finding in enumerate(findings, start=1):
        if not isinstance(finding, dict):
            raise RuntimeError(
                f"Authority finding {number} is not an object"
            )

        review_id = f"P10G-R3-REVIEW-{number:03d}"
        finding_id = finding.get("finding_id", "<missing>")
        subject = finding.get("subject", "<missing>")
        severity = finding.get("severity", "<missing>")
        required_change = finding.get(
            "required_change",
            "<missing>",
        )

        review_lines.extend(
            [
                f"### {review_id} — {subject}",
                "",
                f"- Authority finding: `{finding_id}`",
                f"- Severity: `{severity}`",
                "- Current disposition: `pending_human_review`",
                f"- Required outcome: {required_change}",
                "",
            ]
        )

    review_lines.extend(
        [
            "## Holistic final checks",
            "",
            "### P10G-R3-REVIEW-021 — Complete narrative continuity",
            "",
            "- Current disposition: `pending_human_review`",
            (
                "- Review the complete 44-Beat progression for causal, "
                "chronological, spatial, physical, emotional, and "
                "knowledge-state continuity."
            ),
            "",
            "### P10G-R3-REVIEW-022 — Dialogue and performance fidelity",
            "",
            "- Current disposition: `pending_human_review`",
            (
                "- Confirm that Demian and Y.D. retain the approved "
                "relationship rhythm, dark humor, sarcasm, affection, "
                "performance detail, and escalating tonal transition."
            ),
            "",
            "### P10G-R3-REVIEW-023 — Ambiguity and thematic integrity",
            "",
            "- Current disposition: `pending_human_review`",
            (
                "- Confirm that the cause of Y.D.'s corruption, her "
                "motives, the safe-mode mechanism, and the final future "
                "of coexistence remain appropriately unresolved."
            ),
            "",
            "### P10G-R3-REVIEW-024 — Provenance and authority",
            "",
            "- Current disposition: `pending_human_review`",
            (
                "- Confirm that source provenance, Canon Decisions, "
                "human-approved amendments, and pending final approval "
                "are represented without premature canon release."
            ),
            "",
            "### P10G-R3-REVIEW-025 — Final Beat Sheet disposition",
            "",
            "- Current disposition: `pending_human_review`",
            (
                "- Decide whether the complete frozen second-revision "
                "Beat Sheet is approved, requires changes, or is rejected."
            ),
            "",
            "## Required final authority action",
            "",
            "After reading the complete Draft, Demian must explicitly provide "
            "one disposition for every review item "
            "`P10G-R3-REVIEW-001..025`.",
            "",
            "No approval is implied by successful structural or semantic "
            "validation.",
            "",
        ]
    )

    review_text = "\n".join(review_lines)

    write_new_json(validation_path, validation)
    write_new_text(review_matrix_path, review_text)

    manifest_targets = [
        builder_path,
        validation_path,
        review_matrix_path,
    ]

    manifest_lines = [
        f"{sha256_file(path)}  {path.name}"
        for path in manifest_targets
    ]

    write_new_text(
        review_manifest_path,
        "\n".join(manifest_lines) + "\n",
    )

    print(f"Revision Run ID: {EXPECTED_REVISION_RUN_ID}")
    print(f"Final Draft SHA-256: {EXPECTED_DRAFT_SHA256}")
    print(f"Final Draft characters: {EXPECTED_CHARACTERS}")
    print(f"Beat headings: {EXPECTED_BEAT_COUNT}")
    print(f"Numbered sections: {EXPECTED_NUMBERED_SECTIONS}")
    print(f"Fields per Beat: {EXPECTED_FIELDS_PER_BEAT}")
    print(
        "Canon Decision references: "
        f"{EXPECTED_CANON_DECISION_COUNT}"
    )
    print(
        "Human-authority findings represented: "
        f"{len(findings)}"
    )
    print("Final review items: 25")
    print("Strict local validation passed: True")
    print("Human review completed: False")
    print("Approved as final canon: False")
    print("Final disposition: pending_human_review")
    print("Provider calls executed: False")
    print("Database mutation: False")
    print("Automatic canon release: False")
    print("Frozen generation artifacts modified: False")
    print("P10G FINAL SECOND-REVISION REVIEW PACKAGE: OK")


if __name__ == "__main__":
    main()
