from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

AGENTS_ROOT = Path(__file__).resolve().parents[2]

if str(AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTS_ROOT))

from canonflow_agent.scene_shot_compiler import (  # noqa: E402
    DEMIAN_REFERENCE_SHA256,
    R4_DRAFT_SHA256,
    STORY_BIBLE_SHA256,
    YD_REFERENCE_SHA256,
    build_scene_shot_plan,
    parse_canon_beats,
    write_scene_shot_plan,
)

EXPECTED_HEAD = "64622e30de9899317ced36cd74dfbd7f78ef0439"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    repository_root = Path(
        os.environ.get(
            "REPO_ROOT",
            Path(__file__).resolve().parents[3],
        )
    ).resolve()

    plan = build_scene_shot_plan(repository_root)
    test_count = 0

    require(
        plan["artifact_type"]
        == "canonflow_narrative_context_scene_shot_plan",
        "Unexpected artifact type.",
    )
    test_count += 1

    require(
        plan["status"] == "compiled_pending_human_clarification",
        "Unexpected plan status.",
    )
    test_count += 1

    require(
        plan["baseline"]["evidence_61_head"] == EXPECTED_HEAD,
        "Evidence 61 baseline mismatch.",
    )
    test_count += 1

    require(
        plan["canon_binding"]["draft_sha256"] == R4_DRAFT_SHA256,
        "R4 draft binding mismatch.",
    )
    require(
        plan["canon_binding"]["story_bible_sha256"]
        == STORY_BIBLE_SHA256,
        "Story Bible binding mismatch.",
    )
    test_count += 1

    context_scope = plan["narrative_context_scope"]
    require(context_scope["beat_count"] == 44, "Expected 44 beats.")
    require(
        context_scope["first_beat_id"] == "P10G-BEAT-001",
        "Unexpected first beat.",
    )
    require(
        context_scope["last_beat_id"] == "P10G-BEAT-044",
        "Unexpected last beat.",
    )
    test_count += 1

    beats = parse_canon_beats(
        repository_root
        / "docs/evidence/p10g-canon-beat-sheet"
        / "38-canon-beat-sheet-third-revised-draft.md",
        source_path=(
            "docs/evidence/p10g-canon-beat-sheet/"
            "38-canon-beat-sheet-third-revised-draft.md"
        ),
    )
    require(len(beats) == 44, "Beat parser did not return 44 beats.")
    require(
        all(beat["field_count"] == 16 for beat in beats),
        "Every beat must contain 16 fields.",
    )
    require(
        len({tuple(beat["field_sequence"]) for beat in beats}) == 1,
        "Beat field sequences are inconsistent.",
    )
    test_count += 1

    require(
        beats[-1]["source_locator"]["end_line"] == 865,
        "Beat 44 must end before the post-beat canon sections.",
    )
    require(
        "# 18. Demian Character Arc"
        not in json.dumps(beats[-1], ensure_ascii=True),
        "Post-beat canon sections leaked into Beat 44.",
    )
    require(
        plan["narrative_context_scope"]["beat_boundary_policy"]
        == "top_level_heading_terminates_active_beat",
        "Beat-boundary policy is missing from the compiled plan.",
    )
    test_count += 1

    require(
        all(
            not packet["source_locator"]["path"].startswith("/")
            for packet in plan["scene_context_packets"]
        ),
        "Scene source locators must be repository-relative.",
    )
    require(
        all(
            not section["source_locator"]["path"].startswith("/")
            for section in plan["canonical_context_index"][
                "story_bible_sections"
            ]
        ),
        "Story Bible source locators must be repository-relative.",
    )
    test_count += 1

    render_scope = plan["editorial_render_scope"]
    require(
        render_scope["required_narrative_units"]
        == [
            "prologue_foundation",
            "character_foundation",
            "escalation_bridge",
            "act_2b",
            "act_3",
            "epilogue",
        ],
        "Editorial units are incomplete or out of order.",
    )
    require(
        render_scope["selection_locked"] is False,
        "Editorial selection must remain unlocked.",
    )
    test_count += 1

    require(
        len(plan["scene_context_packets"]) == 44,
        "Expected one source context packet per beat.",
    )
    require(
        all(
            packet["generation_authorized"] is False
            for packet in plan["scene_context_packets"]
        ),
        "Scene packets must not authorize generation.",
    )
    test_count += 1

    require(
        plan["shot_context_packet_contract"]["instance_count"] == 0,
        "Shot packets must remain deferred.",
    )
    require(
        render_scope["final_shot_count"] is None,
        "Final shot count must remain unlocked.",
    )
    test_count += 1

    identity_packs = {
        pack["character_id"]: pack
        for pack in plan["character_identity_packs"]
    }
    require(
        identity_packs["demian"]["asset"]["sha256"]
        == DEMIAN_REFERENCE_SHA256,
        "Demian identity binding mismatch.",
    )
    require(
        identity_packs["yd"]["asset"]["sha256"]
        == YD_REFERENCE_SHA256,
        "Y.D. identity binding mismatch.",
    )
    test_count += 1

    require(
        identity_packs["demian"]["usage_policy"][
            "identity_and_character_state_are_separate"
        ]
        is True,
        "Demian identity and state must remain separate.",
    )
    require(
        identity_packs["yd"]["usage_policy"][
            "identity_persona_and_voice_stage_are_separate"
        ]
        is True,
        "Y.D. identity, persona, and voice stage must remain separate.",
    )
    test_count += 1

    retrieval_policy = plan["canonical_context_index"][
        "retrieval_policy"
    ]
    require(
        retrieval_policy[
            "complete_canon_dump_to_media_model_allowed"
        ]
        is False,
        "Complete canon dumps to media models must be forbidden.",
    )
    require(
        retrieval_policy["exact_filters_precede_semantic_retrieval"]
        is True,
        "Exact filters must precede semantic retrieval.",
    )
    test_count += 1

    require(
        plan["ambiguity_report"]["status"]
        == "clarification_required",
        "Clarification status is incorrect.",
    )
    require(
        len(plan["clarification_requests"]) == 3,
        "Expected three blocking clarification requests.",
    )
    require(
        all(
            request["blocking"] is True
            for request in plan["clarification_requests"]
        ),
        "All current clarification requests must be blocking.",
    )
    test_count += 1

    require(
        plan["generation_authorized"] is False,
        "Generation must not be authorized.",
    )
    require(
        not any(plan["security"].values()),
        "All execution and network flags must remain false.",
    )
    test_count += 1

    with tempfile.TemporaryDirectory() as temporary_directory:
        output_path = Path(temporary_directory) / "plan.json"
        write_scene_shot_plan(output_path, plan)

        loaded = json.loads(output_path.read_text(encoding="utf-8"))
        require(loaded == plan, "Serialized plan mismatch.")

        try:
            write_scene_shot_plan(output_path, plan)
        except FileExistsError:
            pass
        else:
            raise AssertionError(
                "Atomic non-overwrite protection did not activate."
            )

    test_count += 1

    require(test_count == 17, "Unexpected test count.")

    print(f"Scene-shot compiler tests passed: {test_count}")
    print("CANONFLOW NARRATIVE CONTEXT SCENE-SHOT COMPILER: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
