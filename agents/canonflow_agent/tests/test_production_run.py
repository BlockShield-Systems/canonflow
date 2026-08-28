from __future__ import annotations

import json
import shutil
import socket
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


AGENTS_ROOT = Path(__file__).resolve().parents[2]

if str(AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTS_ROOT))

from canonflow_agent.production_run import (
    DRAFT_PATH,
    HUMAN_COMPLETION_PATH,
    HUMAN_DECISIONS_PATH,
    HUMAN_REVIEW_PATH,
    REQUIRED_CANON_PATHS,
    R4_DRAFT_SHA256,
    SEGMENT_RANGES,
    SEMANTIC_VALIDATION_PATH,
    TELEMETRY_CONTRACT_PATH,
    ProductionRunError,
    build_production_run,
    parse_frozen_beats,
    resolve_selection,
    validate_canon_authority,
    write_production_run,
)


REPOSITORY_ROOT = AGENTS_ROOT.parent


def temporary_repository() -> tuple[
    tempfile.TemporaryDirectory[str],
    Path,
]:
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name)

    for relative_path in REQUIRED_CANON_PATHS:
        source = REPOSITORY_ROOT / relative_path
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    return temporary, root


def test_validates_frozen_r4_authority_chain() -> None:
    binding = validate_canon_authority(REPOSITORY_ROOT)

    assert binding["revision"] == "R4"
    assert binding["draft_sha256"] == R4_DRAFT_SHA256
    assert binding["human_review"]["approved_items"] == 25
    assert binding["human_review"]["human_review_completed"] is True
    assert (
        binding["human_review"]["approved_as_final_canon"]
        is True
    )
    assert (
        binding["human_review"]["final_disposition"]
        == "approve"
    )


def test_parses_exactly_44_ordered_beats() -> None:
    beats = parse_frozen_beats(REPOSITORY_ROOT)

    assert len(beats) == 44
    assert beats[0]["beat_id"] == "P10G-BEAT-001"
    assert beats[-1]["beat_id"] == "P10G-BEAT-044"
    assert [
        beat["beat_number"]
        for beat in beats
    ] == list(range(1, 45))


def test_segment_ranges_cover_every_beat_once() -> None:
    covered: list[int] = []

    for start, end in SEGMENT_RANGES.values():
        covered.extend(range(start, end + 1))

    assert covered == list(range(1, 45))


def test_selects_epilogue_only() -> None:
    run = build_production_run(
        REPOSITORY_ROOT,
        segments=("epilogue",),
    )

    selection = run["selection"]

    assert selection["segments"] == ["epilogue"]
    assert selection["selected_beat_count"] == 3
    assert selection["first_beat_id"] == "P10G-BEAT-042"
    assert selection["last_beat_id"] == "P10G-BEAT-044"


def test_custom_segments_are_canonically_ordered() -> None:
    run = build_production_run(
        REPOSITORY_ROOT,
        segments=("epilogue", "prologue", "act_3"),
    )

    assert run["selection"]["segments"] == [
        "prologue",
        "act_3",
        "epilogue",
    ]
    assert run["selection"]["selected_beat_count"] == 14


def test_full_feature_selects_all_beats() -> None:
    run = build_production_run(
        REPOSITORY_ROOT,
        profile="full_feature",
    )

    assert run["selection"]["selected_beat_count"] == 44
    assert run["selection"]["first_beat_id"] == "P10G-BEAT-001"
    assert run["selection"]["last_beat_id"] == "P10G-BEAT-044"


def test_showcase_profile_has_expected_sequence() -> None:
    run = build_production_run(
        REPOSITORY_ROOT,
        profile="showcase",
    )

    selection = run["selection"]

    assert selection["presentation_units"] == [
        "intro",
        "claim",
        "credits",
    ]
    assert selection["segments"] == [
        "act_2b",
        "act_3",
        "epilogue",
    ]
    assert selection["selected_beat_count"] == 22
    assert selection["first_beat_id"] == "P10G-BEAT-023"
    assert selection["last_beat_id"] == "P10G-BEAT-044"


def test_run_and_selection_ids_are_deterministic() -> None:
    first = build_production_run(
        REPOSITORY_ROOT,
        profile="showcase",
    )
    second = build_production_run(
        REPOSITORY_ROOT,
        profile="showcase",
    )

    assert first["selection_id"] == second["selection_id"]
    assert (
        first["production_run_id"]
        == second["production_run_id"]
    )
    assert first["contract_id"] == second["contract_id"]


def test_rejects_unknown_or_duplicate_segments() -> None:
    try:
        resolve_selection(segments=("unknown",))
    except ProductionRunError:
        pass
    else:
        raise AssertionError("Unknown segment was accepted.")

    try:
        resolve_selection(
            segments=("act_3", "act_3"),
        )
    except ProductionRunError:
        pass
    else:
        raise AssertionError("Duplicate segment was accepted.")


def test_rejects_modified_r4_draft() -> None:
    temporary, root = temporary_repository()

    try:
        draft = root / DRAFT_PATH
        draft.write_text(
            draft.read_text(encoding="utf-8")
            + "\nunauthorized mutation\n",
            encoding="utf-8",
        )

        try:
            validate_canon_authority(root)
        except ProductionRunError as exc:
            assert "SHA-256" in str(exc)
        else:
            raise AssertionError("Modified R4 draft was accepted.")
    finally:
        temporary.cleanup()


def test_rejects_modified_human_approval() -> None:
    temporary, root = temporary_repository()

    try:
        decisions_path = root / HUMAN_DECISIONS_PATH
        decisions = json.loads(
            decisions_path.read_text(encoding="utf-8")
        )
        decisions["review_items"][0]["disposition"] = "reject"
        decisions_path.write_text(
            json.dumps(decisions),
            encoding="utf-8",
        )

        try:
            validate_canon_authority(root)
        except ProductionRunError:
            pass
        else:
            raise AssertionError(
                "Modified human approval was accepted."
            )
    finally:
        temporary.cleanup()


def test_atomic_output_and_offline_controls() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "production-run.json"

        with patch.object(
            socket,
            "socket",
            side_effect=AssertionError(
                "Network access is forbidden."
            ),
        ):
            run = build_production_run(
                REPOSITORY_ROOT,
                profile="showcase",
            )
            write_production_run(output, run)

        persisted = json.loads(
            output.read_text(encoding="utf-8")
        )

        assert persisted["controls"]["network_access_performed"] is False
        assert persisted["controls"]["http_request_performed"] is False
        assert (
            persisted["controls"]["identity_token_requested"]
            is False
        )
        assert persisted["controls"]["executor_invoked"] is False

        try:
            write_production_run(output, run)
        except ProductionRunError as exc:
            assert "Refusing to overwrite" in str(exc)
        else:
            raise AssertionError(
                "Existing production run was overwritten."
            )


def main() -> None:
    tests = [
        test_validates_frozen_r4_authority_chain,
        test_parses_exactly_44_ordered_beats,
        test_segment_ranges_cover_every_beat_once,
        test_selects_epilogue_only,
        test_custom_segments_are_canonically_ordered,
        test_full_feature_selects_all_beats,
        test_showcase_profile_has_expected_sequence,
        test_run_and_selection_ids_are_deterministic,
        test_rejects_unknown_or_duplicate_segments,
        test_rejects_modified_r4_draft,
        test_rejects_modified_human_approval,
        test_atomic_output_and_offline_controls,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print()
    print(f"Production-run tests passed: {len(tests)}")
    print("CANONFLOW PRODUCTION RUN CONTRACT: OK")


if __name__ == "__main__":
    main()
