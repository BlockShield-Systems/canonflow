#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKFLOW = "P10G Canon Beat Sheet"

EXPECTED_RUN_ID = "002a27d3-a414-4a25-b21e-d3c924b2a391"

EXPECTED_DRAFT_SHA256 = (
    "f31eb0a475100755e82676dde16d5075a044eea35f426d0e56eab71fcba7e1d8"
)

EXPECTED_CANON_IDS = [
    f"YD-CANON-{number:04d}"
    for number in range(1, 7)
]

EXPECTED_BEAT_IDS = [
    f"P10G-BEAT-{number:03d}"
    for number in range(1, 45)
]

REQUIRED_SECTIONS = [
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

BEAT_FIELD_PATTERNS = {
    "Act / structural position": (
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
        r"Act\s*/\s*structural position(?:\*\*)?\s*:"
    ),
    "Sequence": (
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
        r"Sequence(?:\*\*)?\s*:"
    ),
    "Narrative purpose": (
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
        r"Narrative purpose(?:\*\*)?\s*:"
    ),
    "Location": (
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
        r"Location(?:\*\*)?\s*:"
    ),
    "Participating characters": (
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
        r"Participating characters(?:\*\*)?\s*:"
    ),
    "Action": (
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
        r"Action(?:\*\*)?\s*:"
    ),
    "Conflict or pressure": (
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
        r"Conflict or pressure(?:\*\*)?\s*:"
    ),
    "Emotional movement": (
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
        r"Emotional movement(?:\*\*)?\s*:"
    ),
    "Reversal, reveal, or turn": (
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
        r"Reversal,\s*reveal,\s*or turn(?:\*\*)?\s*:"
    ),
    "Demian knowledge state": (
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
        r"Demian knowledge state(?:\*\*)?\s*:"
    ),
    "Y.D. state and voice stage": (
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
        r"Y\.D\.\s*state and voice stage(?:\*\*)?\s*:"
    ),
    "Canon decision references": (
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
        r"Canon decision references(?:\*\*)?\s*:"
    ),
    "Source references or verified locators": (
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
        r"Source references or verified locators(?:\*\*)?\s*:"
    ),
    "Fact classification": (
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
        r"Fact classification(?:\*\*)?\s*:"
    ),
    "Continuity consequences": (
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
        r"Continuity consequences(?:\*\*)?\s*:"
    ),
    "Production or staging considerations": (
        r"(?im)^\s*(?:[-*]\s*)?(?:\*\*)?"
        r"Production or staging considerations(?:\*\*)?\s*:"
    ),
}

ALLOWED_CLASSIFICATIONS = [
    "canon-explicit",
    "source-supported",
    "canon-derived",
    "non-canon-proposal",
]

END_MARKER = "P10G CANON BEAT SHEET DRAFT END"


def abort(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    ).replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_file(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        abort(f"Missing or empty required file: {path}")


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        abort(f"Invalid JSON in {path}: {error}")

    if not isinstance(value, dict):
        abort(f"Expected JSON object in {path}")

    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def add_check(
    checks: list[dict[str, Any]],
    check_id: str,
    passed: bool,
    details: Any,
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "passed": bool(passed),
            "details": details,
        }
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the generated P10G Canon Beat Sheet"
    )

    parser.add_argument(
        "--p10g",
        required=True,
        type=Path,
        help="P10G evidence directory",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    p10g = args.p10g.expanduser().resolve()

    if not p10g.is_dir():
        abort(f"P10G directory does not exist: {p10g}")

    contract_path = (
        p10g / "02-canon-beat-sheet-generation-contract.json"
    )
    draft_path = p10g / "06-canon-beat-sheet-draft.md"
    summary_path = (
        p10g / "07-canon-beat-sheet-generation-summary.json"
    )
    validation_path = (
        p10g / "08-canon-beat-sheet-validation.json"
    )
    review_path = (
        p10g / "09-canon-beat-sheet-human-review.md"
    )
    log_path = p10g / "10-canon-beat-sheet-generation.log"

    for path in (
        contract_path,
        draft_path,
        summary_path,
        log_path,
    ):
        require_file(path)

    for path in (validation_path, review_path):
        if path.exists():
            abort(f"Refusing to overwrite existing output: {path}")

    contract = load_json(contract_path)
    summary = load_json(summary_path)
    draft = draft_path.read_text(encoding="utf-8")
    log_text = log_path.read_text(encoding="utf-8")

    draft_sha256 = sha256_file(draft_path)
    validated_at = utc_now()

    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "workflow_identity",
        contract.get("workflow") == WORKFLOW,
        contract.get("workflow"),
    )

    add_check(
        checks,
        "generation_run_id",
        summary.get("run_id") == EXPECTED_RUN_ID,
        summary.get("run_id"),
    )

    add_check(
        checks,
        "draft_sha256",
        draft_sha256 == EXPECTED_DRAFT_SHA256,
        {
            "actual": draft_sha256,
            "expected": EXPECTED_DRAFT_SHA256,
        },
    )

    add_check(
        checks,
        "summary_draft_sha256",
        summary.get("output", {}).get("sha256")
        == EXPECTED_DRAFT_SHA256,
        summary.get("output", {}).get("sha256"),
    )

    add_check(
        checks,
        "generation_status",
        summary.get("status")
        == "generated_awaiting_strict_validation",
        summary.get("status"),
    )

    add_check(
        checks,
        "generation_log_success_marker",
        "P10G CANON BEAT SHEET GENERATION: OK"
        in log_text,
        "success marker present",
    )

    transport = summary.get("transport", {})

    add_check(
        checks,
        "afc_chat_transport",
        (
            transport.get("message_method")
            == "Chat.send_message"
            and transport.get("direct_models_generate_content")
            is False
            and transport.get("streaming") is False
            and transport.get("external_tools") is False
        ),
        transport,
    )

    add_check(
        checks,
        "minimum_characters",
        len(draft.rstrip()) >= 30000,
        len(draft.rstrip()),
    )

    add_check(
        checks,
        "required_end_marker",
        draft.rstrip().endswith(END_MARKER),
        END_MARKER,
    )

    section_presence = {
        section: section in draft
        for section in REQUIRED_SECTIONS
    }

    add_check(
        checks,
        "required_sections",
        all(section_presence.values()),
        {
            "found": sum(section_presence.values()),
            "required": len(REQUIRED_SECTIONS),
            "missing": [
                section
                for section, present in section_presence.items()
                if not present
            ],
        },
    )

    beat_matches = list(
        re.finditer(r"\bP10G-BEAT-(\d{3})\b", draft)
    )

    actual_beat_ids = [
        f"P10G-BEAT-{match.group(1)}"
        for match in beat_matches
    ]

    add_check(
        checks,
        "beat_id_count",
        len(actual_beat_ids) == 44,
        len(actual_beat_ids),
    )

    add_check(
        checks,
        "beat_id_sequence",
        actual_beat_ids == EXPECTED_BEAT_IDS,
        {
            "first": (
                actual_beat_ids[0]
                if actual_beat_ids
                else None
            ),
            "last": (
                actual_beat_ids[-1]
                if actual_beat_ids
                else None
            ),
            "count": len(actual_beat_ids),
        },
    )

    beat_blocks: list[tuple[str, str]] = []

    if actual_beat_ids == EXPECTED_BEAT_IDS:
        for index, match in enumerate(beat_matches):
            start = match.start()
            end = (
                beat_matches[index + 1].start()
                if index + 1 < len(beat_matches)
                else len(draft)
            )

            beat_blocks.append(
                (
                    actual_beat_ids[index],
                    draft[start:end],
                )
            )

    field_global_counts = {
        field_name: len(re.findall(pattern, draft))
        for field_name, pattern in BEAT_FIELD_PATTERNS.items()
    }

    add_check(
        checks,
        "global_beat_field_counts",
        all(
            count == 44
            for count in field_global_counts.values()
        ),
        field_global_counts,
    )

    field_block_failures: list[dict[str, Any]] = []

    for beat_id, block in beat_blocks:
        for field_name, pattern in BEAT_FIELD_PATTERNS.items():
            count = len(re.findall(pattern, block))

            if count != 1:
                field_block_failures.append(
                    {
                        "beat_id": beat_id,
                        "field": field_name,
                        "count": count,
                    }
                )

    add_check(
        checks,
        "per_beat_field_completeness",
        (
            len(beat_blocks) == 44
            and not field_block_failures
        ),
        {
            "beat_blocks": len(beat_blocks),
            "failures": field_block_failures,
        },
    )

    classification_counts = {
        classification: len(
            re.findall(
                re.escape(classification),
                draft,
                flags=re.IGNORECASE,
            )
        )
        for classification in ALLOWED_CLASSIFICATIONS
    }

    classification_failures: list[str] = []

    for beat_id, block in beat_blocks:
        present = [
            classification
            for classification in ALLOWED_CLASSIFICATIONS
            if re.search(
                re.escape(classification),
                block,
                flags=re.IGNORECASE,
            )
        ]

        if not present:
            classification_failures.append(beat_id)

    add_check(
        checks,
        "fact_classifications",
        not classification_failures,
        {
            "counts": classification_counts,
            "beats_without_allowed_classification":
                classification_failures,
        },
    )

    canon_counts = {
        decision_id: len(
            re.findall(
                rf"\b{re.escape(decision_id)}\b",
                draft,
            )
        )
        for decision_id in EXPECTED_CANON_IDS
    }

    add_check(
        checks,
        "canon_decision_references",
        all(count > 0 for count in canon_counts.values()),
        canon_counts,
    )

    source_filename_matches = re.findall(
        r"(?i)[^`\n|]{1,180}\.(?:pdf|txt|md)",
        draft,
    )

    page_locator_matches = re.findall(
        r"(?i)\bpages?\s*(?::|#)?\s*\d+"
        r"(?:\s*[-–]\s*\d+)?",
        draft,
    )

    line_locator_matches = re.findall(
        r"(?i)\blines?\s*(?::|#)?\s*\d+"
        r"(?:\s*[-–]\s*\d+)?",
        draft,
    )

    add_check(
        checks,
        "source_filenames",
        len(source_filename_matches) > 0,
        len(source_filename_matches),
    )

    add_check(
        checks,
        "verified_source_locators",
        (
            len(page_locator_matches)
            + len(line_locator_matches)
            > 0
        ),
        {
            "page_locators": len(page_locator_matches),
            "line_locators": len(line_locator_matches),
        },
    )

    semantic_checks = {
        "feature_length": bool(
            re.search(r"(?i)\bfeature[- ]length\b", draft)
        ),
        "demian_age_40": bool(
            re.search(
                r"(?i)\bDemian\b.{0,100}\b40\b"
                r"|\b40(?:-year-old| years old)\b"
                r".{0,100}\bDemian\b",
                draft,
            )
        ),
        "doll_or_puppet": bool(
            re.search(r"(?i)\b(?:doll|puppet)\b", draft)
        ),
        "seismic_hammer": bool(
            re.search(r"(?i)\bseismic hammer\b", draft)
        ),
        "demian_limited_knowledge": bool(
            re.search(
                r"(?i)\bDemian\b.{0,240}"
                r"\b(?:does not know|doesn't know|unaware|"
                r"cannot know|can't know)\b",
                draft,
            )
        ),
        "amusement_park": (
            "Amusement Park of Illusions" in draft
        ),
        "mirror_room": bool(
            re.search(r"(?i)\bMirror Room\b", draft)
        ),
        "mirror_labyrinth": bool(
            re.search(
                r"(?i)\bmirror (?:maze|labyrinth)\b",
                draft,
            )
        ),
        "corruption_ambiguity": bool(
            re.search(
                r"(?i)\b(?:ambiguous|ambiguity|"
                r"multiple plausible causes)\b",
                draft,
            )
        ),
        "dark_humor": bool(
            re.search(r"(?i)\bdark humor\b", draft)
        ),
        "satire": bool(
            re.search(r"(?i)\bsatir(?:e|ical)\b", draft)
        ),
        "historical_timing_not_binding": bool(
            re.search(
                r"(?is)"
                r"(?:four[- ]second|4[- ]second)"
                r".{0,300}"
                r"(?:not binding|discard|non-binding|"
                r"must not constrain|does not constrain)",
                draft,
            )
        ),
    }

    add_check(
        checks,
        "mandatory_canon_semantics",
        all(semantic_checks.values()),
        semantic_checks,
    )

    first_person_present = bool(
        re.search(
            r"(?i)\b(?:first[- ]person|subjective camera|"
            r"subjective POV|POV)\b",
            draft,
        )
    )

    add_check(
        checks,
        "first_person_direction_baseline",
        True,
        {
            "present_in_generated_draft": first_person_present,
            "required_by_original_contract": False,
            "new_post_generation_proposal": True,
            "validation_effect": "informational_only",
        },
    )

    non_canon_proposal_count = classification_counts[
        "non-canon-proposal"
    ]

    add_check(
        checks,
        "non_canon_proposals_flagged",
        non_canon_proposal_count > 0,
        {
            "count": non_canon_proposal_count,
            "human_review_required": True,
        },
    )

    controls = summary.get("controls", {})

    add_check(
        checks,
        "generation_controls",
        (
            controls.get("database_access_performed")
            is False
            and controls.get("database_mutation_performed")
            is False
            and controls.get(
                "automatic_canon_release_performed"
            )
            is False
            and controls.get("human_review_required")
            is True
        ),
        controls,
    )

    failures = [
        check
        for check in checks
        if not check["passed"]
    ]

    status = (
        "passed_structural_awaiting_human_review"
        if not failures
        else "failed_structural_validation"
    )

    validation = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "status": status,
        "validated_at": validated_at,
        "project_id":
            "e8627781-5bf3-4c4d-905f-8dda49ab53d6",
        "project_slug": "yd-when-paradise-glitches",
        "generation_run_id": EXPECTED_RUN_ID,
        "validated_artifact": {
            "path": draft_path.name,
            "sha256": draft_sha256,
            "characters": len(draft.rstrip()),
        },
        "summary": {
            "check_count": len(checks),
            "failure_count": len(failures),
            "required_sections_found":
                sum(section_presence.values()),
            "required_sections_expected":
                len(REQUIRED_SECTIONS),
            "beat_count": len(actual_beat_ids),
            "first_beat_id": (
                actual_beat_ids[0]
                if actual_beat_ids
                else None
            ),
            "last_beat_id": (
                actual_beat_ids[-1]
                if actual_beat_ids
                else None
            ),
            "canon_decision_count":
                len(EXPECTED_CANON_IDS),
            "source_filename_matches":
                len(source_filename_matches),
            "page_locator_matches":
                len(page_locator_matches),
            "line_locator_matches":
                len(line_locator_matches),
            "non_canon_proposal_count":
                non_canon_proposal_count,
            "first_person_direction_present":
                first_person_present,
        },
        "checks": checks,
        "failures": failures,
        "human_authority": {
            "reviewer": "Demian",
            "draft_approved_as_canon": False,
            "human_review_required": True,
        },
        "controls": {
            "additional_model_call_performed": False,
            "database_access_performed": False,
            "database_mutation_performed": False,
            "automatic_canon_release_performed": False,
            "draft_modified": False,
        },
    }

    write_json(validation_path, validation)

    review_matrix = f"""# P10G Canon Beat Sheet – Human Review

## Review status

`pending_human_review`

## Reviewed artifact

- File: `{draft_path.name}`
- SHA-256: `{draft_sha256}`
- Generation run ID: `{EXPECTED_RUN_ID}`
- Structural validation: `{status}`
- Validation failures: `{len(failures)}`
- Beat entries: `{len(actual_beat_ids)}`
- Non-canon proposals detected: `{non_canon_proposal_count}`

## Allowed dispositions

Each review item must receive exactly one disposition:

- `approve`
- `reject`
- `needs_revision`
- `defer`

## Review items

### P10G-REVIEW-001 – Authority and precedence

Confirm that the Beat Sheet correctly treats the approved P10F Story Bible
as primary narrative authority and `YD-CANON-0001..0006` as hard constraints.

Disposition: `pending`

Notes:

### P10G-REVIEW-002 – Feature-film structure

Confirm that the 44 beats form a credible feature-length structure across
Prologue, Act 1, Act 2A, Midpoint, Act 2B, Act 3, and Epilogue without
compressing the project into the historical short runtime.

Disposition: `pending`

Notes:

### P10G-REVIEW-003 – Beat completeness and progression

Confirm that `P10G-BEAT-001..044` are narratively ordered, complete, and
sufficiently detailed for later scene and shot development.

Disposition: `pending`

Notes:

### P10G-REVIEW-004 – Demian character continuity

Confirm Demian's age, knowledge state, emotional progression, behavior, and
relationship arc remain consistent with the approved Story Bible.

Disposition: `pending`

Notes:

### P10G-REVIEW-005 – Y.D. character and voice progression

Confirm Y.D.'s technical role, relationship development, dialogue intent,
dark humor, satire, and voice progression remain correct.

Disposition: `pending`

Notes:

### P10G-REVIEW-006 – Doll and seismic-hammer event

Confirm Y.D. remains the actual originator or deployer while Demian does not
know this during the Act 1 event.

Disposition: `pending`

Notes:

### P10G-REVIEW-007 – Amusement Park of Illusions

Confirm the sequence functions as a major survival escape-room progression
through horror, traps, hallucination, motor impairment, and time pressure,
bridging Act 2B toward the Mirror Room.

Disposition: `pending`

Notes:

### P10G-REVIEW-008 – Mirror Room and final confrontation

Confirm the Mirror Room progression, confrontation, climax, and resolution
fit the approved character and relationship arcs.

Disposition: `pending`

Notes:

### P10G-REVIEW-009 – Corruption ambiguity

Confirm the Beat Sheet preserves multiple plausible causes for Y.D.'s
corruption and does not establish one cause as objective canon.

Disposition: `pending`

Notes:

### P10G-REVIEW-010 – Source traceability

Confirm source filenames, verified line or page locators, Canon Decision
references, and fact classifications provide sufficient traceability.

Disposition: `pending`

Notes:

### P10G-REVIEW-011 – Non-canon proposals

Review every item classified as `non-canon-proposal`. Approve only if each
proposal may be developed further without silently becoming established
story canon.

Detected proposal references: `{non_canon_proposal_count}`

Disposition: `pending`

Notes:

### P10G-REVIEW-012 – Subjective first-person visual language

Review the new post-generation creative-direction proposal:

Selected sequences may transition from objective third-person cinematography
into Demian-anchored subjective first-person perspective when his perception,
orientation, or motor control is destabilized.

Priority sequences:

- Amusement Park of Illusions
- mirror labyrinth
- transition into the Mirror Room

Constraints:

- transitions must be narratively motivated and temporally bounded;
- subjective imagery remains anchored to Demian's knowledge state;
- hallucinations must not be presented as confirmed objective reality;
- Y.D.'s internal intent must not be revealed as fact through Demian's POV;
- the cause of Y.D.'s corruption must remain ambiguous;
- the camera must return deliberately to objective perspective.

This direction is not present in the generated Beat Sheet and was not part of
the original P10G generation contract.

If disposition is `approve`, create controlled proposal `YD-CANON-0007` and
set final draft disposition to `needs_revision` until the direction has been
applied and reviewed.

Disposition: `pending`

Notes:

### P10G-REVIEW-013 – Final Beat Sheet disposition

Approve the final Beat Sheet only if review items `001–011` are approved and
no accepted post-generation direction still requires integration.

If `P10G-REVIEW-012=approve`, this item should currently be
`needs_revision`, because the First-Person direction is not yet present in
the generated artifact.

Disposition: `pending`

Notes:

## Current authority state

- Human reviewer: `Demian`
- Structural validation passed: `{str(not failures).lower()}`
- Human review completed: `false`
- Beat Sheet approved as canon: `false`
- Database mutation authorized: `false`
- Automatic canon release authorized: `false`
"""

    review_path.write_text(
        review_matrix.rstrip() + "\n",
        encoding="utf-8",
    )

    print(f"Validation checks: {len(checks)}")
    print(f"Validation failures: {len(failures)}")
    print(f"Draft characters: {len(draft.rstrip())}")
    print(f"Required sections: {sum(section_presence.values())}")
    print(f"Beat entries: {len(actual_beat_ids)}")
    print(f"Canon decision references: {len(EXPECTED_CANON_IDS)}")
    print(f"Source filename matches: {len(source_filename_matches)}")
    print(f"Page locator matches: {len(page_locator_matches)}")
    print(f"Line locator matches: {len(line_locator_matches)}")
    print(f"Non-canon proposals: {non_canon_proposal_count}")
    print(f"First-person direction present: {first_person_present}")
    print(f"Validation status: {status}")
    print(f"Validation report: {validation_path}")
    print(f"Human review matrix: {review_path}")

    if failures:
        for failure in failures:
            print(
                f"FAILED: {failure['check_id']} -> "
                f"{failure['details']}"
            )

        return 1

    print("Database mutation: False")
    print("Draft modified: False")
    print("P10G CANON BEAT SHEET VALIDATION: OK")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
