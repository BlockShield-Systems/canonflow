"""Offline-first Gemini Interactions runtime adapter.

This module translates frozen CanonFlow request descriptors into arguments for
``client.interactions.create``. It does not construct a Gemini client, inspect
credentials, or authorize provider execution.

A caller must inject an object exposing ``create(**kwargs)``. Local mock
transports are permitted for validation. Any non-mock transport requires an
explicit provider-execution authorization flag.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from jsonschema import ValidationError
from jsonschema.validators import validator_for

from canonflow_agent.gemini_direction_request_builder import (
    SEGMENT_ORDER,
    validate_gemini_direction_request_package,
)


MODEL_ID = "gemini-3.1-pro-preview"
INTERACTIONS_SCHEMA_REVISION = "2026-05-20"
REQUEST_FILENAMES = (
    "01-prologue-request.json",
    "02-act_1-request.json",
    "03-act_2a-request.json",
    "04-act_2b-request.json",
    "05-act_3-request.json",
    "06-epilogue-request.json",
)


class RuntimeAdapterError(RuntimeError):
    """Base error for deterministic runtime-adapter failures."""


class ExecutionNotAuthorizedError(RuntimeAdapterError):
    """Raised when a non-mock transport lacks explicit approval."""


class RequestContractError(RuntimeAdapterError):
    """Raised when a frozen request descriptor cannot be translated safely."""


class InteractionResponseError(RuntimeAdapterError):
    """Raised when an interaction response is malformed or schema-invalid."""


class InteractionTransport(Protocol):
    """Minimal transport surface required by the adapter."""

    def create(self, **kwargs: Any) -> Any:
        """Create one interaction and return an interaction-like object."""


@dataclass(frozen=True)
class PreparedInteractionRequest:
    """Validated SDK arguments for one request descriptor."""

    filename: str
    request_descriptor_id: str
    segment_id: str
    sdk_arguments: dict[str, Any]


@dataclass(frozen=True)
class ValidatedInteractionResult:
    """Validated result of one segment interaction."""

    filename: str
    request_descriptor_id: str
    segment_id: str
    interaction_id: str
    output: dict[str, Any]


@dataclass(frozen=True)
class InteractionChainResult:
    """Complete validated result of the six-request chain."""

    package_path: str
    model_id: str
    interactions_schema_revision: str
    results: tuple[ValidatedInteractionResult, ...]


def canonical_json(value: Any) -> str:
    """Serialize a value as deterministic UTF-8-compatible JSON text."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RequestContractError(
            f"Invalid JSON in {path.name}: line {exc.lineno}, "
            f"column {exc.colno}: {exc.msg}"
        ) from exc


def _require_mapping(
    value: Any,
    *,
    location: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RequestContractError(f"{location} must be an object")

    return value


def _input_runtime_bindings(
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    runtime_bindings = _require_mapping(
        input_payload.get("runtime_bindings"),
        location="sdk_call_template.input_payload.runtime_bindings",
    )

    if "prior_continuity_handoff" not in runtime_bindings:
        raise RequestContractError(
            "input_payload runtime binding "
            "prior_continuity_handoff is missing"
        )

    if runtime_bindings["prior_continuity_handoff"] is not None:
        raise RequestContractError(
            "Frozen input_payload prior_continuity_handoff "
            "slot must initially be null"
        )

    return runtime_bindings


def prepare_interaction_request(
    descriptor: Mapping[str, Any],
    *,
    filename: str,
    previous_interaction_id: str | None,
    prior_continuity_handoff: Mapping[str, Any] | None,
) -> PreparedInteractionRequest:
    """Translate one validated descriptor into SDK 2.19 arguments."""

    descriptor_object = _require_mapping(
        dict(descriptor),
        location=f"{filename}",
    )
    sdk_template = _require_mapping(
        descriptor_object.get("sdk_call_template"),
        location=f"{filename}.sdk_call_template",
    )
    model_binding = _require_mapping(
        descriptor_object.get("model_binding"),
        location=f"{filename}.model_binding",
    )

    request_descriptor_id = descriptor_object.get("request_descriptor_id")
    segment_id = descriptor_object.get("segment_id")

    if not isinstance(request_descriptor_id, str) or not request_descriptor_id:
        raise RequestContractError(
            f"{filename}.request_descriptor_id must be a non-empty string"
        )

    if not isinstance(segment_id, str) or segment_id not in SEGMENT_ORDER:
        raise RequestContractError(
            f"{filename}.segment_id is invalid: {segment_id!r}"
        )

    if sdk_template.get("method") != "client.interactions.create":
        raise RequestContractError(
            f"{filename} has an unsupported SDK method"
        )

    if sdk_template.get("model") != MODEL_ID:
        raise RequestContractError(f"{filename} model mismatch")

    if model_binding.get("model") != MODEL_ID:
        raise RequestContractError(f"{filename} model binding mismatch")

    if (
        model_binding.get("api_revision")
        != INTERACTIONS_SCHEMA_REVISION
    ):
        raise RequestContractError(
            f"{filename} API revision mismatch"
        )

    for key, expected in (
        ("store", True),
        ("stream", False),
        ("background", False),
    ):
        if sdk_template.get(key) is not expected:
            raise RequestContractError(
                f"{filename}.{key} must be {expected!r}"
            )

    if sdk_template.get("tools") != []:
        raise RequestContractError(
            f"{filename}.tools must be an empty array"
        )

    temperature = _require_mapping(
        sdk_template.get("temperature"),
        location=f"{filename}.temperature",
    )

    if temperature.get("included") is not False:
        raise RequestContractError(
            f"{filename} must not forward temperature"
        )

    if temperature.get("policy") != "use_model_default_1.0":
        raise RequestContractError(
            f"{filename} temperature policy mismatch"
        )

    if sdk_template.get("thinking_level") != "high":
        raise RequestContractError(
            f"{filename}.thinking_level must equal high"
        )

    response_format = _require_mapping(
        copy.deepcopy(sdk_template.get("response_format")),
        location=f"{filename}.response_format",
    )

    if response_format.get("type") != "text":
        raise RequestContractError(
            f"{filename}.response_format.type must equal text"
        )

    if response_format.get("mime_type") != "application/json":
        raise RequestContractError(
            f"{filename}.response_format.mime_type must be application/json"
        )

    if not isinstance(response_format.get("schema"), dict):
        raise RequestContractError(
            f"{filename}.response_format.schema must be an object"
        )

    system_instruction = sdk_template.get("system_instruction")

    if not isinstance(system_instruction, str) or not system_instruction:
        raise RequestContractError(
            f"{filename}.system_instruction must be non-empty"
        )

    input_payload = _require_mapping(
        copy.deepcopy(sdk_template.get("input_payload")),
        location=f"{filename}.input_payload",
    )
    payload_runtime_bindings = _input_runtime_bindings(
        input_payload
    )
    descriptor_runtime_bindings = _require_mapping(
        descriptor_object.get("runtime_bindings"),
        location=f"{filename}.runtime_bindings",
    )
    handoff_binding = _require_mapping(
        descriptor_runtime_bindings.get(
            "prior_continuity_handoff"
        ),
        location=(
            f"{filename}.runtime_bindings."
            "prior_continuity_handoff"
        ),
    )

    previous_binding = _require_mapping(
        sdk_template.get("previous_interaction_id_binding"),
        location=f"{filename}.previous_interaction_id_binding",
    )

    previous_required = previous_binding.get("required")
    handoff_required = handoff_binding.get("required")

    if previous_required not in (True, False):
        raise RequestContractError(
            f"{filename} has an invalid previous-interaction binding"
        )

    if handoff_required not in (True, False):
        raise RequestContractError(
            f"{filename} has an invalid continuity-handoff binding"
        )

    if previous_required:
        if not isinstance(previous_interaction_id, str):
            raise RequestContractError(
                f"{filename} requires previous_interaction_id"
            )

        if not previous_interaction_id:
            raise RequestContractError(
                f"{filename} requires non-empty previous_interaction_id"
            )
    elif previous_interaction_id is not None:
        raise RequestContractError(
            f"{filename} must not receive previous_interaction_id"
        )

    if handoff_required:
        if not isinstance(prior_continuity_handoff, Mapping):
            raise RequestContractError(
                f"{filename} requires prior_continuity_handoff"
            )

        payload_runtime_bindings[
            "prior_continuity_handoff"
        ] = copy.deepcopy(dict(prior_continuity_handoff))
    else:
        if prior_continuity_handoff is not None:
            raise RequestContractError(
                f"{filename} must not receive prior_continuity_handoff"
            )

        payload_runtime_bindings[
            "prior_continuity_handoff"
        ] = None

    sdk_arguments: dict[str, Any] = {
        "api_version": INTERACTIONS_SCHEMA_REVISION,
        "model": MODEL_ID,
        "input": canonical_json(input_payload),
        "store": True,
        "stream": False,
        "background": False,
        "system_instruction": system_instruction,
        "tools": [],
        "response_format": response_format,
        "generation_config": {
            "thinking_level": "high",
        },
    }

    if previous_interaction_id is not None:
        sdk_arguments["previous_interaction_id"] = (
            previous_interaction_id
        )

    forbidden_forwarded_arguments = {
        "temperature",
        "response_mime_type",
    } & set(sdk_arguments)

    if forbidden_forwarded_arguments:
        raise RequestContractError(
            "Forbidden SDK arguments were forwarded: "
            + ", ".join(sorted(forbidden_forwarded_arguments))
        )

    return PreparedInteractionRequest(
        filename=filename,
        request_descriptor_id=request_descriptor_id,
        segment_id=segment_id,
        sdk_arguments=sdk_arguments,
    )


def _response_attribute(response: Any, name: str) -> Any:
    if isinstance(response, Mapping):
        return response.get(name)

    return getattr(response, name, None)


def validate_interaction_response(
    response: Any,
    *,
    prepared_request: PreparedInteractionRequest,
) -> ValidatedInteractionResult:
    """Parse and validate one Interactions response."""

    interaction_id = _response_attribute(response, "id")
    output_text = _response_attribute(response, "output_text")

    if not isinstance(interaction_id, str) or not interaction_id:
        raise InteractionResponseError(
            f"{prepared_request.filename} response has no interaction ID"
        )

    if not isinstance(output_text, str) or not output_text:
        raise InteractionResponseError(
            f"{prepared_request.filename} response has no output_text"
        )

    try:
        output = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise InteractionResponseError(
            f"{prepared_request.filename} returned invalid JSON: "
            f"line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    if not isinstance(output, dict):
        raise InteractionResponseError(
            f"{prepared_request.filename} output must be an object"
        )

    schema = prepared_request.sdk_arguments["response_format"]["schema"]
    validator_class = validator_for(schema)

    try:
        validator_class.check_schema(schema)
        validator_class(schema).validate(output)
    except ValidationError as exc:
        location = ".".join(str(part) for part in exc.absolute_path)
        suffix = f" at {location}" if location else ""

        raise InteractionResponseError(
            f"{prepared_request.filename} response schema violation"
            f"{suffix}: {exc.message}"
        ) from exc
    except Exception as exc:
        raise InteractionResponseError(
            f"{prepared_request.filename} contains an invalid JSON schema: "
            f"{exc}"
        ) from exc

    output_segment = output.get("segment_id")

    if (
        output_segment is not None
        and output_segment != prepared_request.segment_id
    ):
        raise InteractionResponseError(
            f"{prepared_request.filename} returned segment_id "
            f"{output_segment!r}, expected "
            f"{prepared_request.segment_id!r}"
        )

    output_descriptor_id = output.get("request_descriptor_id")

    if (
        output_descriptor_id is not None
        and output_descriptor_id
        != prepared_request.request_descriptor_id
    ):
        raise InteractionResponseError(
            f"{prepared_request.filename} returned a mismatched "
            "request_descriptor_id"
        )

    handoff = output.get("continuity_handoff")

    if not isinstance(handoff, dict):
        raise InteractionResponseError(
            f"{prepared_request.filename} response lacks "
            "continuity_handoff"
        )

    return ValidatedInteractionResult(
        filename=prepared_request.filename,
        request_descriptor_id=prepared_request.request_descriptor_id,
        segment_id=prepared_request.segment_id,
        interaction_id=interaction_id,
        output=output,
    )


def execute_interaction_chain(
    package_path: str | Path,
    transport: InteractionTransport,
    *,
    local_mock_transport: bool = False,
    provider_execution_authorized: bool = False,
) -> InteractionChainResult:
    """Execute all six descriptors in order through an injected transport."""

    if not local_mock_transport and not provider_execution_authorized:
        raise ExecutionNotAuthorizedError(
            "Non-mock provider execution requires explicit authorization"
        )

    package = Path(package_path).expanduser().resolve()
    validate_gemini_direction_request_package(package)

    manifest = _require_mapping(
        _load_json(package / "07-request-chain-manifest.json"),
        location="07-request-chain-manifest.json",
    )
    records = manifest.get("request_descriptors")

    if not isinstance(records, list) or len(records) != 6:
        raise RequestContractError(
            "Request-chain manifest must contain six descriptors"
        )

    expected_segments = tuple(SEGMENT_ORDER)
    actual_segments = tuple(
        record.get("segment_id")
        for record in records
        if isinstance(record, dict)
    )

    if actual_segments != expected_segments:
        raise RequestContractError(
            "Request-chain segment order mismatch"
        )

    results: list[ValidatedInteractionResult] = []
    previous_interaction_id: str | None = None
    prior_continuity_handoff: dict[str, Any] | None = None
    previous_descriptor_id: str | None = None

    for index, record_value in enumerate(records):
        record = _require_mapping(
            record_value,
            location=f"request_descriptors[{index}]",
        )
        filename = record.get("filename")

        if filename != REQUEST_FILENAMES[index]:
            raise RequestContractError(
                f"Unexpected descriptor filename at index {index}: "
                f"{filename!r}"
            )

        if record.get("previous_request_descriptor_id") != (
            previous_descriptor_id
        ):
            raise RequestContractError(
                f"Broken descriptor chain at {filename}"
            )

        descriptor = _require_mapping(
            _load_json(package / filename),
            location=filename,
        )

        prepared = prepare_interaction_request(
            descriptor,
            filename=filename,
            previous_interaction_id=previous_interaction_id,
            prior_continuity_handoff=prior_continuity_handoff,
        )

        response = transport.create(**prepared.sdk_arguments)

        validated = validate_interaction_response(
            response,
            prepared_request=prepared,
        )
        results.append(validated)

        previous_interaction_id = validated.interaction_id
        prior_continuity_handoff = copy.deepcopy(
            validated.output["continuity_handoff"]
        )
        previous_descriptor_id = validated.request_descriptor_id

    return InteractionChainResult(
        package_path=str(package),
        model_id=MODEL_ID,
        interactions_schema_revision=INTERACTIONS_SCHEMA_REVISION,
        results=tuple(results),
    )
