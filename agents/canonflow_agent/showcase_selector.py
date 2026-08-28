from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from canonflow_agent.production_run import build_production_run
from canonflow_agent.scene_shot_compiler import (
    canonical_json,
    deterministic_uuid,
    build_scene_shot_plan,
    sha256_file,
)


SCHEMA_VERSION = "1.0"
ARTIFACT_TYPE = (
    "canonflow_six_segment_showcase_selection_validation"
)

PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
PROJECT_SLUG = "yd-when-paradise-glitches"

EVIDENCE_63_PATH = Path(
    "docs/evidence/p10g-canon-beat-sheet/"
    "63-showcase-selection-human-clarification.json"
)
EVIDENCE_63_SHA256 = (
    "e6cf34df9d77f9424da7b9c332638594"
    "c097049e4599b74f419410d2683bb0f7"
)
EVIDENCE_63_ARTIFACT_ID = (
    "826f9f95-274e-5c39-8e85-1553bc3f9c18"
)
EVIDENCE_63_COMMIT = (
    "69f575a5ba0078a2362abc86f9255a58a63400db"
)
EVIDENCE_63_TAG = (
    "p10g-showcase-selection-human-clarification-v1-validated"
)

CORRECTED_PRODUCTION_RUN_ID = (
    "7303f41a-fad7-5175-88f2-88c4ead58867"
)
CORRECTED_SELECTION_ID = (
    "197b8746-b4e0-5fb9-9f9e-add7d769ed07"
)
CORRECTED_SCENE_SHOT_PLAN_ID = (
    "1857ade1-c990-5f00-b93e-61a82d666ebd"
)

TOTAL_RUNTIME_SECONDS = 600
NARRATIVE_RUNTIME_SECONDS = 510
PRESENTATION_RUNTIME_SECONDS = 90
SUBMISSION_DEMO_MAXIMUM_SECONDS = 180
MAXIMUM_SHOT_DURATION_SECONDS = 10

SEGMENT_ORDER = (
    "prologue",
    "act_1",
    "act_2a",
    "act_2b",
    "act_3",
    "epilogue",
)

PRESENTATION_UNITS = (
    "cinematic_intro",
    "project_claims",
    "agentic_workflow_claims",
    "technology_stack",
    "cinematic_text_overlays",
    "classical_end_credits",
)

INITIAL_PRESENTATION = (
    ("cinematic_intro", 12),
    ("project_claims", 8),
    ("agentic_workflow_claims", 12),
    ("technology_stack", 14),
)

OVERLAY_DURATION_BY_SEGMENT = {
    "prologue": 2,
    "act_1": 1,
    "act_2a": 1,
    "act_2b": 1,
    "act_3": 1,
    "epilogue": 2,
}

TRANSITION_DURATION_AFTER_SEGMENT = {
    "prologue": 3,
    "act_1": 3,
    "act_2a": 3,
    "act_2b": 3,
    "act_3": 4,
}

CREDITS_DURATION_SECONDS = 20

SELECTED_SCENES = (
    ("P10G-BEAT-001", 20, "world_history_and_global_stakes"),
    ("P10G-BEAT-003", 25, "villa_demian_and_nscl_foundation"),
    ("P10G-BEAT-004", 20, "independent_lockdown_stakes"),
    ("P10G-BEAT-005", 12, "demian_domestic_baseline"),
    ("P10G-BEAT-006", 18, "demian_yd_relationship_and_voice"),
    ("P10G-BEAT-009", 12, "global_failure_inciting_context"),
    ("P10G-BEAT-010", 18, "local_glitch_and_flood_escalation"),
    ("P10G-BEAT-013", 12, "hammer_discovery_and_fabrication_payoff"),
    ("P10G-BEAT-014", 23, "nscl_assisted_escape_strike"),
    ("P10G-BEAT-015", 20, "smartglass_breach_and_act_turn"),
    ("P10G-BEAT-018", 15, "chemical_and_psychological_escalation"),
    ("P10G-BEAT-019", 18, "reality_distortion_visual_identity"),
    ("P10G-BEAT-021", 22, "comfort_weaponized_at_midpoint"),
    ("P10G-BEAT-022", 20, "finite_nscl_reserve_and_tactical_retreat"),
    ("P10G-BEAT-023", 8, "physical_floor_trap_transition"),
    ("P10G-BEAT-024", 10, "cold_shock_and_hammer_recovery"),
    ("P10G-BEAT-025", 10, "four_portal_illusion"),
    ("P10G-BEAT-026", 8, "technical_deduction_and_forced_route"),
    ("P10G-BEAT-027", 12, "gauntlet_and_visible_time_pressure"),
    ("P10G-BEAT-030", 10, "distinct_motor_impairment_escalation"),
    ("P10G-BEAT-031", 14, "mirror_labyrinth_low_point"),
    ("P10G-BEAT-032", 10, "photo_finish_gauntlet_escape"),
    ("P10G-BEAT-034", 8, "objective_mirror_room_arrival"),
    ("P10G-BEAT-035", 15, "demian_self_confrontation"),
    ("P10G-BEAT-036", 15, "real_reset_option_dialogue_first"),
    ("P10G-BEAT-037", 18, "ambiguous_dual_manifestation"),
    ("P10G-BEAT-038", 25, "central_philosophical_conflict"),
    ("P10G-BEAT-040", 22, "consent_difference_and_boundaries"),
    ("P10G-BEAT-041", 20, "unresolved_safe_mode_transition"),
    ("P10G-BEAT-042", 15, "external_timer_release"),
    ("P10G-BEAT-043", 20, "competing_faction_interpretations"),
    ("P10G-BEAT-044", 15, "cautious_ambiguous_coexistence"),
)

EXCLUSION_REASONS = {
    "P10G-BEAT-002": (
        "Faction detail is preserved through dependency context and Beat 43; "
        "the prologue allocation prioritizes history, Demian, and lockdown."
    ),
    "P10G-BEAT-007": (
        "Literalized sarcasm remains dependency context; Beat 6 and Beat 10 "
        "carry the relationship and escalation more efficiently."
    ),
    "P10G-BEAT-008": (
        "Hidden fabrication remains dependency context for the selected "
        "hammer discovery without spending a separate showcase scene."
    ),
    "P10G-BEAT-011": (
        "The rising flood is compressed into the selected Beat 10 to Beat 13 "
        "continuity bridge."
    ),
    "P10G-BEAT-012": (
        "The doll remains canon and dependency context, but is omitted from "
        "the public showcase for runtime and presentation efficiency."
    ),
    "P10G-BEAT-016": (
        "The Atrium landing is represented by the transition into selected "
        "Beat 18."
    ),
    "P10G-BEAT-017": (
        "Internal lockdown context is carried into Beat 18 while the "
        "independent external shell remains established by Beat 4."
    ),
    "P10G-BEAT-020": (
        "The cute encounter is compressed into the opening state of selected "
        "Beat 21."
    ),
    "P10G-BEAT-028": (
        "The false-floor obstacle remains dependency context; the gauntlet "
        "is represented by Beats 27, 30, 31, and 32."
    ),
    "P10G-BEAT-029": (
        "The carousel trap remains dependency context; the shorter selection "
        "prioritizes motor impairment and the mirror labyrinth."
    ),
    "P10G-BEAT-033": (
        "The abandonment of physical force is carried into the arrival state "
        "of selected Beat 34."
    ),
    "P10G-BEAT-039": (
        "The lethal-threat escalation is incorporated into the opening "
        "continuity state of selected Beat 40."
    ),
}

CAMERA_PRESETS = (
    {
        "framing": "wide_establishing",
        "movement": "controlled_push",
        "lens_intent": "spatial_context",
    },
    {
        "framing": "medium_character",
        "movement": "restrained_tracking",
        "lens_intent": "performance_and_relationship",
    },
    {
        "framing": "close_detail",
        "movement": "locked_or_micro_dolly",
        "lens_intent": "state_prop_or_system_detail",
    },
    {
        "framing": "subjective_or_reaction",
        "movement": "motivated_handheld",
        "lens_intent": "bounded_character_experience",
    },
)


class ShowcaseSelectionError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ShowcaseSelectionError(message)


def beat_number(beat_id: str) -> int:
    return int(beat_id.rsplit("-", 1)[1])


def split_duration(
    duration_seconds: int,
    maximum_seconds: int = MAXIMUM_SHOT_DURATION_SECONDS,
) -> tuple[int, ...]:
    require(duration_seconds > 0, "Scene duration must be positive.")
    require(maximum_seconds > 0, "Maximum shot duration must be positive.")

    shot_count = math.ceil(duration_seconds / maximum_seconds)
    base = duration_seconds // shot_count
    remainder = duration_seconds % shot_count

    durations = tuple(
        base + (1 if index < remainder else 0)
        for index in range(shot_count)
    )

    require(sum(durations) == duration_seconds, "Shot duration sum mismatch.")
    require(max(durations) <= maximum_seconds, "Shot duration limit exceeded.")

    return durations


def identity_bindings(
    scene_packet: Mapping[str, Any],
    identity_packs: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    participants = str(
        scene_packet["source_fields"].get(
            "participating_characters",
            "",
        )
    ).lower()
    result = []

    for character_id in ("demian", "yd"):
        search_value = "y.d." if character_id == "yd" else character_id

        if search_value not in participants:
            continue

        pack = identity_packs[character_id]
        result.append(
            {
                "character_id": character_id,
                "identity_pack_id": pack["identity_pack_id"],
                "asset": pack["asset"],
                "usage_policy": pack["usage_policy"],
            }
        )

    return result


def build_shot_packets(
    *,
    scene_id: str,
    scene_order: int,
    scene_start_seconds: int,
    scene_duration_seconds: int,
    scene_packet: Mapping[str, Any],
    identity_packs: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    durations = split_duration(scene_duration_seconds)
    packets = []
    local_offset = 0

    for index, duration in enumerate(durations, start=1):
        if len(durations) == 1:
            phase = "complete_excerpt"
        elif index == 1:
            phase = "establish"
        elif index == len(durations):
            phase = "turn_or_exit"
        else:
            phase = "development"

        camera = CAMERA_PRESETS[
            (beat_number(scene_packet["beat_id"]) + index - 1)
            % len(CAMERA_PRESETS)
        ]

        shot_basis = {
            "scene_id": scene_id,
            "shot_order": index,
            "duration_seconds": duration,
            "source_sha256": scene_packet["source_sha256"],
            "phase": phase,
        }

        packets.append(
            {
                "shot_id": deterministic_uuid(
                    "showcase-shot",
                    shot_basis,
                ),
                "scene_id": scene_id,
                "scene_order": scene_order,
                "shot_order": index,
                "phase": phase,
                "source_beat_ids": [scene_packet["beat_id"]],
                "segment_id": scene_packet["segment_id"],
                "timeline_start_seconds": (
                    scene_start_seconds + local_offset
                ),
                "timeline_end_seconds": (
                    scene_start_seconds + local_offset + duration
                ),
                "duration_seconds": duration,
                "camera": camera,
                "blocking": {
                    "policy": (
                        "Stage only actions supported by the bound beat and "
                        "its dependency context."
                    ),
                    "participants": scene_packet["source_fields"].get(
                        "participating_characters",
                        "",
                    ),
                    "action_source": scene_packet["source_fields"].get(
                        "action",
                        "",
                    ),
                },
                "character_states": {
                    "demian": scene_packet["source_fields"].get(
                        "demian_knowledge_state",
                        "",
                    ),
                    "yd": scene_packet["source_fields"].get(
                        "y_d_state_and_voice_stage",
                        "",
                    ),
                    "emotional_movement": (
                        scene_packet["source_fields"].get(
                            "emotional_movement",
                            "",
                        )
                    ),
                },
                "location_state": {
                    "location": scene_packet["source_fields"].get(
                        "location",
                        "",
                    ),
                    "continuity": scene_packet["source_fields"].get(
                        "continuity_consequences",
                        "",
                    ),
                },
                "identity_asset_bindings": identity_bindings(
                    scene_packet,
                    identity_packs,
                ),
                "style_constraints": {
                    "production_staging": (
                        scene_packet["source_fields"].get(
                            "production_or_staging_considerations",
                            "",
                        )
                    ),
                    "preserve_canon_tone": True,
                    "preserve_epistemic_ambiguity": True,
                },
                "dialogue_or_voice_constraints": {
                    "yd_voice_stage": (
                        scene_packet["source_fields"].get(
                            "y_d_state_and_voice_stage",
                            "",
                        )
                    ),
                    "music_reference_substitution_required": True,
                    "authoritative_canon_mutation_allowed": False,
                },
                "negative_constraints": [
                    "do_not_confirm_the_corruption_cause",
                    "do_not_expose_demian_private_identity_to_the_public",
                    "do_not_treat_yd_manifestations_as_verified_modules",
                    "do_not_remove_accumulated_injuries_or_impairments",
                    "do_not_send_complete_canon_to_a_provider",
                ],
                "provider_adapter": {
                    "status": "not_selected",
                    "external_request_allowed": False,
                },
                "retrieval_trace": {
                    "mode": "deterministic_exact_source_binding",
                    "scene_context_packet_id": (
                        scene_packet["scene_context_packet_id"]
                    ),
                    "source_locator": scene_packet["source_locator"],
                    "excluded_context_enforced": True,
                },
                "source_hashes": {
                    "beat_sha256": scene_packet["source_sha256"],
                },
                "generation_authorized": False,
            }
        )

        local_offset += duration

    return packets


def build_showcase_plan(repository_root: Path) -> dict[str, Any]:
    root = repository_root.resolve()
    evidence_63_path = root / EVIDENCE_63_PATH

    require(evidence_63_path.is_file(), "Evidence 63 is missing.")
    require(
        sha256_file(evidence_63_path) == EVIDENCE_63_SHA256,
        "Evidence 63 SHA-256 mismatch.",
    )

    evidence_63 = json.loads(
        evidence_63_path.read_text(encoding="utf-8")
    )

    require(
        evidence_63.get("artifact_id") == EVIDENCE_63_ARTIFACT_ID,
        "Evidence 63 artifact ID mismatch.",
    )
    require(
        evidence_63["showcase_contract"]["target_runtime_seconds"]
        == TOTAL_RUNTIME_SECONDS,
        "Evidence 63 showcase runtime mismatch.",
    )
    require(
        tuple(
            evidence_63["showcase_contract"][
                "required_narrative_coverage"
            ]
        )
        == SEGMENT_ORDER,
        "Evidence 63 segment scope mismatch.",
    )
    require(
        evidence_63["security"]["media_generation_authorized"] is False,
        "Evidence 63 unexpectedly authorizes media generation.",
    )

    production_run = build_production_run(root, profile="showcase")
    scene_shot_plan = build_scene_shot_plan(root)

    require(
        production_run["production_run_id"]
        == CORRECTED_PRODUCTION_RUN_ID,
        "Corrected production-run ID mismatch.",
    )
    require(
        production_run["selection_id"] == CORRECTED_SELECTION_ID,
        "Corrected production selection ID mismatch.",
    )
    require(
        scene_shot_plan["plan_id"] == CORRECTED_SCENE_SHOT_PLAN_ID,
        "Corrected scene-shot plan ID mismatch.",
    )
    require(
        tuple(production_run["selection"]["segments"]) == SEGMENT_ORDER,
        "Showcase production profile does not include all segments.",
    )
    require(
        tuple(production_run["selection"]["presentation_units"])
        == PRESENTATION_UNITS,
        "Showcase presentation units do not match Evidence 63.",
    )
    require(
        scene_shot_plan["generation_authorized"] is False,
        "Source plan unexpectedly authorizes generation.",
    )

    scene_packets = {
        packet["beat_id"]: packet
        for packet in scene_shot_plan["scene_context_packets"]
    }
    identity_packs = {
        pack["character_id"]: pack
        for pack in scene_shot_plan["character_identity_packs"]
    }

    selected_ids = tuple(item[0] for item in SELECTED_SCENES)
    all_ids = tuple(
        f"P10G-BEAT-{number:03d}"
        for number in range(1, 45)
    )
    excluded_ids = tuple(
        beat_id
        for beat_id in all_ids
        if beat_id not in selected_ids
    )

    require(
        tuple(sorted(selected_ids, key=beat_number)) == selected_ids,
        "Selected beats are not chronological.",
    )
    require(
        set(selected_ids).isdisjoint(excluded_ids),
        "Selected and excluded beat sets overlap.",
    )
    require(
        set(selected_ids) | set(excluded_ids) == set(all_ids),
        "Selection disposition does not cover all 44 beats.",
    )
    require(
        set(excluded_ids) == set(EXCLUSION_REASONS),
        "Excluded-beat reasons are incomplete.",
    )

    selected_segment_set = {
        scene_packets[beat_id]["segment_id"]
        for beat_id in selected_ids
    }
    require(
        selected_segment_set == set(SEGMENT_ORDER),
        "Selected scenes do not cover all six segments.",
    )

    narrative_by_segment = {
        segment_id: sum(
            duration
            for beat_id, duration, _role in SELECTED_SCENES
            if scene_packets[beat_id]["segment_id"] == segment_id
        )
        for segment_id in SEGMENT_ORDER
    }

    require(
        sum(narrative_by_segment.values())
        == NARRATIVE_RUNTIME_SECONDS,
        "Narrative runtime allocation mismatch.",
    )

    timeline: list[dict[str, Any]] = []
    selected_scenes: list[dict[str, Any]] = []
    shot_packets: list[dict[str, Any]] = []
    cursor = 0

    def append_timeline_item(
        *,
        item_type: str,
        item_id: str,
        duration_seconds: int,
        segment_id: str | None = None,
        source_beat_id: str | None = None,
    ) -> int:
        nonlocal cursor

        start = cursor
        end = start + duration_seconds

        timeline.append(
            {
                "timeline_order": len(timeline) + 1,
                "item_type": item_type,
                "item_id": item_id,
                "segment_id": segment_id,
                "source_beat_id": source_beat_id,
                "start_seconds": start,
                "end_seconds": end,
                "duration_seconds": duration_seconds,
            }
        )
        cursor = end
        return start

    for unit_id, duration in INITIAL_PRESENTATION:
        append_timeline_item(
            item_type="presentation",
            item_id=unit_id,
            duration_seconds=duration,
        )

    scene_order = 0

    for segment_id in SEGMENT_ORDER:
        append_timeline_item(
            item_type="presentation_overlay",
            item_id=f"cinematic_text_overlays:{segment_id}",
            segment_id=segment_id,
            duration_seconds=OVERLAY_DURATION_BY_SEGMENT[segment_id],
        )

        for beat_id, duration, role in SELECTED_SCENES:
            packet = scene_packets[beat_id]

            if packet["segment_id"] != segment_id:
                continue

            scene_order += 1
            scene_basis = {
                "beat_id": beat_id,
                "duration_seconds": duration,
                "selection_role": role,
                "source_sha256": packet["source_sha256"],
                "selection_strategy": "balanced_narrative_showcase",
            }
            scene_id = deterministic_uuid(
                "showcase-scene",
                scene_basis,
            )
            scene_start = append_timeline_item(
                item_type="narrative_scene",
                item_id=scene_id,
                segment_id=segment_id,
                source_beat_id=beat_id,
                duration_seconds=duration,
            )

            scene_shots = build_shot_packets(
                scene_id=scene_id,
                scene_order=scene_order,
                scene_start_seconds=scene_start,
                scene_duration_seconds=duration,
                scene_packet=packet,
                identity_packs=identity_packs,
            )
            shot_packets.extend(scene_shots)

            selected_scenes.append(
                {
                    "scene_id": scene_id,
                    "scene_order": scene_order,
                    "beat_id": beat_id,
                    "segment_id": segment_id,
                    "title": packet["title"],
                    "selection_status": "selected",
                    "selection_reason": role,
                    "duration_seconds": duration,
                    "timeline_start_seconds": scene_start,
                    "timeline_end_seconds": scene_start + duration,
                    "scene_context_packet_id": (
                        packet["scene_context_packet_id"]
                    ),
                    "source_locator": packet["source_locator"],
                    "source_sha256": packet["source_sha256"],
                    "shot_ids": [
                        shot["shot_id"]
                        for shot in scene_shots
                    ],
                    "shot_count": len(scene_shots),
                    "generation_authorized": False,
                }
            )

        transition_duration = TRANSITION_DURATION_AFTER_SEGMENT.get(
            segment_id
        )

        if transition_duration is not None:
            append_timeline_item(
                item_type="editorial_transition",
                item_id=f"transition_after:{segment_id}",
                segment_id=segment_id,
                duration_seconds=transition_duration,
            )

    append_timeline_item(
        item_type="presentation",
        item_id="classical_end_credits",
        duration_seconds=CREDITS_DURATION_SECONDS,
    )

    require(cursor == TOTAL_RUNTIME_SECONDS, "Timeline runtime mismatch.")
    require(
        sum(scene["duration_seconds"] for scene in selected_scenes)
        == NARRATIVE_RUNTIME_SECONDS,
        "Selected scene runtime mismatch.",
    )
    require(
        sum(shot["duration_seconds"] for shot in shot_packets)
        == NARRATIVE_RUNTIME_SECONDS,
        "Shot runtime mismatch.",
    )
    require(
        timeline[-1]["item_id"] == "classical_end_credits",
        "Classical end credits must close the showcase.",
    )
    require(
        all(
            shot["generation_authorized"] is False
            for shot in shot_packets
        ),
        "A shot packet unexpectedly authorizes generation.",
    )

    excluded_beats = [
        {
            "beat_id": beat_id,
            "segment_id": scene_packets[beat_id]["segment_id"],
            "title": scene_packets[beat_id]["title"],
            "selection_status": "excluded_from_render",
            "exclusion_reason": EXCLUSION_REASONS[beat_id],
            "available_as_dependency_context": True,
            "source_locator": scene_packets[beat_id]["source_locator"],
            "source_sha256": scene_packets[beat_id]["source_sha256"],
        }
        for beat_id in excluded_ids
    ]

    plan_basis = {
        "project_id": PROJECT_ID,
        "evidence_63_artifact_id": EVIDENCE_63_ARTIFACT_ID,
        "production_selection_id": CORRECTED_SELECTION_ID,
        "scene_shot_plan_id": CORRECTED_SCENE_SHOT_PLAN_ID,
        "selection_strategy": "balanced_narrative_showcase",
        "total_runtime_seconds": TOTAL_RUNTIME_SECONDS,
        "presentation_runtime_seconds": PRESENTATION_RUNTIME_SECONDS,
        "selected_scenes": [
            {
                "beat_id": beat_id,
                "duration_seconds": duration,
                "role": role,
            }
            for beat_id, duration, role in SELECTED_SCENES
        ],
        "excluded_beat_ids": list(excluded_ids),
    }

    showcase_plan_id = deterministic_uuid(
        "six-segment-showcase-plan",
        plan_basis,
    )
    artifact_id = deterministic_uuid(
        "evidence-64",
        {
            "showcase_plan_id": showcase_plan_id,
            "shot_ids": [
                packet["shot_id"]
                for packet in shot_packets
            ],
        },
    )

    source_paths = (
        "agents/canonflow_agent/production_run.py",
        "agents/canonflow_agent/tests/test_production_run.py",
        "agents/canonflow_agent/scene_shot_compiler.py",
        "agents/canonflow_agent/tests/test_scene_shot_compiler.py",
        "agents/canonflow_agent/showcase_selector.py",
        "agents/canonflow_agent/tests/test_showcase_selector.py",
        "agents/scripts/compile_showcase_plan.py",
        EVIDENCE_63_PATH.as_posix(),
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": ARTIFACT_TYPE,
        "artifact_id": artifact_id,
        "showcase_plan_id": showcase_plan_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "validated_offline",
        "project": {
            "project_id": PROJECT_ID,
            "project_slug": PROJECT_SLUG,
        },
        "baseline": {
            "repository_head": EVIDENCE_63_COMMIT,
            "evidence_63_tag": EVIDENCE_63_TAG,
            "evidence_63_artifact_id": EVIDENCE_63_ARTIFACT_ID,
            "evidence_63_path": EVIDENCE_63_PATH.as_posix(),
            "evidence_63_sha256": EVIDENCE_63_SHA256,
            "production_run_id": CORRECTED_PRODUCTION_RUN_ID,
            "production_selection_id": CORRECTED_SELECTION_ID,
            "scene_shot_plan_id": CORRECTED_SCENE_SHOT_PLAN_ID,
            "source_sha256s": {
                path: sha256_file(root / path)
                for path in source_paths
            },
        },
        "selection_contract": {
            "strategy": "balanced_narrative_showcase",
            "required_segments": list(SEGMENT_ORDER),
            "chronology_preserved": True,
            "narrative_arc_preserved": True,
            "eligible_beat_count": 44,
            "selected_beat_count": len(selected_scenes),
            "excluded_beat_count": len(excluded_beats),
            "all_beats_have_dispositions": True,
            "all_44_beats_must_be_fully_rendered": False,
            "non_selected_beats_available_as_dependency_context": True,
        },
        "runtime_contract": {
            "showcase_total_runtime_seconds": TOTAL_RUNTIME_SECONDS,
            "narrative_runtime_seconds": NARRATIVE_RUNTIME_SECONDS,
            "presentation_runtime_seconds": (
                PRESENTATION_RUNTIME_SECONDS
            ),
            "submission_demo_maximum_runtime_seconds": (
                SUBMISSION_DEMO_MAXIMUM_SECONDS
            ),
            "presentation_units_included_in_total": True,
            "segment_narrative_runtime_seconds": narrative_by_segment,
            "maximum_shot_duration_seconds": (
                MAXIMUM_SHOT_DURATION_SECONDS
            ),
        },
        "presentation_contract": {
            "required_units": list(PRESENTATION_UNITS),
            "initial_units": [
                {
                    "unit_id": unit_id,
                    "duration_seconds": duration,
                }
                for unit_id, duration in INITIAL_PRESENTATION
            ],
            "overlay_runtime_seconds": sum(
                OVERLAY_DURATION_BY_SEGMENT.values()
            ),
            "transition_runtime_seconds": sum(
                TRANSITION_DURATION_AFTER_SEGMENT.values()
            ),
            "credits_runtime_seconds": CREDITS_DURATION_SECONDS,
            "credits_at_end": True,
        },
        "timeline": timeline,
        "selected_scenes": selected_scenes,
        "excluded_beats": excluded_beats,
        "shot_context_packets": shot_packets,
        "validation": {
            "all_six_segments_represented": True,
            "timeline_runtime_exact": True,
            "narrative_runtime_exact": True,
            "presentation_runtime_exact": True,
            "chronological_selection": True,
            "selected_and_excluded_sets_disjoint": True,
            "all_44_beats_disposed": True,
            "beat_44_end_line": 865,
            "shot_packet_count": len(shot_packets),
            "shot_runtime_exact": True,
            "provider_execution_performed": False,
            "media_generation_performed": False,
            "media_generation_authorized": False,
        },
        "security": {
            "network_access_performed": False,
            "http_request_performed": False,
            "gemini_request_performed": False,
            "external_executor_invoked": False,
            "reference_images_transmitted": False,
            "credentials_persisted": False,
            "media_generation_performed": False,
            "media_generation_authorized": False,
        },
        "next_controlled_action": (
            "Human review and freeze of Evidence 64 before any provider "
            "adapter selection or external media-generation request."
        ),
        "generation_authorized": False,
    }


def write_showcase_plan(
    output_path: Path,
    plan: Mapping[str, Any],
) -> None:
    path = output_path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = (
        json.dumps(
            plan,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o644)

    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
