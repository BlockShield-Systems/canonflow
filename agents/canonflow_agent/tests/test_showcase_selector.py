from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


AGENTS_ROOT = Path(__file__).resolve().parents[2]

if str(AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTS_ROOT))

from canonflow_agent.showcase_selector import (
    NARRATIVE_RUNTIME_SECONDS,
    PRESENTATION_RUNTIME_SECONDS,
    SEGMENT_ORDER,
    TOTAL_RUNTIME_SECONDS,
    build_showcase_plan,
    write_showcase_plan,
)


REPOSITORY_ROOT = Path(
    os.environ.get(
        "REPO_ROOT",
        Path(__file__).resolve().parents[3],
    )
).resolve()


def test_deterministic_identity() -> None:
    first = build_showcase_plan(REPOSITORY_ROOT)
    second = build_showcase_plan(REPOSITORY_ROOT)

    assert first["artifact_id"] == second["artifact_id"]
    assert first["showcase_plan_id"] == second["showcase_plan_id"]


def test_six_segment_coverage() -> None:
    plan = build_showcase_plan(REPOSITORY_ROOT)
    selected_segments = {
        scene["segment_id"]
        for scene in plan["selected_scenes"]
    }

    assert selected_segments == set(SEGMENT_ORDER)
    assert plan["validation"]["all_six_segments_represented"] is True


def test_complete_beat_disposition() -> None:
    plan = build_showcase_plan(REPOSITORY_ROOT)
    selected = {
        scene["beat_id"]
        for scene in plan["selected_scenes"]
    }
    excluded = {
        beat["beat_id"]
        for beat in plan["excluded_beats"]
    }

    assert selected.isdisjoint(excluded)
    assert len(selected | excluded) == 44
    assert plan["selection_contract"]["all_beats_have_dispositions"]


def test_chronological_selection() -> None:
    plan = build_showcase_plan(REPOSITORY_ROOT)
    numbers = [
        int(scene["beat_id"].rsplit("-", 1)[1])
        for scene in plan["selected_scenes"]
    ]

    assert numbers == sorted(numbers)


def test_runtime_contract() -> None:
    plan = build_showcase_plan(REPOSITORY_ROOT)
    runtime = plan["runtime_contract"]

    assert runtime["showcase_total_runtime_seconds"] == 600
    assert runtime["narrative_runtime_seconds"] == 510
    assert runtime["presentation_runtime_seconds"] == 90
    assert (
        NARRATIVE_RUNTIME_SECONDS
        + PRESENTATION_RUNTIME_SECONDS
        == TOTAL_RUNTIME_SECONDS
    )
    assert plan["timeline"][-1]["end_seconds"] == 600


def test_timeline_is_contiguous() -> None:
    plan = build_showcase_plan(REPOSITORY_ROOT)
    timeline = plan["timeline"]

    assert timeline[0]["start_seconds"] == 0

    for previous, current in zip(timeline, timeline[1:]):
        assert previous["end_seconds"] == current["start_seconds"]


def test_classical_credits_are_last() -> None:
    plan = build_showcase_plan(REPOSITORY_ROOT)
    final_item = plan["timeline"][-1]

    assert final_item["item_id"] == "classical_end_credits"
    assert final_item["end_seconds"] == 600


def test_shot_packets_cover_narrative_runtime() -> None:
    plan = build_showcase_plan(REPOSITORY_ROOT)
    shots = plan["shot_context_packets"]

    assert sum(shot["duration_seconds"] for shot in shots) == 510
    assert all(shot["duration_seconds"] <= 10 for shot in shots)
    assert all(shot["duration_seconds"] > 0 for shot in shots)


def test_generation_remains_disabled() -> None:
    plan = build_showcase_plan(REPOSITORY_ROOT)

    assert plan["generation_authorized"] is False
    assert not any(plan["security"].values())
    assert all(
        shot["generation_authorized"] is False
        for shot in plan["shot_context_packets"]
    )
    assert all(
        scene["generation_authorized"] is False
        for scene in plan["selected_scenes"]
    )


def test_beat_44_boundary_is_correct() -> None:
    plan = build_showcase_plan(REPOSITORY_ROOT)
    beat_44 = next(
        scene
        for scene in plan["selected_scenes"]
        if scene["beat_id"] == "P10G-BEAT-044"
    )

    assert beat_44["source_locator"]["end_line"] == 865


def test_offline_execution() -> None:
    with patch.object(
        socket,
        "socket",
        side_effect=AssertionError("Network access is forbidden."),
    ):
        plan = build_showcase_plan(REPOSITORY_ROOT)

    assert plan["security"]["network_access_performed"] is False


def test_atomic_non_overwrite() -> None:
    plan = build_showcase_plan(REPOSITORY_ROOT)

    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "showcase.json"
        write_showcase_plan(output, plan)

        loaded = json.loads(output.read_text(encoding="utf-8"))
        assert loaded == plan

        try:
            write_showcase_plan(output, plan)
        except FileExistsError:
            pass
        else:
            raise AssertionError("Existing output was overwritten.")


def main() -> int:
    tests = [
        test_deterministic_identity,
        test_six_segment_coverage,
        test_complete_beat_disposition,
        test_chronological_selection,
        test_runtime_contract,
        test_timeline_is_contiguous,
        test_classical_credits_are_last,
        test_shot_packets_cover_narrative_runtime,
        test_generation_remains_disabled,
        test_beat_44_boundary_is_correct,
        test_offline_execution,
        test_atomic_non_overwrite,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print()
    print(f"Showcase-selector tests passed: {len(tests)}")
    print("CANONFLOW SIX-SEGMENT SHOWCASE SELECTOR: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
