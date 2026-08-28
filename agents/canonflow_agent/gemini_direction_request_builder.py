"""Deterministic offline Gemini direction-request descriptor compiler.

This module compiles the frozen Evidence 65 direction package into the
validated eight-file Gemini Interactions API request-descriptor package.

It does not inspect credentials, initialize a provider client, perform
network access, submit requests, or authorize media generation.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterator

MODEL_ID = "gemini-3.1-pro-preview"
INTERACTIONS_SCHEMA_REVISION = "2026-05-20"
EXPECTED_REQUEST_COUNT = 6
EXPECTED_SHOT_DIRECTION_INPUT_COUNT = 62
EXPECTED_NARRATIVE_RUNTIME_SECONDS = 510
EXPECTED_FALSE_CONTROL_COUNT = 195

RESPONSE_SCHEMA_TEMPLATE_ID = (
    "89f5aa30-6a03-50aa-b4b8-d1f0392ddb5c"
)
REQUEST_CHAIN_MANIFEST_ID = (
    "4ea32302-9fdf-5f41-8644-00d59c7acf42"
)

SEGMENT_ORDER = (
    "prologue",
    "act_1",
    "act_2a",
    "act_2b",
    "act_3",
    "epilogue",
)

EXPECTED_FILE_HASHES = {'00-response-schema-template.json': '00d88cdc47032725e2e07c4ad2916a4d52d0d6e0859e1c719a09c9fe272ac2a2',
 '01-prologue-request.json': 'c22f4ecad0feb1ad47eee674aa8273554e9d2106285f552062c7460d2641990d',
 '02-act_1-request.json': '59b66677af5a4d9e9cfff066757a0ef142e0d33ba894686f9fad2eb9402f573b',
 '03-act_2a-request.json': '61bd07cbd1e2ea1b7faeb095eb0937067ff40f631c0c74b671b578a1d21776e2',
 '04-act_2b-request.json': 'dd36559d0d7c52f540c91bbd670372232debba7de82b54c149ee4100d5318073',
 '05-act_3-request.json': '86c5edfd4b9ffa95814b0c5f4174d0ffbcc643c802abf7d19ef1d8e09f14de5a',
 '06-epilogue-request.json': '44329ca0f0259e045ef9b7d2f354a38e5142fc10f91a6e7084e428ff48493f25',
 '07-request-chain-manifest.json': '8cca5d023a8e470621e6a82d7fb4b9a9b3f6d9ea6536df9e8c092adeffc7dcd8'}


def _generate_legacy_package(
    output_dir: Path,
    repository_root: Path,
) -> None:
    import hashlib
    import json
    import math
    import os
    import uuid
    from copy import deepcopy
    from pathlib import Path
    from typing import Any, Iterator

    from canonflow_agent.direction_package_builder import (
        EXPECTED_GLOBAL_CONTRACT_ID,
        EXPECTED_MERGE_MANIFEST_ID,
        SEGMENT_ORDER,
        build_direction_package,
        serialized_bytes,
        serialized_sha256,
        validate_direction_package,
    )

    output_dir = Path(output_dir)
    repository_root = Path(repository_root)

    model_id = "gemini-3.1-pro-preview"
    input_token_limit = 1_048_576
    output_token_limit = 65_536

    package_files = build_direction_package(repository_root)
    validate_direction_package(package_files)

    global_contract = package_files[
        "00-global-contract.json"
    ]
    direction_merge_manifest = package_files[
        "07-merge-manifest.json"
    ]

    namespace = uuid.UUID(EXPECTED_MERGE_MANIFEST_ID)


    def canonical_bytes(value: Any) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")


    def canonical_sha256(value: Any) -> str:
        return hashlib.sha256(canonical_bytes(value)).hexdigest()


    def stable_id(label: str, value: Any) -> str:
        return str(
            uuid.uuid5(
                namespace,
                f"{label}:{canonical_sha256(value)}",
            )
        )


    def write_json(
        filename: str,
        value: Any,
    ) -> tuple[str, int]:
        payload = (
            json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")

        path = output_dir / filename
        path.write_bytes(payload)

        return hashlib.sha256(payload).hexdigest(), len(payload)


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


    def string_array_schema(
        description: str,
    ) -> dict[str, Any]:
        return {
            "type": "array",
            "description": description,
            "items": {
                "type": "string",
            },
        }


    def direction_response_schema(
        segment_id: str,
        shot_ids: list[str],
    ) -> dict[str, Any]:
        shot_count = len(shot_ids)

        shot_schema = {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "shot_id",
                "duration_seconds",
                "visual_intent",
                "adopted_creative_hints",
                "rejected_creative_hints",
                "composition",
                "camera",
                "lighting",
                "color_and_finish",
                "effects",
                "transition",
                "continuity",
                "assumptions",
                "constraint_checks",
            ],
            "properties": {
                "shot_id": {
                    "type": "string",
                    "enum": shot_ids,
                    "description": (
                        "Existing immutable shot ID from the input."
                    ),
                },
                "duration_seconds": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10,
                    "description": (
                        "Must exactly match the fixed input duration."
                    ),
                },
                "visual_intent": {
                    "type": "string",
                    "description": (
                        "Concise narrative and visual purpose."
                    ),
                },
                "adopted_creative_hints": string_array_schema(
                    "Input creative hints adopted by the model."
                ),
                "rejected_creative_hints": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "hint",
                            "reason",
                        ],
                        "properties": {
                            "hint": {
                                "type": "string",
                            },
                            "reason": {
                                "type": "string",
                            },
                        },
                    },
                },
                "composition": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "framing",
                        "camera_position",
                        "camera_angle",
                        "subject_blocking",
                        "depth_staging",
                    ],
                    "properties": {
                        "framing": {"type": "string"},
                        "camera_position": {"type": "string"},
                        "camera_angle": {"type": "string"},
                        "subject_blocking": {"type": "string"},
                        "depth_staging": {"type": "string"},
                    },
                },
                "camera": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "camera_system_intent",
                        "sensor_format_intent",
                        "lens_type",
                        "focal_length_mm",
                        "focus_strategy",
                        "depth_of_field",
                        "frame_rate_fps",
                        "shutter_angle_degrees",
                        "aperture",
                        "iso",
                        "exposure_compensation",
                        "movement",
                        "support_system",
                    ],
                    "properties": {
                        "camera_system_intent": {
                            "type": "string"
                        },
                        "sensor_format_intent": {
                            "type": "string"
                        },
                        "lens_type": {
                            "type": "string"
                        },
                        "focal_length_mm": {
                            "type": "string",
                            "description": (
                                "Single focal length or bounded range."
                            ),
                        },
                        "focus_strategy": {
                            "type": "string"
                        },
                        "depth_of_field": {
                            "type": "string"
                        },
                        "frame_rate_fps": {
                            "type": "number",
                            "minimum": 1,
                        },
                        "shutter_angle_degrees": {
                            "type": "number",
                            "minimum": 1,
                            "maximum": 360,
                        },
                        "aperture": {
                            "type": "string"
                        },
                        "iso": {
                            "type": "string",
                            "description": (
                                "Single ISO value or bounded range."
                            ),
                        },
                        "exposure_compensation": {
                            "type": "string"
                        },
                        "movement": {
                            "type": "string"
                        },
                        "support_system": {
                            "type": "string"
                        },
                    },
                },
                "lighting": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "motivation",
                        "key",
                        "fill",
                        "backlight_or_edge",
                        "practicals",
                        "contrast_ratio_intent",
                        "atmosphere",
                    ],
                    "properties": {
                        "motivation": {"type": "string"},
                        "key": {"type": "string"},
                        "fill": {"type": "string"},
                        "backlight_or_edge": {
                            "type": "string"
                        },
                        "practicals": {"type": "string"},
                        "contrast_ratio_intent": {
                            "type": "string"
                        },
                        "atmosphere": {"type": "string"},
                    },
                },
                "color_and_finish": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "palette",
                        "white_balance_intent",
                        "grading_intent",
                        "texture",
                        "filters",
                    ],
                    "properties": {
                        "palette": string_array_schema(
                            "Dominant and supporting colors."
                        ),
                        "white_balance_intent": {
                            "type": "string"
                        },
                        "grading_intent": {
                            "type": "string"
                        },
                        "texture": {"type": "string"},
                        "filters": string_array_schema(
                            "Optical or digital finishing filters."
                        ),
                    },
                },
                "effects": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "practical_effects",
                        "visual_effects",
                        "optical_effects",
                        "prohibited_effects",
                    ],
                    "properties": {
                        "practical_effects": string_array_schema(
                            "Practical effects required for the shot."
                        ),
                        "visual_effects": string_array_schema(
                            "Post-production visual effects."
                        ),
                        "optical_effects": string_array_schema(
                            "In-camera or lens-based effects."
                        ),
                        "prohibited_effects": string_array_schema(
                            "Effects excluded by canon or continuity."
                        ),
                    },
                },
                "transition": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "entry",
                        "exit",
                        "continuity_purpose",
                    ],
                    "properties": {
                        "entry": {"type": "string"},
                        "exit": {"type": "string"},
                        "continuity_purpose": {
                            "type": "string"
                        },
                    },
                },
                "continuity": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "inherits",
                        "establishes",
                        "must_preserve",
                    ],
                    "properties": {
                        "inherits": string_array_schema(
                            "Inherited continuity states."
                        ),
                        "establishes": string_array_schema(
                            "New continuity states established."
                        ),
                        "must_preserve": string_array_schema(
                            "Continuity states that cannot change."
                        ),
                    },
                },
                "assumptions": string_array_schema(
                    "Explicit assumptions made by the model."
                ),
                "constraint_checks": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "canon_preserved",
                        "identity_preserved",
                        "runtime_preserved",
                        "timeline_preserved",
                    ],
                    "properties": {
                        "canon_preserved": {
                            "type": "boolean"
                        },
                        "identity_preserved": {
                            "type": "boolean"
                        },
                        "runtime_preserved": {
                            "type": "boolean"
                        },
                        "timeline_preserved": {
                            "type": "boolean"
                        },
                    },
                },
            },
        }

        return {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "segment_id",
                "source_segment_package_id",
                "shot_directions",
                "continuity_handoff",
            ],
            "properties": {
                "segment_id": {
                    "type": "string",
                    "enum": [segment_id],
                },
                "source_segment_package_id": {
                    "type": "string",
                },
                "shot_directions": {
                    "type": "array",
                    "minItems": shot_count,
                    "maxItems": shot_count,
                    "items": shot_schema,
                },
                "continuity_handoff": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
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
                    "properties": {
                        "last_shot_id": {
                            "type": "string",
                            "enum": [shot_ids[-1]],
                        },
                        "character_visual_states": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "string"
                            },
                        },
                        "location_visual_state": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "string"
                            },
                        },
                        "lighting_state": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "string"
                            },
                        },
                        "color_state": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "string"
                            },
                        },
                        "camera_rhythm_state": {
                            "type": "object",
                            "additionalProperties": {
                                "type": "string"
                            },
                        },
                        "active_visual_motifs": string_array_schema(
                            "Visual motifs active after this segment."
                        ),
                        "unresolved_visual_requirements": (
                            string_array_schema(
                                "Visual requirements unresolved."
                            )
                        ),
                        "next_segment_requirements": (
                            string_array_schema(
                                "Requirements for the next segment."
                            )
                        ),
                    },
                },
            },
        }


    schema_template = {
        "schema_version": "1.0",
        "schema_type": (
            "canonflow_gemini_direction_segment_response_template"
        ),
        "description": (
            "Template contract. Each request descriptor contains a "
            "resolved segment-specific response_format schema."
        ),
        "segment_specific_bindings": [
            "segment_id.enum",
            "shot_directions.minItems",
            "shot_directions.maxItems",
            "shot_directions.items.properties.shot_id.enum",
            "continuity_handoff.properties.last_shot_id.enum",
        ],
        "validation_requirements": {
            "shot_ids_exactly_once": True,
            "canonical_shot_order_required": True,
            "fixed_duration_required": True,
            "fixed_timeline_required": True,
            "all_constraint_checks_true": True,
            "continuity_handoff_required": True,
        },
    }

    schema_template["schema_template_id"] = stable_id(
        "direction-response-schema-template",
        schema_template,
    )

    written_files: dict[str, dict[str, Any]] = {}

    schema_filename = "00-response-schema-template.json"
    schema_sha256, schema_bytes = write_json(
        schema_filename,
        schema_template,
    )

    written_files[schema_filename] = {
        "sha256": schema_sha256,
        "bytes": schema_bytes,
        "file_type": "response_schema_template",
    }

    system_instruction = (
        "You are the cinematic direction synthesis stage of CanonFlow. "
        "Create production-oriented visual direction for every supplied "
        "shot while preserving immutable canon, identity, duration, "
        "timeline, scene order, and segment order. Existing camera values "
        "and legacy production-staging text are advisory references, not "
        "binding decisions. Resolve contradictions in favor of hard "
        "constraints, canon context, identity continuity, and motivated "
        "visual continuity. Do not add, remove, merge, split, reorder, or "
        "renumber shots. Do not request tools, external data, image "
        "generation, or media execution. Return only JSON conforming to "
        "the supplied response format."
    )

    request_records: list[dict[str, Any]] = []
    previous_descriptor_id = None

    for index, segment_id in enumerate(
        SEGMENT_ORDER,
        start=1,
    ):
        segment_filename = f"{index:02d}-{segment_id}.json"
        segment_package = package_files[segment_filename]

        fixed_contract = segment_package[
            "fixed_segment_contract"
        ]
        shot_ids = fixed_contract["shot_ids_in_order"]

        response_format = direction_response_schema(
            segment_id,
            shot_ids,
        )

        input_payload: dict[str, Any] = {
            "task": (
                "Produce the structured cinematic direction result for "
                f"segment {segment_id!r}."
            ),
            "segment_package": deepcopy(segment_package),
            "runtime_bindings": {
                "previous_interaction_id": None,
                "prior_continuity_handoff": None,
            },
            "instructions": [
                "Return exactly one direction record per supplied shot.",
                "Preserve shot IDs, order, durations, and timeline.",
                "Treat creative_hints as advisory and non-binding.",
                "Never override hard_constraints or canon_context.",
                "Set every constraint_checks field to true only when true.",
                "Return the final continuity_handoff for the next segment.",
            ],
        }

        if index == 1:
            input_payload["global_contract"] = deepcopy(
                global_contract
            )
            previous_interaction_binding = {
                "required": False,
                "source_request_descriptor_id": None,
                "runtime_value": None,
            }
            handoff_binding = {
                "required": False,
                "source_request_descriptor_id": None,
                "runtime_value": None,
            }
        else:
            previous_interaction_binding = {
                "required": True,
                "source_request_descriptor_id": (
                    previous_descriptor_id
                ),
                "runtime_value": None,
                "runtime_resolution": (
                    "Use the interaction.id returned by the immediately "
                    "preceding successful segment request."
                ),
            }
            handoff_binding = {
                "required": True,
                "source_request_descriptor_id": (
                    previous_descriptor_id
                ),
                "runtime_value": None,
                "runtime_resolution": (
                    "Use the validated continuity_handoff returned by "
                    "the immediately preceding segment request."
                ),
            }

        descriptor_core = {
            "schema_version": "1.0",
            "descriptor_type": (
                "canonflow_gemini_interaction_request_descriptor"
            ),
            "request_index": index,
            "segment_id": segment_id,
            "model_binding": {
                "model": model_id,
                "api_family": "Gemini Developer API",
                "api_surface": "Interactions API",
                "api_revision": "v1beta",
                "input_token_limit": input_token_limit,
                "output_token_limit": output_token_limit,
            },
            "source_bindings": {
                "global_contract_id": (
                    EXPECTED_GLOBAL_CONTRACT_ID
                ),
                "merge_manifest_id": (
                    EXPECTED_MERGE_MANIFEST_ID
                ),
                "segment_package_id": segment_package[
                    "segment_package_id"
                ],
                "segment_package_filename": segment_filename,
                "segment_package_sha256": serialized_sha256(
                    segment_package
                ),
                "response_schema_template_id": (
                    schema_template["schema_template_id"]
                ),
                "response_schema_template_sha256": (
                    schema_sha256
                ),
            },
            "sdk_call_template": {
                "method": "client.interactions.create",
                "model": model_id,
                "system_instruction": system_instruction,
                "input_payload": input_payload,
                "input_rendering": (
                    "Serialize input_payload as canonical UTF-8 JSON "
                    "preceded by no additional unbound context."
                ),
                "previous_interaction_id": None,
                "previous_interaction_id_binding": (
                    previous_interaction_binding
                ),
                "response_mime_type": "application/json",
                "response_format": response_format,
                "generation_config": {
                    "thinking_level": "high",
                },
                "temperature": {
                    "included": False,
                    "policy": "use_model_default_1.0",
                },
                "tools": [],
                "store": True,
                "stream": False,
                "background": False,
            },
            "runtime_bindings": {
                "prior_continuity_handoff": handoff_binding,
            },
            "expected_result_contract": {
                "segment_id": segment_id,
                "source_segment_package_id": segment_package[
                    "segment_package_id"
                ],
                "shot_ids_in_order": shot_ids,
                "shot_count": fixed_contract["shot_count"],
                "runtime_seconds": fixed_contract[
                    "runtime_seconds"
                ],
                "last_shot_id": shot_ids[-1],
            },
            "execution_controls": {
                "descriptor_only": True,
                "actual_http_request_body_authorized": False,
                "credentials_read": False,
                "credentials_persisted": False,
                "client_initialized": False,
                "provider_calls": False,
                "http_requests": False,
                "network_access": False,
                "reference_images_transmitted": False,
                "media_generation_authorized": False,
                "media_generation_performed": False,
            },
        }

        descriptor = deepcopy(descriptor_core)
        descriptor["request_descriptor_id"] = stable_id(
            f"gemini-direction-request:{segment_id}",
            descriptor_core,
        )

        filename = f"{index:02d}-{segment_id}-request.json"
        file_sha256, file_bytes = write_json(
            filename,
            descriptor,
        )

        approximate_input_bytes = len(
            canonical_bytes(input_payload)
        )
        approximate_input_tokens = math.ceil(
            approximate_input_bytes / 4
        )

        request_record = {
            "filename": filename,
            "request_descriptor_id": descriptor[
                "request_descriptor_id"
            ],
            "segment_id": segment_id,
            "segment_package_id": segment_package[
                "segment_package_id"
            ],
            "sha256": file_sha256,
            "bytes": file_bytes,
            "shot_count": fixed_contract["shot_count"],
            "runtime_seconds": fixed_contract[
                "runtime_seconds"
            ],
            "approximate_input_bytes": (
                approximate_input_bytes
            ),
            "approximate_input_tokens": (
                approximate_input_tokens
            ),
            "previous_request_descriptor_id": (
                previous_descriptor_id
            ),
        }

        request_records.append(request_record)
        written_files[filename] = {
            "sha256": file_sha256,
            "bytes": file_bytes,
            "file_type": "request_descriptor",
            "segment_id": segment_id,
            "request_descriptor_id": descriptor[
                "request_descriptor_id"
            ],
        }

        previous_descriptor_id = descriptor[
            "request_descriptor_id"
        ]

    execution_manifest_core = {
        "schema_version": "1.0",
        "manifest_type": (
            "canonflow_gemini_direction_request_chain_manifest"
        ),
        "model_binding": {
            "model": model_id,
            "api_family": "Gemini Developer API",
            "api_surface": "Interactions API",
            "api_revision": "v1beta",
            "structured_output": True,
            "thinking_level": "high",
            "temperature_included": False,
            "temperature_policy": "use_model_default_1.0",
        },
        "source_bindings": {
            "global_contract_id": EXPECTED_GLOBAL_CONTRACT_ID,
            "merge_manifest_id": EXPECTED_MERGE_MANIFEST_ID,
            "response_schema_template_id": (
                schema_template["schema_template_id"]
            ),
            "response_schema_template_sha256": schema_sha256,
        },
        "execution_order": list(SEGMENT_ORDER),
        "request_descriptors": request_records,
        "chain_contract": {
            "request_count": 6,
            "processing_is_sequential": True,
            "independent_parallel_processing_allowed": False,
            "previous_interaction_id_required_after_first": True,
            "prior_continuity_handoff_required_after_first": True,
            "stop_on_failed_request": True,
            "stop_on_failed_schema_validation": True,
            "stop_on_failed_semantic_validation": True,
            "retry_requires_explicit_human_action": True,
            "creative_merge_model_call_required": False,
            "final_merge": "local_deterministic_validation",
            "expected_shot_direction_count": 62,
            "expected_narrative_runtime_seconds": 510,
            "canonical_shot_ids": direction_merge_manifest[
                "merge_contract"
            ]["shot_ids_in_canonical_order"],
        },
        "execution_controls": {
            "descriptor_only": True,
            "actual_http_request_body_authorized": False,
            "credentials_read": False,
            "credentials_persisted": False,
            "client_initialized": False,
            "provider_calls": False,
            "http_requests": False,
            "network_access": False,
            "reference_images_transmitted": False,
            "media_generation_authorized": False,
            "media_generation_performed": False,
        },
    }

    execution_manifest = deepcopy(execution_manifest_core)
    execution_manifest["request_chain_manifest_id"] = stable_id(
        "gemini-direction-request-chain",
        execution_manifest_core,
    )

    manifest_filename = "07-request-chain-manifest.json"
    manifest_sha256, manifest_bytes = write_json(
        manifest_filename,
        execution_manifest,
    )

    written_files[manifest_filename] = {
        "sha256": manifest_sha256,
        "bytes": manifest_bytes,
        "file_type": "request_chain_manifest",
        "request_chain_manifest_id": execution_manifest[
            "request_chain_manifest_id"
        ],
    }

    if len(written_files) != 8:
        raise ValueError(
            f"Expected 8 descriptor files, found {len(written_files)}."
        )

    if len(request_records) != 6:
        raise ValueError(
            f"Expected 6 request descriptors, found {len(request_records)}."
        )

    all_shot_ids: list[str] = []
    total_runtime = 0
    false_control_count = 0
    forbidden_secret_field_count = 0

    for index, request_record in enumerate(
        request_records,
        start=1,
    ):
        descriptor = json.loads(
            (
                output_dir / request_record["filename"]
            ).read_text(encoding="utf-8")
        )

        expected_segment_id = SEGMENT_ORDER[index - 1]

        if descriptor["segment_id"] != expected_segment_id:
            raise ValueError("Request segment order mismatch.")

        if descriptor["model_binding"]["model"] != model_id:
            raise ValueError("Request model binding mismatch.")

        sdk_template = descriptor["sdk_call_template"]

        if sdk_template["method"] != (
            "client.interactions.create"
        ):
            raise ValueError("Unexpected SDK method.")

        if sdk_template["temperature"]["included"] is not False:
            raise ValueError("Temperature must remain omitted.")

        if sdk_template["tools"] != []:
            raise ValueError("Tools must remain disabled.")

        if sdk_template["store"] is not True:
            raise ValueError(
                "Interaction storage is required for chaining."
            )

        previous_binding = sdk_template[
            "previous_interaction_id_binding"
        ]

        if index == 1:
            if previous_binding["required"] is not False:
                raise ValueError(
                    "First request must not require prior interaction."
                )
        else:
            if previous_binding["required"] is not True:
                raise ValueError(
                    "Later request requires prior interaction."
                )

            if (
                previous_binding[
                    "source_request_descriptor_id"
                ]
                != request_records[index - 2][
                    "request_descriptor_id"
                ]
            ):
                raise ValueError(
                    "Previous request binding mismatch."
                )

        expected_result = descriptor[
            "expected_result_contract"
        ]
        all_shot_ids.extend(
            expected_result["shot_ids_in_order"]
        )
        total_runtime += expected_result["runtime_seconds"]

        for object_path, value in walk(descriptor):
            if not object_path:
                continue

            leaf = object_path[-1]

            if leaf in {
                "api_key",
                "authorization",
                "authorization_header",
                "credential",
                "credential_value",
                "secret",
                "token_value",
            }:
                forbidden_secret_field_count += 1

            if leaf in {
                "actual_http_request_body_authorized",
                "credentials_read",
                "credentials_persisted",
                "client_initialized",
                "provider_calls",
                "http_requests",
                "network_access",
                "reference_images_transmitted",
                "media_generation_authorized",
                "media_generation_performed",
            }:
                if value is not False:
                    raise ValueError(
                        "Execution control must remain false: "
                        + ".".join(object_path)
                    )
                false_control_count += 1

    if len(all_shot_ids) != 62:
        raise ValueError("Expected 62 request-bound shot IDs.")

    if len(set(all_shot_ids)) != 62:
        raise ValueError("Request-bound shot IDs are not unique.")

    if total_runtime != 510:
        raise ValueError("Expected 510 request-bound seconds.")

    if forbidden_secret_field_count != 0:
        raise ValueError(
            "Credential or secret fields exist in descriptors."
        )

    checksums = "".join(
        f"{metadata['sha256']}  {filename}\n"
        for filename, metadata in sorted(written_files.items())
    )

    (output_dir / "SHA256SUMS").write_text(
        checksums,
        encoding="ascii",
    )

    print("--- EVIDENCE 66 REQUEST DESCRIPTOR PROTOTYPE START ---")
    print(
        "response_schema_template_id="
        + schema_template["schema_template_id"]
    )
    print(
        "request_chain_manifest_id="
        + execution_manifest["request_chain_manifest_id"]
    )
    print("model_id=gemini-3.1-pro-preview")
    print("request_descriptor_count=6")
    print("descriptor_file_count=8")
    print("shot_direction_input_count=62")
    print("narrative_runtime_seconds=510")
    print(f"validated_false_control_count={false_control_count}")
    print("forbidden_secret_field_count=0")

    for record in request_records:
        print(
            "request="
            + json.dumps(
                {
                    "segment_id": record["segment_id"],
                    "request_descriptor_id": record[
                        "request_descriptor_id"
                    ],
                    "shot_count": record["shot_count"],
                    "runtime_seconds": record["runtime_seconds"],
                    "approximate_input_bytes": record[
                        "approximate_input_bytes"
                    ],
                    "approximate_input_tokens": record[
                        "approximate_input_tokens"
                    ],
                    "bytes": record["bytes"],
                    "sha256": record["sha256"],
                },
                sort_keys=True,
            )
        )

    print(f"response_schema_sha256={schema_sha256}")
    print(f"request_chain_manifest_sha256={manifest_sha256}")
    print("credentials_environment_inspected=false")
    print("credentials_read=false")
    print("credentials_persisted=false")
    print("client_initialized=false")
    print("provider_calls=false")
    print("http_requests=false")
    print("network_access=false")
    print("reference_images_transmitted=false")
    print("media_generation_authorized=false")
    print("media_generation_performed=false")
    print(
        "PASS: Deterministic Gemini request-descriptor "
        "prototype generated."
    )
    print("--- EVIDENCE 66 REQUEST DESCRIPTOR PROTOTYPE END ---")


def _correct_legacy_package(
    source: Path,
    target: Path,
) -> None:
    import hashlib
    import json
    import sys
    import uuid
    from copy import deepcopy
    from pathlib import Path
    from typing import Any, Iterator

    source = Path(source)
    target = Path(target)

    segment_order = (
        "prologue",
        "act_1",
        "act_2a",
        "act_2b",
        "act_3",
        "epilogue",
    )

    segment_filenames = {
        "prologue": "01-prologue-request.json",
        "act_1": "02-act_1-request.json",
        "act_2a": "03-act_2a-request.json",
        "act_2b": "04-act_2b-request.json",
        "act_3": "05-act_3-request.json",
        "epilogue": "06-epilogue-request.json",
    }

    expected_source_hashes = {
        "00-response-schema-template.json": (
            "00d88cdc47032725e2e07c4ad2916a4d52d0d6e0859e1c719a09c9fe272ac2a2"
        ),
        "01-prologue-request.json": (
            "d5063bbd49308d9668f1466a71c3970f5b23d729ac666c5a960ca61a06f6d714"
        ),
        "02-act_1-request.json": (
            "0d02ff6fb116be7890f44a7bd32699e548f8ebd83ac9ef7408c13ec905c9abca"
        ),
        "03-act_2a-request.json": (
            "d2072bec8626af556126e0940ad35bc22967ccd745c4d88129ec9b0a820acb33"
        ),
        "04-act_2b-request.json": (
            "9febd22fe6d7735b98167a9fbfca63923c540004df5723e322b34fadf11e45c4"
        ),
        "05-act_3-request.json": (
            "1af1ac5c2bc4cc68e09ff4fdc559237a3ae83daf5696eaff9c37384287c5bd32"
        ),
        "06-epilogue-request.json": (
            "6ccf00a0d308bc424df865a5c2d5616c63bd5b895c5253db9d8604afaedee2ee"
        ),
        "07-request-chain-manifest.json": (
            "84b3bb7b7d0cadfc1308a1b8457aba36d0dacfac68dba023ed4252f3c25c7a61"
        ),
    }

    namespace = uuid.UUID(
        "826f785d-fccb-57f6-91a3-28b45cac3055"
    )


    def canonical_bytes(value: Any) -> bytes:
        return json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")


    def canonical_sha256(value: Any) -> str:
        return hashlib.sha256(canonical_bytes(value)).hexdigest()


    def stable_id(label: str, value: Any) -> str:
        return str(
            uuid.uuid5(
                namespace,
                f"{label}:{canonical_sha256(value)}",
            )
        )


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


    def write_json(
        filename: str,
        value: Any,
    ) -> tuple[str, int]:
        payload = serialized_bytes(value)
        (target / filename).write_bytes(payload)

        return hashlib.sha256(payload).hexdigest(), len(payload)


    def load_json(filename: str) -> Any:
        return json.loads(
            (source / filename).read_text(encoding="utf-8")
        )


    def file_sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()


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


    for filename, expected_hash in expected_source_hashes.items():
        actual_hash = file_sha256(source / filename)

        if actual_hash != expected_hash:
            raise ValueError(
                f"{filename}: source prototype SHA-256 mismatch."
            )

    schema_template = load_json(
        "00-response-schema-template.json"
    )
    schema_sha256, schema_bytes = write_json(
        "00-response-schema-template.json",
        schema_template,
    )

    request_records: list[dict[str, Any]] = []
    previous_descriptor_id: str | None = None
    all_shot_ids: list[str] = []
    total_runtime = 0

    for index, segment_id in enumerate(
        segment_order,
        start=1,
    ):
        filename = segment_filenames[segment_id]
        original = load_json(filename)
        descriptor_core = deepcopy(original)

        descriptor_core.pop("request_descriptor_id", None)

        model_binding = descriptor_core["model_binding"]
        model_binding["api_revision"] = "2026-05-20"

        sdk_template = descriptor_core["sdk_call_template"]

        original_schema = sdk_template.pop(
            "response_format"
        )
        sdk_template.pop("response_mime_type", None)
        sdk_template.pop("generation_config", None)

        sdk_template["response_format"] = {
            "type": "text",
            "mime_type": "application/json",
            "schema": original_schema,
        }
        sdk_template["thinking_level"] = "high"

        previous_binding = sdk_template[
            "previous_interaction_id_binding"
        ]
        handoff_binding = descriptor_core[
            "runtime_bindings"
        ]["prior_continuity_handoff"]

        if index == 1:
            previous_binding[
                "source_request_descriptor_id"
            ] = None
            handoff_binding[
                "source_request_descriptor_id"
            ] = None
        else:
            previous_binding[
                "source_request_descriptor_id"
            ] = previous_descriptor_id
            handoff_binding[
                "source_request_descriptor_id"
            ] = previous_descriptor_id

        descriptor = deepcopy(descriptor_core)
        descriptor_id = stable_id(
            f"gemini-direction-request:{segment_id}",
            descriptor_core,
        )
        descriptor["request_descriptor_id"] = descriptor_id

        file_sha256_value, file_bytes = write_json(
            filename,
            descriptor,
        )

        expected_result = descriptor[
            "expected_result_contract"
        ]
        shot_ids = expected_result["shot_ids_in_order"]

        request_records.append(
            {
                "filename": filename,
                "request_descriptor_id": descriptor_id,
                "segment_id": segment_id,
                "segment_package_id": expected_result[
                    "source_segment_package_id"
                ],
                "sha256": file_sha256_value,
                "bytes": file_bytes,
                "shot_ids_in_order": shot_ids,
                "shot_count": expected_result["shot_count"],
                "runtime_seconds": expected_result[
                    "runtime_seconds"
                ],
                "approximate_input_bytes": len(
                    canonical_bytes(
                        sdk_template["input_payload"]
                    )
                ),
                "approximate_input_tokens": (
                    len(
                        canonical_bytes(
                            sdk_template["input_payload"]
                        )
                    )
                    + 3
                )
                // 4,
                "previous_request_descriptor_id": (
                    previous_descriptor_id
                ),
            }
        )

        all_shot_ids.extend(shot_ids)
        total_runtime += expected_result["runtime_seconds"]
        previous_descriptor_id = descriptor_id

    original_manifest = load_json(
        "07-request-chain-manifest.json"
    )
    manifest_core = deepcopy(original_manifest)
    manifest_core.pop("request_chain_manifest_id", None)

    manifest_core["model_binding"][
        "api_revision"
    ] = "2026-05-20"
    manifest_core["request_descriptors"] = request_records

    corrected_manifest = deepcopy(manifest_core)
    corrected_manifest_id = stable_id(
        "gemini-direction-request-chain",
        manifest_core,
    )
    corrected_manifest[
        "request_chain_manifest_id"
    ] = corrected_manifest_id

    manifest_sha256, manifest_bytes = write_json(
        "07-request-chain-manifest.json",
        corrected_manifest,
    )

    if len(all_shot_ids) != 62:
        raise ValueError("Expected 62 request-bound shots.")

    if len(set(all_shot_ids)) != 62:
        raise ValueError("Request-bound shot IDs are not unique.")

    if total_runtime != 510:
        raise ValueError("Expected 510 request-bound seconds.")

    false_control_count = 0
    forbidden_secret_field_count = 0

    for record in request_records:
        descriptor = json.loads(
            (target / record["filename"]).read_text(
                encoding="utf-8"
            )
        )

        model_binding = descriptor["model_binding"]
        sdk_template = descriptor["sdk_call_template"]
        response_format = sdk_template["response_format"]

        if model_binding["api_revision"] != "2026-05-20":
            raise ValueError("API revision mismatch.")

        if response_format["type"] != "text":
            raise ValueError(
                "Structured response type must be text."
            )

        if response_format["mime_type"] != "application/json":
            raise ValueError(
                "Structured response MIME type mismatch."
            )

        if not isinstance(response_format["schema"], dict):
            raise ValueError(
                "Structured response schema is missing."
            )

        if "response_mime_type" in sdk_template:
            raise ValueError(
                "Legacy response_mime_type field remains."
            )

        if "generation_config" in sdk_template:
            raise ValueError(
                "Legacy generation_config field remains."
            )

        if sdk_template.get("thinking_level") != "high":
            raise ValueError(
                "thinking_level must be a direct SDK argument."
            )

        if sdk_template["temperature"]["included"] is not False:
            raise ValueError("Temperature must remain omitted.")

        if sdk_template["tools"] != []:
            raise ValueError("Tools must remain disabled.")

        for object_path, value in walk(descriptor):
            if not object_path:
                continue

            leaf = object_path[-1]

            if leaf in {
                "api_key",
                "authorization",
                "authorization_header",
                "credential",
                "credential_value",
                "secret",
                "token_value",
            }:
                forbidden_secret_field_count += 1

            if leaf in {
                "actual_http_request_body_authorized",
                "credentials_read",
                "credentials_persisted",
                "client_initialized",
                "provider_calls",
                "http_requests",
                "network_access",
                "reference_images_transmitted",
                "media_generation_authorized",
                "media_generation_performed",
            }:
                if value is not False:
                    raise ValueError(
                        "Execution control must remain false: "
                        + ".".join(object_path)
                    )

                false_control_count += 1

    if forbidden_secret_field_count != 0:
        raise ValueError(
            "Credential or secret fields exist in descriptors."
        )

    written_hashes = {
        "00-response-schema-template.json": schema_sha256,
        **{
            record["filename"]: record["sha256"]
            for record in request_records
        },
        "07-request-chain-manifest.json": manifest_sha256,
    }

    checksums = "".join(
        f"{digest}  {filename}\n"
        for filename, digest in sorted(written_hashes.items())
    )

    (target / "SHA256SUMS").write_text(
        checksums,
        encoding="ascii",
    )

    print("--- EVIDENCE 66 CORRECTED REQUEST DESCRIPTOR START ---")
    print(
        "response_schema_template_id="
        + schema_template["schema_template_id"]
    )
    print(
        "request_chain_manifest_id="
        + corrected_manifest_id
    )
    print("model_id=gemini-3.1-pro-preview")
    print("interactions_schema_revision=2026-05-20")
    print("request_descriptor_count=6")
    print("descriptor_file_count=8")
    print("shot_direction_input_count=62")
    print("narrative_runtime_seconds=510")
    print(f"validated_false_control_count={false_control_count}")
    print("forbidden_secret_field_count=0")

    for record in request_records:
        print(
            "request="
            + json.dumps(
                {
                    "segment_id": record["segment_id"],
                    "request_descriptor_id": record[
                        "request_descriptor_id"
                    ],
                    "shot_count": record["shot_count"],
                    "runtime_seconds": record["runtime_seconds"],
                    "approximate_input_bytes": record[
                        "approximate_input_bytes"
                    ],
                    "approximate_input_tokens": record[
                        "approximate_input_tokens"
                    ],
                    "bytes": record["bytes"],
                    "sha256": record["sha256"],
                },
                sort_keys=True,
            )
        )

    print(f"response_schema_sha256={schema_sha256}")
    print(f"request_chain_manifest_sha256={manifest_sha256}")
    print("response_format_type=text")
    print("response_format_mime_type=application/json")
    print("response_format_schema_embedded=true")
    print("thinking_level_direct_argument=high")
    print("temperature_included=false")
    print("credentials_environment_inspected=false")
    print("credentials_read=false")
    print("credentials_persisted=false")
    print("client_initialized=false")
    print("provider_calls=false")
    print("http_requests=false")
    print("network_access=false")
    print("reference_images_transmitted=false")
    print("media_generation_authorized=false")
    print("media_generation_performed=false")
    print(
        "PASS: Corrected Gemini Interactions API descriptor "
        "prototype generated."
    )
    print("--- EVIDENCE 66 CORRECTED REQUEST DESCRIPTOR END ---")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def _walk(
    value: Any,
    path: tuple[str, ...] = (),
) -> Iterator[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = (*path, key)
            yield child_path, child
            yield from _walk(child, child_path)

    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, (*path, str(index)))


def validate_gemini_direction_request_package(
    package_path: str | Path,
) -> dict[str, Any]:
    package = Path(package_path)

    if not package.is_dir():
        raise ValueError(
            f"Direction-request package does not exist: {package}"
        )

    checksum_path = package / "SHA256SUMS"

    if not checksum_path.is_file():
        raise ValueError("Direction-request SHA256SUMS is missing.")

    actual_json_files = {
        path.name
        for path in package.glob("*.json")
        if path.is_file()
    }

    if actual_json_files != set(EXPECTED_FILE_HASHES):
        raise ValueError(
            "Direction-request package file set mismatch."
        )

    expected_checksum_text = "".join(
        f"{digest}  {filename}\n"
        for filename, digest in sorted(EXPECTED_FILE_HASHES.items())
    )

    if checksum_path.read_text(encoding="ascii") != expected_checksum_text:
        raise ValueError("Direction-request checksum manifest mismatch.")

    documents: dict[str, Any] = {}

    for filename, expected_sha256 in EXPECTED_FILE_HASHES.items():
        path = package / filename
        actual_sha256 = _sha256_file(path)

        if actual_sha256 != expected_sha256:
            raise ValueError(
                f"Direction-request SHA-256 mismatch: {filename}"
            )

        documents[filename] = json.loads(
            path.read_text(encoding="utf-8")
        )

    schema = documents["00-response-schema-template.json"]
    manifest = documents["07-request-chain-manifest.json"]

    if schema.get("schema_template_id") != RESPONSE_SCHEMA_TEMPLATE_ID:
        raise ValueError("Response-schema template ID mismatch.")

    if (
        manifest.get("request_chain_manifest_id")
        != REQUEST_CHAIN_MANIFEST_ID
    ):
        raise ValueError("Request-chain manifest ID mismatch.")

    records = manifest.get("request_descriptors")

    if not isinstance(records, list) or len(records) != 6:
        raise ValueError(
            "Request-chain manifest must contain six descriptors."
        )

    chain_contract = manifest.get("chain_contract")

    if not isinstance(chain_contract, dict):
        raise ValueError("Request-chain contract is missing.")

    if chain_contract.get("request_count") != EXPECTED_REQUEST_COUNT:
        raise ValueError("Request count mismatch.")

    if (
        chain_contract.get("expected_shot_direction_count")
        != EXPECTED_SHOT_DIRECTION_INPUT_COUNT
    ):
        raise ValueError("Shot-direction input count mismatch.")

    if (
        chain_contract.get("expected_narrative_runtime_seconds")
        != EXPECTED_NARRATIVE_RUNTIME_SECONDS
    ):
        raise ValueError("Narrative runtime mismatch.")

    if chain_contract.get("processing_is_sequential") is not True:
        raise ValueError("Sequential processing is not enforced.")

    if (
        chain_contract.get("independent_parallel_processing_allowed")
        is not False
    ):
        raise ValueError("Independent parallel processing is enabled.")

    false_control_keys = {
        "actual_http_request_body_authorized",
        "credentials_read",
        "credentials_persisted",
        "client_initialized",
        "provider_calls",
        "http_requests",
        "network_access",
        "reference_images_transmitted",
        "media_generation_authorized",
        "media_generation_performed",
    }

    forbidden_secret_keys = {
        "api_key",
        "authorization",
        "authorization_header",
        "credential",
        "credential_value",
        "secret",
        "token_value",
    }

    false_control_count = 0
    forbidden_secret_field_count = 0
    previous_descriptor_id: str | None = None

    for index, record in enumerate(records):
        filename = record["filename"]
        descriptor = documents[filename]
        descriptor_id = descriptor["request_descriptor_id"]
        sdk = descriptor["sdk_call_template"]
        model_binding = descriptor["model_binding"]

        if descriptor["segment_id"] != SEGMENT_ORDER[index]:
            raise ValueError("Segment order mismatch.")

        if descriptor_id != record["request_descriptor_id"]:
            raise ValueError("Descriptor ID mismatch.")

        if (
            record.get("previous_request_descriptor_id")
            != previous_descriptor_id
        ):
            raise ValueError("Manifest request chain mismatch.")

        if model_binding.get("model") != MODEL_ID:
            raise ValueError("Model binding mismatch.")

        if (
            model_binding.get("api_revision")
            != INTERACTIONS_SCHEMA_REVISION
        ):
            raise ValueError("Interactions API revision mismatch.")

        interaction_binding = sdk.get(
            "previous_interaction_id_binding"
        )

        if not isinstance(interaction_binding, dict):
            raise ValueError(
                "Previous-interaction binding is missing."
            )

        required = index > 0

        if interaction_binding.get("required") is not required:
            raise ValueError(
                "Previous-interaction required-state mismatch."
            )

        if (
            interaction_binding.get("source_request_descriptor_id")
            != previous_descriptor_id
        ):
            raise ValueError(
                "Previous-interaction source mismatch."
            )

        if interaction_binding.get("runtime_value") is not None:
            raise ValueError(
                "Previous interaction was populated before runtime."
            )

        response_format = sdk.get("response_format")

        if not isinstance(response_format, dict):
            raise ValueError("Response format is missing.")

        if response_format.get("type") != "text":
            raise ValueError("Response format type mismatch.")

        if response_format.get("mime_type") != "application/json":
            raise ValueError("Response MIME type mismatch.")

        if not isinstance(response_format.get("schema"), dict):
            raise ValueError("Embedded response schema is missing.")

        if sdk.get("thinking_level") != "high":
            raise ValueError("Thinking level mismatch.")

        if sdk.get("temperature") != {
            "included": False,
            "policy": "use_model_default_1.0",
        }:
            raise ValueError("Temperature policy mismatch.")

        if sdk.get("tools") != []:
            raise ValueError("Tools must remain disabled.")

        for object_path, value in _walk(descriptor):
            leaf = object_path[-1]

            if leaf in forbidden_secret_keys:
                forbidden_secret_field_count += 1

            if leaf in false_control_keys:
                if value is not False:
                    raise ValueError(
                        "Execution control must remain false: "
                        + ".".join(object_path)
                    )

                false_control_count += 1

        previous_descriptor_id = descriptor_id

    if false_control_count != EXPECTED_FALSE_CONTROL_COUNT:
        raise ValueError(
            "False-control count mismatch: "
            f"{false_control_count}"
        )

    if forbidden_secret_field_count != 0:
        raise ValueError("Forbidden secret field detected.")

    return {
        "response_schema_template_id":
            RESPONSE_SCHEMA_TEMPLATE_ID,
        "request_chain_manifest_id":
            REQUEST_CHAIN_MANIFEST_ID,
        "model_id": MODEL_ID,
        "interactions_schema_revision":
            INTERACTIONS_SCHEMA_REVISION,
        "descriptor_file_count": len(EXPECTED_FILE_HASHES),
        "request_descriptor_count": len(records),
        "shot_direction_input_count":
            EXPECTED_SHOT_DIRECTION_INPUT_COUNT,
        "narrative_runtime_seconds":
            EXPECTED_NARRATIVE_RUNTIME_SECONDS,
        "validated_false_control_count":
            false_control_count,
        "forbidden_secret_field_count":
            forbidden_secret_field_count,
        "credentials_read": False,
        "provider_calls": False,
        "http_requests": False,
        "network_access": False,
        "media_generation_authorized": False,
    }


def build_gemini_direction_request_package(
    output_path: str | Path,
    *,
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    destination = Path(output_path)

    if destination.exists():
        raise FileExistsError(
            f"Output path already exists: {destination}"
        )

    if repository_root is None:
        root = Path(__file__).resolve().parents[2]
    else:
        root = Path(repository_root).resolve()

    destination.parent.mkdir(parents=True, exist_ok=True)

    staging_root = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.",
            dir=destination.parent,
        )
    )
    legacy_path = staging_root / "legacy"
    corrected_path = staging_root / "corrected"

    legacy_path.mkdir()
    corrected_path.mkdir()

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            _generate_legacy_package(legacy_path, root)
            _correct_legacy_package(
                legacy_path,
                corrected_path,
            )

        result = validate_gemini_direction_request_package(
            corrected_path
        )

        os.replace(corrected_path, destination)
        return result

    except Exception:
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        raise

    finally:
        shutil.rmtree(staging_root, ignore_errors=True)
