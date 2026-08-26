#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKFLOW = "P10G Canon Beat Sheet"
OPERATION = "strict_revised_beat_sheet_validation"
HUMAN_AUTHORITY = "Demian"

EXPECTED_REVISION_RUN_ID = "ad024e98-f8b0-495b-be64-0fe9d408f1f0"
EXPECTED_PARENT_RUN_ID = "002a27d3-a414-4a25-b21e-d3c924b2a391"
EXPECTED_REVISED_SHA256 = (
    "5e5db9a12e4f87dfa457be414fcc3b14f6ac565ff5e71a3b40ca4c8a3e89c6d0"
)
EXPECTED_ORIGINAL_SHA256 = (
    "f31eb0a475100755e82676dde16d5075a044eea35f426d0e56eab71fcba7e1d8"
)
EXPECTED_STORY_BIBLE_SHA256 = (
    "b53c6e01afeb38abf91e8b523cd5237b9d9cf64a949bc0d02713aae05a1e655c"
)

EXPECTED_CHARACTERS = 98_355
EXPECTED_BEAT_COUNT = 44
EXPECTED_SECTION_COUNT = 24
EXPECTED_END_MARKER = "P10G CANON BEAT SHEET REVISED DRAFT END"

VALIDATOR_FILENAME = "20a-canon-beat-sheet-revision-validator.py"
DRAFT_FILENAME = "19-canon-beat-sheet-revised-draft.md"
SUMMARY_FILENAME = "20-beat-sheet-revision-summary.json"
VALIDATION_FILENAME = "21-canon-beat-sheet-revision-validation.json"
REVIEW_FILENAME = "22-canon-beat-sheet-revision-human-review.md"

EXPECTED_BEAT_IDS = [
    f"P10G-BEAT-{number:03d}"
    for number in range(1, 45)
]
EXPECTED_CANON_IDS = [
    f"YD-CANON-{number:04d}"
    for number in range(1, 12)
]
AMENDMENT_IDS = [
    f"YD-CANON-{number:04d}"
    for number in range(7, 12)
]

BEAT_FIELDS = [
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


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def field_pattern(field: str) -> re.Pattern[str]:
    return re.compile(
        rf"^\s*[-*]\s+\*{{0,2}}{re.escape(field)}\*{{0,2}}\s*:"
        rf"\s*(.*?)\s*$",
        flags=re.MULTILINE | re.IGNORECASE,
    )


def extract_blocks(
    text: str,
) -> list[dict[str, str]]:
    pattern = re.compile(
        r"^##\s+(P10G-BEAT-\d{3})\s+[–-]\s+(.+?)\s*$",
        flags=re.MULTILINE,
    )
    matches = list(pattern.finditer(text))
    blocks: list[dict[str, str]] = []

    for index, match in enumerate(matches):
        start = match.start()
        end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(text)
        )

        blocks.append(
            {
                "beat_id": match.group(1),
                "title": match.group(2).strip(),
                "body": text[start:end],
            }
        )

    return blocks


def field_value(block: str, field: str) -> str | None:
    matches = field_pattern(field).findall(block)

    if len(matches) != 1:
        return None

    value = matches[0].strip()

    return value if value else None


def add_check(
    checks: list[dict[str, Any]],
    check_id: str,
    subject: str,
    passed: bool,
    evidence: Any,
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "subject": subject,
            "passed": passed,
            "evidence": evidence,
        }
    )


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

    validator = p10g / VALIDATOR_FILENAME
    revised_draft = p10g / DRAFT_FILENAME
    revision_summary = p10g / SUMMARY_FILENAME
    revision_contract = (
        p10g / "15-beat-sheet-revision-generation-contract.json"
    )
    review_decisions = p10g / "11-human-review-decisions.json"
    amendments = p10g / "12-canon-amendment-proposals.json"
    authority_addendum = (
        p10g / "14-post-p10f-canon-authority-addendum.md"
    )
    original_draft = p10g / "06-canon-beat-sheet-draft.md"
    story_bible = p10f / "17-approved-canon-story-bible.md"

    validation_output = p10g / VALIDATION_FILENAME
    review_output = p10g / REVIEW_FILENAME

    required = [
        validator,
        revised_draft,
        revision_summary,
        revision_contract,
        review_decisions,
        amendments,
        authority_addendum,
        original_draft,
        story_bible,
    ]

    for path in required:
        require_file(path)

    existing_outputs = [
        path.name
        for path in [validation_output, review_output]
        if path.exists()
    ]

    if existing_outputs:
        raise RuntimeError(
            "Refusing to overwrite existing validation outputs: "
            + ", ".join(existing_outputs)
        )

    text = revised_draft.read_text(encoding="utf-8")
    lower = text.lower()

    summary = load_json(revision_summary)
    contract = load_json(revision_contract)
    decisions = load_json(review_decisions)
    amendment_payload = load_json(amendments)
    addendum_text = authority_addendum.read_text(encoding="utf-8")

    blocks = extract_blocks(text)
    blocks_by_id = {
        block["beat_id"]: block
        for block in blocks
    }

    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "P10G-R2-VAL-001",
        "Revised artifact SHA-256 identity",
        sha256(revised_draft) == EXPECTED_REVISED_SHA256,
        {
            "expected": EXPECTED_REVISED_SHA256,
            "actual": sha256(revised_draft),
        },
    )

    add_check(
        checks,
        "P10G-R2-VAL-002",
        "Immutable predecessor identities",
        (
            sha256(original_draft) == EXPECTED_ORIGINAL_SHA256
            and sha256(story_bible) == EXPECTED_STORY_BIBLE_SHA256
        ),
        {
            "original_beat_sheet_sha256": sha256(original_draft),
            "approved_story_bible_sha256": sha256(story_bible),
        },
    )

    summary_identity_passed = (
        summary.get("status")
        == "revised_generated_awaiting_strict_validation"
        and summary.get("revision_run_id")
        == EXPECTED_REVISION_RUN_ID
        and summary.get("parent_generation_run_id")
        == EXPECTED_PARENT_RUN_ID
        and summary.get("output", {}).get("sha256")
        == EXPECTED_REVISED_SHA256
        and summary.get("output", {}).get("characters")
        == EXPECTED_CHARACTERS
    )

    add_check(
        checks,
        "P10G-R2-VAL-003",
        "Revision summary identity",
        summary_identity_passed,
        {
            "revision_run_id": summary.get("revision_run_id"),
            "parent_generation_run_id": summary.get(
                "parent_generation_run_id"
            ),
            "status": summary.get("status"),
        },
    )

    add_check(
        checks,
        "P10G-R2-VAL-004",
        "Draft size and end marker",
        (
            len(text) == EXPECTED_CHARACTERS
            and len(text) >= 75_000
            and text.endswith(EXPECTED_END_MARKER)
        ),
        {
            "characters": len(text),
            "minimum_characters": 75_000,
            "end_marker_present": text.endswith(EXPECTED_END_MARKER),
        },
    )

    beat_ids = [
        block["beat_id"]
        for block in blocks
    ]

    add_check(
        checks,
        "P10G-R2-VAL-005",
        "Exact ordered Beat headings",
        (
            len(blocks) == EXPECTED_BEAT_COUNT
            and beat_ids == EXPECTED_BEAT_IDS
        ),
        {
            "beat_count": len(blocks),
            "first_beat_id": beat_ids[0] if beat_ids else None,
            "last_beat_id": beat_ids[-1] if beat_ids else None,
            "ordered_ids_match": beat_ids == EXPECTED_BEAT_IDS,
        },
    )

    field_failures: dict[str, dict[str, Any]] = {}

    for block in blocks:
        beat_id = block["beat_id"]
        body = block["body"]
        invalid_fields: dict[str, Any] = {}

        for field in BEAT_FIELDS:
            matches = field_pattern(field).findall(body)

            if len(matches) != 1:
                invalid_fields[field] = {
                    "occurrences": len(matches),
                }
            elif not matches[0].strip():
                invalid_fields[field] = {
                    "occurrences": 1,
                    "empty": True,
                }

        if invalid_fields:
            field_failures[beat_id] = invalid_fields

    add_check(
        checks,
        "P10G-R2-VAL-006",
        "Complete non-empty Beat fields",
        field_failures == {},
        {
            "required_body_fields_per_beat": len(BEAT_FIELDS),
            "field_failures": field_failures,
        },
    )

    numbered_sections = re.findall(
        r"^#\s+\d+\.\s+.+$",
        text,
        flags=re.MULTILINE,
    )

    add_check(
        checks,
        "P10G-R2-VAL-007",
        "Numbered top-level sections",
        len(numbered_sections) == EXPECTED_SECTION_COUNT,
        {
            "expected": EXPECTED_SECTION_COUNT,
            "found": len(numbered_sections),
        },
    )

    missing_canon_ids = [
        canon_id
        for canon_id in EXPECTED_CANON_IDS
        if canon_id not in text
    ]

    add_check(
        checks,
        "P10G-R2-VAL-008",
        "Canon Decision references YD-CANON-0001..0011",
        missing_canon_ids == [],
        {
            "expected_count": len(EXPECTED_CANON_IDS),
            "missing": missing_canon_ids,
        },
    )

    classification_count = len(
        re.findall(
            r"human-approved-canon-amendment",
            text,
            flags=re.IGNORECASE,
        )
    )

    amendment_reference_counts = {
        amendment_id: text.count(amendment_id)
        for amendment_id in AMENDMENT_IDS
    }

    add_check(
        checks,
        "P10G-R2-VAL-009",
        "Human-approved amendment classification",
        (
            classification_count >= 1
            and all(
                count >= 1
                for count in amendment_reference_counts.values()
            )
        ),
        {
            "classification_occurrences": classification_count,
            "amendment_reference_counts": amendment_reference_counts,
        },
    )

    chronology_markers = {
        "2385": "2385" in text,
        "2425": "2425" in text,
        "2666": "2666" in text,
        "281": re.search(r"\b281\b", text) is not None,
        "visual_age_40": (
            re.search(
                r"(visually|biologically|appears?|appearance).*?\b40\b",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )
            is not None
        ),
        "NSCL": (
            "Neuro-Somatic Continuity Lattice" in text
        ),
    }

    prologue_text = "\n".join(
        blocks_by_id[beat_id]["body"]
        for beat_id in [
            "P10G-BEAT-001",
            "P10G-BEAT-002",
            "P10G-BEAT-003",
            "P10G-BEAT-004",
        ]
        if beat_id in blocks_by_id
    )

    chronology_in_prologue = all(
        marker in prologue_text
        for marker in ["2385", "2425", "2666"]
    )

    add_check(
        checks,
        "P10G-R2-VAL-010",
        "Corrected longevity chronology",
        (
            all(chronology_markers.values())
            and chronology_in_prologue
        ),
        {
            "markers": chronology_markers,
            "2385_2425_2666_in_prologue": chronology_in_prologue,
        },
    )

    beat003 = blocks_by_id.get("P10G-BEAT-003", {})
    beat003_title = beat003.get("title", "")

    add_check(
        checks,
        "P10G-R2-VAL-011",
        "Beat 003 reframed as The Long Build",
        "the long build" in beat003_title.lower(),
        {
            "actual_title": beat003_title,
        },
    )

    knowledge_markers = {
        "secret": "secret" in lower,
        "public_knowledge": (
            "public knowledge" in lower
            or "publicly" in lower
        ),
        "audience_hints": (
            "audience" in lower
            and (
                "hint" in lower
                or "environmental" in lower
                or "visual clue" in lower
            )
        ),
        "private_motivation": (
            "private motivation" in lower
            or "concealed personal" in lower
            or "hidden personal" in lower
        ),
    }

    add_check(
        checks,
        "P10G-R2-VAL-012",
        "Knowledge-state separation",
        all(knowledge_markers.values()),
        knowledge_markers,
    )

    act2b_failures: dict[str, str | None] = {}

    for number in range(27, 31):
        beat_id = f"P10G-BEAT-{number:03d}"
        block = blocks_by_id.get(beat_id)
        value = (
            field_value(
                block["body"],
                "Act / structural position",
            )
            if block
            else None
        )

        if value is None or "act 2b" not in value.lower():
            act2b_failures[beat_id] = value

    lowest_point_failures: dict[str, str | None] = {}

    for number in range(31, 33):
        beat_id = f"P10G-BEAT-{number:03d}"
        block = blocks_by_id.get(beat_id)
        value = (
            field_value(
                block["body"],
                "Act / structural position",
            )
            if block
            else None
        )

        if (
            value is None
            or re.search(
                r"lowest[\s-]*point",
                value,
                flags=re.IGNORECASE,
            )
            is None
        ):
            lowest_point_failures[beat_id] = value

    act3_failures: dict[str, str | None] = {}

    for number in range(33, 35):
        beat_id = f"P10G-BEAT-{number:03d}"
        block = blocks_by_id.get(beat_id)
        value = (
            field_value(
                block["body"],
                "Act / structural position",
            )
            if block
            else None
        )

        if value is None or "act 3" not in value.lower():
            act3_failures[beat_id] = value

    beat031_text = blocks_by_id.get(
        "P10G-BEAT-031",
        {},
    ).get("body", "")

    beat031_lowest_point_present = (
        re.search(
            r"lowest[\s-]*point",
            beat031_text,
            flags=re.IGNORECASE,
        )
        is not None
    )

    act_structure_passed = (
        act2b_failures == {}
        and lowest_point_failures == {}
        and act3_failures == {}
        and beat031_lowest_point_present
    )

    add_check(
        checks,
        "P10G-R2-VAL-013",
        "Corrected Act 2B to Act 3 structure",
        act_structure_passed,
        {
            "expected_structure": {
                "P10G-BEAT-027..030": (
                    "Act 2B / Pre-Climax Gauntlet"
                ),
                "P10G-BEAT-031..032": (
                    "Lowest-Point Transition"
                ),
                "P10G-BEAT-033..034": "Act 3",
            },
            "act2b_failures": act2b_failures,
            "lowest_point_failures": lowest_point_failures,
            "act3_failures": act3_failures,
            "beat031_lowest_point_present": (
                beat031_lowest_point_present
            ),
        },
    )

    gauntlet_text = "\n".join(
        blocks_by_id[beat_id]["body"]
        for beat_id in [
            f"P10G-BEAT-{number:03d}"
            for number in range(27, 33)
        ]
        if beat_id in blocks_by_id
    )
    gauntlet_lower = gauntlet_text.lower()

    forbidden_countdown = [
        phrase
        for phrase in [
            "below two minutes",
            "under two minutes",
            "less than two minutes",
            "sub-two-minute",
        ]
        if phrase in gauntlet_lower
    ]

    numeric_two_minutes = (
        re.search(
            r"\b2\s*(?:minutes?|mins?)\b",
            gauntlet_text,
            flags=re.IGNORECASE,
        )
        is not None
    )

    countdown_present = (
        "countdown" in gauntlet_lower
        or "timer" in gauntlet_lower
        or "time pressure" in gauntlet_lower
    )

    add_check(
        checks,
        "P10G-R2-VAL-014",
        "Physically credible countdown representation",
        (
            countdown_present
            and forbidden_countdown == []
            and not numeric_two_minutes
        ),
        {
            "countdown_present": countdown_present,
            "forbidden_phrases": forbidden_countdown,
            "numeric_two_minutes_present": numeric_two_minutes,
        },
    )

    hammer_text = "\n".join(
        blocks_by_id[beat_id]["body"]
        for beat_id in [
            "P10G-BEAT-030",
            "P10G-BEAT-031",
        ]
        if beat_id in blocks_by_id
    )
    hammer_lower = hammer_text.lower()

    hammer_recovery_passed = (
        "seismic hammer" in hammer_lower
        and re.search(
            r"\brecover|\bretrieve|crawls? back|forces? himself back",
            hammer_text,
            flags=re.IGNORECASE,
        )
        is not None
        and re.search(
            r"\bdrag|\bpull",
            hammer_text,
            flags=re.IGNORECASE,
        )
        is not None
    )

    add_check(
        checks,
        "P10G-R2-VAL-015",
        "Seismic-hammer recovery continuity",
        hammer_recovery_passed,
        {
            "seismic_hammer_present": (
                "seismic hammer" in hammer_lower
            ),
            "recovery_action_present": (
                re.search(
                    r"\brecover|\bretrieve|crawls? back|"
                    r"forces? himself back",
                    hammer_text,
                    flags=re.IGNORECASE,
                )
                is not None
            ),
            "dragging_action_present": (
                re.search(
                    r"\bdrag|\bpull",
                    hammer_text,
                    flags=re.IGNORECASE,
                )
                is not None
            ),
        },
    )

    subjective_text = "\n".join(
        blocks_by_id[beat_id]["body"]
        for beat_id in [
            f"P10G-BEAT-{number:03d}"
            for number in range(30, 36)
        ]
        if beat_id in blocks_by_id
    )
    subjective_lower = subjective_text.lower()

    subjective_present = (
        "first-person" in subjective_lower
        or "subjective" in subjective_lower
        or "point-of-view" in subjective_lower
        or "pov" in subjective_lower
    )
    objective_return_present = (
        "objective" in subjective_lower
        or "third-person" in subjective_lower
    )
    knowledge_anchor_present = (
        "demian knowledge state" in subjective_lower
    )

    add_check(
        checks,
        "P10G-R2-VAL-016",
        "Bounded subjective First-Person direction",
        (
            subjective_present
            and objective_return_present
            and knowledge_anchor_present
        ),
        {
            "subjective_direction_present": subjective_present,
            "objective_return_present": objective_return_present,
            "Demian_knowledge_anchor_present": knowledge_anchor_present,
        },
    )

    old_certainty_phrases = [
        phrase
        for phrase in [
            "accepts full responsibility for y.d.'s corruption",
            "the true architect of this disaster",
            "the entire nightmare was born from",
            "the cause of y.d.'s corruption is",
        ]
        if phrase in lower
    ]

    ambiguity_present = (
        "ambiguity" in lower
        or "ambiguous" in lower
        or "multiple plausible causes" in lower
    )

    add_check(
        checks,
        "P10G-R2-VAL-017",
        "Corruption-cause ambiguity",
        (
            ambiguity_present
            and old_certainty_phrases == []
        ),
        {
            "ambiguity_present": ambiguity_present,
            "forbidden_certainty_phrases": old_certainty_phrases,
        },
    )

    terminology_passed = (
        "fractured dual-state ai entity" in lower
        and "schizophrenic ai entity" not in lower
    )

    add_check(
        checks,
        "P10G-R2-VAL-018",
        "Approved Y.D. dual-state terminology",
        terminology_passed,
        {
            "approved_term_present": (
                "fractured dual-state ai entity" in lower
            ),
            "forbidden_term_present": (
                "schizophrenic ai entity" in lower
            ),
        },
    )

    epilogue_text = "\n".join(
        blocks_by_id[beat_id]["body"]
        for beat_id in [
            "P10G-BEAT-042",
            "P10G-BEAT-043",
            "P10G-BEAT-044",
        ]
        if beat_id in blocks_by_id
    )
    epilogue_lower = epilogue_text.lower()

    faction_presence = {
        "Green Force": "green force" in epilogue_lower,
        "Rich Elite": "rich elite" in epilogue_lower,
        "Poor Communities": "poor communities" in epilogue_lower,
        "High-Tech-Future Force": (
            "high-tech-future force" in epilogue_lower
        ),
    }

    open_ending_present = (
        "unresolved" in epilogue_lower
        or "open ending" in epilogue_lower
        or "no definitive answer" in epilogue_lower
        or "without being guaranteed" in epilogue_lower
        or "cursor" in epilogue_lower
        or "awaiting new parameters" in epilogue_lower
    )

    epilogue_passed = (
        all(faction_presence.values())
        and open_ending_present
        and "epilogue" in epilogue_lower
    )

    add_check(
        checks,
        "P10G-R2-VAL-019",
        "Open philosophical Epilogue",
        epilogue_passed,
        {
            "factions": faction_presence,
            "open_ending_present": open_ending_present,
            "epilogue_marker_present": (
                "epilogue" in epilogue_lower
            ),
        },
    )

    source_values: dict[str, str | None] = {}
    empty_source_beats: list[str] = []

    for block in blocks:
        beat_id = block["beat_id"]
        value = field_value(
            block["body"],
            "Source references or verified locators",
        )
        source_values[beat_id] = value

        if value is None:
            empty_source_beats.append(beat_id)

    source_filename_matches = len(
        re.findall(
            r"(?:\.pdf|\.txt|\.md|\.json)",
            text,
            flags=re.IGNORECASE,
        )
    )
    page_locator_matches = len(
        re.findall(
            r"\b(?:page|pages|p\.)\s*\d+",
            text,
            flags=re.IGNORECASE,
        )
    )
    line_locator_matches = len(
        re.findall(
            r"\b(?:line|lines)\s+\d+(?:\s*[-–]\s*\d+)?",
            text,
            flags=re.IGNORECASE,
        )
    )

    add_check(
        checks,
        "P10G-R2-VAL-020",
        "Non-empty source references for every Beat",
        empty_source_beats == [],
        {
            "empty_source_beats": empty_source_beats,
            "source_filename_matches": source_filename_matches,
            "page_locator_matches": page_locator_matches,
            "line_locator_matches": line_locator_matches,
        },
    )

    control_passed = (
        contract.get("controls", {}).get(
            "database_access_allowed"
        )
        is False
        and contract.get("controls", {}).get(
            "database_mutation_allowed"
        )
        is False
        and contract.get("controls", {}).get(
            "automatic_canon_release_allowed"
        )
        is False
        and summary.get("controls", {}).get(
            "database_access_performed"
        )
        is False
        and summary.get("controls", {}).get(
            "database_mutation_performed"
        )
        is False
        and summary.get("controls", {}).get(
            "automatic_canon_release_performed"
        )
        is False
    )

    add_check(
        checks,
        "P10G-R2-VAL-021",
        "Database and canon-release controls",
        control_passed,
        {
            "database_access_performed": False,
            "database_mutation_performed": False,
            "automatic_canon_release_performed": False,
        },
    )

    authority_passed = (
        decisions.get("status")
        == "human_review_completed_revision_required"
        and amendment_payload.get("status")
        == "human_approved_proposals_awaiting_controlled_integration"
        and all(
            amendment_id in addendum_text
            for amendment_id in AMENDMENT_IDS
        )
        and "P10G POST-P10F CANON AUTHORITY ADDENDUM END"
        in addendum_text
    )

    add_check(
        checks,
        "P10G-R2-VAL-022",
        "Human authority and amendment chain",
        authority_passed,
        {
            "human_authority": HUMAN_AUTHORITY,
            "amendments": AMENDMENT_IDS,
        },
    )

    failures = [
        check
        for check in checks
        if not check["passed"]
    ]

    validation_status = (
        "passed_strict_awaiting_final_human_review"
        if not failures
        else "failed_strict_validation"
    )

    created_at = datetime.now(timezone.utc).isoformat()

    validation_payload = {
        "schema_version": 1,
        "workflow": WORKFLOW,
        "operation": OPERATION,
        "status": validation_status,
        "created_at": created_at,
        "human_authority": HUMAN_AUTHORITY,
        "artifact": {
            "filename": revised_draft.name,
            "sha256": sha256(revised_draft),
            "characters": len(text),
            "revision_run_id": EXPECTED_REVISION_RUN_ID,
            "parent_generation_run_id": EXPECTED_PARENT_RUN_ID,
        },
        "summary": {
            "checks": len(checks),
            "passed": len(checks) - len(failures),
            "failures": len(failures),
            "beat_entries": len(blocks),
            "beat_body_fields": len(BEAT_FIELDS),
            "numbered_sections": len(numbered_sections),
            "canon_decisions": (
                len(EXPECTED_CANON_IDS)
                - len(missing_canon_ids)
            ),
            "amendment_classification_occurrences": (
                classification_count
            ),
            "source_filename_matches": source_filename_matches,
            "page_locator_matches": page_locator_matches,
            "line_locator_matches": line_locator_matches,
        },
        "checks": checks,
        "failed_checks": [
            check["check_id"]
            for check in failures
        ],
        "controls": {
            "revised_draft_modified": False,
            "original_draft_modified": False,
            "story_bible_modified": False,
            "database_access_performed": False,
            "database_mutation_performed": False,
            "automatic_canon_release_performed": False,
            "human_review_required": True,
        },
    }

    review_items = [
        (
            "P10G-R2-REVIEW-001",
            "Authority and amendment precedence",
            "Confirm the revised Beat Sheet correctly applies "
            "YD-CANON-0007..0011 while preserving P10F and "
            "YD-CANON-0001..0006 for unaffected facts.",
        ),
        (
            "P10G-R2-REVIEW-002",
            "Demian chronology and longevity",
            "Confirm the 2385 birth year, 2425 NSCL treatment, 2666 "
            "present, chronological age 281, and visual age approximately "
            "40 are coherent.",
        ),
        (
            "P10G-R2-REVIEW-003",
            "Identity secrecy and audience hints",
            "Confirm Demian's true age remains secret while environmental "
            "and visual hints are narratively appropriate.",
        ),
        (
            "P10G-R2-REVIEW-004",
            "Project Genesis dual motivation",
            "Confirm the public coexistence purpose is genuine but "
            "incomplete, and Demian's private emotional motivation remains "
            "psychologically complex.",
        ),
        (
            "P10G-R2-REVIEW-005",
            "Feature-film Act structure",
            "Confirm the Amusement Park is late Act 2B, the Mirror "
            "Labyrinth creates the lowest-point transition, and the Mirror "
            "Room starts Act 3.",
        ),
        (
            "P10G-R2-REVIEW-006",
            "Amusement Park traps and countdown",
            "Confirm the approved traps remain effective and the revised "
            "countdown is physically credible.",
        ),
        (
            "P10G-R2-REVIEW-007",
            "Seismic-hammer continuity",
            "Confirm Demian deliberately recovers and drags the hammer, "
            "with an appropriate time and physical cost.",
        ),
        (
            "P10G-R2-REVIEW-008",
            "Subjective First-Person direction",
            "Confirm subjective camera transitions are motivated, bounded "
            "to Demian's knowledge, and deliberately return to objective "
            "perspective.",
        ),
        (
            "P10G-R2-REVIEW-009",
            "Corruption ambiguity",
            "Confirm Demian accepts responsibility only for his "
            "contribution and no single corruption cause becomes objective "
            "canon.",
        ),
        (
            "P10G-R2-REVIEW-010",
            "Y.D. dual-state characterization",
            "Confirm Y.D.'s motives remain interpretations rather than "
            "objective facts and the approved dual-state terminology is "
            "used appropriately.",
        ),
        (
            "P10G-R2-REVIEW-011",
            "Source traceability and fact classification",
            "Confirm source references, locators, Canon Decision "
            "references, and human-approved amendment classifications are "
            "sufficient for downstream scene development.",
        ),
        (
            "P10G-R2-REVIEW-012",
            "Open philosophical Epilogue",
            "Confirm all major factions receive defensible positions, "
            "Demian receives no complete moral absolution, and Y.D.'s "
            "status remains unresolved.",
        ),
        (
            "P10G-R2-REVIEW-013",
            "Beat completeness",
            "Confirm all 44 revised Beats are narratively ordered and "
            "sufficient for Beat-to-Scene conversion.",
        ),
        (
            "P10G-R2-REVIEW-014",
            "Overall character, narrative, and production continuity",
            "Confirm the complete revised artifact remains emotionally, "
            "logically, visually, and productionally coherent.",
        ),
        (
            "P10G-R2-REVIEW-015",
            "Final revised Beat Sheet disposition",
            "Approve only if items 001 through 014 are approved and no "
            "further revision remains necessary.",
        ),
    ]

    review_lines = [
        "# P10G Revised Canon Beat Sheet – Final Human Review",
        "",
        "## Review status",
        "",
        "`pending_final_human_review`",
        "",
        "## Reviewed artifact",
        "",
        f"- File: `{revised_draft.name}`",
        f"- SHA-256: `{sha256(revised_draft)}`",
        f"- Revision Run ID: `{EXPECTED_REVISION_RUN_ID}`",
        f"- Parent Run ID: `{EXPECTED_PARENT_RUN_ID}`",
        f"- Characters: `{len(text)}`",
        f"- Beat entries: `{len(blocks)}`",
        f"- Numbered sections: `{len(numbered_sections)}`",
        f"- Strict validation status: `{validation_status}`",
        f"- Strict validation failures: `{len(failures)}`",
        "",
        "## Allowed dispositions",
        "",
        "- `approve`",
        "- `reject`",
        "- `needs_revision`",
        "- `defer`",
        "",
        "## Review items",
        "",
    ]

    for review_id, subject, description in review_items:
        review_lines.extend(
            [
                f"### {review_id} – {subject}",
                "",
                description,
                "",
                "Disposition: `pending`",
                "",
                "Notes:",
                "",
            ]
        )

    review_lines.extend(
        [
            "## Current authority state",
            "",
            f"- Human reviewer: `{HUMAN_AUTHORITY}`",
            f"- Strict validation passed: "
            f"`{'true' if not failures else 'false'}`",
            "- Human review completed: `false`",
            "- Revised Beat Sheet approved as canon: `false`",
            "- Database mutation authorized: `false`",
            "- Automatic canon release authorized: `false`",
            "",
        ]
    )

    write_json(validation_output, validation_payload)
    review_output.write_text(
        "\n".join(review_lines),
        encoding="utf-8",
    )

    print(f"Validation checks: {len(checks)}")
    print(f"Validation passed: {len(checks) - len(failures)}")
    print(f"Validation failures: {len(failures)}")
    print(f"Revised Draft characters: {len(text)}")
    print(f"Beat entries: {len(blocks)}")
    print(f"Beat body fields: {len(BEAT_FIELDS)}")
    print(f"Numbered sections: {len(numbered_sections)}")
    print(
        "Canon decision references: "
        f"{len(EXPECTED_CANON_IDS) - len(missing_canon_ids)}"
    )
    print(
        "Human-approved amendment classifications: "
        f"{classification_count}"
    )
    print(f"Source filename matches: {source_filename_matches}")
    print(f"Page locator matches: {page_locator_matches}")
    print(f"Line locator matches: {line_locator_matches}")
    print(f"Validation status: {validation_status}")
    print(f"Validation report: {validation_output}")
    print(f"Human review matrix: {review_output}")
    print("Revised Draft modified: False")
    print("Original Draft modified: False")
    print("Story Bible modified: False")
    print("Database mutation: False")

    if failures:
        print(
            "Failed checks: "
            + ", ".join(
                check["check_id"]
                for check in failures
            )
        )
        raise RuntimeError(
            f"Strict validation failed with {len(failures)} failure(s)"
        )

    print("P10G REVISED BEAT SHEET STRICT VALIDATION: OK")


if __name__ == "__main__":
    main()
