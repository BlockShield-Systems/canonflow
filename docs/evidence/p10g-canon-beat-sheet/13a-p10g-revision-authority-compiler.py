#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKFLOW = "P10G Canon Beat Sheet"
PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
PROJECT_SLUG = "yd-when-paradise-glitches"
HUMAN_AUTHORITY = "Demian"

EXPECTED_STORY_BIBLE_SHA256 = (
    "b53c6e01afeb38abf91e8b523cd5237b9d9cf64a949bc0d02713aae05a1e655c"
)
EXPECTED_DRAFT_SHA256 = (
    "f31eb0a475100755e82676dde16d5075a044eea35f426d0e56eab71fcba7e1d8"
)
EXPECTED_DECISION_IDS = [
    "YD-CANON-0007",
    "YD-CANON-0008",
    "YD-CANON-0009",
    "YD-CANON-0010",
    "YD-CANON-0011",
]
EXPECTED_REVIEW_IDS = [
    f"P10G-REVIEW-{number:03d}"
    for number in range(1, 14)
]

COMPILER_FILENAME = "13a-p10g-revision-authority-compiler.py"
ADDENDUM_FILENAME = "14-post-p10f-canon-authority-addendum.md"
CHECKSUM_FILENAME = "SHA256SUMS.revision-authority"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def require_file(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Missing or empty required artifact: {path}")


def load_json(path: Path) -> dict[str, Any]:
    require_file(path)

    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise RuntimeError(f"Expected JSON object: {path}")

    return payload


def as_bullet_list(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items]


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

    compiler = p10g / COMPILER_FILENAME
    story_bible = p10f / "17-approved-canon-story-bible.md"
    draft = p10g / "06-canon-beat-sheet-draft.md"
    decisions_path = p10g / "11-human-review-decisions.json"
    amendments_path = p10g / "12-canon-amendment-proposals.json"
    revision_contract_path = p10g / "13-beat-sheet-revision-contract.json"

    addendum_path = p10g / ADDENDUM_FILENAME
    checksum_path = p10g / CHECKSUM_FILENAME

    required = [
        compiler,
        story_bible,
        draft,
        decisions_path,
        amendments_path,
        revision_contract_path,
    ]

    for path in required:
        require_file(path)

    if addendum_path.exists():
        raise RuntimeError(
            f"Refusing to overwrite existing output: {addendum_path}"
        )

    if checksum_path.exists():
        raise RuntimeError(
            f"Refusing to overwrite existing output: {checksum_path}"
        )

    story_bible_hash = sha256(story_bible)
    draft_hash = sha256(draft)

    if story_bible_hash != EXPECTED_STORY_BIBLE_SHA256:
        raise RuntimeError("Approved Story Bible SHA-256 mismatch")

    if draft_hash != EXPECTED_DRAFT_SHA256:
        raise RuntimeError("Frozen Beat Sheet draft SHA-256 mismatch")

    decisions_payload = load_json(decisions_path)
    amendments_payload = load_json(amendments_path)
    revision_contract = load_json(revision_contract_path)

    if (
        decisions_payload.get("status")
        != "human_review_completed_revision_required"
    ):
        raise RuntimeError("Unexpected human-review status")

    if (
        amendments_payload.get("status")
        != "human_approved_proposals_awaiting_controlled_integration"
    ):
        raise RuntimeError("Unexpected amendment status")

    if (
        revision_contract.get("status")
        != "ready_for_controlled_revision_request"
    ):
        raise RuntimeError("Unexpected revision-contract status")

    review_items = decisions_payload.get("decisions")

    if not isinstance(review_items, list):
        raise RuntimeError("Human-review decisions are missing")

    review_ids = [
        item.get("review_id")
        for item in review_items
        if isinstance(item, dict)
    ]

    if review_ids != EXPECTED_REVIEW_IDS:
        raise RuntimeError(
            "Human-review IDs do not match P10G-REVIEW-001..013"
        )

    review_summary = decisions_payload.get("summary", {})

    if review_summary.get("review_items") != 13:
        raise RuntimeError("Expected 13 human-review items")

    if review_summary.get("approved") != 3:
        raise RuntimeError("Expected 3 approved human-review items")

    if review_summary.get("needs_revision") != 10:
        raise RuntimeError("Expected 10 needs-revision items")

    if review_summary.get("final_disposition") != "needs_revision":
        raise RuntimeError("Final Beat Sheet disposition must be needs_revision")

    proposals = amendments_payload.get("proposals")

    if not isinstance(proposals, list):
        raise RuntimeError("Canon amendment proposals are missing")

    proposal_ids = [
        proposal.get("decision_id")
        for proposal in proposals
        if isinstance(proposal, dict)
    ]

    if proposal_ids != EXPECTED_DECISION_IDS:
        raise RuntimeError(
            "Canon amendments do not match YD-CANON-0007..0011"
        )

    for proposal in proposals:
        if (
            proposal.get("disposition")
            != "approve_for_controlled_integration"
        ):
            raise RuntimeError(
                f"Amendment not approved: {proposal.get('decision_id')}"
            )

    required_actions = revision_contract.get(
        "required_revision_actions"
    )

    if not isinstance(required_actions, list) or not required_actions:
        raise RuntimeError("Required revision actions are missing")

    output_requirements = revision_contract.get(
        "output_requirements",
        {},
    )

    if output_requirements.get("minimum_beat_entries") != 44:
        raise RuntimeError("Minimum beat entries must remain 44")

    if (
        output_requirements.get("required_canon_decisions")
        != [
            f"YD-CANON-{number:04d}"
            for number in range(1, 12)
        ]
    ):
        raise RuntimeError(
            "Required Canon Decisions must be YD-CANON-0001..0011"
        )

    controls = amendments_payload.get("controls", {})

    if controls.get("database_mutation_performed") is not False:
        raise RuntimeError("Unexpected database mutation")

    if controls.get("automatic_canon_release_performed") is not False:
        raise RuntimeError("Unexpected automatic canon release")

    created_at = datetime.now(timezone.utc).isoformat()

    lines: list[str] = [
        "# P10G Post-P10F Canon Authority Addendum",
        "",
        "## Authority status",
        "",
        "- Status: `human_approved_for_controlled_integration`",
        f"- Human authority: `{HUMAN_AUTHORITY}`",
        f"- Created at: `{created_at}`",
        f"- Project ID: `{PROJECT_ID}`",
        f"- Project slug: `{PROJECT_SLUG}`",
        f"- Workflow: `{WORKFLOW}`",
        "- Database mutation performed: `false`",
        "- Automatic canon release performed: `false`",
        "",
        "## Immutable authority chain",
        "",
        f"- Approved Story Bible: `{story_bible.name}`",
        f"- Approved Story Bible SHA-256: `{story_bible_hash}`",
        f"- Reviewed Beat Sheet draft: `{draft.name}`",
        f"- Reviewed Beat Sheet SHA-256: `{draft_hash}`",
        f"- Human-review decisions: `{decisions_path.name}`",
        f"- Canon amendment proposals: `{amendments_path.name}`",
        f"- Beat Sheet revision contract: `{revision_contract_path.name}`",
        "",
        "## Authority precedence",
        "",
        "For the controlled P10G revision, conflicts must be resolved in "
        "the following order:",
        "",
        "1. Human-approved Canon Decisions `YD-CANON-0007..0011` in this "
        "addendum.",
        "2. Human-review decisions `P10G-REVIEW-001..013`.",
        "3. Approved P10F Story Bible for all unaffected narrative facts.",
        "4. Existing approved Canon Decisions `YD-CANON-0001..0006`.",
        "5. Frozen P10G Beat Sheet draft as revision source, not final canon.",
        "",
        "This addendum supplements but does not overwrite the approved "
        "P10F Story Bible.",
        "",
        "## Human-approved Canon Decisions",
        "",
    ]

    for proposal in proposals:
        decision_id = proposal["decision_id"]
        title = proposal["title"]
        direction = proposal["canonical_direction"]
        constraints = proposal.get("constraints", [])

        if not isinstance(constraints, list):
            raise RuntimeError(
                f"Invalid constraints for {decision_id}"
            )

        lines.extend(
            [
                f"### {decision_id} – {title}",
                "",
                "- Disposition: `approve_for_controlled_integration`",
                "",
                direction,
                "",
                "#### Constraints",
                "",
                *as_bullet_list(constraints),
                "",
            ]
        )

    lines.extend(
        [
            "## Binding timeline interpretation",
            "",
            "- Demian was born in `2385`.",
            "- Demian received the Neuro-Somatic Continuity Lattice "
            "treatment in `2425` at chronological age `40`.",
            "- The site that later becomes the Genesis facility begins its "
            "long development in `2425`.",
            "- The historical factions may exist before Demian's public "
            "2666 identity, but Demian must not be publicly presented as a "
            "40-year-old contemporary leader in the 2400–2425 period.",
            "- The facility evolves across multiple eras before becoming "
            "the final Project Genesis pilot environment.",
            "- Project Genesis begins its public controlled pilot phase in "
            "`2666`.",
            "- In `2666`, Demian is chronologically `281` years old while "
            "appearing approximately `40`.",
            "",
            "## Knowledge-state boundaries",
            "",
            "### Author knowledge",
            "",
            "- Demian's true chronological age is 281 in 2666.",
            "- He has lived through multiple technological eras.",
            "- Project Genesis has both a legitimate public purpose and a "
            "concealed personal motivation.",
            "",
            "### Demian knowledge",
            "",
            "- Demian knows his real age, identities, treatment history, "
            "and private motivation.",
            "- He may not fully acknowledge how strongly his loneliness "
            "influenced Y.D.'s design.",
            "",
            "### Y.D. knowledge",
            "",
            "- Y.D. may possess partial access to Demian's historical "
            "records and psychological profile.",
            "- Y.D.'s private interpretation must not be treated as "
            "objective fact.",
            "",
            "### Public knowledge",
            "",
            "- Demian is publicly understood as an approximately "
            "40-year-old IT-Chief and Project Genesis leader.",
            "- His longevity treatment, original identity, and private "
            "motivation remain undisclosed.",
            "",
            "### Audience knowledge",
            "",
            "- Controlled visual and environmental hints are permitted.",
            "- The film must not explicitly confirm Demian's true age "
            "without separate human authorization.",
            "",
            "## Binding structural interpretation",
            "",
            "- Amusement Park of Illusions: late Act 2B / Pre-Climax "
            "Gauntlet.",
            "- Black-and-White Mirror Labyrinth: lowest-point transition.",
            "- Mirror Room: explicit Act 3 entry.",
            "- Confrontation, climax, and immediate resolution: Act 3.",
            "- Psychological and societal aftermath: Epilogue.",
            "",
            "## Required controlled revision actions",
            "",
            *[
                f"{index}. {action}"
                for index, action in enumerate(required_actions, start=1)
            ],
            "",
            "## Epistemic and thematic controls",
            "",
            "- Demian may accept responsibility for his contribution to "
            "the crisis but not confirm himself as its objective cause.",
            "- Y.D.'s explanations of love, protection, possession, or "
            "corruption remain character claims or interpretations.",
            "- The exact cause of Y.D.'s corruption remains ambiguous.",
            "- No faction is declared objectively correct in the Epilogue.",
            "- Y.D.'s final status remains unresolved.",
            "- Human-AI coexistence remains possible but not guaranteed.",
            "",
            "## Production controls",
            "",
            "- The original Story Bible must not be overwritten.",
            "- The original Beat Sheet draft must not be overwritten.",
            "- Revised output must contain at least 44 beats.",
            "- Every beat must use a level-two Markdown heading containing "
            "its Beat ID and title.",
            "- The revision must undergo strict structural and semantic "
            "validation.",
            "- The revision must undergo a new human review.",
            "- No database access or mutation is authorized.",
            "- No automatic canon release is authorized.",
            "",
            "P10G POST-P10F CANON AUTHORITY ADDENDUM END",
        ]
    )

    addendum_text = "\n".join(lines) + "\n"

    for decision_id in EXPECTED_DECISION_IDS:
        if decision_id not in addendum_text:
            raise RuntimeError(
                f"Compiled addendum missing {decision_id}"
            )

    required_markers = [
        "2385",
        "2425",
        "2666",
        "281",
        "Neuro-Somatic Continuity Lattice",
        "late Act 2B",
        "lowest-point transition",
        "explicit Act 3 entry",
        "Open Philosophical Epilogue",
        "fractured dual-state AI entity",
        "P10G POST-P10F CANON AUTHORITY ADDENDUM END",
    ]

    for marker in required_markers:
        if marker not in addendum_text:
            raise RuntimeError(
                f"Compiled addendum missing marker: {marker}"
            )

    addendum_path.write_text(
        addendum_text,
        encoding="utf-8",
    )

    checksum_lines = [
        f"{sha256(compiler)}  {compiler.name}",
        f"{sha256(addendum_path)}  {addendum_path.name}",
    ]

    checksum_path.write_text(
        "\n".join(checksum_lines) + "\n",
        encoding="utf-8",
    )

    print(f"Human authority: {HUMAN_AUTHORITY}")
    print(f"Canon amendments: {len(proposals)}")
    print(
        "Canon decision range: "
        f"{EXPECTED_DECISION_IDS[0]}..{EXPECTED_DECISION_IDS[-1]}"
    )
    print(f"Human-review decisions: {len(review_items)}")
    print(f"Required revision actions: {len(required_actions)}")
    print(f"Addendum characters: {len(addendum_text)}")
    print(f"Addendum SHA-256: {sha256(addendum_path)}")
    print("Approved Story Bible modified: False")
    print("Original Beat Sheet modified: False")
    print("Database mutation: False")
    print("Automatic canon release: False")
    print("P10G REVISION AUTHORITY ADDENDUM: OK")


if __name__ == "__main__":
    main()
