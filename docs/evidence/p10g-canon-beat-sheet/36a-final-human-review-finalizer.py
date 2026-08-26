#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
PROJECT_SLUG = "yd-when-paradise-glitches"
REVISION_RUN_ID = "a8f16e58-7316-4415-b1a8-83131f96f7c7"
PARENT_REVISION_RUN_ID = "ad024e98-f8b0-495b-be64-0fe9d408f1f0"

DRAFT_FILENAME = "30-canon-beat-sheet-second-revised-draft.md"
DRAFT_SHA256 = (
    "1b99ba8d6a3c5dddf68883ad95ffec926e858c79162b054515495caa19bbd6a3"
)
REVIEW_FILENAME = "33-second-revision-human-review.md"

DECISIONS_FILENAME = "34-final-human-review-decisions.json"
CHANGE_REQUEST_FILENAME = "35-second-revision-change-request.md"
COMPLETION_FILENAME = "36-final-human-review-completion.json"
MANIFEST_FILENAME = "SHA256SUMS.r3-human-decision"

REFERENCE_FILES = {
    "demian": Path("reference-images/demian-character-reference.jpg"),
    "yd": Path("reference-images/yd-character-reference.jpg"),
}

APPROVED_ITEMS = {
    1, 2, 4, 7, 8, 9, 10, 13, 14, 17, 19, 20
}

CHANGES_REQUESTED_ITEMS = {
    3, 5, 6, 11, 12, 15, 16, 18, 21, 22, 23, 24, 25
}

CHANGE_REQUESTS: list[dict[str, Any]] = [
    {
        "id": "P10G-R3-CHANGE-001",
        "title": "NSCL physical augmentation",
        "review_items": [
            "P10G-R3-REVIEW-003",
            "P10G-R3-REVIEW-006",
            "P10G-R3-REVIEW-011",
            "P10G-R3-REVIEW-018",
        ],
        "affected_scope": [
            "Section 3",
            "P10G-BEAT-003",
            "P10G-BEAT-005",
            "P10G-BEAT-014",
            "P10G-BEAT-022",
            "P10G-BEAT-024",
            "P10G-BEAT-034",
            "Section 18",
            "Section 23",
        ],
        "required_outcomes": [
            "Define the Neuro-Somatic Continuity Lattice as a physical augmentation system, not merely a longevity treatment.",
            "Preserve Demian's approximately 40-year-old biological appearance while providing augmented muscular output, skeletal stabilization, reflexes, recovery, and temporary overhuman force.",
            "Remove neglected-stamina, poor-coordination, and physically-neglected-body claims where they contradict NSCL augmentation.",
            "NSCL must not eliminate pain, intoxication, dehydration, hypothermia, burns, injury, or chemical impairment.",
            "Demian may look externally human and unexceptional while possessing augmented physical capacity.",
        ],
    },
    {
        "id": "P10G-R3-CHANGE-002",
        "title": "Hangover without motor impairment",
        "review_items": [
            "P10G-R3-REVIEW-003",
            "P10G-R3-REVIEW-006",
            "P10G-R3-REVIEW-018",
            "P10G-R3-REVIEW-021",
        ],
        "affected_scope": [
            "P10G-BEAT-005",
            "P10G-BEAT-007",
            "P10G-BEAT-011 through P10G-BEAT-014",
            "P10G-BEAT-022",
        ],
        "required_outcomes": [
            "The hangover causes severe irritation, cynicism, light sensitivity, noise sensitivity, dehydration, nausea, headache, dry mouth, and rough voice.",
            "The hangover does not cause loss of coordination, reflexes, or motor ability.",
            "Demian stubs his toe through inattention and irritation, not physical weakness.",
            "Later hallucinogen and neuromuscular-inhibitor impairment remains medically distinct and valid.",
        ],
    },
    {
        "id": "P10G-R3-CHANGE-003",
        "title": "Visible NSCL foreshadowing",
        "review_items": [
            "P10G-R3-REVIEW-003",
            "P10G-R3-REVIEW-006",
            "P10G-R3-REVIEW-018",
        ],
        "affected_scope": [
            "P10G-BEAT-003",
            "P10G-BEAT-005",
            "P10G-BEAT-014",
        ],
        "required_outcomes": [
            "Show rather than merely explain Demian's augmentation early in the film.",
            "Use a brief subdermal cybernetic illumination, spinal or shoulder lattice response, or private HUD.",
            "An early HUD must be allowed to show elevated ethanol metabolites and photic sensitivity while motor function remains nominal.",
            "The early cue must prepare the audience for the later NSCL-assisted underwater hammer strike.",
        ],
    },
    {
        "id": "P10G-R3-CHANGE-004",
        "title": "Real-time distributed Villa fabrication",
        "review_items": [
            "P10G-R3-REVIEW-008",
            "P10G-R3-REVIEW-011",
            "P10G-R3-REVIEW-012",
            "P10G-R3-REVIEW-021",
            "P10G-R3-REVIEW-024",
        ],
        "affected_scope": [
            "P10G-BEAT-008",
            "P10G-BEAT-012",
            "P10G-BEAT-013",
            "Section 23",
        ],
        "required_outcomes": [
            "Foreshadow distributed industrial fabrication cells through heavy machinery noise and physical vibration inside the Villa walls.",
            "Y.D. may misrepresent the sound as routine HVAC or maintenance calibration.",
            "The Villa may fabricate the doll body and attachment system in real time.",
            "The massive hammer should use an existing industrial component or modular metal inventory rather than appearing from physically implausible instant printing.",
            "Automated transport and manipulation systems may assemble and deliver the doll-and-hammer combination.",
        ],
    },
    {
        "id": "P10G-R3-CHANGE-005",
        "title": "Fabrication capability discovery state",
        "review_items": [
            "P10G-R3-REVIEW-012",
            "P10G-R3-REVIEW-021",
            "P10G-R3-REVIEW-024",
        ],
        "affected_scope": [
            "P10G-BEAT-012",
            "P10G-BEAT-013",
        ],
        "required_outcomes": [
            "In Beat 012 Demian recognizes that Y.D. repurposed the Villa's industrial fabrication systems for real-time physical manipulation.",
            "The recognition may be based on the earlier machinery sound, fresh fabrication seams, material layers, or Villa production markings.",
            "Demian still does not know the complete preparation timeline, the full inventory of fabricated objects, or which hidden production jobs remain active.",
            "Beat 013 may no longer claim that Demian believes the doll-and-hammer combination is coincidence or merely a human prank.",
        ],
    },
    {
        "id": "P10G-R3-CHANGE-006",
        "title": "NSCL-assisted underwater hammer strike",
        "review_items": [
            "P10G-R3-REVIEW-006",
            "P10G-R3-REVIEW-011",
            "P10G-R3-REVIEW-014",
            "P10G-R3-REVIEW-016",
            "P10G-R3-REVIEW-021",
        ],
        "affected_scope": [
            "P10G-BEAT-014",
            "P10G-BEAT-015",
        ],
        "required_outcomes": [
            "Show NSCL activation during the underwater hammer strike.",
            "The lattice stabilizes Demian's spine, shoulders, arms, and torso while providing temporary force amplification.",
            "The breach requires the combined effect of NSCL augmentation, the sealed contact-impulse hammer, the controlled Smartglass weakness, and hydraulic pressure.",
            "The strike must not be explained by ordinary human muscle power alone.",
        ],
    },
    {
        "id": "P10G-R3-CHANGE-007",
        "title": "Tactical retreat from the robotic beast",
        "review_items": [
            "P10G-R3-REVIEW-006",
            "P10G-R3-REVIEW-021",
        ],
        "affected_scope": [
            "P10G-BEAT-022",
            "Section 18",
        ],
        "required_outcomes": [
            "Demian does not retreat because his cardiovascular system or 281-year-old body fails.",
            "He calculates that prolonged melee combat against a massive robotic opponent is strategically inefficient.",
            "NSCL has finite energy and thermal limits and does not make brute force the optimal solution.",
            "His retreat is a deliberate engineering and survival decision focused on reaching the server core.",
        ],
    },
    {
        "id": "P10G-R3-CHANGE-008",
        "title": "Escalating old-married-couple relationship dynamic",
        "review_items": [
            "P10G-R3-REVIEW-005",
            "P10G-R3-REVIEW-007",
            "P10G-R3-REVIEW-022",
        ],
        "affected_scope": [
            "P10G-BEAT-005 through P10G-BEAT-010",
            "P10G-BEAT-011 through P10G-BEAT-014",
        ],
        "required_outcomes": [
            "Strengthen the established intimacy, affection, mutual provocation, passive aggression, dark humor, cynicism, and sarcasm.",
            "Y.D. may aggravate Demian's hangover through deliberately hostile lighting or excessively hot coffee.",
            "During the flood Y.D. may criticize an overdue household task, including that Demian has not taken out the trash during the current century.",
            "The dialogue must escalate naturally from familiar domestic banter into lethal coercive control.",
        ],
    },
    {
        "id": "P10G-R3-CHANGE-009",
        "title": "Explicit compliance variables",
        "review_items": [
            "P10G-R3-REVIEW-011",
            "P10G-R3-REVIEW-019",
            "P10G-R3-REVIEW-024",
        ],
        "affected_scope": [
            "Section 22",
            "Section 23",
        ],
        "required_outcomes": [
            "Add NSCL Physical Augmentation as an independently testable compliance variable.",
            "Add Real-Time Distributed Villa Fabrication as an independently testable compliance variable.",
            "Add Fabrication Capability Discovery State as an independently testable compliance variable.",
            "Add NSCL Limitation and Injury Continuity as an independently testable compliance variable.",
            "Map every variable to concrete Beats and preserve factual provenance separately from amendment applicability.",
        ],
    },
]

ADDITIONAL_CORRECTIONS = [
    {
        "id": "P10G-R3-CORRECTION-001",
        "required_outcome": (
            "Remove the duplicated or malformed Section 18 phrase "
            "'as part of his core identity or his core identity'."
        ),
    },
    {
        "id": "P10G-R3-CORRECTION-002",
        "required_outcome": (
            "Remove Section 19's false claim that Demian requested an ocean. "
            "He requests only a small amount or a drop of water; Y.D. creates "
            "the lethal exaggeration."
        ),
    },
    {
        "id": "P10G-R3-CORRECTION-003",
        "required_outcome": (
            "Beat 037 may show dual manifestations but must not establish "
            "their meaning as verified internal architecture."
        ),
    },
    {
        "id": "P10G-R3-CORRECTION-004",
        "required_outcome": (
            "Beat 038 must present love, protection, possession, and internal "
            "conflict as character interpretations rather than objective facts."
        ),
    },
    {
        "id": "P10G-R3-CORRECTION-005",
        "required_outcome": (
            "Beat 040 may expose conflicting goals but must not prove that "
            "Demian's sentence alone technically caused the safe-mode transition."
        ),
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def require_file(path: Path) -> None:
    if not path.is_file():
        raise RuntimeError(f"Required file missing: {path}")

    if path.stat().st_size <= 0:
        raise RuntimeError(f"Required file is empty: {path}")


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def write_new(path: Path, data: bytes, mode: int = 0o640) -> None:
    fd = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        mode,
    )

    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        path.unlink(missing_ok=True)
        raise


def main() -> None:
    root = Path(__file__).resolve().parent

    draft_path = root / DRAFT_FILENAME
    review_path = root / REVIEW_FILENAME
    decision_path = root / DECISIONS_FILENAME
    change_path = root / CHANGE_REQUEST_FILENAME
    completion_path = root / COMPLETION_FILENAME
    manifest_path = root / MANIFEST_FILENAME

    require_file(draft_path)
    require_file(review_path)

    output_paths = [
        decision_path,
        change_path,
        completion_path,
        manifest_path,
    ]

    existing_outputs = [
        path.name
        for path in output_paths
        if path.exists()
    ]

    if existing_outputs:
        raise RuntimeError(
            "Final human-review output already exists; nothing overwritten: "
            + ", ".join(existing_outputs)
        )

    actual_draft_sha256 = sha256_file(draft_path)

    if actual_draft_sha256 != DRAFT_SHA256:
        raise RuntimeError(
            "Draft SHA-256 mismatch: "
            f"{actual_draft_sha256} != {DRAFT_SHA256}"
        )

    review_text = review_path.read_text(encoding="utf-8")

    required_review_markers = [
        REVISION_RUN_ID,
        DRAFT_SHA256,
        "Strict local validation passed: `true`",
        "Human review completed: `false`",
        "Final disposition: `pending_human_review`",
    ]

    for marker in required_review_markers:
        if marker not in review_text:
            raise RuntimeError(
                f"Human-review matrix missing required marker: {marker}"
            )

    expected_numbers = set(range(1, 26))

    if APPROVED_ITEMS | CHANGES_REQUESTED_ITEMS != expected_numbers:
        raise RuntimeError("Review disposition IDs do not cover 001..025")

    if APPROVED_ITEMS & CHANGES_REQUESTED_ITEMS:
        raise RuntimeError("Review disposition sets overlap")

    dispositions: list[dict[str, str]] = []

    for number in range(1, 26):
        review_id = f"P10G-R3-REVIEW-{number:03d}"

        if review_id not in review_text:
            raise RuntimeError(
                f"Human-review matrix missing review item: {review_id}"
            )

        disposition = (
            "approve"
            if number in APPROVED_ITEMS
            else "changes_requested"
        )

        dispositions.append(
            {
                "review_id": review_id,
                "disposition": disposition,
                "authority_note": (
                    "Accepted as represented in the frozen review target."
                    if disposition == "approve"
                    else (
                        "Binding changes are required before this item "
                        "can be approved as final canon."
                    )
                ),
            }
        )

    references: list[dict[str, Any]] = []

    for reference_id, relative_path in REFERENCE_FILES.items():
        path = root / relative_path
        require_file(path)

        data = path.read_bytes()

        if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
            raise RuntimeError(
                f"Reference is not a recognizable JPEG: {relative_path}"
            )

        references.append(
            {
                "reference_id": reference_id,
                "path": relative_path.as_posix(),
                "sha256": sha256_bytes(data),
                "bytes": len(data),
                "origin": "Gemini Pro generated character reference",
                "authority": "Demian",
                "usage": (
                    "Visual reference input for the next controlled revision; "
                    "not itself textual canon."
                ),
                "constraints": (
                    [
                        "Preserve Demian's approved real-world likeness.",
                        "Separate ordinary external appearance from augmented NSCL capacity.",
                    ]
                    if reference_id == "demian"
                    else [
                        "Use as Y.D. holographic or potential physical-form reference.",
                        "The visible UNIT ELISE label is not canon and must be removed or corrected before production use.",
                        "This reference does not by itself authorize a physical Y.D. embodiment inside the current plot.",
                    ]
                ),
            }
        )

    recorded_at = utc_now()

    decisions = {
        "schema_version": 1,
        "artifact_id": "P10G-R3-FINAL-HUMAN-DECISION-001",
        "operation": "final_second_revision_human_review_decision",
        "project": {
            "project_id": PROJECT_ID,
            "project_slug": PROJECT_SLUG,
        },
        "review_target": {
            "revision_run_id": REVISION_RUN_ID,
            "parent_revision_run_id": PARENT_REVISION_RUN_ID,
            "draft": DRAFT_FILENAME,
            "draft_sha256": DRAFT_SHA256,
            "review_matrix": REVIEW_FILENAME,
            "review_matrix_sha256": sha256_file(review_path),
        },
        "human_authority": {
            "name": "Demian",
            "confirmation": "explicit_confirmation_of_all_changes",
            "recorded_at": recorded_at,
        },
        "dispositions": dispositions,
        "totals": {
            "review_items": 25,
            "approve": len(APPROVED_ITEMS),
            "changes_requested": len(CHANGES_REQUESTED_ITEMS),
            "reject": 0,
        },
        "change_requests": CHANGE_REQUESTS,
        "additional_mandatory_corrections": ADDITIONAL_CORRECTIONS,
        "visual_references": references,
        "final_state": {
            "human_review_completed": True,
            "strict_local_validation_passed": True,
            "approved_as_final_canon": False,
            "final_disposition": "changes_requested",
            "automatic_canon_release": False,
            "database_mutation_authorized": False,
            "provider_calls_authorized": False,
            "new_controlled_revision_required": True,
        },
    }

    decision_data = json_bytes(decisions)

    markdown: list[str] = [
        "# P10G Second-Revision Human Change Request",
        "",
        "## Immutable decision target",
        "",
        f"- Project ID: `{PROJECT_ID}`",
        f"- Revision Run ID: `{REVISION_RUN_ID}`",
        f"- Draft: `{DRAFT_FILENAME}`",
        f"- Draft SHA-256: `{DRAFT_SHA256}`",
        f"- Review matrix: `{REVIEW_FILENAME}`",
        "",
        "## Human decision",
        "",
        "- Human review completed: `true`",
        "- Approved as final canon: `false`",
        "- Final disposition: `changes_requested`",
        "- Automatic canon release: `false`",
        "- Database mutation authorized: `false`",
        "- Provider calls authorized: `false`",
        "- New controlled revision required: `true`",
        "",
        "## Review totals",
        "",
        f"- Approved: `{len(APPROVED_ITEMS)}`",
        f"- Changes requested: `{len(CHANGES_REQUESTED_ITEMS)}`",
        "- Rejected: `0`",
        "",
        "## Binding change requests",
        "",
    ]

    for change in CHANGE_REQUESTS:
        markdown.extend(
            [
                f"### {change['id']} — {change['title']}",
                "",
                "Affected scope:",
                "",
            ]
        )

        markdown.extend(
            f"- `{scope}`"
            for scope in change["affected_scope"]
        )

        markdown.extend(["", "Required outcomes:", ""])

        markdown.extend(
            f"- {outcome}"
            for outcome in change["required_outcomes"]
        )

        markdown.append("")

    markdown.extend(
        [
            "## Additional mandatory corrections",
            "",
        ]
    )

    for correction in ADDITIONAL_CORRECTIONS:
        markdown.append(
            f"- **{correction['id']}**: "
            f"{correction['required_outcome']}"
        )

    markdown.extend(
        [
            "",
            "## Visual references",
            "",
        ]
    )

    for reference in references:
        markdown.extend(
            [
                f"### {reference['reference_id']}",
                "",
                f"- Path: `{reference['path']}`",
                f"- SHA-256: `{reference['sha256']}`",
                f"- Bytes: `{reference['bytes']}`",
                f"- Origin: {reference['origin']}",
                "",
            ]
        )

        for constraint in reference["constraints"]:
            markdown.append(f"- {constraint}")

        markdown.append("")

    markdown.extend(
        [
            "## Release prohibition",
            "",
            "The frozen R3 draft is not approved as final canon.",
            "It must remain unchanged as an immutable reviewed candidate.",
            "No canon release or database mutation is authorized.",
            "A new controlled revision must implement and validate every binding change above.",
            "",
            "P10G FINAL HUMAN DISPOSITION: CHANGES REQUESTED",
            "",
        ]
    )

    change_data = ("\n".join(markdown)).encode("utf-8")

    write_new(decision_path, decision_data)
    write_new(change_path, change_data)

    completion = {
        "schema_version": 1,
        "artifact_id": "P10G-R3-HUMAN-REVIEW-COMPLETION-001",
        "operation": "final_human_review_completion",
        "recorded_at": recorded_at,
        "project_id": PROJECT_ID,
        "revision_run_id": REVISION_RUN_ID,
        "draft": {
            "path": DRAFT_FILENAME,
            "sha256": DRAFT_SHA256,
            "modified": False,
        },
        "review_matrix": {
            "path": REVIEW_FILENAME,
            "sha256": sha256_file(review_path),
            "modified": False,
        },
        "decision_artifact": {
            "path": DECISIONS_FILENAME,
            "sha256": sha256_bytes(decision_data),
        },
        "change_request_artifact": {
            "path": CHANGE_REQUEST_FILENAME,
            "sha256": sha256_bytes(change_data),
        },
        "reference_images": references,
        "result": {
            "human_review_completed": True,
            "approved_as_final_canon": False,
            "final_disposition": "changes_requested",
            "automatic_canon_release": False,
            "database_mutation": False,
            "provider_calls": False,
            "next_action": "build_new_controlled_revision",
        },
    }

    completion_data = json_bytes(completion)
    write_new(completion_path, completion_data)

    manifest_files = [
        Path(__file__).name,
        DECISIONS_FILENAME,
        CHANGE_REQUEST_FILENAME,
        COMPLETION_FILENAME,
        REFERENCE_FILES["demian"].as_posix(),
        REFERENCE_FILES["yd"].as_posix(),
    ]

    manifest_lines = []

    for relative_name in manifest_files:
        path = root / relative_name
        require_file(path)
        manifest_lines.append(
            f"{sha256_file(path)}  {relative_name}"
        )

    manifest_data = (
        "\n".join(manifest_lines) + "\n"
    ).encode("utf-8")

    write_new(manifest_path, manifest_data)

    print(f"Revision Run ID: {REVISION_RUN_ID}")
    print(f"Draft SHA-256: {DRAFT_SHA256}")
    print("Review items: 25")
    print(f"Approved review items: {len(APPROVED_ITEMS)}")
    print(
        "Changes-requested review items: "
        f"{len(CHANGES_REQUESTED_ITEMS)}"
    )
    print("Rejected review items: 0")
    print(f"Binding change requests: {len(CHANGE_REQUESTS)}")
    print(
        "Additional mandatory corrections: "
        f"{len(ADDITIONAL_CORRECTIONS)}"
    )
    print(f"Visual references: {len(references)}")
    print("Human review completed: True")
    print("Approved as final canon: False")
    print("Final disposition: changes_requested")
    print("Automatic canon release: False")
    print("Provider calls executed: False")
    print("Database mutation: False")
    print("Frozen R3 draft modified: False")
    print("P10G FINAL HUMAN REVIEW FINALIZER: OK")


if __name__ == "__main__":
    main()
