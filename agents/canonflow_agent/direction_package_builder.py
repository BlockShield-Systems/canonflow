from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator, Mapping


SCHEMA_VERSION = "1.0"

PACKAGE_TYPE_GLOBAL = (
    "canonflow_gemini_structured_direction_global_contract"
)
PACKAGE_TYPE_SEGMENT = (
    "canonflow_gemini_structured_direction_segment_input"
)
PACKAGE_TYPE_MERGE = (
    "canonflow_gemini_structured_direction_merge_manifest"
)

EVIDENCE_64_PATH = Path(
    "docs/evidence/p10g-canon-beat-sheet/"
    "64-six-segment-showcase-selection-validation.json"
)
EVIDENCE_64_SHA256 = (
    "a2949559676d5ed332d5c5815e61ee89"
    "a58a8714f286d39b138560089d9ded2a"
)
EVIDENCE_64_TAG = (
    "p10g-six-segment-showcase-selection-v1-validated"
)
EVIDENCE_64_COMMIT = (
    "9f5efadfedb29081e44193f5f78f5c9ac6e21cf1"
)
EVIDENCE_64_ARTIFACT_ID = (
    "73d5bbd5-3458-5269-8d09-a5522f28c237"
)
SHOWCASE_PLAN_ID = (
    "437f1eca-41e6-58e6-9899-a80b280de0bd"
)

SEGMENT_ORDER = (
    "prologue",
    "act_1",
    "act_2a",
    "act_2b",
    "act_3",
    "epilogue",
)

SEGMENT_CONTRACT = {
    "prologue": {
        "shot_count": 7,
        "scene_count": 3,
        "runtime_seconds": 65,
    },
    "act_1": {
        "shot_count": 15,
        "scene_count": 7,
        "runtime_seconds": 115,
    },
    "act_2a": {
        "shot_count": 9,
        "scene_count": 4,
        "runtime_seconds": 75,
    },
    "act_2b": {
        "shot_count": 11,
        "scene_count": 9,
        "runtime_seconds": 90,
    },
    "act_3": {
        "shot_count": 14,
        "scene_count": 6,
        "runtime_seconds": 115,
    },
    "epilogue": {
        "shot_count": 6,
        "scene_count": 3,
        "runtime_seconds": 50,
    },
}

EXPECTED_FILE_SHA256S = {
    "00-global-contract.json": (
        "e39bf4f7806764eb8777c17f63c9b86a"
        "34a924958e70e93d346c101fd4420bb0"
    ),
    "01-prologue.json": (
        "f25fc6e9a67b63f4550ee17f483ad296"
        "cb87dbfa6846d0751d70df70d8179db3"
    ),
    "02-act_1.json": (
        "eaa86bb7824412610df87dc7a57042d6"
        "702c3f3ace04b2aa9844ccc8f1a9f528"
    ),
    "03-act_2a.json": (
        "0d88db2a81fbce5e416593a2c4fe5ff9"
        "3083ce59fb0eef697e90d39c4b10b06a"
    ),
    "04-act_2b.json": (
        "bd46b69187f2618fcc1129c685e6d783"
        "5dfebddeba7967286aa9884274388187"
    ),
    "05-act_3.json": (
        "d6c1a5c05fccc10579bd9b901a9e810f"
        "9288d4abfdba241746c9dd49dd77774f"
    ),
    "06-epilogue.json": (
        "3d8b425dc7f99d191cf30780766933b2"
        "f59e8ef1a5c8c60c2bed6ff4b23c3aec"
    ),
    "07-merge-manifest.json": (
        "5e04a87892012cec401478e61903dcacab"
        "155374c3d6fb0c2d929b22011174b1"
    ),
}

EXPECTED_GLOBAL_CONTRACT_ID = (
    "d436347d-3068-5a0f-98db-21386ba492aa"
)
EXPECTED_MERGE_MANIFEST_ID = (
    "826f785d-fccb-57f6-91a3-28b45cac3055"
)


class DirectionPackageError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DirectionPackageError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def serialized_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def value_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def serialized_sha256(value: Any) -> str:
    return hashlib.sha256(serialized_bytes(value)).hexdigest()


def stable_id(
    namespace: uuid.UUID,
    label: str,
    value: Any,
) -> str:
    return str(
        uuid.uuid5(
            namespace,
            f"{label}:{value_sha256(value)}",
        )
    )


def sanitize_identity_bindings(
    bindings: Any,
) -> list[dict[str, Any]]:
    if not isinstance(bindings, list):
        return []

    sanitized: list[dict[str, Any]] = []

    for binding in bindings:
        if not isinstance(binding, dict):
            continue

        asset = binding.get("asset")
        usage_policy = binding.get("usage_policy")
        asset_metadata: dict[str, Any] = {}

        if isinstance(asset, dict):
            for key in (
                "sha256",
                "mime_type",
                "width",
                "height",
                "view_layout",
            ):
                if key in asset:
                    asset_metadata[key] = deepcopy(asset[key])

        sanitized.append(
            {
                "character_id": binding.get("character_id"),
                "identity_pack_id": binding.get(
                    "identity_pack_id"
                ),
                "reference_asset_metadata": asset_metadata,
                "usage_policy": (
                    deepcopy(usage_policy)
                    if isinstance(usage_policy, dict)
                    else {}
                ),
                "reference_image_bytes_included": False,
                "reference_image_transmission_authorized": False,
            }
        )

    return sanitized


def sanitize_scene_context(value: Any) -> Any:
    if isinstance(value, list):
        return [
            sanitize_scene_context(item)
            for item in value
        ]

    if not isinstance(value, dict):
        return deepcopy(value)

    sanitized: dict[str, Any] = {}

    for key, child in value.items():
        if key == "generation_authorized":
            sanitized[key] = False
        elif key == "provider_adapter":
            sanitized[key] = {
                "external_request_allowed": False,
                "status": "not_selected",
            }
        elif key == "identity_asset_bindings":
            sanitized[key] = sanitize_identity_bindings(child)
        else:
            sanitized[key] = sanitize_scene_context(child)

    return sanitized


def transform_shot_packet(
    packet: Mapping[str, Any],
) -> dict[str, Any]:
    blocking = packet.get("blocking", {})
    camera = packet.get("camera", {})
    character_states = packet.get("character_states", {})
    location_state = packet.get("location_state", {})
    style_constraints = packet.get("style_constraints", {})
    dialogue_constraints = packet.get(
        "dialogue_or_voice_constraints",
        {},
    )
    retrieval_trace = packet.get("retrieval_trace", {})
    source_hashes = packet.get("source_hashes", {})

    if not isinstance(blocking, dict):
        blocking = {}
    if not isinstance(camera, dict):
        camera = {}
    if not isinstance(character_states, dict):
        character_states = {}
    if not isinstance(location_state, dict):
        location_state = {}
    if not isinstance(style_constraints, dict):
        style_constraints = {}
    if not isinstance(dialogue_constraints, dict):
        dialogue_constraints = {}
    if not isinstance(retrieval_trace, dict):
        retrieval_trace = {}
    if not isinstance(source_hashes, dict):
        source_hashes = {}

    legacy_staging = style_constraints.get(
        "production_staging"
    )

    return {
        "identity": {
            "shot_id": packet.get("shot_id"),
            "scene_id": packet.get("scene_id"),
            "segment_id": packet.get("segment_id"),
            "scene_order": packet.get("scene_order"),
            "shot_order": packet.get("shot_order"),
            "phase": packet.get("phase"),
        },
        "timeline": {
            "duration_seconds": packet.get("duration_seconds"),
            "start_seconds": packet.get(
                "timeline_start_seconds"
            ),
            "end_seconds": packet.get(
                "timeline_end_seconds"
            ),
            "duration_is_fixed": True,
            "timeline_position_is_fixed": True,
        },
        "canon_context": {
            "source_beat_ids": deepcopy(
                packet.get("source_beat_ids", [])
            ),
            "beat_sha256": source_hashes.get("beat_sha256"),
            "retrieval_trace": deepcopy(retrieval_trace),
            "canon_mutation_allowed": False,
        },
        "narrative_context": {
            "action_source": deepcopy(
                blocking.get("action_source")
            ),
            "participants": deepcopy(
                blocking.get("participants")
            ),
            "character_states": deepcopy(character_states),
            "location_state": deepcopy(location_state),
            "dialogue_or_voice_constraints": deepcopy(
                dialogue_constraints
            ),
        },
        "identity_context": {
            "bindings": sanitize_identity_bindings(
                packet.get("identity_asset_bindings")
            ),
            "identity_and_character_state_are_separate": True,
            "reference_image_bytes_included": False,
            "reference_images_transmitted": False,
        },
        "hard_constraints": {
            "blocking_policy": deepcopy(
                blocking.get("policy")
            ),
            "negative_constraints": deepcopy(
                packet.get("negative_constraints", [])
            ),
            "preserve_canon_tone": style_constraints.get(
                "preserve_canon_tone"
            ),
            "preserve_epistemic_ambiguity": (
                style_constraints.get(
                    "preserve_epistemic_ambiguity"
                )
            ),
            "authoritative_canon_mutation_allowed": False,
            "shot_duration_mutation_allowed": False,
            "timeline_mutation_allowed": False,
            "identity_substitution_allowed": False,
        },
        "creative_hints": {
            "policy": (
                "Advisory and non-binding. The model may adopt, "
                "refine, or reject each hint when justified by "
                "canon, continuity, runtime, and visual quality."
            ),
            "camera": {
                "framing": deepcopy(camera.get("framing")),
                "lens_intent": deepcopy(
                    camera.get("lens_intent")
                ),
                "movement": deepcopy(camera.get("movement")),
            },
            "legacy_production_staging_reference": {
                "value": deepcopy(legacy_staging),
                "classification": (
                    "legacy_mixed_direction_reference"
                ),
                "binding": False,
                "must_not_override_hard_constraints": True,
            },
        },
        "model_decisions_required": {
            "visual_intent": True,
            "shot_design": True,
            "composition_and_framing": True,
            "camera_position_and_angle": True,
            "camera_system_and_sensor_intent": True,
            "lens_and_focal_length": True,
            "focus_and_depth_of_field": True,
            "frame_rate_and_shutter": True,
            "aperture_iso_and_exposure": True,
            "camera_movement": True,
            "lighting_design": True,
            "color_palette_and_grading": True,
            "filters_and_optical_effects": True,
            "visual_effects": True,
            "transition_design": True,
            "continuity_state": True,
        },
        "execution_controls": {
            "provider_request_authorized": False,
            "reference_image_transmission_authorized": False,
            "media_generation_authorized": False,
        },
    }


def build_global_contract(
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    core = {
        "schema_version": SCHEMA_VERSION,
        "package_type": PACKAGE_TYPE_GLOBAL,
        "source": {
            "repository_head": EVIDENCE_64_COMMIT,
            "evidence_tag": EVIDENCE_64_TAG,
            "evidence_path": EVIDENCE_64_PATH.as_posix(),
            "evidence_sha256": EVIDENCE_64_SHA256,
            "evidence_artifact_id": EVIDENCE_64_ARTIFACT_ID,
            "showcase_plan_id": SHOWCASE_PLAN_ID,
        },
        "purpose": {
            "task": (
                "Create structured cinematic direction decisions "
                "for existing deterministic shot context containers."
            ),
            "shot_selection_mutation_allowed": False,
            "timeline_mutation_allowed": False,
            "canon_mutation_allowed": False,
            "media_generation_requested": False,
        },
        "runtime_contract": deepcopy(
            evidence.get("runtime_contract", {})
        ),
        "presentation_contract": deepcopy(
            evidence.get("presentation_contract", {})
        ),
        "selection_contract": deepcopy(
            evidence.get("selection_contract", {})
        ),
        "segment_order": list(SEGMENT_ORDER),
        "creative_authority": {
            "final_creative_direction_source": (
                "gemini_structured_direction_synthesis"
            ),
            "existing_camera_values_are": (
                "advisory_non_binding_hints"
            ),
            "legacy_production_staging_is": (
                "advisory_mixed_direction_reference"
            ),
            "model_may_reject_hints": True,
            "rejection_requires_short_reason": True,
            "hard_constraints_override_hints": True,
            "canon_context_overrides_hints": True,
            "continuity_overrides_unmotivated_variation": True,
        },
        "continuity_protocol": {
            "processing_order_is_mandatory": True,
            "first_segment_has_no_prior_handoff": True,
            "later_segments_require_previous_handoff": True,
            "handoff_fields": [
                "last_shot_id",
                "character_visual_states",
                "location_visual_state",
                "lighting_state",
                "color_state",
                "camera_rhythm_state",
                "active_visual_motifs",
                "unresolved_visual_requirements",
                "next_segment_requirements",
            ],
        },
        "required_segment_output_schema": {
            "segment_id": "string",
            "source_segment_package_id": "uuid",
            "shot_directions": [
                {
                    "shot_id": "existing UUID; exactly once",
                    "duration_seconds": "fixed integer",
                    "visual_intent": "string",
                    "adopted_creative_hints": ["string"],
                    "rejected_creative_hints": [
                        {
                            "hint": "string",
                            "reason": "string",
                        }
                    ],
                    "composition": {
                        "framing": "string",
                        "camera_position": "string",
                        "camera_angle": "string",
                        "subject_blocking": "string",
                        "depth_staging": "string",
                    },
                    "camera": {
                        "camera_system_intent": "string",
                        "sensor_format_intent": "string",
                        "lens_type": "string",
                        "focal_length_mm": (
                            "number or bounded range"
                        ),
                        "focus_strategy": "string",
                        "depth_of_field": "string",
                        "frame_rate_fps": "number",
                        "shutter_angle_degrees": "number",
                        "aperture": "string",
                        "iso": "number or bounded range",
                        "exposure_compensation": "string",
                        "movement": "string",
                        "support_system": "string",
                    },
                    "lighting": {
                        "motivation": "string",
                        "key": "string",
                        "fill": "string",
                        "backlight_or_edge": "string",
                        "practicals": "string",
                        "contrast_ratio_intent": "string",
                        "atmosphere": "string",
                    },
                    "color_and_finish": {
                        "palette": ["string"],
                        "white_balance_intent": "string",
                        "grading_intent": "string",
                        "texture": "string",
                        "filters": ["string"],
                    },
                    "effects": {
                        "practical_effects": ["string"],
                        "visual_effects": ["string"],
                        "optical_effects": ["string"],
                        "prohibited_effects": ["string"],
                    },
                    "transition": {
                        "entry": "string",
                        "exit": "string",
                        "continuity_purpose": "string",
                    },
                    "continuity": {
                        "inherits": ["string"],
                        "establishes": ["string"],
                        "must_preserve": ["string"],
                    },
                    "assumptions": ["string"],
                    "constraint_checks": {
                        "canon_preserved": "boolean",
                        "identity_preserved": "boolean",
                        "runtime_preserved": "boolean",
                        "timeline_preserved": "boolean",
                    },
                }
            ],
            "continuity_handoff": {
                "last_shot_id": "existing UUID",
                "character_visual_states": "object",
                "location_visual_state": "object",
                "lighting_state": "object",
                "color_state": "object",
                "camera_rhythm_state": "object",
                "active_visual_motifs": ["string"],
                "unresolved_visual_requirements": ["string"],
                "next_segment_requirements": ["string"],
            },
        },
        "execution_controls": {
            "provider_calls": False,
            "http_requests": False,
            "network_access": False,
            "reference_images_transmitted": False,
            "media_generation_authorized": False,
        },
    }

    result = deepcopy(core)
    namespace = uuid.UUID(SHOWCASE_PLAN_ID)
    result["global_contract_id"] = stable_id(
        namespace,
        "global-direction-contract",
        core,
    )
    return result


def build_direction_package(
    repository_root: Path,
) -> dict[str, dict[str, Any]]:
    root = repository_root.resolve()
    evidence_path = root / EVIDENCE_64_PATH

    require(
        evidence_path.is_file(),
        f"Evidence 64 artifact not found: {evidence_path}",
    )
    require(
        sha256_file(evidence_path) == EVIDENCE_64_SHA256,
        "Evidence 64 artifact SHA-256 mismatch.",
    )

    evidence = json.loads(
        evidence_path.read_text(encoding="utf-8")
    )

    require(
        evidence.get("artifact_id") == EVIDENCE_64_ARTIFACT_ID,
        "Evidence 64 artifact ID mismatch.",
    )
    require(
        evidence.get("showcase_plan_id") == SHOWCASE_PLAN_ID,
        "Evidence 64 showcase-plan ID mismatch.",
    )

    source_packets = evidence.get("shot_context_packets")
    source_scenes = evidence.get("selected_scenes")

    require(
        isinstance(source_packets, list),
        "shot_context_packets must be a list.",
    )
    require(
        isinstance(source_scenes, list),
        "selected_scenes must be a list.",
    )
    require(
        len(source_packets) == 62,
        "Evidence 64 must contain exactly 62 shot packets.",
    )
    require(
        len(source_scenes) == 32,
        "Evidence 64 must contain exactly 32 selected scenes.",
    )

    source_shot_ids = [
        packet.get("shot_id")
        for packet in source_packets
    ]

    require(
        all(
            isinstance(shot_id, str)
            for shot_id in source_shot_ids
        ),
        "Every shot packet requires a string shot_id.",
    )
    require(
        len(set(source_shot_ids)) == 62,
        "Evidence 64 shot IDs must be unique.",
    )

    namespace = uuid.UUID(SHOWCASE_PLAN_ID)
    global_contract = build_global_contract(evidence)
    global_sha256 = serialized_sha256(global_contract)

    package_files: dict[str, dict[str, Any]] = {
        "00-global-contract.json": global_contract,
    }

    segment_manifest_records: list[dict[str, Any]] = []
    transformed_shot_ids: list[str] = []

    for segment_index, segment_id in enumerate(
        SEGMENT_ORDER,
        start=1,
    ):
        segment_packets = [
            packet
            for packet in source_packets
            if packet.get("segment_id") == segment_id
        ]
        segment_packets.sort(
            key=lambda packet: (
                packet.get("timeline_start_seconds", 0),
                packet.get("scene_order", 0),
                packet.get("shot_order", 0),
                packet.get("shot_id", ""),
            )
        )

        segment_scenes = [
            sanitize_scene_context(scene)
            for scene in source_scenes
            if isinstance(scene, dict)
            and scene.get("segment_id") == segment_id
        ]
        segment_scenes.sort(
            key=lambda scene: (
                scene.get("scene_order", 0),
                scene.get("scene_id", ""),
            )
        )

        transformed_packets = [
            transform_shot_packet(packet)
            for packet in segment_packets
        ]
        shot_ids = [
            packet["identity"]["shot_id"]
            for packet in transformed_packets
        ]
        runtime_seconds = sum(
            int(packet["timeline"]["duration_seconds"])
            for packet in transformed_packets
        )

        expected = SEGMENT_CONTRACT[segment_id]
        require(
            len(transformed_packets)
            == expected["shot_count"],
            f"{segment_id}: shot count mismatch.",
        )
        require(
            len(segment_scenes)
            == expected["scene_count"],
            f"{segment_id}: scene count mismatch.",
        )
        require(
            runtime_seconds == expected["runtime_seconds"],
            f"{segment_id}: runtime mismatch.",
        )

        previous_segment_id = (
            SEGMENT_ORDER[segment_index - 2]
            if segment_index > 1
            else None
        )
        next_segment_id = (
            SEGMENT_ORDER[segment_index]
            if segment_index < len(SEGMENT_ORDER)
            else None
        )

        segment_core = {
            "schema_version": SCHEMA_VERSION,
            "package_type": PACKAGE_TYPE_SEGMENT,
            "segment_id": segment_id,
            "segment_index": segment_index,
            "global_contract": {
                "filename": "00-global-contract.json",
                "global_contract_id": global_contract[
                    "global_contract_id"
                ],
                "sha256": global_sha256,
            },
            "processing_context": {
                "previous_segment_id": previous_segment_id,
                "next_segment_id": next_segment_id,
                "prior_continuity_handoff_required": (
                    previous_segment_id is not None
                ),
                "prior_continuity_handoff": None,
                "model_must_return_continuity_handoff": True,
                "independent_parallel_processing_allowed": False,
            },
            "fixed_segment_contract": {
                "shot_count": len(transformed_packets),
                "scene_count": len(segment_scenes),
                "runtime_seconds": runtime_seconds,
                "shot_ids_in_order": shot_ids,
            },
            "selected_scene_contexts": segment_scenes,
            "shot_direction_inputs": transformed_packets,
            "execution_controls": {
                "provider_request_authorized": False,
                "reference_image_transmission_authorized": False,
                "media_generation_authorized": False,
            },
        }

        segment_package = deepcopy(segment_core)
        segment_package["segment_package_id"] = stable_id(
            namespace,
            f"segment-direction-package:{segment_id}",
            segment_core,
        )

        filename = f"{segment_index:02d}-{segment_id}.json"
        file_sha256 = serialized_sha256(segment_package)
        file_size = len(serialized_bytes(segment_package))

        package_files[filename] = segment_package
        transformed_shot_ids.extend(shot_ids)

        segment_manifest_records.append(
            {
                "filename": filename,
                "segment_id": segment_id,
                "segment_package_id": segment_package[
                    "segment_package_id"
                ],
                "sha256": file_sha256,
                "bytes": file_size,
                "shot_ids_in_order": shot_ids,
                "shot_count": len(transformed_packets),
                "scene_count": len(segment_scenes),
                "runtime_seconds": runtime_seconds,
                "previous_segment_id": previous_segment_id,
                "next_segment_id": next_segment_id,
            }
        )

    require(
        transformed_shot_ids == source_shot_ids,
        "Transformed shot ordering differs from Evidence 64.",
    )

    narrative_runtime = sum(
        record["runtime_seconds"]
        for record in segment_manifest_records
    )
    require(
        narrative_runtime == 510,
        "Direction package must contain 510 narrative seconds.",
    )

    merge_core = {
        "schema_version": SCHEMA_VERSION,
        "package_type": PACKAGE_TYPE_MERGE,
        "source": {
            "repository_head": EVIDENCE_64_COMMIT,
            "evidence_tag": EVIDENCE_64_TAG,
            "evidence_sha256": EVIDENCE_64_SHA256,
            "evidence_artifact_id": EVIDENCE_64_ARTIFACT_ID,
            "showcase_plan_id": SHOWCASE_PLAN_ID,
        },
        "global_contract": {
            "filename": "00-global-contract.json",
            "global_contract_id": global_contract[
                "global_contract_id"
            ],
            "sha256": global_sha256,
        },
        "processing_order": list(SEGMENT_ORDER),
        "segment_packages": segment_manifest_records,
        "merge_contract": {
            "merge_execution": (
                "local_deterministic_validation"
            ),
            "creative_merge_model_call_required": False,
            "expected_segment_result_count": 6,
            "expected_shot_direction_count": 62,
            "expected_narrative_runtime_seconds": 510,
            "shot_ids_in_canonical_order": transformed_shot_ids,
            "duplicate_shot_ids_allowed": False,
            "unknown_shot_ids_allowed": False,
            "missing_shot_ids_allowed": False,
            "shot_reordering_allowed": False,
            "runtime_mutation_allowed": False,
            "timeline_mutation_allowed": False,
            "canon_mutation_allowed": False,
            "continuity_handoff_chain_required": True,
        },
        "execution_controls": {
            "provider_calls": False,
            "http_requests": False,
            "network_access": False,
            "reference_images_transmitted": False,
            "media_generation_authorized": False,
        },
    }

    merge_manifest = deepcopy(merge_core)
    merge_manifest["merge_manifest_id"] = stable_id(
        namespace,
        "direction-merge-manifest",
        merge_core,
    )
    package_files["07-merge-manifest.json"] = merge_manifest

    validate_direction_package(package_files)
    return package_files


def walk(
    value: Any,
    path: tuple[str, ...] = (),
) -> Iterator[tuple[tuple[str, ...], Any]]:
    yield path, value

    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, path + (str(key),))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, path + (str(index),))


def validate_direction_package(
    package_files: Mapping[str, Mapping[str, Any]],
) -> None:
    require(
        set(package_files) == set(EXPECTED_FILE_SHA256S),
        "Direction package file set mismatch.",
    )

    actual_hashes = {
        filename: serialized_sha256(value)
        for filename, value in package_files.items()
    }
    require(
        actual_hashes == EXPECTED_FILE_SHA256S,
        "Direction package differs from validated prototype.",
    )

    global_contract = package_files[
        "00-global-contract.json"
    ]
    merge_manifest = package_files[
        "07-merge-manifest.json"
    ]

    require(
        global_contract.get("global_contract_id")
        == EXPECTED_GLOBAL_CONTRACT_ID,
        "Global contract ID mismatch.",
    )
    require(
        merge_manifest.get("merge_manifest_id")
        == EXPECTED_MERGE_MANIFEST_ID,
        "Merge-manifest ID mismatch.",
    )

    false_only_keys = {
        "provider_calls",
        "http_requests",
        "network_access",
        "media_generation_requested",
        "media_generation_authorized",
        "provider_request_authorized",
        "reference_images_transmitted",
        "reference_image_bytes_included",
        "reference_image_transmission_authorized",
        "external_model_submission_allowed",
    }

    shot_ids: list[str] = []
    total_runtime = 0
    identity_binding_count = 0
    shot_locator_count = 0
    scene_locator_count = 0

    for filename, document in package_files.items():
        for object_path, value in walk(document):
            if not object_path:
                continue

            leaf = object_path[-1]

            if leaf in false_only_keys:
                require(
                    value is False,
                    f"{filename}: {'.'.join(object_path)} "
                    "must be false.",
                )

            if leaf != "path":
                continue

            require(
                not any(
                    token in object_path
                    for token in (
                        "identity_asset_bindings",
                        "identity_context",
                        "reference_asset_metadata",
                    )
                ),
                f"{filename}: identity asset path detected.",
            )
            require(
                object_path[-2:]
                == ("source_locator", "path"),
                f"{filename}: unexpected path field.",
            )

            if "shot_direction_inputs" in object_path:
                shot_locator_count += 1
            elif "selected_scene_contexts" in object_path:
                scene_locator_count += 1
            else:
                raise DirectionPackageError(
                    f"{filename}: source locator in "
                    "unexpected context."
                )

    for index, segment_id in enumerate(
        SEGMENT_ORDER,
        start=1,
    ):
        filename = f"{index:02d}-{segment_id}.json"
        package = package_files[filename]
        packets = package["shot_direction_inputs"]

        for packet in packets:
            shot_ids.append(packet["identity"]["shot_id"])
            total_runtime += packet["timeline"][
                "duration_seconds"
            ]
            identity_binding_count += len(
                packet["identity_context"]["bindings"]
            )

    require(len(shot_ids) == 62, "Expected 62 shots.")
    require(
        len(set(shot_ids)) == 62,
        "Shot IDs must be unique.",
    )
    require(
        total_runtime == 510,
        "Expected 510 narrative seconds.",
    )
    require(
        identity_binding_count == 98,
        "Expected 98 sanitized identity bindings.",
    )
    require(
        shot_locator_count == 62,
        "Expected 62 shot source locators.",
    )
    require(
        scene_locator_count == 32,
        "Expected 32 scene source locators.",
    )
    require(
        merge_manifest["merge_contract"][
            "shot_ids_in_canonical_order"
        ]
        == shot_ids,
        "Merge-manifest shot order mismatch.",
    )


def checksum_manifest(
    package_files: Mapping[str, Mapping[str, Any]],
) -> str:
    return "".join(
        f"{serialized_sha256(package_files[filename])}"
        f"  {filename}\n"
        for filename in sorted(package_files)
    )


def write_direction_package(
    output_path: Path,
    package_files: Mapping[str, Mapping[str, Any]],
) -> None:
    validate_direction_package(package_files)

    target = output_path.resolve()
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        raise FileExistsError(
            f"Output path already exists: {target}"
        )

    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{target.name}.tmp-",
            dir=parent,
        )
    )

    try:
        for filename in sorted(package_files):
            path = temporary / filename
            payload = serialized_bytes(package_files[filename])

            descriptor = os.open(
                path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o644,
            )
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())

        checksum_path = temporary / "SHA256SUMS"
        checksum_payload = checksum_manifest(
            package_files
        ).encode("ascii")

        descriptor = os.open(
            checksum_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o644,
        )
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(checksum_payload)
            handle.flush()
            os.fsync(handle.fileno())

        directory_descriptor = os.open(
            temporary,
            os.O_RDONLY,
        )
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)

        if target.exists():
            raise FileExistsError(
                f"Output path already exists: {target}"
            )

        os.rename(temporary, target)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
