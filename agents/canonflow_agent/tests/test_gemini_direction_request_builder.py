from __future__ import annotations

import hashlib
import json
import shutil
import socket
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from unittest import mock

from canonflow_agent.gemini_direction_request_builder import (
    EXPECTED_FALSE_CONTROL_COUNT,
    EXPECTED_FILE_HASHES,
    EXPECTED_NARRATIVE_RUNTIME_SECONDS,
    EXPECTED_REQUEST_COUNT,
    EXPECTED_SHOT_DIRECTION_INPUT_COUNT,
    INTERACTIONS_SCHEMA_REVISION,
    MODEL_ID,
    REQUEST_CHAIN_MANIFEST_ID,
    RESPONSE_SCHEMA_TEMPLATE_ID,
    SEGMENT_ORDER,
    build_gemini_direction_request_package,
    validate_gemini_direction_request_package,
)

REQUEST_FILES = (
    "01-prologue-request.json",
    "02-act_1-request.json",
    "03-act_2a-request.json",
    "04-act_2b-request.json",
    "05-act_3-request.json",
    "06-epilogue-request.json",
)

FALSE_ONLY_KEYS = {
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

FORBIDDEN_SECRET_KEYS = {
    "api_key",
    "authorization",
    "authorization_header",
    "credential",
    "credential_value",
    "secret",
    "token_value",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def load_json(package: Path, filename: str) -> Any:
    return json.loads(
        (package / filename).read_text(encoding="utf-8")
    )


def walk(
    value: Any,
    location: tuple[str, ...] = (),
) -> Iterator[tuple[tuple[str, ...], Any]]:
    if isinstance(value, dict):
        for key, child in value.items():
            child_location = (*location, key)
            yield child_location, child
            yield from walk(child, child_location)

    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, (*location, str(index)))


@contextmanager
def built_package() -> Iterator[tuple[Path, dict[str, Any]]]:
    with tempfile.TemporaryDirectory(
        prefix="canonflow-e66-test-"
    ) as temporary:
        output = Path(temporary) / "package"
        result = build_gemini_direction_request_package(output)
        yield output, result


def assert_raises(
    exception_type: type[BaseException],
    callback: Any,
) -> BaseException:
    try:
        callback()
    except exception_type as exc:
        return exc

    raise AssertionError(
        f"Expected {exception_type.__name__} was not raised."
    )


def test_deterministic_identity_and_hashes() -> None:
    with built_package() as (first, first_result):
        with built_package() as (second, second_result):
            assert first_result == second_result

            first_files = sorted(
                path.name
                for path in first.iterdir()
                if path.is_file()
            )
            second_files = sorted(
                path.name
                for path in second.iterdir()
                if path.is_file()
            )

            assert first_files == second_files

            for filename in first_files:
                assert (
                    (first / filename).read_bytes()
                    == (second / filename).read_bytes()
                )


def test_expected_file_set_and_hashes() -> None:
    with built_package() as (package, _):
        json_files = {
            path.name
            for path in package.glob("*.json")
        }

        assert json_files == set(EXPECTED_FILE_HASHES)

        for filename, expected_hash in EXPECTED_FILE_HASHES.items():
            assert sha256_file(package / filename) == expected_hash

        assert (package / "SHA256SUMS").is_file()


def test_six_segment_request_contract() -> None:
    with built_package() as (package, result):
        assert result["request_descriptor_count"] == 6
        assert result["descriptor_file_count"] == 8
        assert (
            result["shot_direction_input_count"]
            == EXPECTED_SHOT_DIRECTION_INPUT_COUNT
        )
        assert (
            result["narrative_runtime_seconds"]
            == EXPECTED_NARRATIVE_RUNTIME_SECONDS
        )

        segments = tuple(
            load_json(package, filename)["segment_id"]
            for filename in REQUEST_FILES
        )

        assert segments == SEGMENT_ORDER


def test_schema_and_manifest_identity() -> None:
    with built_package() as (package, _):
        schema = load_json(
            package,
            "00-response-schema-template.json",
        )
        manifest = load_json(
            package,
            "07-request-chain-manifest.json",
        )

        assert (
            schema["schema_template_id"]
            == RESPONSE_SCHEMA_TEMPLATE_ID
        )
        assert (
            manifest["request_chain_manifest_id"]
            == REQUEST_CHAIN_MANIFEST_ID
        )


def test_model_and_api_revision_binding() -> None:
    with built_package() as (package, _):
        for filename in REQUEST_FILES:
            descriptor = load_json(package, filename)
            model_binding = descriptor["model_binding"]
            sdk = descriptor["sdk_call_template"]

            assert model_binding["model"] == MODEL_ID
            assert (
                model_binding["api_revision"]
                == INTERACTIONS_SCHEMA_REVISION
            )
            assert sdk["model"] == MODEL_ID
            assert sdk["method"] == "client.interactions.create"


def test_structured_response_format() -> None:
    with built_package() as (package, _):
        for filename in REQUEST_FILES:
            sdk = load_json(
                package,
                filename,
            )["sdk_call_template"]

            response_format = sdk["response_format"]

            assert response_format["type"] == "text"
            assert (
                response_format["mime_type"]
                == "application/json"
            )
            assert isinstance(response_format["schema"], dict)
            assert "response_mime_type" not in sdk
            assert "generation_config" not in sdk


def test_thinking_temperature_and_tools_policy() -> None:
    with built_package() as (package, _):
        for filename in REQUEST_FILES:
            sdk = load_json(
                package,
                filename,
            )["sdk_call_template"]

            assert sdk["thinking_level"] == "high"
            assert sdk["temperature"] == {
                "included": False,
                "policy": "use_model_default_1.0",
            }
            assert sdk["tools"] == []
            assert sdk["background"] is False
            assert sdk["stream"] is False


def test_ordered_runtime_chain() -> None:
    with built_package() as (package, _):
        previous_descriptor_id: str | None = None

        for index, filename in enumerate(REQUEST_FILES):
            descriptor = load_json(package, filename)
            descriptor_id = descriptor["request_descriptor_id"]
            sdk = descriptor["sdk_call_template"]
            interaction = sdk[
                "previous_interaction_id_binding"
            ]
            handoff = descriptor["runtime_bindings"][
                "prior_continuity_handoff"
            ]

            expected_required = index > 0

            assert interaction["required"] is expected_required
            assert handoff["required"] is expected_required

            assert (
                interaction["source_request_descriptor_id"]
                == previous_descriptor_id
            )
            assert (
                handoff["source_request_descriptor_id"]
                == previous_descriptor_id
            )

            assert interaction["runtime_value"] is None
            assert handoff["runtime_value"] is None
            assert sdk["previous_interaction_id"] is None

            previous_descriptor_id = descriptor_id


def test_global_contract_first_request_only() -> None:
    with built_package() as (package, _):
        for index, filename in enumerate(REQUEST_FILES):
            descriptor = load_json(package, filename)
            payload = descriptor[
                "sdk_call_template"
            ]["input_payload"]

            assert (
                "global_contract" in payload
            ) is (index == 0)


def test_controls_and_secret_exclusion() -> None:
    with built_package() as (package, result):
        false_count = 0
        forbidden_count = 0

        for filename in REQUEST_FILES:
            descriptor = load_json(package, filename)

            for location, value in walk(descriptor):
                leaf = location[-1]

                if leaf in FALSE_ONLY_KEYS:
                    assert value is False
                    false_count += 1

                if leaf in FORBIDDEN_SECRET_KEYS:
                    forbidden_count += 1

        assert false_count == EXPECTED_FALSE_CONTROL_COUNT
        assert (
            result["validated_false_control_count"]
            == EXPECTED_FALSE_CONTROL_COUNT
        )
        assert forbidden_count == 0
        assert result["forbidden_secret_field_count"] == 0


def test_atomic_writer_refuses_existing_output() -> None:
    with tempfile.TemporaryDirectory(
        prefix="canonflow-e66-collision-"
    ) as temporary:
        output = Path(temporary) / "existing"
        output.mkdir()
        sentinel = output / "sentinel.txt"
        sentinel.write_text("preserve\n", encoding="utf-8")

        exc = assert_raises(
            FileExistsError,
            lambda: build_gemini_direction_request_package(
                output
            ),
        )

        assert "Output path already exists:" in str(exc)
        assert sentinel.read_text(encoding="utf-8") == "preserve\n"


def test_offline_execution() -> None:
    with tempfile.TemporaryDirectory(
        prefix="canonflow-e66-offline-"
    ) as temporary:
        output = Path(temporary) / "package"

        with mock.patch.object(
            socket,
            "socket",
            side_effect=AssertionError(
                "Network socket creation is forbidden."
            ),
        ):
            result = build_gemini_direction_request_package(
                output
            )

        assert result["provider_calls"] is False
        assert result["http_requests"] is False
        assert result["network_access"] is False
        assert result["credentials_read"] is False
        assert result["media_generation_authorized"] is False


def test_validator_rejects_modified_descriptor() -> None:
    with built_package() as (package, _):
        with tempfile.TemporaryDirectory(
            prefix="canonflow-e66-mutated-descriptor-"
        ) as temporary:
            mutated = Path(temporary) / "package"
            shutil.copytree(package, mutated)

            path = mutated / "02-act_1-request.json"
            document = json.loads(
                path.read_text(encoding="utf-8")
            )
            document["model_binding"]["model"] = "invalid-model"
            path.write_text(
                json.dumps(
                    document,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )

            assert_raises(
                ValueError,
                lambda: validate_gemini_direction_request_package(
                    mutated
                ),
            )


def test_validator_rejects_modified_manifest_chain() -> None:
    with built_package() as (package, _):
        with tempfile.TemporaryDirectory(
            prefix="canonflow-e66-mutated-manifest-"
        ) as temporary:
            mutated = Path(temporary) / "package"
            shutil.copytree(package, mutated)

            path = mutated / "07-request-chain-manifest.json"
            document = json.loads(
                path.read_text(encoding="utf-8")
            )
            document["request_descriptors"][1][
                "previous_request_descriptor_id"
            ] = None
            path.write_text(
                json.dumps(
                    document,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )

            assert_raises(
                ValueError,
                lambda: validate_gemini_direction_request_package(
                    mutated
                ),
            )


TESTS = (
    test_deterministic_identity_and_hashes,
    test_expected_file_set_and_hashes,
    test_six_segment_request_contract,
    test_schema_and_manifest_identity,
    test_model_and_api_revision_binding,
    test_structured_response_format,
    test_thinking_temperature_and_tools_policy,
    test_ordered_runtime_chain,
    test_global_contract_first_request_only,
    test_controls_and_secret_exclusion,
    test_atomic_writer_refuses_existing_output,
    test_offline_execution,
    test_validator_rejects_modified_descriptor,
    test_validator_rejects_modified_manifest_chain,
)


def main() -> int:
    for test in TESTS:
        test()
        print(f"PASS: {test.__name__}")

    print(
        f"Gemini direction-request-builder tests passed: "
        f"{len(TESTS)}"
    )
    print("CANONFLOW GEMINI DIRECTION REQUEST BUILDER: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
