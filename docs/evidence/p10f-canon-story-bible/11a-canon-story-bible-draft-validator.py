from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_IDS = [
    "YD-CANON-0001",
    "YD-CANON-0002",
    "YD-CANON-0003",
    "YD-CANON-0004",
    "YD-CANON-0005",
    "YD-CANON-0006",
]

END_MARKER = "P10F CANON STORY BIBLE DRAFT END"
MINIMUM_CHARACTERS = 12_000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    details: Any,
    category: str = "structural",
) -> None:
    checks.append(
        {
            "name": name,
            "category": category,
            "passed": passed,
            "details": details,
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--draft",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--summary",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--contract",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--validation-output",
        required=True,
        type=Path,
    )
    parser.add_argument(
        "--review-output",
        required=True,
        type=Path,
    )

    args = parser.parse_args()

    draft_path = args.draft.resolve()
    summary_path = args.summary.resolve()
    contract_path = args.contract.resolve()
    validation_path = args.validation_output.resolve()
    review_path = args.review_output.resolve()

    for path in [
        draft_path,
        summary_path,
        contract_path,
    ]:
        if not path.is_file():
            raise SystemExit(f"Required file missing: {path}")

    for path in [
        validation_path,
        review_path,
    ]:
        if path.exists():
            raise SystemExit(
                f"Refusing to overwrite existing output: {path}"
            )

    draft = draft_path.read_text(encoding="utf-8")
    summary = json.loads(
        summary_path.read_text(encoding="utf-8")
    )
    contract = json.loads(
        contract_path.read_text(encoding="utf-8")
    )

    required_sections = contract.get(
        "required_sections",
        [],
    )

    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "contract_status",
        contract.get("status")
        == "awaiting_controlled_draft_generation",
        contract.get("status"),
    )

    authority = contract.get("authority", {})

    add_check(
        checks,
        "contract_database_mutation_prohibited",
        authority.get("database_mutation_permitted") is False,
        authority.get("database_mutation_permitted"),
    )

    add_check(
        checks,
        "contract_autonomous_canon_change_prohibited",
        authority.get(
            "autonomous_canon_changes_permitted"
        ) is False,
        authority.get(
            "autonomous_canon_changes_permitted"
        ),
    )

    add_check(
        checks,
        "summary_status",
        summary.get("status")
        == "generated_awaiting_validation",
        summary.get("status"),
    )

    summary_authority = summary.get("authority", {})

    add_check(
        checks,
        "summary_database_mutation_not_performed",
        summary_authority.get(
            "database_mutation_performed"
        ) is False,
        summary_authority.get(
            "database_mutation_performed"
        ),
    )

    add_check(
        checks,
        "summary_draft_not_approved_canon",
        summary_authority.get(
            "draft_is_approved_canon"
        ) is False,
        summary_authority.get(
            "draft_is_approved_canon"
        ),
    )

    generation_config = summary.get(
        "generation_config",
        {},
    )

    add_check(
        checks,
        "afc_chat_transport",
        generation_config.get("transport")
        == "Chat.send_message",
        generation_config.get("transport"),
    )

    add_check(
        checks,
        "afc_chat_route",
        generation_config.get(
            "automatic_function_calling_route"
        ) == "chat",
        generation_config.get(
            "automatic_function_calling_route"
        ),
    )

    add_check(
        checks,
        "streaming_disabled",
        generation_config.get("streaming") is False,
        generation_config.get("streaming"),
    )

    add_check(
        checks,
        "tools_disabled",
        generation_config.get("tools") is False,
        generation_config.get("tools"),
    )

    add_check(
        checks,
        "database_access_disabled",
        generation_config.get(
            "database_access"
        ) is False,
        generation_config.get(
            "database_access"
        ),
    )

    output = summary.get("output", {})

    actual_draft_hash = sha256(draft_path)

    add_check(
        checks,
        "draft_sha256_matches_summary",
        output.get("sha256") == actual_draft_hash,
        {
            "summary": output.get("sha256"),
            "actual": actual_draft_hash,
        },
    )

    add_check(
        checks,
        "draft_bytes_match_summary",
        output.get("bytes") == draft_path.stat().st_size,
        {
            "summary": output.get("bytes"),
            "actual": draft_path.stat().st_size,
        },
    )

    add_check(
        checks,
        "minimum_character_count",
        len(draft) >= MINIMUM_CHARACTERS,
        {
            "minimum": MINIMUM_CHARACTERS,
            "actual": len(draft),
        },
    )

    add_check(
        checks,
        "required_section_count",
        len(required_sections) == 17,
        len(required_sections),
    )

    missing_section_headings: list[str] = []

    for section in required_sections:
        pattern = re.compile(
            rf"(?m)^#{{1,6}}\s+"
            rf"{re.escape(section)}\s*$"
        )

        if not pattern.search(draft):
            missing_section_headings.append(section)

    add_check(
        checks,
        "required_section_headings",
        not missing_section_headings,
        {
            "expected": 17,
            "missing": missing_section_headings,
        },
    )

    missing_decision_ids = [
        decision_id
        for decision_id in EXPECTED_IDS
        if decision_id not in draft
    ]

    decision_reference_counts = {
        decision_id: draft.count(decision_id)
        for decision_id in EXPECTED_IDS
    }

    add_check(
        checks,
        "canon_decision_references",
        not missing_decision_ids,
        {
            "missing": missing_decision_ids,
            "counts": decision_reference_counts,
        },
    )

    stripped_draft = draft.rstrip()

    add_check(
        checks,
        "exact_end_marker",
        stripped_draft.endswith(END_MARKER),
        stripped_draft.splitlines()[-1]
        if stripped_draft
        else None,
    )

    required_labels = [
        "CANON",
        "SUPERSEDED",
        "UNRESOLVED",
        "PROPOSED — HUMAN APPROVAL REQUIRED",
    ]

    label_counts = {
        label: draft.count(label)
        for label in required_labels
    }

    missing_labels = [
        label
        for label, count in label_counts.items()
        if count == 0
    ]

    add_check(
        checks,
        "required_epistemic_labels",
        not missing_labels,
        {
            "missing": missing_labels,
            "counts": label_counts,
        },
    )

    locator_patterns = {
        "page_locator": bool(
            re.search(
                r"\bpages?\s*:\s*\d+",
                draft,
                re.IGNORECASE,
            )
        ),
        "line_locator": bool(
            re.search(
                r"\blines?\s*:\s*\d+",
                draft,
                re.IGNORECASE,
            )
        ),
        "source_filename": bool(
            re.search(
                r"\.(?:txt|pdf|md)\b",
                draft,
                re.IGNORECASE,
            )
        ),
    }

    add_check(
        checks,
        "source_traceability_markers",
        all(locator_patterns.values()),
        locator_patterns,
        category="traceability",
    )

    presence_requirements = {
        "canonical_age_40": bool(
            re.search(r"\b40\b", draft)
        ),
        "full_length_film": bool(
            re.search(
                r"full[- ]length",
                draft,
                re.IGNORECASE,
            )
        ),
        "doll_and_hammer": (
            "doll" in draft.lower()
            and "hammer" in draft.lower()
        ),
        "amusement_park": (
            "Amusement Park of Illusions" in draft
        ),
        "corruption_unresolved": (
            "corruption" in draft.lower()
            and "unresolved" in draft.lower()
        ),
        "four_second_history": bool(
            re.search(
                r"four[- ]second|4[- ]second",
                draft,
                re.IGNORECASE,
            )
        ),
    }

    add_check(
        checks,
        "canon_topic_presence",
        all(presence_requirements.values()),
        presence_requirements,
        category="semantic_presence_only",
    )

    failures = [
        check
        for check in checks
        if not check["passed"]
    ]

    validation_status = (
        "passed_structural_awaiting_human_review"
        if not failures
        else "failed_structural_validation"
    )

    validation = {
        "schema_version": 1,
        "workflow": "P10F Canon Story Bible",
        "stage": "draft_validation",
        "status": validation_status,
        "validated_at_utc": datetime.now(
            timezone.utc
        ).isoformat(timespec="seconds"),
        "run_id": summary.get("run_id"),
        "model": summary.get("model"),
        "draft": {
            "path": str(draft_path),
            "bytes": draft_path.stat().st_size,
            "characters": len(draft),
            "sha256": actual_draft_hash,
        },
        "authority": {
            "human_authority": "Demian",
            "draft_is_approved_canon": False,
            "database_mutation_permitted": False,
            "human_review_required": True,
        },
        "checks": checks,
        "check_count": len(checks),
        "failure_count": len(failures),
        "failures": failures,
        "semantic_validation_boundary": (
            "Automated checks validate structure, hashes, required "
            "references, labels, and topic presence. They do not "
            "constitute human approval of narrative meaning."
        ),
    }

    validation_path.write_text(
        json.dumps(
            validation,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    review_lines = [
        "# P10F Canon Story Bible — Human Review Matrix",
        "",
        "## Status",
        "",
        "`awaiting_human_review`",
        "",
        "## Authority",
        "",
        "- Reviewer: `Demian`",
        "- Draft is approved canon: `false`",
        "- Database mutation permitted: `false`",
        f"- Generation run ID: `{summary.get('run_id')}`",
        f"- Model: `{summary.get('model')}`",
        f"- Draft SHA-256: `{actual_draft_hash}`",
        "",
        "## Review dispositions",
        "",
        "Use exactly one disposition per item:",
        "",
        "- `approve`",
        "- `reject`",
        "- `needs_revision`",
        "- `defer`",
        "",
        "## Review items",
        "",
        "### P10F-REVIEW-001 — Authority and precedence",
        "",
        "- Disposition: `pending`",
        "- Confirm approved decisions override conflicting historical text.",
        "- Confirm no proposal is silently promoted to canon.",
        "",
        "### P10F-REVIEW-002 — Project definition",
        "",
        "- Disposition: `pending`",
        "- Confirm full-length-film status.",
        "- Confirm no fixed target runtime was invented.",
        "- Confirm the obsolete 15-minute limit is superseded.",
        "",
        "### P10F-REVIEW-003 — Demian",
        "",
        "- Disposition: `pending`",
        "- Confirm canonical age 40.",
        "- Confirm age 38 appears only as superseded history.",
        "- Confirm characterization matches the primary sources.",
        "",
        "### P10F-REVIEW-004 — Y.D.",
        "",
        "- Disposition: `pending`",
        "- Confirm initial harmonious relationship and communication modes.",
        "- Confirm corruption behavior and thematic contradictions.",
        "- Confirm Y.D. eventually recognizes her errors without forcing",
        "  an unapproved technical explanation.",
        "",
        "### P10F-REVIEW-005 — Doll and seismic hammer",
        "",
        "- Disposition: `pending`",
        "- Confirm Y.D. is the true originator or deployer.",
        "- Confirm Demian does not know this during the kitchen sequence.",
        "- Confirm the audience remains inside Demian's uncertainty.",
        "",
        "### P10F-REVIEW-006 — Amusement Park of Illusions",
        "",
        "- Disposition: `pending`",
        "- Confirm it remains a major survival escape-room sequence.",
        "- Confirm all required horror, trap, hallucination, motor-control,",
        "  time-pressure, mirror-labyrinth, and transition elements.",
        "- Confirm unapproved room order and riddles remain unresolved.",
        "",
        "### P10F-REVIEW-007 — Corruption mystery",
        "",
        "- Disposition: `pending`",
        "- Confirm no single corruption cause is declared canonical.",
        "- Confirm dependency, server fault, hacker influence, and combined",
        "  causation remain plausible.",
        "",
        "### P10F-REVIEW-008 — Dialogue, tone, and timing",
        "",
        "- Disposition: `pending`",
        "- Confirm historical four-second timings are non-binding.",
        "- Confirm dialogue intent, dark humor, satire, sarcasm, irony,",
        "  slapstick, cynicism, and voice progression are preserved.",
        "",
        "### P10F-REVIEW-009 — Source traceability",
        "",
        "- Disposition: `pending`",
        "- Confirm factual claims are traceable to sources or Canon Decisions.",
        "- Confirm historical and superseded material is correctly labeled.",
        "",
        "### P10F-REVIEW-010 — Final draft disposition",
        "",
        "- Disposition: `pending`",
        "- This item may be approved only after items 001–009 are resolved.",
        "- Approval here authorizes freezing the Story Bible as reviewed",
        "  evidence; it does not authorize a database write.",
        "",
        "## Reviewer notes",
        "",
        "_Pending Demian review._",
        "",
    ]

    review_path.write_text(
        "\n".join(review_lines),
        encoding="utf-8",
    )

    print(f"Validation checks: {len(checks)}")
    print(f"Validation failures: {len(failures)}")
    print(f"Draft characters: {len(draft)}")
    print("Required sections: 17")
    print("Canon decision references: 6")
    print(f"Validation status: {validation_status}")
    print(f"Validation report: {validation_path}")
    print(f"Human review matrix: {review_path}")

    if failures:
        for failure in failures:
            print(
                "FAILED: "
                f"{failure['name']} -> "
                f"{failure['details']}"
            )

        return 1

    print("P10F CANON STORY BIBLE DRAFT VALIDATION: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
