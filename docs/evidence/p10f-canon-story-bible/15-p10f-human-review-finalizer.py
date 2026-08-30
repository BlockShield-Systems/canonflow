#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
PROJECT_SLUG = "yd-when-paradise-glitches"
WORKFLOW = "P10F Canon Story Bible"
GENERATION_RUN_ID = "7fb97e75-acaf-4074-b3b3-4521d0ffbc35"

REVIEWER = "Demian"
EXPECTED_DRAFT_SHA256 = (
    "b53c6e01afeb38abf91e8b523cd5237b9d9cf64a949bc0d02713aae05a1e655c"
)

AUTHORIZATION_STATEMENT = (
    "Ja ich genehmige alle diese Punkte. Der Draft ist absolut im Einklang "
    "mit meinen Vorstellungen und ich habe jeden einzelnen Abschnitt "
    "detailliert geprüft und stimme jedem Abschnitt zu."
)

REVIEW_IDS = [f"P10F-REVIEW-{number:03d}" for number in range(1, 11)]

REVIEW_SUBJECTS = {
    "P10F-REVIEW-001": "Authority and precedence",
    "P10F-REVIEW-002": "Project definition",
    "P10F-REVIEW-003": "Demian age and character",
    "P10F-REVIEW-004": "Y.D. relationship and technology",
    "P10F-REVIEW-005": "Doll and seismic hammer authorship",
    "P10F-REVIEW-006": "Amusement Park of Illusions design",
    "P10F-REVIEW-007": "Corruption mystery cause",
    "P10F-REVIEW-008": "Dialogue timing and tone",
    "P10F-REVIEW-009": "Source traceability",
    "P10F-REVIEW-010": "Final draft disposition",
}

INPUT_FILES = {
    "contract": "07-canon-story-bible-generation-contract.json",
    "candidate_draft": "10a-canon-story-bible-draft-traceability-revised.md",
    "generation_summary": "11-canon-story-bible-generation-summary.json",
    "traceability_revision_summary":
        "11b-canon-story-bible-traceability-revision-summary.json",
    "structural_validation":
        "12-canon-story-bible-draft-validation.json",
    "pending_human_review_matrix":
        "13-canon-story-bible-human-review.md",
}

OUTPUT_FILES = {
    "review_decisions": "16-human-review-decisions.json",
    "approved_story_bible": "17-approved-canon-story-bible.md",
    "final_verification": "18-final-approval-verification.json",
    "completion_record": "19-completion-record.md",
    "checksum_manifest": "SHA256SUMS.approved",
}


def abort(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def recursive_values_for_key(value: Any, key: str) -> list[Any]:
    results: list[Any] = []

    if isinstance(value, dict):
        for current_key, current_value in value.items():
            if current_key == key:
                results.append(current_value)
            results.extend(recursive_values_for_key(current_value, key))
    elif isinstance(value, list):
        for item in value:
            results.extend(recursive_values_for_key(item, key))

    return results


p10f_env = os.environ.get("P10F", "")
if not p10f_env:
    abort("P10F is not exported")

p10f = Path(p10f_env).expanduser().resolve()
if not p10f.is_dir():
    abort(f"P10F directory does not exist: {p10f}")

input_paths = {name: p10f / filename for name, filename in INPUT_FILES.items()}
output_paths = {name: p10f / filename for name, filename in OUTPUT_FILES.items()}

for name, path in input_paths.items():
    if not path.is_file() or path.stat().st_size == 0:
        abort(f"Missing or empty input artifact {name}: {path}")

existing_outputs = [
    str(path)
    for path in output_paths.values()
    if path.exists()
]
if existing_outputs:
    abort(
        "Refusing to overwrite existing finalization artifacts:\n"
        + "\n".join(existing_outputs)
    )

candidate_path = input_paths["candidate_draft"]
candidate_sha256 = sha256_file(candidate_path)

if candidate_sha256 != EXPECTED_DRAFT_SHA256:
    abort(
        "Reviewed draft SHA-256 mismatch:\n"
        f"Actual:   {candidate_sha256}\n"
        f"Expected: {EXPECTED_DRAFT_SHA256}"
    )

validation_data = json.loads(
    input_paths["structural_validation"].read_text(encoding="utf-8")
)
validation_serialized = json.dumps(validation_data, ensure_ascii=False)

if "passed_structural_awaiting_human_review" not in validation_serialized:
    abort("Structural validation is not passed_structural_awaiting_human_review")

status_values = []
for key in ("status", "validation_status"):
    status_values.extend(recursive_values_for_key(validation_data, key))

if (
    status_values
    and "passed_structural_awaiting_human_review" not in status_values
):
    abort(f"Unexpected structural validation status values: {status_values}")

failure_values = []
for key in ("failure_count", "validation_failures"):
    failure_values.extend(recursive_values_for_key(validation_data, key))

numeric_failure_values = [
    int(value)
    for value in failure_values
    if isinstance(value, (int, float, str))
    and str(value).strip().isdigit()
]

if numeric_failure_values and any(value != 0 for value in numeric_failure_values):
    abort(f"Structural validation contains failures: {numeric_failure_values}")

review_matrix_text = input_paths["pending_human_review_matrix"].read_text(
    encoding="utf-8"
)

for review_id in REVIEW_IDS:
    if review_id not in review_matrix_text:
        abort(f"Review matrix does not contain {review_id}")

generation_summary_text = input_paths["generation_summary"].read_text(
    encoding="utf-8"
)
if GENERATION_RUN_ID not in generation_summary_text:
    abort(
        "Generation summary does not reference expected run ID "
        f"{GENERATION_RUN_ID}"
    )

reviewed_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
    "+00:00",
    "Z",
)

review_decisions = {
    "schema_version": 1,
    "workflow": WORKFLOW,
    "project_id": PROJECT_ID,
    "project_slug": PROJECT_SLUG,
    "status": "approved",
    "reviewed_at": reviewed_at,
    "reviewer": {
        "name": REVIEWER,
        "role": "human_canon_authority",
        "authorization_statement": AUTHORIZATION_STATEMENT,
    },
    "reviewed_artifact": {
        "path": INPUT_FILES["candidate_draft"],
        "sha256": candidate_sha256,
        "generation_run_id": GENERATION_RUN_ID,
    },
    "decision_policy": {
        "allowed_dispositions": [
            "approve",
            "reject",
            "needs_revision",
            "defer",
        ],
        "all_review_items_resolved": True,
        "final_approval_requires_items_001_through_009_approved": True,
        "requirement_satisfied": True,
    },
    "decisions": [
        {
            "review_id": review_id,
            "subject": REVIEW_SUBJECTS[review_id],
            "disposition": "approve",
            "reviewer": REVIEWER,
            "reviewed_at": reviewed_at,
            "notes": (
                "Approved without requested changes after detailed human review."
            ),
        }
        for review_id in REVIEW_IDS
    ],
    "summary": {
        "review_item_count": 10,
        "approved_count": 10,
        "rejected_count": 0,
        "needs_revision_count": 0,
        "deferred_count": 0,
        "pending_count": 0,
        "final_draft_approved": True,
    },
    "controls": {
        "additional_model_call_performed": False,
        "database_access_performed": False,
        "database_mutation_performed": False,
        "existing_frozen_evidence_modified": False,
    },
}

write_json(output_paths["review_decisions"], review_decisions)

shutil.copyfile(candidate_path, output_paths["approved_story_bible"])

approved_sha256 = sha256_file(output_paths["approved_story_bible"])
if approved_sha256 != candidate_sha256:
    abort("Approved Story Bible is not byte-identical to reviewed draft")

verification = {
    "schema_version": 1,
    "workflow": WORKFLOW,
    "project_id": PROJECT_ID,
    "project_slug": PROJECT_SLUG,
    "status": "completed_and_verified",
    "story_bible_status": "reviewed_approved_and_frozen",
    "verified_at": reviewed_at,
    "human_authority": {
        "reviewer": REVIEWER,
        "review_items": REVIEW_IDS,
        "approved_count": 10,
        "final_draft_approved": True,
        "authorization_statement": AUTHORIZATION_STATEMENT,
    },
    "reviewed_draft": {
        "path": INPUT_FILES["candidate_draft"],
        "sha256": candidate_sha256,
    },
    "approved_story_bible": {
        "path": OUTPUT_FILES["approved_story_bible"],
        "sha256": approved_sha256,
        "byte_identical_to_reviewed_draft": True,
    },
    "generation": {
        "run_id": GENERATION_RUN_ID,
        "structural_validation_status":
            "passed_structural_awaiting_human_review",
    },
    "verification_checks": {
        "authoritative_input_chain_verified": True,
        "reviewed_draft_sha256_verified": True,
        "structural_validation_passed": True,
        "review_items_present": 10,
        "review_items_approved": 10,
        "final_disposition_approved": True,
        "approved_copy_matches_reviewed_draft": True,
        "unresolved_review_items": 0,
    },
    "artifacts": {
        "review_decisions": {
            "path": OUTPUT_FILES["review_decisions"],
            "sha256": sha256_file(output_paths["review_decisions"]),
        },
        "structural_validation": {
            "path": INPUT_FILES["structural_validation"],
            "sha256": sha256_file(input_paths["structural_validation"]),
        },
        "pending_review_matrix": {
            "path": INPUT_FILES["pending_human_review_matrix"],
            "sha256": sha256_file(input_paths["pending_human_review_matrix"]),
        },
        "approved_story_bible": {
            "path": OUTPUT_FILES["approved_story_bible"],
            "sha256": approved_sha256,
        },
    },
    "controls": {
        "additional_model_call_performed": False,
        "database_access_performed": False,
        "database_mutation_performed": False,
        "prior_evidence_files_overwritten": False,
    },
    "next_controlled_action": {
        "action": "use_approved_story_bible_as_authoritative_story_reference",
        "artifact": OUTPUT_FILES["approved_story_bible"],
        "requires_database_mutation": False,
    },
}

write_json(output_paths["final_verification"], verification)

verification_sha256 = sha256_file(output_paths["final_verification"])

completion_record = f"""# P10F Canon Story Bible – Completion Record

- Workflow: `{WORKFLOW}`
- Project ID: `{PROJECT_ID}`
- Project slug: `{PROJECT_SLUG}`
- Status: `completed_and_verified`
- Story Bible status: `reviewed_approved_and_frozen`
- Human authority: `{REVIEWER}`
- Reviewed at: `{reviewed_at}`
- Generation run ID: `{GENERATION_RUN_ID}`

## Human-review result

- Review items: `10`
- Approved: `10`
- Rejected: `0`
- Needs revision: `0`
- Deferred: `0`
- Pending: `0`
- Final draft approved: `true`

## Approved artifact

- File: `{OUTPUT_FILES["approved_story_bible"]}`
- SHA-256: `{approved_sha256}`
- Byte-identical to: `{INPUT_FILES["candidate_draft"]}`

## Verification

- Structural validation: `passed_structural_awaiting_human_review`
- Human review: `approved`
- Final verification SHA-256: `{verification_sha256}`
- Additional model call performed: `false`
- Database access performed: `false`
- Database mutation performed: `false`
- Existing frozen evidence modified: `false`

## Authorization statement

> {AUTHORIZATION_STATEMENT}
"""

output_paths["completion_record"].write_text(
    completion_record,
    encoding="utf-8",
)

manifest_files = [
    "README.md",
    "01-authoritative-input-manifest.json",
    "06-read-only-canon-snapshot-verification.json",
    "07-canon-story-bible-generation-contract.json",
    "10-canon-story-bible-draft.md",
    "10a-canon-story-bible-draft-traceability-revised.md",
    "11-canon-story-bible-generation-summary.json",
    "11a-canon-story-bible-draft-validator.py",
    "11b-canon-story-bible-traceability-revision-summary.json",
    "12-canon-story-bible-draft-validation.json",
    "13-canon-story-bible-human-review.md",
    "14-canon-story-bible-generation.log",
    "15-p10f-human-review-finalizer.py",
    "16-human-review-decisions.json",
    "17-approved-canon-story-bible.md",
    "18-final-approval-verification.json",
    "19-completion-record.md",
    "SHA256SUMS.bootstrap",
    "SHA256SUMS.snapshot",
    "SHA256SUMS.draft-request",
    "SHA256SUMS.runner",
    "SHA256SUMS.draft",
]

for relative_name in manifest_files:
    path = p10f / relative_name
    if not path.is_file() or path.stat().st_size == 0:
        abort(f"Missing final manifest artifact: {relative_name}")

manifest_lines = [
    f"{sha256_file(p10f / relative_name)}  {relative_name}"
    for relative_name in manifest_files
]

output_paths["checksum_manifest"].write_text(
    "\n".join(manifest_lines) + "\n",
    encoding="utf-8",
)

print(f"Review decisions: {len(REVIEW_IDS)}")
print("Approved decisions: 10")
print("Unresolved decisions: 0")
print(f"Reviewer: {REVIEWER}")
print(f"Reviewed draft SHA-256: {candidate_sha256}")
print(f"Approved Story Bible SHA-256: {approved_sha256}")
print("Approved copy byte-identical: True")
print("Additional model call: False")
print("Database mutation: False")
print("Story Bible status: reviewed_approved_and_frozen")
print("P10F HUMAN REVIEW FINALIZATION: OK")
