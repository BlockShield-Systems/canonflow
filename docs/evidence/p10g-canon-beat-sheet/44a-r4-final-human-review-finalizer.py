#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
PROJECT_SLUG = "yd-when-paradise-glitches"
REVISION = "R4"

CANDIDATE_TAG = "p10g-r4-review-candidate"
FINAL_DISPOSITION = "approve"
REVIEWER = "Demian"

HUMAN_APPROVAL_STATEMENT = (
    "The complete R4 review candidate was read and approved. "
    "The narrative implementation is considered coherent, professionally "
    "structured, emotionally effective, and suitable as final canon. "
    "All 25 R4 human-review items are approved without additional changes."
)

DRAFT = Path("38-canon-beat-sheet-third-revised-draft.md")
CHANGE_APPLICATION = Path("39-r4-change-application.json")
STRICT_VALIDATION = Path("40-r4-strict-validation.json")
SEMANTIC_VALIDATION = Path("41-r4-semantic-validation.json")
REVIEW_MATRIX = Path("42-r4-human-review.md")
FINALIZER = Path("44a-r4-final-human-review-finalizer.py")

DECISIONS = Path("43-r4-final-human-review-decisions.json")
COMPLETION = Path("44-r4-final-human-review-completion.json")
MANIFEST = Path("SHA256SUMS.r4-human-approval")

REQUIRED_INPUTS = (
    DRAFT,
    CHANGE_APPLICATION,
    STRICT_VALIDATION,
    SEMANTIC_VALIDATION,
    REVIEW_MATRIX,
    FINALIZER,
)

R4_MANIFESTS = (
    Path("SHA256SUMS.r4-reference-images"),
    Path("SHA256SUMS.r4-controlled-revision"),
    Path("SHA256SUMS.r4-final-review"),
)

R3_MANIFESTS = (
    Path("SHA256SUMS.r3-generation"),
    Path("SHA256SUMS.r3-multipart-assembly-runner"),
    Path("SHA256SUMS.r3-final-review"),
    Path("SHA256SUMS.r3-human-decision"),
)


def fail(message: str) -> None:
    raise AssertionError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=Path.cwd(),
        text=True,
    ).strip()


def verify_manifest(path: Path) -> None:
    result = subprocess.run(
        ["sha256sum", "-c", path.name],
        cwd=Path.cwd(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    print(result.stdout, end="")

    if result.returncode != 0:
        fail(f"Manifest verification failed: {path}")


def atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    serialized = (
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=False,
        )
        + "\n"
    )

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )

    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())

        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def collect_key_values(value: Any, key: str) -> list[Any]:
    found: list[Any] = []

    if isinstance(value, dict):
        for current_key, current_value in value.items():
            if current_key == key:
                found.append(current_value)
            found.extend(collect_key_values(current_value, key))

    elif isinstance(value, list):
        for item in value:
            found.extend(collect_key_values(item, key))

    return found


def unique_string_value(documents: list[Any], key: str) -> str:
    values: set[str] = set()

    for document in documents:
        for value in collect_key_values(document, key):
            if isinstance(value, str) and value.strip():
                values.add(value.strip())

    if len(values) != 1:
        fail(
            f"Expected exactly one distinct value for {key!r}; "
            f"found: {sorted(values)!r}"
        )

    return next(iter(values))


def main() -> None:
    if Path.cwd().resolve() != Path(__file__).resolve().parent:
        fail("Run the finalizer from its own evidence directory")

    for path in REQUIRED_INPUTS + R4_MANIFESTS + R3_MANIFESTS:
        if not path.is_file():
            fail(f"Required file missing: {path}")

    for output in (DECISIONS, COMPLETION, MANIFEST):
        if output.exists():
            fail(f"Refusing to overwrite existing approval artifact: {output}")

    repo_root = git("rev-parse", "--show-toplevel")
    candidate_commit = git("rev-parse", f"{CANDIDATE_TAG}^{{commit}}")
    current_head = git("rev-parse", "HEAD")

    if current_head != candidate_commit:
        fail(
            "Current HEAD is not the tagged R4 review candidate: "
            f"HEAD={current_head}, candidate={candidate_commit}"
        )

    print("===== R4 MANIFEST VERIFICATION =====")
    for manifest in R4_MANIFESTS:
        verify_manifest(manifest)

    print("===== R3 FREEZE VERIFICATION =====")
    for manifest in R3_MANIFESTS:
        verify_manifest(manifest)

    matrix_text = REVIEW_MATRIX.read_text(encoding="utf-8")

    review_matches = re.findall(
        r"\bP10G-R4-REVIEW-(\d{3})\b",
        matrix_text,
    )
    review_counts = Counter(review_matches)
    expected_numbers = [f"{number:03d}" for number in range(1, 26)]

    if sorted(review_counts) != expected_numbers:
        fail(
            "Human-review matrix does not contain the expected "
            "P10G-R4-REVIEW-001..025 identifiers"
        )

    duplicates = {
        review_id: count
        for review_id, count in review_counts.items()
        if count != 1
    }

    if duplicates:
        fail(f"Review identifiers must occur exactly once: {duplicates}")

    required_pending_markers = (
        "Human review completed: `false`",
        "Approved as final canon: `false`",
        "Final disposition: `pending_human_review`",
        "P10G R4 FINAL HUMAN REVIEW: PENDING",
    )

    for marker in required_pending_markers:
        if marker not in matrix_text:
            fail(f"Required candidate-state marker missing: {marker}")

    parsed_documents: list[Any] = []

    for path in (
        CHANGE_APPLICATION,
        STRICT_VALIDATION,
        SEMANTIC_VALIDATION,
    ):
        with path.open("r", encoding="utf-8") as handle:
            parsed_documents.append(json.load(handle))

    revision_run_id = unique_string_value(
        parsed_documents,
        "revision_run_id",
    )

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    draft_sha256 = sha256(DRAFT)
    matrix_sha256 = sha256(REVIEW_MATRIX)
    semantic_validation_sha256 = sha256(SEMANTIC_VALIDATION)

    decisions_payload: dict[str, Any] = {
        "schema_version": "1.0",
        "artifact_type": "p10g_r4_final_human_review_decisions",
        "project_id": PROJECT_ID,
        "project_slug": PROJECT_SLUG,
        "revision": REVISION,
        "revision_run_id": revision_run_id,
        "candidate_tag": CANDIDATE_TAG,
        "candidate_commit_sha": candidate_commit,
        "draft_file": DRAFT.name,
        "draft_sha256": draft_sha256,
        "review_matrix_file": REVIEW_MATRIX.name,
        "review_matrix_sha256": matrix_sha256,
        "reviewer": REVIEWER,
        "recorded_at_utc": generated_at,
        "human_approval_statement": HUMAN_APPROVAL_STATEMENT,
        "allowed_dispositions": [
            "approve",
            "changes_requested",
            "reject",
        ],
        "review_items": [
            {
                "review_id": f"P10G-R4-REVIEW-{number:03d}",
                "disposition": "approve",
                "reviewer": REVIEWER,
                "basis": "Approved during complete human review of the R4 candidate.",
            }
            for number in range(1, 26)
        ],
        "summary": {
            "review_items": 25,
            "approved": 25,
            "changes_requested": 0,
            "rejected": 0,
            "human_review_completed": True,
            "approved_as_final_canon": True,
            "final_disposition": FINAL_DISPOSITION,
        },
        "automation_policy": {
            "provider_calls_executed": False,
            "clickhouse_mutation_executed": False,
            "automatic_canon_release": False,
            "human_decision_required": True,
            "human_decision_present": True,
        },
    }

    atomic_json_write(DECISIONS, decisions_payload)
    decisions_sha256 = sha256(DECISIONS)

    completion_payload: dict[str, Any] = {
        "schema_version": "1.0",
        "artifact_type": "p10g_r4_final_human_review_completion",
        "project_id": PROJECT_ID,
        "project_slug": PROJECT_SLUG,
        "revision": REVISION,
        "revision_run_id": revision_run_id,
        "candidate_tag": CANDIDATE_TAG,
        "candidate_commit_sha": candidate_commit,
        "completed_at_utc": generated_at,
        "reviewer": REVIEWER,
        "status": "completed",
        "human_review_completed": True,
        "approved_as_final_canon": True,
        "final_disposition": FINAL_DISPOSITION,
        "counts": {
            "review_items": 25,
            "approved": 25,
            "changes_requested": 0,
            "rejected": 0,
        },
        "bindings": {
            "draft": {
                "path": DRAFT.name,
                "sha256": draft_sha256,
            },
            "semantic_validation": {
                "path": SEMANTIC_VALIDATION.name,
                "sha256": semantic_validation_sha256,
            },
            "human_review_matrix": {
                "path": REVIEW_MATRIX.name,
                "sha256": matrix_sha256,
            },
            "human_review_decisions": {
                "path": DECISIONS.name,
                "sha256": decisions_sha256,
            },
        },
        "release_policy": {
            "final_canon_release_authorized": True,
            "authorization_source": "explicit_human_review",
            "provider_calls_executed": False,
            "clickhouse_mutation_executed": False,
            "frozen_r3_artifacts_modified": False,
            "r4_candidate_artifacts_modified": False,
        },
    }

    atomic_json_write(COMPLETION, completion_payload)

    manifest_files = (
        DRAFT,
        SEMANTIC_VALIDATION,
        REVIEW_MATRIX,
        DECISIONS,
        COMPLETION,
        FINALIZER,
    )

    manifest_content = "".join(
        f"{sha256(path)}  {path.name}\n"
        for path in manifest_files
    )

    MANIFEST.write_text(
        manifest_content,
        encoding="utf-8",
        newline="\n",
    )

    print("===== R4 HUMAN APPROVAL SUMMARY =====")
    print(f"Repository root:             {repo_root}")
    print(f"Candidate commit:            {candidate_commit}")
    print(f"Revision run ID:             {revision_run_id}")
    print(f"Draft SHA-256:               {draft_sha256}")
    print("Review items:                25")
    print("Approved:                    25")
    print("Changes requested:           0")
    print("Rejected:                    0")
    print("Human review completed:      True")
    print("Approved as final canon:     True")
    print(f"Final disposition:           {FINAL_DISPOSITION}")
    print("Provider calls executed:     False")
    print("ClickHouse mutation executed: False")
    print("Automatic canon release:     False")
    print("Frozen R3 artifacts modified: False")
    print("R4 candidate files modified: False")
    print("P10G R4 FINAL HUMAN APPROVAL: OK")


if __name__ == "__main__":
    main()
