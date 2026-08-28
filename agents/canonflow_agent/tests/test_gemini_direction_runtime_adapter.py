"""Offline tests for the Gemini direction runtime adapter."""

from __future__ import annotations

import copy
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

AGENTS_ROOT = Path(__file__).resolve().parents[2]

if str(AGENTS_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENTS_ROOT))

from canonflow_agent.gemini_direction_runtime_adapter import (
    ExecutionNotAuthorizedError,
    InteractionResponseError,
    RequestContractError,
    canonical_json,
    execute_interaction_chain,
    prepare_interaction_request,
    validate_interaction_response,
)


PACKAGE = Path("/tmp/p10g-evidence-66-release-package")
REQUEST_FILES = (
    "01-prologue-request.json",
    "02-act_1-request.json",
    "03-act_2a-request.json",
    "04-act_2b-request.json",
    "05-act_3-request.json",
    "06-epilogue-request.json",
)


def load_json(filename: str) -> Any:
    return json.loads(
        (PACKAGE / filename).read_text(encoding="utf-8")
    )


def assert_raises(
    exception_type: type[BaseException],
    callback: Any,
) -> BaseException:
    try:
        callback()
    except exception_type as exc:
        return exc

    raise AssertionError(
        f"Expected {exception_type.__name__} to be raised"
    )


def resolve_ref(root: Mapping[str, Any], reference: str) -> Any:
    if not reference.startswith("#/"):
        raise AssertionError(f"Unsupported test schema reference: {reference}")

    value: Any = root

    for part in reference[2:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        value = value[key]

    return value


def schema_example(
    schema: Mapping[str, Any],
    *,
    root: Mapping[str, Any] | None = None,
) -> Any:
    if root is None:
        root = schema

    if "$ref" in schema:
        return schema_example(
            resolve_ref(root, schema["$ref"]),
            root=root,
        )

    if "const" in schema:
        return copy.deepcopy(schema["const"])

    enum_values = schema.get("enum")

    if isinstance(enum_values, list) and enum_values:
        return copy.deepcopy(enum_values[0])

    for union_key in ("oneOf", "anyOf"):
        variants = schema.get(union_key)

        if isinstance(variants, list) and variants:
            return schema_example(variants[0], root=root)

    all_of = schema.get("allOf")

    if isinstance(all_of, list) and all_of:
        merged: dict[str, Any] = {}

        for part in all_of:
            value = schema_example(part, root=root)

            if isinstance(value, dict):
                merged.update(value)

        return merged

    schema_type = schema.get("type")

    if isinstance(schema_type, list):
        schema_type = next(
            (item for item in schema_type if item != "null"),
            "null",
        )

    if schema_type == "object" or "properties" in schema:
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        result: dict[str, Any] = {}

        for key in required:
            result[key] = schema_example(
                properties[key],
                root=root,
            )

        return result

    if schema_type == "array":
        item_schema = schema.get("items", {})
        count = max(int(schema.get("minItems", 0)), 1)
        max_items = schema.get("maxItems")

        if isinstance(max_items, int):
            count = min(count, max_items)

        return [
            schema_example(item_schema, root=root)
            for _ in range(count)
        ]

    if schema_type == "integer":
        return int(schema.get("minimum", 0))

    if schema_type == "number":
        return float(schema.get("minimum", 0.0))

    if schema_type == "boolean":
        return False

    if schema_type == "null":
        return None

    if schema_type == "string" or schema_type is None:
        min_length = max(int(schema.get("minLength", 1)), 1)
        return "x" * min_length

    raise AssertionError(
        f"Unsupported test schema fragment: {schema!r}"
    )


def patch_identity_fields(
    value: Any,
    *,
    descriptor: Mapping[str, Any],
    segment_record: Mapping[str, Any],
) -> None:
    if isinstance(value, dict):
        replacements = {
            "segment_id": descriptor["segment_id"],
            "request_descriptor_id": descriptor[
                "request_descriptor_id"
            ],
            "shot_ids": segment_record["shot_ids_in_order"],
            "shot_ids_in_order": segment_record[
                "shot_ids_in_order"
            ],
        }

        for key, replacement in replacements.items():
            if key in value:
                value[key] = copy.deepcopy(replacement)

        for child in value.values():
            patch_identity_fields(
                child,
                descriptor=descriptor,
                segment_record=segment_record,
            )

    elif isinstance(value, list):
        for child in value:
            patch_identity_fields(
                child,
                descriptor=descriptor,
                segment_record=segment_record,
            )


@dataclass
class MockInteraction:
    id: str
    output_text: str
    status: str = "completed"
    steps: tuple[Any, ...] = ()


class MockTransport:
    def __init__(
        self,
        *,
        invalid_json_at: int | None = None,
        schema_failure_at: int | None = None,
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self.outputs: list[dict[str, Any]] = []
        self.invalid_json_at = invalid_json_at
        self.schema_failure_at = schema_failure_at
        self.manifest = load_json(
            "07-request-chain-manifest.json"
        )

    def create(self, **kwargs: Any) -> MockInteraction:
        call_index = len(self.calls)
        self.calls.append(copy.deepcopy(kwargs))

        if self.invalid_json_at == call_index:
            return MockInteraction(
                id=f"interaction-{call_index + 1}",
                output_text="{invalid",
            )

        record = self.manifest["request_descriptors"][call_index]
        descriptor = load_json(record["filename"])
        schema = descriptor["sdk_call_template"][
            "response_format"
        ]["schema"]

        output = schema_example(schema)
        patch_identity_fields(
            output,
            descriptor=descriptor,
            segment_record=record,
        )

        if not isinstance(output, dict):
            raise AssertionError("Expected object response fixture")

        output.setdefault(
            "continuity_handoff",
            {
                "source_segment_id": descriptor["segment_id"],
                "sequence": call_index + 1,
            },
        )

        if self.schema_failure_at == call_index:
            required = schema.get("required", [])

            if not required:
                raise AssertionError(
                    "Schema has no required field for failure test"
                )

            output.pop(required[0], None)

        self.outputs.append(copy.deepcopy(output))

        return MockInteraction(
            id=f"interaction-{call_index + 1}",
            output_text=canonical_json(output),
        )


def first_descriptor() -> dict[str, Any]:
    return load_json(REQUEST_FILES[0])


def second_descriptor() -> dict[str, Any]:
    return load_json(REQUEST_FILES[1])


def test_first_request_translation() -> None:
    prepared = prepare_interaction_request(
        first_descriptor(),
        filename=REQUEST_FILES[0],
        previous_interaction_id=None,
        prior_continuity_handoff=None,
    )
    arguments = prepared.sdk_arguments

    assert arguments["model"] == "gemini-3.1-pro-preview"
    assert arguments["api_version"] == "2026-05-20"
    assert arguments["generation_config"] == {
        "thinking_level": "high"
    }
    assert arguments["response_format"]["type"] == "text"
    assert (
        arguments["response_format"]["mime_type"]
        == "application/json"
    )
    assert "temperature" not in arguments
    assert "previous_interaction_id" not in arguments


def test_second_request_runtime_bindings() -> None:
    handoff = {"source": "prologue", "state": ["cold"]}
    prepared = prepare_interaction_request(
        second_descriptor(),
        filename=REQUEST_FILES[1],
        previous_interaction_id="interaction-1",
        prior_continuity_handoff=handoff,
    )

    arguments = prepared.sdk_arguments
    payload = json.loads(arguments["input"])

    assert (
        arguments["previous_interaction_id"]
        == "interaction-1"
    )
    assert (
        payload["runtime_bindings"]["prior_continuity_handoff"]
        == handoff
    )


def test_missing_previous_interaction_rejected() -> None:
    assert_raises(
        RequestContractError,
        lambda: prepare_interaction_request(
            second_descriptor(),
            filename=REQUEST_FILES[1],
            previous_interaction_id=None,
            prior_continuity_handoff={"valid": True},
        ),
    )


def test_missing_handoff_rejected() -> None:
    assert_raises(
        RequestContractError,
        lambda: prepare_interaction_request(
            second_descriptor(),
            filename=REQUEST_FILES[1],
            previous_interaction_id="interaction-1",
            prior_continuity_handoff=None,
        ),
    )


def test_temperature_never_forwarded() -> None:
    prepared = prepare_interaction_request(
        first_descriptor(),
        filename=REQUEST_FILES[0],
        previous_interaction_id=None,
        prior_continuity_handoff=None,
    )

    assert "temperature" not in prepared.sdk_arguments
    assert "response_mime_type" not in prepared.sdk_arguments


def test_non_mock_execution_requires_authorization() -> None:
    transport = MockTransport()

    assert_raises(
        ExecutionNotAuthorizedError,
        lambda: execute_interaction_chain(
            PACKAGE,
            transport,
            local_mock_transport=False,
            provider_execution_authorized=False,
        ),
    )

    assert transport.calls == []


def test_mock_chain_executes_six_requests() -> None:
    transport = MockTransport()
    result = execute_interaction_chain(
        PACKAGE,
        transport,
        local_mock_transport=True,
        provider_execution_authorized=False,
    )

    assert len(result.results) == 6
    assert len(transport.calls) == 6
    assert result.model_id == "gemini-3.1-pro-preview"


def test_previous_interaction_chain_is_ordered() -> None:
    transport = MockTransport()

    execute_interaction_chain(
        PACKAGE,
        transport,
        local_mock_transport=True,
    )

    assert "previous_interaction_id" not in transport.calls[0]

    for index in range(1, 6):
        assert (
            transport.calls[index]["previous_interaction_id"]
            == f"interaction-{index}"
        )


def test_continuity_handoff_is_forwarded() -> None:
    transport = MockTransport()

    execute_interaction_chain(
        PACKAGE,
        transport,
        local_mock_transport=True,
    )

    for index in range(1, 6):
        payload = json.loads(transport.calls[index]["input"])
        runtime_value = payload["runtime_bindings"][
            "prior_continuity_handoff"
        ]

        expected_handoff = transport.outputs[index - 1][
            "continuity_handoff"
        ]

        assert runtime_value == expected_handoff


def test_invalid_json_stops_chain() -> None:
    transport = MockTransport(invalid_json_at=2)

    assert_raises(
        InteractionResponseError,
        lambda: execute_interaction_chain(
            PACKAGE,
            transport,
            local_mock_transport=True,
        ),
    )

    assert len(transport.calls) == 3


def test_schema_failure_stops_chain() -> None:
    transport = MockTransport(schema_failure_at=1)

    assert_raises(
        InteractionResponseError,
        lambda: execute_interaction_chain(
            PACKAGE,
            transport,
            local_mock_transport=True,
        ),
    )

    assert len(transport.calls) == 2


def test_response_without_interaction_id_rejected() -> None:
    prepared = prepare_interaction_request(
        first_descriptor(),
        filename=REQUEST_FILES[0],
        previous_interaction_id=None,
        prior_continuity_handoff=None,
    )

    response = {
        "id": "",
        "output_text": "{}",
    }

    assert_raises(
        InteractionResponseError,
        lambda: validate_interaction_response(
            response,
            prepared_request=prepared,
        ),
    )



def test_google_genai_request_model_accepts_arguments() -> None:
    from google.genai._gaos.types.interactions.createmodelinteraction import (
        CreateModelInteraction,
    )

    prepared = prepare_interaction_request(
        first_descriptor(),
        filename=REQUEST_FILES[0],
        previous_interaction_id=None,
        prior_continuity_handoff=None,
    )
    body = copy.deepcopy(prepared.sdk_arguments)
    api_version = body.pop("api_version")

    request = CreateModelInteraction(**body)
    serialized = request.model_dump(
        mode="json",
        by_alias=True,
        exclude_none=True,
    )

    assert api_version == "2026-05-20"
    assert serialized["model"] == "gemini-3.1-pro-preview"
    assert serialized["generation_config"]["thinking_level"] == "high"
    assert serialized["response_format"]["type"] == "text"
    assert (
        serialized["response_format"]["mime_type"]
        == "application/json"
    )
    assert isinstance(
        serialized["response_format"]["schema"],
        dict,
    )
    assert serialized["store"] is True
    assert serialized["stream"] is False
    assert serialized["background"] is False
    assert serialized["tools"] == []
    assert "temperature" not in serialized
    assert "response_mime_type" not in serialized


TESTS = (
    test_first_request_translation,
    test_google_genai_request_model_accepts_arguments,
    test_second_request_runtime_bindings,
    test_missing_previous_interaction_rejected,
    test_missing_handoff_rejected,
    test_temperature_never_forwarded,
    test_non_mock_execution_requires_authorization,
    test_mock_chain_executes_six_requests,
    test_previous_interaction_chain_is_ordered,
    test_continuity_handoff_is_forwarded,
    test_invalid_json_stops_chain,
    test_schema_failure_stops_chain,
    test_response_without_interaction_id_rejected,
)


def main() -> int:
    if not PACKAGE.is_dir():
        print(f"ERROR: Missing descriptor package: {PACKAGE}")
        return 1

    for test in TESTS:
        test()
        print(f"PASS: {test.__name__}")

    print(
        "Gemini direction runtime-adapter tests passed: "
        f"{len(TESTS)}"
    )
    print("CANONFLOW GEMINI DIRECTION RUNTIME ADAPTER: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
