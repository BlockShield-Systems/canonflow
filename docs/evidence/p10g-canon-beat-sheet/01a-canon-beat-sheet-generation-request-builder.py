#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
PROJECT_SLUG = "yd-when-paradise-glitches"
WORKFLOW = "P10G Canon Beat Sheet"
MODEL = "gemini-3.1-pro-preview"

EXPECTED_STORY_BIBLE_SHA256 = (
    "b53c6e01afeb38abf91e8b523cd5237b9d9cf64a949bc0d02713aae05a1e655c"
)

CANON_IDS = [
    f"YD-CANON-{number:04d}"
    for number in range(1, 7)
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

BEAT_FIELDS = [
    "Beat ID",
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


def abort(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def env_directory(name: str) -> Path:
    value = os.environ.get(name, "")
    if not value:
        abort(f"{name} is not exported")

    path = Path(value).expanduser().resolve()

    if not path.is_dir():
        abort(f"{name} directory does not exist: {path}")

    return path


def require_file(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        abort(f"Missing or empty required file: {path}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def write_text(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


p10c = env_directory("P10C")
p10f = env_directory("P10F")
p10g = env_directory("P10G")

configured_model = os.environ.get("CANONFLOW_MODEL", "")

if configured_model != MODEL:
    abort(
        "Unexpected CANONFLOW_MODEL:\n"
        f"Actual:   {configured_model!r}\n"
        f"Expected: {MODEL!r}"
    )

builder_path = (
    p10g / "01a-canon-beat-sheet-generation-request-builder.py"
)
bootstrap_manifest_path = (
    p10g / "01-authoritative-input-manifest.json"
)
story_bible_path = (
    p10f / "17-approved-canon-story-bible.md"
)
canon_snapshot_path = (
    p10f / "03-read-only-canon-snapshot.jsonl"
)
snapshot_verification_path = (
    p10f / "06-read-only-canon-snapshot-verification.json"
)
human_review_path = (
    p10f / "16-human-review-decisions.json"
)
final_approval_path = (
    p10f / "18-final-approval-verification.json"
)
source_audit_path = (
    p10c / "08-source-audit-report.md"
)

contract_path = (
    p10g / "02-canon-beat-sheet-generation-contract.json"
)
request_path = (
    p10g / "03-canon-beat-sheet-generation-request.md"
)
input_path = (
    p10g / "04-canon-beat-sheet-generation-input.md"
)
checksum_path = (
    p10g / "SHA256SUMS.generation-request"
)

required_inputs = [
    builder_path,
    bootstrap_manifest_path,
    story_bible_path,
    canon_snapshot_path,
    snapshot_verification_path,
    human_review_path,
    final_approval_path,
    source_audit_path,
]

for path in required_inputs:
    require_file(path)

for path in (
    contract_path,
    request_path,
    input_path,
    checksum_path,
):
    if path.exists():
        abort(f"Refusing to overwrite existing output: {path}")

bootstrap = json.loads(
    bootstrap_manifest_path.read_text(encoding="utf-8")
)

if bootstrap.get("workflow") != WORKFLOW:
    abort("Unexpected bootstrap workflow")

if (
    bootstrap.get("status")
    != "initialized_awaiting_generation_contract"
):
    abort("Unexpected bootstrap status")

story_bible_sha256 = sha256_file(story_bible_path)

if story_bible_sha256 != EXPECTED_STORY_BIBLE_SHA256:
    abort(
        "Approved Story Bible SHA-256 mismatch:\n"
        f"Actual:   {story_bible_sha256}\n"
        f"Expected: {EXPECTED_STORY_BIBLE_SHA256}"
    )

if (
    bootstrap
    .get("authoritative_story_bible", {})
    .get("sha256")
    != story_bible_sha256
):
    abort("Bootstrap Story Bible SHA-256 mismatch")

if (
    bootstrap
    .get("canon_constraints", {})
    .get("decision_ids")
    != CANON_IDS
):
    abort("Bootstrap contains unexpected canon decision IDs")

snapshot_rows: list[dict[str, Any]] = []

for line_number, line in enumerate(
    canon_snapshot_path.read_text(
        encoding="utf-8-sig"
    ).splitlines(),
    start=1,
):
    if not line.strip():
        continue

    try:
        row = json.loads(line)
    except json.JSONDecodeError as error:
        abort(
            f"Invalid canon snapshot line {line_number}: {error}"
        )

    if not isinstance(row, dict):
        abort(
            f"Canon snapshot line {line_number} is not an object"
        )

    snapshot_rows.append(row)

if len(snapshot_rows) != 6:
    abort(
        f"Expected 6 canon snapshot rows, found {len(snapshot_rows)}"
    )

actual_canon_ids = [
    row.get("decision_id")
    for row in snapshot_rows
]

if actual_canon_ids != CANON_IDS:
    abort(
        "Unexpected canon snapshot IDs:\n"
        f"Actual:   {actual_canon_ids}\n"
        f"Expected: {CANON_IDS}"
    )

if any(row.get("status") != "approved" for row in snapshot_rows):
    abort("Canon snapshot contains a non-approved decision")

if any(row.get("approved_by") != "Demian" for row in snapshot_rows):
    abort("Canon snapshot contains a non-Demian approval")

human_review = json.loads(
    human_review_path.read_text(encoding="utf-8")
)

if human_review.get("status") != "approved":
    abort("P10F human-review status is not approved")

review_summary = human_review.get("summary", {})

if review_summary.get("approved_count") != 10:
    abort("Expected 10 approved P10F review items")

if review_summary.get("pending_count") != 0:
    abort("P10F contains pending review items")

if review_summary.get("final_draft_approved") is not True:
    abort("P10F final Story Bible is not approved")

final_approval = json.loads(
    final_approval_path.read_text(encoding="utf-8")
)

if final_approval.get("status") != "completed_and_verified":
    abort("P10F final approval is not completed_and_verified")

if (
    final_approval.get("story_bible_status")
    != "reviewed_approved_and_frozen"
):
    abort("P10F Story Bible is not frozen and approved")

created_at = datetime.now(timezone.utc).isoformat(
    timespec="seconds"
).replace("+00:00", "Z")

contract: dict[str, Any] = {
    "schema_version": 1,
    "workflow": WORKFLOW,
    "status": "ready_for_afc_chat_generation",
    "created_at": created_at,
    "project_id": PROJECT_ID,
    "project_slug": PROJECT_SLUG,
    "human_authority": {
        "name": "Demian",
        "role": "human_canon_authority",
    },
    "generation": {
        "provider": "Google Gemini API",
        "sdk": "google-genai",
        "model": MODEL,
        "temperature": 0.2,
        "max_output_tokens": 32768,
        "streaming": False,
        "external_tools_enabled": False,
        "automatic_function_calling": {
            "routing_mode": "afc_compatible_chat",
            "required_transport": "Chat.send_message",
            "client_route": [
                "genai.Client",
                "client.chats.create",
                "chat.send_message",
            ],
            "direct_models_generate_content_allowed": False,
            "automatic_function_tools_configured": False,
        },
    },
    "input_authority": {
        "approved_story_bible": {
            "path": str(story_bible_path),
            "sha256": story_bible_sha256,
            "precedence": 1,
        },
        "approved_canon_snapshot": {
            "path": str(canon_snapshot_path),
            "sha256": sha256_file(canon_snapshot_path),
            "decision_ids": CANON_IDS,
            "decision_count": 6,
            "precedence": 2,
        },
        "source_audit": {
            "path": str(source_audit_path),
            "sha256": sha256_file(source_audit_path),
            "precedence": 3,
        },
    },
    "authority_precedence": [
        "Approved P10F Canon Story Bible",
        "Approved Canon Decisions YD-CANON-0001 through YD-CANON-0006",
        "Accepted P10C source evidence and verified locators",
        "Clearly marked non-canon structural proposals",
    ],
    "output": {
        "format": "Markdown",
        "artifact": "06-canon-beat-sheet-draft.md",
        "summary_artifact":
            "07-canon-beat-sheet-generation-summary.json",
        "minimum_characters": 30000,
        "minimum_beat_entries": 40,
        "required_sections": REQUIRED_SECTIONS,
        "required_section_count": len(REQUIRED_SECTIONS),
        "required_beat_fields": BEAT_FIELDS,
        "required_beat_field_count": len(BEAT_FIELDS),
        "required_canon_decision_ids": CANON_IDS,
        "end_marker": "P10G CANON BEAT SHEET DRAFT END",
    },
    "structural_requirements": {
        "feature_length_film": True,
        "forbidden_short_runtime_compression": True,
        "required_act_regions": [
            "Prologue",
            "Act 1",
            "Act 2A",
            "Midpoint",
            "Act 2B",
            "Act 3",
            "Epilogue",
        ],
        "beats_must_be_sequentially_numbered": True,
        "beat_id_format": "P10G-BEAT-###",
        "each_beat_requires_fact_classification": True,
        "allowed_fact_classifications": [
            "canon-explicit",
            "source-supported",
            "canon-derived",
            "non-canon-proposal",
        ],
        "non_canon_proposals_must_be_visibly_marked": True,
    },
    "mandatory_canon_constraints": [
        {
            "decision_id": "YD-CANON-0001",
            "constraint": "Demian is 40 years old.",
        },
        {
            "decision_id": "YD-CANON-0002",
            "constraint": (
                "The project is a feature-length film and must not "
                "be compressed into the historical fifteen-minute "
                "runtime limit."
            ),
        },
        {
            "decision_id": "YD-CANON-0003",
            "constraint": (
                "Y.D. originated or deployed the modified doll and "
                "seismic hammer, while Demian does not know this "
                "during the Act 1 event."
            ),
        },
        {
            "decision_id": "YD-CANON-0004",
            "constraint": (
                "The Amusement Park of Illusions is a major survival "
                "escape-room sequence bridging Act 2B into the "
                "Mirror Room."
            ),
        },
        {
            "decision_id": "YD-CANON-0005",
            "constraint": (
                "The cause of Y.D.'s corruption remains causally "
                "ambiguous with multiple plausible causes."
            ),
        },
        {
            "decision_id": "YD-CANON-0006",
            "constraint": (
                "Preserve dialogue intent, dark humor, satire, and "
                "Y.D.'s voice progression. Historical four-second "
                "frame timings are not binding."
            ),
        },
    ],
    "epistemic_controls": {
        "demian_must_not_know_yd_doll_authorship_in_act1": True,
        "audience_reveal_timing_must_not_be_invented_as_canon": True,
        "corruption_cause_must_not_be_resolved": True,
        "ambiguities_must_be_preserved_or_flagged": True,
        "new_facts_must_not_be_presented_as_approved_canon": True,
    },
    "traceability": {
        "source_filename_required": True,
        "page_or_line_locator_required_when_available": True,
        "canon_decision_id_required_for_constrained_beats": True,
        "unsupported_claims_must_be_marked_non_canon_proposal": True,
        "fabricated_citations_forbidden": True,
    },
    "validation": {
        "strict_local_validation_required": True,
        "human_review_required": True,
        "automatic_canon_release_allowed": False,
        "database_mutation_allowed": False,
    },
    "controls": {
        "additional_model_call_performed_during_packaging": False,
        "database_access_performed": False,
        "database_mutation_performed": False,
        "existing_frozen_evidence_modified": False,
    },
}

section_list = "\n".join(
    f"- `{section}`"
    for section in REQUIRED_SECTIONS
)

field_list = "\n".join(
    f"- `{field}`"
    for field in BEAT_FIELDS
)

canon_list = "\n".join(
    f"- `{decision_id}`"
    for decision_id in CANON_IDS
)

request = f"""# P10G Canon Beat Sheet – Controlled Generation Request

## Execution status

`ready_for_afc_chat_generation`

## Task

Generate a complete, production-usable feature-film Canon Beat Sheet for
**Y.D. – When Paradise Glitches**.

The Beat Sheet must transform the approved Story Bible into a sequential
feature-film beat structure without silently creating new canon.

## Authority precedence

1. Approved P10F Canon Story Bible
2. Approved Canon Decisions `YD-CANON-0001` through `YD-CANON-0006`
3. Accepted P10C source evidence and verified locators
4. Explicitly marked `non-canon-proposal` material

Lower-precedence material must not override higher-precedence authority.

## Canon decisions

{canon_list}

## Required output

- Markdown only
- Minimum characters: `30000`
- Minimum sequential beat entries: `40`
- Beat ID format: `P10G-BEAT-###`
- Feature-film structure
- All 24 required sections
- All 17 beat fields where applicable
- Explicit source and Canon Decision traceability
- Unsupported connective material marked `non-canon-proposal`
- No fabricated citations
- No resolution of Y.D.'s corruption cause
- Demian remains unaware of Y.D.'s doll authorship during the Act 1 event
- Historical four-second frame timings are not binding
- Human review remains mandatory

## Required sections

{section_list}

## Required beat fields

{field_list}

## Transport contract

The runner must use:

`genai.Client → client.chats.create(...) → Chat.send_message(...)`

The runner must not call `client.models.generate_content(...)` directly.

- Streaming: disabled
- External tools: disabled
- Database access: disabled
- Database mutation: disabled
- Automatic canon release: disabled

## Required end marker

`P10G CANON BEAT SHEET DRAFT END`

## Acceptance boundary

The generated Beat Sheet remains a draft until strict local validation passes
and Demian explicitly approves the later human-review matrix.
"""

story_bible_text = story_bible_path.read_text(encoding="utf-8")
canon_snapshot_text = canon_snapshot_path.read_text(
    encoding="utf-8-sig"
)
snapshot_verification_text = (
    snapshot_verification_path.read_text(encoding="utf-8")
)
source_audit_text = source_audit_path.read_text(encoding="utf-8")

contract_json = json.dumps(
    contract,
    ensure_ascii=False,
    indent=2,
)

generation_input = f"""# P10G Canon Beat Sheet – Authoritative Input Bundle

## Bundle metadata

- Workflow: `{WORKFLOW}`
- Project ID: `{PROJECT_ID}`
- Project slug: `{PROJECT_SLUG}`
- Human authority: `Demian`
- Model: `{MODEL}`
- Approved Story Bible SHA-256: `{story_bible_sha256}`
- Canon snapshot SHA-256: `{sha256_file(canon_snapshot_path)}`
- Source audit SHA-256: `{sha256_file(source_audit_path)}`
- Canon decisions: `6`
- Database mutation authorized: `false`

## Final generation instruction

Use the enclosed authorities according to the contract. Return only the
requested Markdown Beat Sheet. Do not return analysis, JSON metadata, or a
preamble outside the Beat Sheet.

<generation_contract>
{contract_json}
</generation_contract>

<generation_request>
{request}
</generation_request>

<approved_canon_story_bible
  authority="primary"
  sha256="{story_bible_sha256}"
>
{story_bible_text}
</approved_canon_story_bible>

<approved_canon_decisions
  authority="hard-constraints"
  count="6"
>
{canon_snapshot_text}
</approved_canon_decisions>

<canon_snapshot_verification>
{snapshot_verification_text}
</canon_snapshot_verification>

<p10c_source_audit
  authority="traceability-evidence"
>
{source_audit_text}
</p10c_source_audit>

## Final instruction

Generate the complete Beat Sheet now. End the result exactly with:

P10G CANON BEAT SHEET DRAFT END
"""

if len(generation_input) <= 30000:
    abort(
        "Generation input bundle is unexpectedly short: "
        f"{len(generation_input)} characters"
    )

for decision_id in CANON_IDS:
    if decision_id not in request:
        abort(f"Request is missing {decision_id}")

    if decision_id not in generation_input:
        abort(f"Input bundle is missing {decision_id}")

for section in REQUIRED_SECTIONS:
    if section not in request:
        abort(f"Request is missing required section: {section}")

    if section not in generation_input:
        abort(f"Input bundle is missing required section: {section}")

write_json(contract_path, contract)
write_text(request_path, request)
write_text(input_path, generation_input)

checksum_files = [
    "README.md",
    "01-authoritative-input-manifest.json",
    "01a-canon-beat-sheet-generation-request-builder.py",
    "02-canon-beat-sheet-generation-contract.json",
    "03-canon-beat-sheet-generation-request.md",
    "04-canon-beat-sheet-generation-input.md",
]

checksum_lines = []

for filename in checksum_files:
    path = p10g / filename
    require_file(path)
    checksum_lines.append(
        f"{sha256_file(path)}  {filename}"
    )

write_text(
    checksum_path,
    "\n".join(checksum_lines),
)

print(f"Created: {contract_path}")
print(f"Created: {request_path}")
print(f"Created: {input_path}")
print(f"Created: {checksum_path}")
print(f"Required sections: {len(REQUIRED_SECTIONS)}")
print(f"Required beat fields: {len(BEAT_FIELDS)}")
print("Minimum beat entries: 40")
print("Authoritative canon decisions: 6")
print(f"Generation input characters: {len(generation_input)}")
print("Transport: Chat.send_message")
print("Direct Models.generate_content: disabled")
print("Streaming: disabled")
print("External tools: disabled")
print("Database mutation: disabled")
print("P10G GENERATION REQUEST PACKAGE: OK")
