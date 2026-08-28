from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import tempfile
import urllib.request
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch


AGENTS_ROOT = Path(__file__).resolve().parents[2]

if str(AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTS_ROOT))


from canonflow_agent.direction_package_builder import (
    EVIDENCE_64_PATH,
    EXPECTED_FILE_SHA256S,
    EXPECTED_GLOBAL_CONTRACT_ID,
    EXPECTED_MERGE_MANIFEST_ID,
    SEGMENT_CONTRACT,
    SEGMENT_ORDER,
    DirectionPackageError,
    build_direction_package,
    serialized_bytes,
    serialized_sha256,
    validate_direction_package,
    walk,
    write_direction_package,
)


REPOSITORY_ROOT = Path(
    os.environ.get(
        "REPO_ROOT",
        Path(__file__).resolve().parents[3],
    )
).resolve()


def built_package() -> dict[str, dict[str, object]]:
    return build_direction_package(REPOSITORY_ROOT)


def test_deterministic_identity_and_hashes() -> None:
    first = built_package()
    second = built_package()

    assert first == second

    assert (
        first["00-global-contract.json"]["global_contract_id"]
        == EXPECTED_GLOBAL_CONTRACT_ID
    )
    assert (
        first["07-merge-manifest.json"]["merge_manifest_id"]
        == EXPECTED_MERGE_MANIFEST_ID
    )

    actual_hashes = {
        filename: serialized_sha256(value)
        for filename, value in first.items()
    }

    assert actual_hashes == EXPECTED_FILE_SHA256S


def test_six_segment_contract() -> None:
    package = built_package()

    for segment_index, segment_id in enumerate(
        SEGMENT_ORDER,
        start=1,
    ):
        filename = f"{segment_index:02d}-{segment_id}.json"
        segment = package[filename]
        expected = SEGMENT_CONTRACT[segment_id]
        fixed = segment["fixed_segment_contract"]

        assert segment["segment_id"] == segment_id
        assert segment["segment_index"] == segment_index
        assert fixed["shot_count"] == expected["shot_count"]
        assert fixed["scene_count"] == expected["scene_count"]
        assert (
            fixed["runtime_seconds"]
            == expected["runtime_seconds"]
        )
        assert (
            len(segment["shot_direction_inputs"])
            == expected["shot_count"]
        )
        assert (
            len(segment["selected_scene_contexts"])
            == expected["scene_count"]
        )

    merge = package["07-merge-manifest.json"]

    assert merge["processing_order"] == list(SEGMENT_ORDER)
    assert (
        merge["merge_contract"][
            "expected_segment_result_count"
        ]
        == 6
    )
    assert (
        merge["merge_contract"][
            "expected_shot_direction_count"
        ]
        == 62
    )
    assert (
        merge["merge_contract"][
            "expected_narrative_runtime_seconds"
        ]
        == 510
    )


def test_all_shot_inputs_have_required_semantics() -> None:
    package = built_package()
    shot_count = 0
    runtime = 0

    for index, segment_id in enumerate(
        SEGMENT_ORDER,
        start=1,
    ):
        segment = package[f"{index:02d}-{segment_id}.json"]

        for packet in segment["shot_direction_inputs"]:
            shot_count += 1
            runtime += packet["timeline"]["duration_seconds"]

            assert set(packet) == {
                "identity",
                "timeline",
                "canon_context",
                "narrative_context",
                "identity_context",
                "hard_constraints",
                "creative_hints",
                "model_decisions_required",
                "execution_controls",
            }

            assert packet["identity"]["shot_id"]
            assert packet["identity"]["scene_id"]
            assert (
                packet["identity"]["segment_id"]
                == segment_id
            )

            assert packet["timeline"]["duration_is_fixed"]
            assert (
                packet["timeline"][
                    "timeline_position_is_fixed"
                ]
            )

            assert packet["canon_context"]["source_beat_ids"]
            assert packet["canon_context"]["beat_sha256"]
            assert (
                packet["canon_context"]["retrieval_trace"][
                    "source_locator"
                ]["path"]
            )
            assert (
                packet["canon_context"][
                    "canon_mutation_allowed"
                ]
                is False
            )

            assert packet["narrative_context"]["action_source"]
            assert packet["narrative_context"]["participants"]
            assert packet["narrative_context"]["character_states"]
            assert packet["narrative_context"]["location_state"]
            assert (
                packet["narrative_context"][
                    "dialogue_or_voice_constraints"
                ]
            )

            assert packet["hard_constraints"][
                "negative_constraints"
            ]
            assert (
                packet["hard_constraints"][
                    "preserve_canon_tone"
                ]
                is True
            )
            assert (
                packet["hard_constraints"][
                    "preserve_epistemic_ambiguity"
                ]
                is True
            )

    assert shot_count == 62
    assert runtime == 510


def test_creative_values_are_advisory() -> None:
    package = built_package()
    creative_hint_count = 0

    for index, segment_id in enumerate(
        SEGMENT_ORDER,
        start=1,
    ):
        segment = package[f"{index:02d}-{segment_id}.json"]

        for packet in segment["shot_direction_inputs"]:
            hints = packet["creative_hints"]
            camera = hints["camera"]
            legacy = hints[
                "legacy_production_staging_reference"
            ]

            assert "Advisory and non-binding" in hints["policy"]
            assert camera["framing"]
            assert camera["lens_intent"]
            assert camera["movement"]
            assert legacy["value"]
            assert (
                legacy["classification"]
                == "legacy_mixed_direction_reference"
            )
            assert legacy["binding"] is False
            assert (
                legacy[
                    "must_not_override_hard_constraints"
                ]
                is True
            )

            decisions = packet["model_decisions_required"]
            assert all(decisions.values())
            creative_hint_count += 1

    assert creative_hint_count == 62


def test_identity_metadata_excludes_asset_paths() -> None:
    package = built_package()
    binding_count = 0

    for index, segment_id in enumerate(
        SEGMENT_ORDER,
        start=1,
    ):
        segment = package[f"{index:02d}-{segment_id}.json"]

        for packet in segment["shot_direction_inputs"]:
            identity_context = packet["identity_context"]

            assert (
                identity_context[
                    "reference_image_bytes_included"
                ]
                is False
            )
            assert (
                identity_context[
                    "reference_images_transmitted"
                ]
                is False
            )

            for binding in identity_context["bindings"]:
                binding_count += 1
                metadata = binding[
                    "reference_asset_metadata"
                ]

                assert "path" not in metadata
                assert metadata["sha256"]
                assert metadata["mime_type"]
                assert (
                    binding[
                        "reference_image_bytes_included"
                    ]
                    is False
                )
                assert (
                    binding[
                        "reference_image_transmission_authorized"
                    ]
                    is False
                )
                assert (
                    binding["usage_policy"][
                        "external_model_submission_allowed"
                    ]
                    is False
                )

    assert binding_count == 98


def test_only_canon_source_locator_paths_remain() -> None:
    package = built_package()
    shot_locator_count = 0
    scene_locator_count = 0

    for filename, document in package.items():
        for object_path, value in walk(document):
            if not object_path or object_path[-1] != "path":
                continue

            assert object_path[-2:] == (
                "source_locator",
                "path",
            )
            assert isinstance(value, str)
            assert value

            assert "identity_context" not in object_path
            assert "reference_asset_metadata" not in object_path

            if "shot_direction_inputs" in object_path:
                shot_locator_count += 1
            elif "selected_scene_contexts" in object_path:
                scene_locator_count += 1
            else:
                raise AssertionError(
                    f"{filename}: unexpected path context: "
                    + ".".join(object_path)
                )

    assert shot_locator_count == 62
    assert scene_locator_count == 32


def test_generation_and_provider_controls_remain_false() -> None:
    package = built_package()

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

    validated_count = 0

    for filename, document in package.items():
        for object_path, value in walk(document):
            if not object_path:
                continue

            if object_path[-1] not in false_only_keys:
                continue

            assert value is False, (
                f"{filename}: expected false at "
                + ".".join(object_path)
            )
            validated_count += 1

    assert validated_count == 633


def test_ordered_continuity_handoff_protocol() -> None:
    package = built_package()

    for index, segment_id in enumerate(
        SEGMENT_ORDER,
        start=1,
    ):
        segment = package[f"{index:02d}-{segment_id}.json"]
        context = segment["processing_context"]

        expected_previous = (
            SEGMENT_ORDER[index - 2]
            if index > 1
            else None
        )
        expected_next = (
            SEGMENT_ORDER[index]
            if index < len(SEGMENT_ORDER)
            else None
        )

        assert (
            context["previous_segment_id"]
            == expected_previous
        )
        assert context["next_segment_id"] == expected_next
        assert (
            context["prior_continuity_handoff_required"]
            is (expected_previous is not None)
        )
        assert context["prior_continuity_handoff"] is None
        assert (
            context["model_must_return_continuity_handoff"]
            is True
        )
        assert (
            context[
                "independent_parallel_processing_allowed"
            ]
            is False
        )

    global_contract = package["00-global-contract.json"]
    continuity = global_contract["continuity_protocol"]

    assert continuity["processing_order_is_mandatory"]
    assert continuity["later_segments_require_previous_handoff"]
    assert (
        "last_shot_id"
        in continuity["handoff_fields"]
    )
    assert (
        "next_segment_requirements"
        in continuity["handoff_fields"]
    )


def test_atomic_writer_and_checksums() -> None:
    package = built_package()

    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "direction-package"
        write_direction_package(output, package)

        assert output.is_dir()

        expected_names = set(package) | {"SHA256SUMS"}
        actual_names = {
            path.name
            for path in output.iterdir()
        }
        assert actual_names == expected_names

        checksum_lines = (
            output / "SHA256SUMS"
        ).read_text(encoding="ascii").splitlines()

        checksum_records = {}

        for line in checksum_lines:
            digest, filename = line.split("  ", 1)
            checksum_records[filename] = digest

        assert checksum_records == EXPECTED_FILE_SHA256S

        for filename, expected_sha256 in (
            EXPECTED_FILE_SHA256S.items()
        ):
            actual_sha256 = hashlib.sha256(
                (output / filename).read_bytes()
            ).hexdigest()
            assert actual_sha256 == expected_sha256

            generated = json.loads(
                (output / filename).read_text(
                    encoding="utf-8"
                )
            )
            assert generated == package[filename]


def test_atomic_writer_refuses_existing_output() -> None:
    package = built_package()

    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "direction-package"
        output.mkdir()
        sentinel = output / "sentinel.txt"
        sentinel.write_text("preserve", encoding="utf-8")

        try:
            write_direction_package(output, package)
        except FileExistsError:
            pass
        else:
            raise AssertionError(
                "Existing output directory was overwritten."
            )

        assert sentinel.read_text(encoding="utf-8") == "preserve"
        assert list(output.iterdir()) == [sentinel]


def test_offline_execution() -> None:
    with patch.object(
        socket,
        "socket",
        side_effect=AssertionError(
            "Network socket creation is forbidden."
        ),
    ), patch.object(
        urllib.request,
        "urlopen",
        side_effect=AssertionError(
            "HTTP requests are forbidden."
        ),
    ):
        package = built_package()
        validate_direction_package(package)

    assert (
        package["00-global-contract.json"][
            "execution_controls"
        ]["provider_calls"]
        is False
    )
    assert (
        package["00-global-contract.json"][
            "execution_controls"
        ]["network_access"]
        is False
    )


def test_rejects_modified_evidence_64() -> None:
    source = REPOSITORY_ROOT / EVIDENCE_64_PATH

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        target = root / EVIDENCE_64_PATH
        target.parent.mkdir(parents=True, exist_ok=True)

        payload = source.read_bytes()
        target.write_bytes(payload + b"\n")

        try:
            build_direction_package(root)
        except DirectionPackageError as exc:
            assert "SHA-256 mismatch" in str(exc)
        else:
            raise AssertionError(
                "Modified Evidence 64 artifact was accepted."
            )


def test_validator_rejects_mutated_package() -> None:
    package = built_package()

    mutated_runtime = deepcopy(package)
    mutated_runtime["01-prologue.json"][
        "shot_direction_inputs"
    ][0]["timeline"]["duration_seconds"] += 1

    try:
        validate_direction_package(mutated_runtime)
    except DirectionPackageError as exc:
        assert "validated prototype" in str(exc)
    else:
        raise AssertionError(
            "Mutated runtime was accepted."
        )

    mutated_authorization = deepcopy(package)
    mutated_authorization["01-prologue.json"][
        "shot_direction_inputs"
    ][0]["execution_controls"][
        "provider_request_authorized"
    ] = True

    try:
        validate_direction_package(mutated_authorization)
    except DirectionPackageError as exc:
        assert "validated prototype" in str(exc)
    else:
        raise AssertionError(
            "Provider authorization mutation was accepted."
        )

    mutated_identity = deepcopy(package)
    mutated_identity["02-act_1.json"][
        "shot_direction_inputs"
    ][0]["identity_context"]["bindings"][0][
        "reference_asset_metadata"
    ]["path"] = "/forbidden/reference.png"

    try:
        validate_direction_package(mutated_identity)
    except DirectionPackageError as exc:
        assert "validated prototype" in str(exc)
    else:
        raise AssertionError(
            "Identity asset path mutation was accepted."
        )


def main() -> int:
    tests = [
        test_deterministic_identity_and_hashes,
        test_six_segment_contract,
        test_all_shot_inputs_have_required_semantics,
        test_creative_values_are_advisory,
        test_identity_metadata_excludes_asset_paths,
        test_only_canon_source_locator_paths_remain,
        test_generation_and_provider_controls_remain_false,
        test_ordered_continuity_handoff_protocol,
        test_atomic_writer_and_checksums,
        test_atomic_writer_refuses_existing_output,
        test_offline_execution,
        test_rejects_modified_evidence_64,
        test_validator_rejects_mutated_package,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print()
    print(f"Direction-package-builder tests passed: {len(tests)}")
    print("CANONFLOW GEMINI DIRECTION PACKAGE BUILDER: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
