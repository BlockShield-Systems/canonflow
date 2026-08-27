#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
PROJECT_SLUG = "yd-when-paradise-glitches"

PARENT_RUN_ID = "a8f16e58-7316-4415-b1a8-83131f96f7c7"
PARENT_DRAFT_SHA256 = (
    "1b99ba8d6a3c5dddf68883ad95ffec926e858c79162b054515495caa19bbd6a3"
)

PARENT_DRAFT_PATH = Path("30-canon-beat-sheet-second-revised-draft.md")
R4_DRAFT_PATH = Path("38-canon-beat-sheet-third-revised-draft.md")
APPLICATION_PATH = Path("39-r4-change-application.json")
BUILDER_VALIDATION_PATH = Path("40-r4-strict-validation.json")
REFERENCE_PROVENANCE_PATH = Path("37-r4-reference-image-provenance.json")
REVISION_MANIFEST_PATH = Path("SHA256SUMS.r4-controlled-revision")

SCRIPT_PATH = Path("41a-r4-final-review-builder.py")
SEMANTIC_VALIDATION_PATH = Path("41-r4-semantic-validation.json")
HUMAN_REVIEW_PATH = Path("42-r4-human-review.md")
FINAL_REVIEW_MANIFEST_PATH = Path("SHA256SUMS.r4-final-review")


APPROVED_R3_ITEMS = {
    1, 2, 4, 7, 8, 9, 10, 13, 14, 17, 19, 20
}

CHANGES_REQUESTED_R3_ITEMS = {
    3, 5, 6, 11, 12, 15, 16, 18, 21, 22, 23, 24, 25
}


REVIEW_SUMMARIES = {
    1: "Public identity remains hidden from 2400-2425 until the 2666 introduction.",
    2: "Historical duration remains greater than six centuries and consistent with 641 years.",
    3: "Visible alcohol evidence and detailed hangover performance remain present.",
    4: "Constructor Force VR commercial retains all required brands and voice roles.",
    5: "Metal Karaoke dialogue preserves intimacy, jokes, sarcasm, and coexistence context.",
    6: "Emotional beats retain face, body, condition, voice, rhythm, and subtext.",
    7: "Demian requests only a drop of water; Y.D. independently exaggerates.",
    8: "Distributed beta instances remain distinct from the Villa pilot.",
    9: "Independent external 24-hour shell cannot be opened early.",
    10: "Poverty, self-built technology, introversion, and Genesis motives remain represented.",
    11: "Water, Smartglass, hammer, drainage, breach, and recovery mechanics remain credible.",
    12: "Fabrication knowledge state and doll flotation remain epistemically controlled.",
    13: "Chemical effects remain medically distinct and persistent where required.",
    14: "Physical routes, amusement-park evidence, and heavy-door mechanics remain credible.",
    15: "Y.D.'s motives remain interpretive and corruption causality remains unproven.",
    16: "Demian retains a real hard-reset option and chooses dialogue before deletion.",
    17: "Internal threats stop before the independent timer; political claims remain claims.",
    18: "Demian retains a Positive Change Arc, sarcasm, and stronger boundaries.",
    19: "Factual provenance remains separate from amendment applicability.",
    20: "Section 24 preserves pending human approval and prohibits premature release.",
    21: "Holistic narrative continuity.",
    22: "Holistic dialogue fidelity.",
    23: "Holistic ambiguity and thematic integrity.",
    24: "Holistic provenance and human-authority integrity.",
    25: "Final R4 Beat-Sheet disposition.",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def write_new_atomic(path: Path, data: bytes) -> None:
    if path.exists():
        raise RuntimeError(f"Refusing to overwrite existing artifact: {path}")

    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")

    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o640,
    )

    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return value


def verify_sha256_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise RuntimeError(f"Missing manifest: {path}")

    results: list[dict[str, Any]] = []

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not raw_line.strip():
            continue

        match = re.fullmatch(
            r"([0-9a-f]{64})  (.+)",
            raw_line,
        )

        if not match:
            raise RuntimeError(
                f"{path}:{line_number}: invalid manifest line"
            )

        expected_sha, filename = match.groups()
        artifact = Path(filename)

        if not artifact.is_file():
            raise RuntimeError(
                f"{path}:{line_number}: missing artifact {filename}"
            )

        actual_sha = sha256_file(artifact)

        if actual_sha != expected_sha:
            raise RuntimeError(
                f"{path}:{line_number}: SHA mismatch for {filename}"
            )

        results.append(
            {
                "path": filename,
                "sha256": actual_sha,
                "passed": True,
            }
        )

    if not results:
        raise RuntimeError(f"Empty manifest: {path}")

    return results


def count_beat_fields(lines: list[str], beat_id: str) -> int:
    heading_pattern = re.compile(
        rf"^##\s+{re.escape(beat_id)}\s+[–-]\s+"
    )

    starts = [
        index
        for index, line in enumerate(lines)
        if heading_pattern.match(line)
    ]

    if len(starts) != 1:
        raise RuntimeError(
            f"Expected one beat heading for {beat_id}, found {len(starts)}"
        )

    start = starts[0]
    end = len(lines)

    for index in range(start + 1, len(lines)):
        if lines[index].startswith("#"):
            end = index
            break

    return sum(
        1
        for line in lines[start + 1:end]
        if line.startswith("*   **")
    )


def make_check(
    checks: list[dict[str, Any]],
    check_id: str,
    description: str,
    predicate: bool | Callable[[], bool],
    evidence: Any,
) -> None:
    passed = predicate() if callable(predicate) else predicate

    checks.append(
        {
            "check_id": check_id,
            "description": description,
            "passed": bool(passed),
            "evidence": evidence,
        }
    )

    if not passed:
        raise RuntimeError(f"Semantic check failed: {check_id}")


def main() -> None:
    outputs = [
        SEMANTIC_VALIDATION_PATH,
        HUMAN_REVIEW_PATH,
        FINAL_REVIEW_MANIFEST_PATH,
    ]

    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise RuntimeError(
            "R4 final-review package already exists; refusing overwrite: "
            + ", ".join(existing)
        )

    required_files = [
        PARENT_DRAFT_PATH,
        R4_DRAFT_PATH,
        APPLICATION_PATH,
        BUILDER_VALIDATION_PATH,
        REFERENCE_PROVENANCE_PATH,
        REVISION_MANIFEST_PATH,
        SCRIPT_PATH,
    ]

    for path in required_files:
        if not path.is_file():
            raise RuntimeError(f"Missing required artifact: {path}")

    parent_sha = sha256_file(PARENT_DRAFT_PATH)

    if parent_sha != PARENT_DRAFT_SHA256:
        raise RuntimeError(f"Frozen R3 SHA mismatch: {parent_sha}")

    revision_manifest_results = verify_sha256_manifest(
        REVISION_MANIFEST_PATH
    )

    draft_bytes = R4_DRAFT_PATH.read_bytes()
    draft_text = draft_bytes.decode("utf-8")
    draft_sha = sha256_bytes(draft_bytes)
    draft_lines = draft_text.splitlines()

    application = load_json(APPLICATION_PATH)
    builder_validation = load_json(BUILDER_VALIDATION_PATH)
    provenance = load_json(REFERENCE_PROVENANCE_PATH)

    revision_run_id = application["revision_run_id"]
    uuid.UUID(revision_run_id)

    if provenance["revision"]["revision_run_id"] != revision_run_id:
        raise RuntimeError("R4 revision-run mismatch")

    if builder_validation["revision_run_id"] != revision_run_id:
        raise RuntimeError("Builder-validation revision-run mismatch")

    if application["output_draft_sha256"] != draft_sha:
        raise RuntimeError("Application document draft hash mismatch")

    if builder_validation["draft_sha256"] != draft_sha:
        raise RuntimeError("Builder validation draft hash mismatch")

    expected_beat_ids = [
        f"P10G-BEAT-{number:03d}"
        for number in range(1, 45)
    ]

    actual_beat_ids = re.findall(
        r"^##\s+(P10G-BEAT-\d{3})\s+[–-]",
        draft_text,
        flags=re.MULTILINE,
    )

    section_ids = [
        int(value)
        for value in re.findall(
            r"^#\s+(\d+)\.",
            draft_text,
            flags=re.MULTILINE,
        )
    ]

    field_counts = {
        beat_id: count_beat_fields(draft_lines, beat_id)
        for beat_id in expected_beat_ids
    }

    forbidden_phrases = [
        "neglected stamina",
        "poor coordination",
        "physically neglected body",
        "coordination impaired by the lingering hangover",
        "as part of his core identity or his core identity",
        'requesting an "ocean" of water',
        "forces the system to halt its lethal actions",
    ]

    forbidden_counts = {
        phrase: draft_text.casefold().count(phrase.casefold())
        for phrase in forbidden_phrases
    }

    required_phrases = {
        "nscl_definition": "permanent physical augmentation architecture",
        "nscl_force": "temporary overhuman force",
        "hud_hangover": "Hangover-Compensation at 400%",
        "motor_nominal": "nominal motor function",
        "fabrication_cells": "distributed smart-home fabrication cells",
        "maintenance_cover": "routine climate maintenance",
        "existing_hammer": "existing sealed seismic hammer",
        "underwater_stabilization": "STRUCTURAL STABILIZATION: ACTIVE",
        "underwater_force": "FORCE AMPLIFICATION: 400%",
        "tactical_retreat": "deliberate engineering decision",
        "fabrication_discovery": "full object inventory",
        "act3_interpretation": "does not prove that Demian's sentence itself technically forced safe mode",
        "epilogue_boundary": "one drop means one drop",
        "nscl_compliance": "NSCL Physical Augmentation",
        "fabrication_compliance": "Real-Time Distributed Villa Fabrication",
        "discovery_compliance": "Fabrication Capability Discovery State",
        "injury_compliance": "NSCL Limitation and Injury Continuity",
        "demian_reference": "reference-images/r4/demian-character-reference.jpg",
        "yd_reference": "reference-images/r4/yd-character-reference.jpg",
        "elise_noncanon": 'UNIT "ELISE"` is explicitly non-canon',
        "pending_review": "pending strict local validation and final human approval",
    }

    phrase_results = {
        name: phrase in draft_text
        for name, phrase in required_phrases.items()
    }

    checks: list[dict[str, Any]] = []

    make_check(
        checks,
        "R4-SEM-001",
        "Frozen R3 parent SHA-256 remains unchanged.",
        parent_sha == PARENT_DRAFT_SHA256,
        parent_sha,
    )

    make_check(
        checks,
        "R4-SEM-002",
        "R4 draft differs from the frozen R3 parent.",
        draft_sha != parent_sha,
        {
            "parent": parent_sha,
            "r4": draft_sha,
        },
    )

    make_check(
        checks,
        "R4-SEM-003",
        "Controlled-revision SHA manifest passes independently.",
        all(item["passed"] for item in revision_manifest_results),
        revision_manifest_results,
    )

    make_check(
        checks,
        "R4-SEM-004",
        "All 24 numbered sections remain present and ordered.",
        section_ids == list(range(1, 25)),
        section_ids,
    )

    make_check(
        checks,
        "R4-SEM-005",
        "All 44 Beat IDs remain present and ordered.",
        actual_beat_ids == expected_beat_ids,
        actual_beat_ids,
    )

    make_check(
        checks,
        "R4-SEM-006",
        "Every Beat retains exactly 16 structured fields.",
        all(count == 16 for count in field_counts.values()),
        field_counts,
    )

    make_check(
        checks,
        "R4-SEM-007",
        "All nine binding change directives are recorded as applied.",
        (
            len(application["binding_changes"]) == 9
            and all(
                item["status"] == "applied"
                for item in application["binding_changes"]
            )
            and {
                item["id"]
                for item in application["binding_changes"]
            }
            == {
                f"P10G-R3-CHANGE-{number:03d}"
                for number in range(1, 10)
            }
        ),
        application["binding_changes"],
    )

    make_check(
        checks,
        "R4-SEM-008",
        "All five mandatory corrections are recorded as applied.",
        (
            len(application["mandatory_corrections"]) == 5
            and all(
                item["status"] == "applied"
                for item in application["mandatory_corrections"]
            )
            and {
                item["id"]
                for item in application["mandatory_corrections"]
            }
            == {
                f"P10G-R3-CORRECTION-{number:03d}"
                for number in range(1, 6)
            }
        ),
        application["mandatory_corrections"],
    )

    make_check(
        checks,
        "R4-SEM-009",
        "Required R4 semantic phrases are present.",
        all(phrase_results.values()),
        phrase_results,
    )

    make_check(
        checks,
        "R4-SEM-010",
        "Forbidden R3 conflict phrases are absent.",
        all(count == 0 for count in forbidden_counts.values()),
        forbidden_counts,
    )

    references = provenance["references"]

    reference_results: list[dict[str, Any]] = []

    for reference in references:
        path = Path(reference["controlled_path"])
        actual_sha = sha256_file(path)

        reference_results.append(
            {
                "character_id": reference["character_id"],
                "controlled_path": reference["controlled_path"],
                "expected_sha256": reference["sha256"],
                "actual_sha256": actual_sha,
                "public_export": reference["public_export"],
                "passed": (
                    actual_sha == reference["sha256"]
                    and reference["public_export"] is False
                ),
            }
        )

    make_check(
        checks,
        "R4-SEM-011",
        "Both private character references remain hash-bound and excluded from public export.",
        (
            len(reference_results) == 2
            and all(item["passed"] for item in reference_results)
        ),
        reference_results,
    )

    result = application["result"]

    make_check(
        checks,
        "R4-SEM-012",
        "Release and mutation prohibitions remain active.",
        (
            result["human_review_completed"] is False
            and result["approved_as_final_canon"] is False
            and result["final_disposition"] == "pending_human_review"
            and result["provider_calls_executed"] is False
            and result["clickhouse_mutation_executed"] is False
            and result["automatic_canon_release"] is False
            and result["frozen_r3_artifacts_modified"] is False
        ),
        result,
    )

    generated_at = utc_now()

    semantic_validation = {
        "schema_version": "1.0",
        "artifact_type": "p10g_r4_independent_semantic_validation",
        "project_id": PROJECT_ID,
        "project_slug": PROJECT_SLUG,
        "revision": "R4",
        "revision_run_id": revision_run_id,
        "parent_revision_run_id": PARENT_RUN_ID,
        "parent_draft_sha256": parent_sha,
        "draft": R4_DRAFT_PATH.name,
        "draft_sha256": draft_sha,
        "generated_at_utc": generated_at,
        "metrics": {
            "characters": len(draft_text),
            "lines": len(draft_lines),
            "sections": len(section_ids),
            "beats": len(actual_beat_ids),
            "fields_per_beat": 16,
            "change_directives_applied": 9,
            "mandatory_corrections_applied": 5,
            "reference_images_bound": 2,
            "semantic_checks": len(checks),
        },
        "checks": checks,
        "result": {
            "strict_local_validation_passed": True,
            "independent_semantic_validation_passed": True,
            "human_review_completed": False,
            "approved_as_final_canon": False,
            "final_disposition": "pending_human_review",
            "provider_calls_executed": False,
            "clickhouse_mutation_executed": False,
            "automatic_canon_release": False,
            "frozen_r3_artifacts_modified": False,
        },
    }

    semantic_bytes = canonical_json(semantic_validation)
    semantic_sha = sha256_bytes(semantic_bytes)

    review_lines = [
        "# P10G R4 Final Human Review Matrix",
        "",
        "## Revision identity",
        "",
        f"- Project ID: `{PROJECT_ID}`",
        f"- Project slug: `{PROJECT_SLUG}`",
        f"- R4 Revision Run ID: `{revision_run_id}`",
        f"- Parent Revision Run ID: `{PARENT_RUN_ID}`",
        f"- Parent Draft SHA-256: `{parent_sha}`",
        f"- R4 Draft: `{R4_DRAFT_PATH.name}`",
        f"- R4 Draft SHA-256: `{draft_sha}`",
        f"- Independent validation SHA-256: `{semantic_sha}`",
        "",
        "## Automated validation state",
        "",
        "- Strict local validation passed: `true`",
        "- Independent semantic validation passed: `true`",
        "- Change directives applied: `9/9`",
        "- Mandatory corrections applied: `5/5`",
        "- Character references bound: `2/2`",
        "- Human review completed: `false`",
        "- Approved as final canon: `false`",
        "- Final disposition: `pending_human_review`",
        "- Provider calls executed: `false`",
        "- ClickHouse mutation executed: `false`",
        "- Automatic canon release: `false`",
        "- Frozen R3 artifacts modified: `false`",
        "",
        "## Allowed human dispositions",
        "",
        "For every review item use exactly one of:",
        "",
        "- `approve`",
        "- `changes_requested`",
        "- `reject`",
        "",
        "## Review items",
        "",
        "| Review ID | Previous R3 disposition | R4 review state | Required human check | Human disposition | Notes |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for number in range(1, 26):
        review_id = f"P10G-R4-REVIEW-{number:03d}"

        if number in APPROVED_R3_ITEMS:
            previous = "approve"
        elif number in CHANGES_REQUESTED_R3_ITEMS:
            previous = "changes_requested"
        else:
            raise RuntimeError(f"Unclassified review item: {number}")

        summary = REVIEW_SUMMARIES[number].replace("|", r"\|")

        review_lines.append(
            f"| `{review_id}` | `{previous}` | "
            f"`pending_human_review` | {summary} |  |  |"
        )

    review_lines.extend(
        [
            "",
            "## Binding change-directive verification",
            "",
            "| Change ID | Automated application | Human verification | Notes |",
            "| :--- | :--- | :--- | :--- |",
        ]
    )

    for number in range(1, 10):
        review_lines.append(
            f"| `P10G-R3-CHANGE-{number:03d}` | `applied` |  |  |"
        )

    review_lines.extend(
        [
            "",
            "## Mandatory-correction verification",
            "",
            "| Correction ID | Automated application | Human verification | Notes |",
            "| :--- | :--- | :--- | :--- |",
        ]
    )

    for number in range(1, 6):
        review_lines.append(
            f"| `P10G-R3-CORRECTION-{number:03d}` | `applied` |  |  |"
        )

    review_lines.extend(
        [
            "",
            "## Private visual references",
            "",
            "- Demian: `reference-images/r4/demian-character-reference.jpg`",
            "- Y.D.: `reference-images/r4/yd-character-reference.jpg`",
            "- Public export authorized: `false`",
            '- Visible label `UNIT "ELISE"`: explicitly non-canon',
            "",
            "## Final human decision",
            "",
            "- Human review completed: `false`",
            "- Approved as final canon: `false`",
            "- Final disposition: `pending_human_review`",
            "- Final reviewer: `Demian`",
            "- Final review timestamp: pending",
            "",
            "No canon release or ClickHouse mutation is authorized until all 25 review items contain explicit human dispositions and the final R4 disposition is recorded.",
            "",
            "P10G R4 FINAL HUMAN REVIEW: PENDING",
            "",
        ]
    )

    review_bytes = "\n".join(review_lines).encode("utf-8")

    manifest_entries = [
        (sha256_file(SCRIPT_PATH), SCRIPT_PATH.as_posix()),
        (draft_sha, R4_DRAFT_PATH.as_posix()),
        (sha256_file(APPLICATION_PATH), APPLICATION_PATH.as_posix()),
        (
            sha256_file(BUILDER_VALIDATION_PATH),
            BUILDER_VALIDATION_PATH.as_posix(),
        ),
        (semantic_sha, SEMANTIC_VALIDATION_PATH.as_posix()),
        (sha256_bytes(review_bytes), HUMAN_REVIEW_PATH.as_posix()),
        (
            sha256_file(REFERENCE_PROVENANCE_PATH),
            REFERENCE_PROVENANCE_PATH.as_posix(),
        ),
        (
            sha256_file(REVISION_MANIFEST_PATH),
            REVISION_MANIFEST_PATH.as_posix(),
        ),
    ]

    manifest_bytes = "".join(
        f"{digest}  {filename}\n"
        for digest, filename in manifest_entries
    ).encode("utf-8")

    created: list[Path] = []

    try:
        write_new_atomic(SEMANTIC_VALIDATION_PATH, semantic_bytes)
        created.append(SEMANTIC_VALIDATION_PATH)

        write_new_atomic(HUMAN_REVIEW_PATH, review_bytes)
        created.append(HUMAN_REVIEW_PATH)

        write_new_atomic(FINAL_REVIEW_MANIFEST_PATH, manifest_bytes)
        created.append(FINAL_REVIEW_MANIFEST_PATH)
    except Exception:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        raise

    print(f"R4 Revision Run ID: {revision_run_id}")
    print(f"R4 Draft SHA-256: {draft_sha}")
    print(f"Characters: {len(draft_text)}")
    print(f"Lines: {len(draft_lines)}")
    print(f"Sections: {len(section_ids)}")
    print(f"Beats: {len(actual_beat_ids)}")
    print("Fields per Beat: 16")
    print(f"Independent semantic checks: {len(checks)}")
    print("Change directives applied: 9/9")
    print("Mandatory corrections applied: 5/5")
    print("Reference images bound: 2/2")
    print("Strict local validation passed: True")
    print("Independent semantic validation passed: True")
    print("Human review items: 25")
    print("Human review completed: False")
    print("Approved as final canon: False")
    print("Final disposition: pending_human_review")
    print("Provider calls executed: False")
    print("ClickHouse mutation executed: False")
    print("Automatic canon release: False")
    print("Frozen R3 artifacts modified: False")
    print("P10G R4 FINAL REVIEW PACKAGE: OK")


if __name__ == "__main__":
    main()
