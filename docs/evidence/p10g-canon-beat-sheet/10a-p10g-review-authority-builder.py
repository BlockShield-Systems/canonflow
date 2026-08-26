#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
PROJECT_SLUG = "yd-when-paradise-glitches"
WORKFLOW = "P10G Canon Beat Sheet"
REVIEWER = "Demian"

GENERATION_RUN_ID = "002a27d3-a414-4a25-b21e-d3c924b2a391"
STORY_BIBLE_SHA256 = (
    "b53c6e01afeb38abf91e8b523cd5237b9d9cf64a949bc0d02713aae05a1e655c"
)
DRAFT_SHA256 = (
    "f31eb0a475100755e82676dde16d5075a044eea35f426d0e56eab71fcba7e1d8"
)

BUILDER_FILENAME = "10a-p10g-review-authority-builder.py"
DECISIONS_FILENAME = "11-human-review-decisions.json"
AMENDMENTS_FILENAME = "12-canon-amendment-proposals.json"
REVISION_CONTRACT_FILENAME = "13-beat-sheet-revision-contract.json"
CHECKSUM_FILENAME = "SHA256SUMS.review-authority"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def require_file(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Missing or empty required artifact: {path}")


def review_item(
    review_id: str,
    subject: str,
    disposition: str,
    notes: list[str],
) -> dict[str, Any]:
    return {
        "review_id": review_id,
        "subject": subject,
        "reviewer": REVIEWER,
        "disposition": disposition,
        "notes": notes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p10g", required=True)
    parser.add_argument("--p10f", required=True)
    args = parser.parse_args()

    p10g = Path(args.p10g).expanduser().resolve()
    p10f = Path(args.p10f).expanduser().resolve()

    if not p10g.is_dir():
        raise RuntimeError(f"P10G directory not found: {p10g}")

    if not p10f.is_dir():
        raise RuntimeError(f"P10F directory not found: {p10f}")

    story_bible = p10f / "17-approved-canon-story-bible.md"
    draft = p10g / "06-canon-beat-sheet-draft.md"
    validation = p10g / "08-canon-beat-sheet-validation.json"
    review_matrix = p10g / "09-canon-beat-sheet-human-review.md"
    builder = p10g / BUILDER_FILENAME

    required = [
        story_bible,
        draft,
        validation,
        review_matrix,
        builder,
    ]

    for path in required:
        require_file(path)

    if sha256(story_bible) != STORY_BIBLE_SHA256:
        raise RuntimeError("Approved Story Bible SHA-256 mismatch")

    if sha256(draft) != DRAFT_SHA256:
        raise RuntimeError("P10G Beat Sheet draft SHA-256 mismatch")

    validation_payload = json.loads(validation.read_text(encoding="utf-8"))
    validation_text = json.dumps(validation_payload, ensure_ascii=False)

    if "passed_structural_awaiting_human_review" not in validation_text:
        raise RuntimeError("Unexpected structural validation status")

    review_text = review_matrix.read_text(encoding="utf-8")

    for number in range(1, 14):
        review_id = f"P10G-REVIEW-{number:03d}"

        if review_id not in review_text:
            raise RuntimeError(f"Missing review item: {review_id}")

    output_paths = [
        p10g / DECISIONS_FILENAME,
        p10g / AMENDMENTS_FILENAME,
        p10g / REVISION_CONTRACT_FILENAME,
        p10g / CHECKSUM_FILENAME,
    ]

    existing = [path for path in output_paths if path.exists()]

    if existing:
        names = ", ".join(path.name for path in existing)
        raise RuntimeError(f"Refusing to overwrite existing outputs: {names}")

    created_at = datetime.now(timezone.utc).isoformat()

    decisions = [
        review_item(
            "P10G-REVIEW-001",
            "Authority and precedence",
            "needs_revision",
            [
                "The approved P10F Story Bible remains primary authority.",
                "Chronology and corruption-ambiguity wording require revision.",
                "Approved amendments YD-CANON-0007..0011 must be integrated "
                "through a controlled revision.",
            ],
        ),
        review_item(
            "P10G-REVIEW-002",
            "Feature-film structure",
            "needs_revision",
            [
                "Use Amusement Park as late Act 2B / Pre-Climax Gauntlet.",
                "Use Mirror Labyrinth as the transition into the lowest point.",
                "Use Mirror Room as the explicit Act 3 entry.",
                "Keep a separate philosophical Epilogue after Act 3.",
            ],
        ),
        review_item(
            "P10G-REVIEW-003",
            "Beat completeness and progression",
            "needs_revision",
            [
                "The 44-beat foundation is accepted.",
                "Normalize every beat as a real Markdown heading.",
                "Correct chronology, act labels, countdown timing, and hammer continuity.",
            ],
        ),
        review_item(
            "P10G-REVIEW-004",
            "Demian character continuity",
            "needs_revision",
            [
                "Demian was born in 2385.",
                "He received longevity treatment in 2425 at chronological age 40.",
                "In 2666 he is chronologically 281 but visually approximately 40.",
                "His age, identities, treatment, and multi-era history remain secret.",
            ],
        ),
        review_item(
            "P10G-REVIEW-005",
            "Y.D. character and voice progression",
            "needs_revision",
            [
                "The Your Dear, Your Devil, fracture, and neutral stages are accepted.",
                "Y.D.'s internal motives must not be presented as objective fact.",
                "Use the term 'fractured dual-state AI entity'.",
            ],
        ),
        review_item(
            "P10G-REVIEW-006",
            "Doll and seismic-hammer event",
            "approve",
            [
                "Y.D. remains the actual deployer or originator.",
                "Demian remains unaware of this during the Act 1 event.",
            ],
        ),
        review_item(
            "P10G-REVIEW-007",
            "Amusement Park of Illusions",
            "needs_revision",
            [
                "The major survival escape-room concept is approved.",
                "The proposed traps are approved for controlled integration.",
                "The countdown must be increased and made physically credible.",
                "Demian must explicitly recover and drag the seismic hammer.",
            ],
        ),
        review_item(
            "P10G-REVIEW-008",
            "Mirror Room and final confrontation",
            "needs_revision",
            [
                "The confrontation and thematic climax are accepted.",
                "Interpretations of Y.D.'s motives must remain subjective.",
                "The immediate threat may resolve without resolving the ethical questions.",
            ],
        ),
        review_item(
            "P10G-REVIEW-009",
            "Corruption ambiguity",
            "needs_revision",
            [
                "Demian may accept responsibility for his contribution.",
                "He must not confirm himself as the objective cause of the corruption.",
                "Multiple plausible corruption causes must remain viable.",
            ],
        ),
        review_item(
            "P10G-REVIEW-010",
            "Source traceability",
            "needs_revision",
            [
                "Existing filenames and Canon Decision references are useful.",
                "Revision must improve verified page or line locator granularity.",
                "New post-P10F material must reference the amendment package.",
            ],
        ),
        review_item(
            "P10G-REVIEW-011",
            "Non-canon proposals",
            "approve",
            [
                "Amusement Park trap concepts are approved.",
                "Countdown and neurotoxin pressure are approved as concepts.",
                "Exact timing must be revised during scene development.",
                "Absolute physical isolation remains until the lockdown ends.",
                "No physical outside rescue occurs during the central conflict.",
            ],
        ),
        review_item(
            "P10G-REVIEW-012",
            "Subjective first-person visual language",
            "approve",
            [
                "Use controlled Demian-anchored subjective first-person perspective.",
                "Priority beats include 030, 031, 032, 034, and 035.",
                "Subjective imagery must remain bounded by Demian's knowledge.",
                "Return deliberately to objective perspective in the Mirror Room.",
            ],
        ),
        review_item(
            "P10G-REVIEW-013",
            "Final Beat Sheet disposition",
            "needs_revision",
            [
                "The current frozen draft is not approved as final canon.",
                "A controlled revision is required.",
                "The revised artifact requires strict validation and new human review.",
            ],
        ),
    ]

    approved_count = sum(
        item["disposition"] == "approve"
        for item in decisions
    )
    needs_revision_count = sum(
        item["disposition"] == "needs_revision"
        for item in decisions
    )

    decision_payload = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "status": "human_review_completed_revision_required",
        "created_at": created_at,
        "project_id": PROJECT_ID,
        "project_slug": PROJECT_SLUG,
        "reviewer": REVIEWER,
        "reviewed_artifact": {
            "filename": draft.name,
            "sha256": DRAFT_SHA256,
            "generation_run_id": GENERATION_RUN_ID,
        },
        "structural_validation": {
            "filename": validation.name,
            "status": "passed_structural_awaiting_human_review",
            "failures": 0,
        },
        "summary": {
            "review_items": len(decisions),
            "approved": approved_count,
            "needs_revision": needs_revision_count,
            "rejected": 0,
            "deferred": 0,
            "final_disposition": "needs_revision",
        },
        "decisions": decisions,
        "controls": {
            "draft_modified": False,
            "story_bible_modified": False,
            "database_access_performed": False,
            "database_mutation_performed": False,
            "automatic_canon_release_performed": False,
            "human_review_completed": True,
            "revised_draft_required": True,
        },
    }

    amendment_payload = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "status": "human_approved_proposals_awaiting_controlled_integration",
        "created_at": created_at,
        "project_id": PROJECT_ID,
        "project_slug": PROJECT_SLUG,
        "human_authority": REVIEWER,
        "authority_chain": {
            "approved_story_bible_filename": story_bible.name,
            "approved_story_bible_sha256": STORY_BIBLE_SHA256,
            "reviewed_beat_sheet_filename": draft.name,
            "reviewed_beat_sheet_sha256": DRAFT_SHA256,
            "human_review_decisions_filename": DECISIONS_FILENAME,
        },
        "proposals": [
            {
                "decision_id": "YD-CANON-0007",
                "title": "Subjective First-Person Visual Language",
                "disposition": "approve_for_controlled_integration",
                "canonical_direction": (
                    "Selected sequences may transition from objective third-person "
                    "cinematography into Demian-anchored subjective first-person "
                    "perspective when his perception, orientation, or motor control "
                    "is destabilized."
                ),
                "constraints": [
                    "Transitions must be narratively motivated and temporally bounded.",
                    "Subjective imagery remains limited to Demian's knowledge state.",
                    "Hallucinations must not become confirmed objective reality.",
                    "Y.D.'s internal intent must not be revealed as fact.",
                    "The corruption cause remains ambiguous.",
                    "The camera returns deliberately to objective perspective.",
                ],
            },
            {
                "decision_id": "YD-CANON-0008",
                "title": "Demian Longevity and Secret Identity",
                "disposition": "approve_for_controlled_integration",
                "canonical_direction": (
                    "Demian was born in 2385 and received the Neuro-Somatic "
                    "Continuity Lattice treatment in 2425 at chronological age 40. "
                    "In 2666 he is chronologically 281 while biologically and "
                    "visually approximately 40."
                ),
                "constraints": [
                    "Demian remains visually human.",
                    "The treatment must not alter his normal human appearance.",
                    "His true age and identity history remain secret.",
                    "Hints may appear through props, furniture, archives, and posters.",
                    "Audience confirmation requires separate human approval.",
                ],
            },
            {
                "decision_id": "YD-CANON-0009",
                "title": "Project Genesis Dual Motivation",
                "disposition": "approve_for_controlled_integration",
                "canonical_direction": (
                    "Project Genesis has a legitimate public human-AI coexistence "
                    "purpose while also serving Demian's concealed personal desire "
                    "to create an emotionally compatible long-term companion."
                ),
                "constraints": [
                    "The public purpose is genuine but incomplete.",
                    "Y.D. must not be reduced to a sexual objective.",
                    "Demian's motive includes isolation, grief, introversion, "
                    "romantic longing, and fear of recurring loss.",
                    "The private motivation is not public knowledge.",
                ],
            },
            {
                "decision_id": "YD-CANON-0010",
                "title": "Open Philosophical Epilogue",
                "disposition": "approve_for_controlled_integration",
                "canonical_direction": (
                    "The film ends with an open philosophical epilogue after the "
                    "immediate Act 3 resolution. No faction is objectively correct, "
                    "Demian receives no complete moral absolution, Y.D.'s final "
                    "status remains unresolved, and coexistence remains possible "
                    "without being guaranteed."
                ),
                "constraints": [
                    "Green Force, Rich Elite, Poor Communities, and High-Tech-Future "
                    "Force interpret the incident differently.",
                    "Every position contains legitimate benefits and risks.",
                    "The corruption cause remains ambiguous.",
                    "Demian's longevity remains undisclosed to the public.",
                    "The ending must invite audience interpretation.",
                ],
            },
            {
                "decision_id": "YD-CANON-0011",
                "title": "Amusement Park Gauntlet and Isolation",
                "disposition": "approve_for_controlled_integration",
                "canonical_direction": (
                    "The Amusement Park of Illusions is a late Act 2B pre-climax "
                    "gauntlet containing false-floor hazards, fire and riddle "
                    "mechanics, temporary motor impairment, a black-and-white "
                    "mirror labyrinth, and escalating time pressure."
                ),
                "constraints": [
                    "The countdown must remain physically credible.",
                    "Exact timing is deferred to scene and shot planning.",
                    "Demian explicitly recovers and drags the seismic hammer.",
                    "The Mirror Labyrinth transitions into the lowest point.",
                    "The Mirror Room is the explicit Act 3 entry.",
                    "No physical external rescue occurs before lockdown termination.",
                ],
            },
        ],
        "controls": {
            "proposal_count": 5,
            "post_p10f_amendment": True,
            "original_story_bible_overwritten": False,
            "original_beat_sheet_overwritten": False,
            "database_mutation_performed": False,
            "automatic_canon_release_performed": False,
            "revised_story_authority_artifact_required": True,
            "revised_beat_sheet_required": True,
            "human_review_required_after_revision": True,
        },
    }

    revision_contract_payload = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "status": "ready_for_controlled_revision_request",
        "created_at": created_at,
        "project_id": PROJECT_ID,
        "project_slug": PROJECT_SLUG,
        "revision_authority": {
            "reviewer": REVIEWER,
            "review_decisions_filename": DECISIONS_FILENAME,
            "canon_amendments_filename": AMENDMENTS_FILENAME,
        },
        "input_artifact": {
            "filename": draft.name,
            "sha256": DRAFT_SHA256,
            "generation_run_id": GENERATION_RUN_ID,
            "immutable": True,
        },
        "required_revision_actions": [
            "Preserve the 44-beat foundation unless a change is explicitly required.",
            "Correct the 2385–2666 chronology and Demian's multi-era identity.",
            "Reframe Beat 003 as The Long Build.",
            "Separate public, private, author, character, and audience knowledge.",
            "Place Amusement Park in late Act 2B.",
            "Use Mirror Labyrinth as the lowest-point transition.",
            "Use Mirror Room as the explicit Act 3 entry.",
            "Increase the countdown and remove the sub-two-minute impossibility.",
            "Add Demian recovering and dragging the seismic hammer.",
            "Integrate controlled subjective first-person visual language.",
            "Preserve corruption-cause ambiguity in Beats 035 and 038.",
            "Add the open philosophical Epilogue.",
            "Normalize beats as Markdown level-two headings with ID and title.",
            "Replace 'schizophrenic AI entity' with "
            "'fractured dual-state AI entity'.",
            "Improve verified source locator granularity.",
            "Update fact classifications after approved amendments.",
            "Do not introduce Creator Credits, Tech Credits, or CanonFlow claim "
            "inside the narrative canon; those belong to the presentation contract.",
        ],
        "output_requirements": {
            "minimum_beat_entries": 44,
            "required_canon_decisions": [
                "YD-CANON-0001",
                "YD-CANON-0002",
                "YD-CANON-0003",
                "YD-CANON-0004",
                "YD-CANON-0005",
                "YD-CANON-0006",
                "YD-CANON-0007",
                "YD-CANON-0008",
                "YD-CANON-0009",
                "YD-CANON-0010",
                "YD-CANON-0011",
            ],
            "strict_validation_required": True,
            "human_review_required": True,
            "overwrite_original_draft": False,
            "database_access_allowed": False,
            "database_mutation_allowed": False,
            "automatic_canon_release_allowed": False,
        },
    }

    decisions_path = p10g / DECISIONS_FILENAME
    amendments_path = p10g / AMENDMENTS_FILENAME
    revision_contract_path = p10g / REVISION_CONTRACT_FILENAME
    checksum_path = p10g / CHECKSUM_FILENAME

    write_json(decisions_path, decision_payload)
    write_json(amendments_path, amendment_payload)
    write_json(revision_contract_path, revision_contract_payload)

    checksum_artifacts = [
        builder,
        decisions_path,
        amendments_path,
        revision_contract_path,
    ]

    checksum_lines = [
        f"{sha256(path)}  {path.name}"
        for path in checksum_artifacts
    ]

    checksum_path.write_text(
        "\n".join(checksum_lines) + "\n",
        encoding="utf-8",
    )

    print(f"Review items: {len(decisions)}")
    print(f"Approved items: {approved_count}")
    print(f"Needs-revision items: {needs_revision_count}")
    print("Canon amendment proposals: 5")
    print("Canon decisions: YD-CANON-0007..YD-CANON-0011")
    print("Final Beat Sheet disposition: needs_revision")
    print("Story Bible modified: False")
    print("Beat Sheet draft modified: False")
    print("Database mutation: False")
    print("Automatic canon release: False")
    print("P10G HUMAN REVIEW AUTHORITY PACKAGE: OK")


if __name__ == "__main__":
    main()
