"""Google Gen AI production transport for the frozen direction adapter.

The frozen request package uses an Interactions-shaped contract. This module
validates that contract and translates it to a stateful Google Gen AI
Chat/GenerateContent invocation.

No automatic retries are permitted. One transport instance represents one
authorized sequential six-request run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from google import genai
from google.genai import types


MODEL = "gemini-3.1-pro-preview"
INTERACTIONS_SCHEMA_REVISION = "2026-05-20"
GOOGLE_HTTP_API_VERSION = "v1"


class GoogleGenAITransportError(RuntimeError):
    """Raised when the frozen provider contract is violated."""


@dataclass(frozen=True)
class GoogleGenAIInteractionResponse:
    """Response shape expected by the frozen runtime adapter."""

    id: str
    output_text: str
    status: str = "completed"
    steps: tuple[Any, ...] = ()
    raw_output_text: str | None = None
    normalization_actions: tuple[str, ...] = ()


class GoogleGenAIChatTransport:
    """Stateful sequential Chat/GenerateContent transport."""

    def __init__(
        self,
        *,
        project: str,
        location: str = "global",
        expected_model: str = MODEL,
        maximum_request_count: int = 6,
        client_factory: Callable[..., Any] | None = None,
    ) -> None:
        if not isinstance(project, str) or not project.strip():
            raise ValueError("project must be a non-empty string")

        if location != "global":
            raise ValueError("location must equal global")

        if expected_model != MODEL:
            raise ValueError(f"expected_model must equal {MODEL}")

        if maximum_request_count != 6:
            raise ValueError("maximum_request_count must equal 6")

        self._project = project
        self._location = location
        self._expected_model = expected_model
        self._maximum_request_count = maximum_request_count
        self._client_factory = client_factory or genai.Client

        self._client: Any | None = None
        self._chat: Any | None = None
        self._last_response_id: str | None = None
        self._request_count = 0
        self._closed = False

    @property
    def request_count(self) -> int:
        return self._request_count

    @property
    def last_response_id(self) -> str | None:
        return self._last_response_id

    @staticmethod
    def _require_mapping(
        value: Any,
        *,
        field: str,
    ) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise GoogleGenAITransportError(
                f"{field} must be an object"
            )

        return value

    @staticmethod
    def _validate_exact_control(
        *,
        name: str,
        observed: Any,
        expected: Any,
    ) -> None:
        if observed != expected:
            raise GoogleGenAITransportError(
                f"{name} must equal {expected!r}"
            )

    def _ensure_client(self, *, model: str) -> None:
        if self._client is not None:
            return

        self._client = self._client_factory(
            enterprise=True,
            project=self._project,
            location=self._location,
            http_options=types.HttpOptions(
                api_version=GOOGLE_HTTP_API_VERSION,
                retry_options=types.HttpRetryOptions(
                    attempts=1,
                ),
            ),
        )
        self._chat = self._client.chats.create(
            model=model,
            history=[],
        )

    @classmethod
    def _normalize_to_schema(
        cls,
        value: Any,
        schema: Mapping[str, Any],
        *,
        path: str = "$",
    ) -> tuple[Any, list[str]]:
        """Apply only deterministic representation normalization."""

        actions: list[str] = []
        expected_type = schema.get("type")

        if isinstance(expected_type, list):
            expected_types = set(expected_type)
        elif isinstance(expected_type, str):
            expected_types = {expected_type}
        else:
            expected_types = set()

        if (
            "object" in expected_types
            and isinstance(value, list)
            and len(value) == 1
            and isinstance(value[0], Mapping)
        ):
            value = dict(value[0])
            actions.append(f"{path}:unwrapped_single_object_array")

        if "object" in expected_types and isinstance(value, Mapping):
            properties = schema.get("properties")
            normalized_object = dict(value)

            if isinstance(properties, Mapping):
                for key, property_schema in properties.items():
                    if (
                        key in normalized_object
                        and isinstance(property_schema, Mapping)
                    ):
                        normalized_value, child_actions = (
                            cls._normalize_to_schema(
                                normalized_object[key],
                                property_schema,
                                path=f"{path}.{key}",
                            )
                        )
                        normalized_object[key] = normalized_value
                        actions.extend(child_actions)

            return normalized_object, actions

        if "array" in expected_types and isinstance(value, list):
            item_schema = schema.get("items")

            if isinstance(item_schema, Mapping):
                normalized_items: list[Any] = []

                for index, item in enumerate(value):
                    normalized_item, child_actions = (
                        cls._normalize_to_schema(
                            item,
                            item_schema,
                            path=f"{path}[{index}]",
                        )
                    )
                    normalized_items.append(normalized_item)
                    actions.extend(child_actions)

                return normalized_items, actions

            return value, actions

        if "string" in expected_types and not isinstance(value, str):
            if isinstance(value, bool):
                normalized_string = (
                    "true" if value else "false"
                )
                action_kind = "scalar_to_string:bool"
            elif isinstance(value, (int, float)):
                normalized_string = str(value)
                action_kind = (
                    "scalar_to_string:"
                    f"{type(value).__name__}"
                )
            elif isinstance(value, (list, Mapping)):
                normalized_string = json.dumps(
                    value,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=isinstance(value, Mapping),
                )
                action_kind = (
                    "composite_to_json_string:"
                    f"{type(value).__name__}"
                )
            else:
                return value, actions

            actions.append(
                f"{path}:{action_kind}"
            )
            return normalized_string, actions

        return value, actions

    def create(
        self,
        **kwargs: Any,
    ) -> GoogleGenAIInteractionResponse:
        if self._closed:
            raise GoogleGenAITransportError(
                "transport is closed"
            )

        if self._request_count >= self._maximum_request_count:
            raise GoogleGenAITransportError(
                "authorized maximum_request_count exceeded"
            )

        allowed_arguments = {
            "api_version",
            "background",
            "generation_config",
            "input",
            "model",
            "previous_interaction_id",
            "response_format",
            "store",
            "stream",
            "system_instruction",
            "tools",
        }

        unexpected = sorted(
            set(kwargs) - allowed_arguments
        )

        if unexpected:
            raise GoogleGenAITransportError(
                "unexpected SDK arguments: "
                + ", ".join(unexpected)
            )

        required_arguments = {
            "api_version",
            "background",
            "generation_config",
            "input",
            "model",
            "response_format",
            "store",
            "stream",
            "system_instruction",
            "tools",
        }

        missing = sorted(
            required_arguments - set(kwargs)
        )

        if missing:
            raise GoogleGenAITransportError(
                "missing SDK arguments: "
                + ", ".join(missing)
            )

        model = kwargs["model"]
        schema_revision = kwargs["api_version"]
        background = kwargs["background"]
        generation_config = self._require_mapping(
            kwargs["generation_config"],
            field="generation_config",
        )
        input_value = kwargs["input"]
        previous_interaction_id = kwargs.get(
            "previous_interaction_id"
        )
        response_format = self._require_mapping(
            kwargs["response_format"],
            field="response_format",
        )
        store = kwargs["store"]
        stream = kwargs["stream"]
        system_instruction = kwargs["system_instruction"]
        tools = kwargs["tools"]

        self._validate_exact_control(
            name="model",
            observed=model,
            expected=self._expected_model,
        )
        self._validate_exact_control(
            name="api_version",
            observed=schema_revision,
            expected=INTERACTIONS_SCHEMA_REVISION,
        )
        self._validate_exact_control(
            name="background",
            observed=background,
            expected=False,
        )
        self._validate_exact_control(
            name="store",
            observed=store,
            expected=True,
        )
        self._validate_exact_control(
            name="stream",
            observed=stream,
            expected=False,
        )
        self._validate_exact_control(
            name="tools",
            observed=tools,
            expected=[],
        )

        if dict(generation_config) != {
            "thinking_level": "high"
        }:
            raise GoogleGenAITransportError(
                "generation_config must contain only "
                "thinking_level='high'"
            )

        if not isinstance(input_value, str) or not input_value:
            raise GoogleGenAITransportError(
                "input must be a non-empty JSON string"
            )

        try:
            parsed_input = __import__("json").loads(input_value)
        except (TypeError, ValueError) as exc:
            raise GoogleGenAITransportError(
                "input must contain valid JSON"
            ) from exc

        if not isinstance(parsed_input, dict):
            raise GoogleGenAITransportError(
                "input JSON must be an object"
            )

        if (
            not isinstance(system_instruction, str)
            or not system_instruction
        ):
            raise GoogleGenAITransportError(
                "system_instruction must be non-empty"
            )

        if response_format.get("type") != "text":
            raise GoogleGenAITransportError(
                "response_format.type must equal text"
            )

        if response_format.get("mime_type") != "application/json":
            raise GoogleGenAITransportError(
                "response_format.mime_type must equal application/json"
            )

        response_schema = response_format.get("schema")

        if not isinstance(response_schema, dict):
            raise GoogleGenAITransportError(
                "response_format.schema must be an object"
            )

        if self._request_count == 0:
            if previous_interaction_id not in (None, ""):
                raise GoogleGenAITransportError(
                    "first request must not contain "
                    "previous_interaction_id"
                )
        elif previous_interaction_id != self._last_response_id:
            raise GoogleGenAITransportError(
                "previous_interaction_id does not bind "
                "the preceding response"
            )

        self._ensure_client(model=model)

        if self._chat is None:
            raise GoogleGenAITransportError(
                "SDK chat initialization failed"
            )

        # The complete frozen schema remains mandatory for local validation.
        # It is intentionally not transmitted because the provider rejects
        # this schema complexity with HTTP 400 INVALID_ARGUMENT.
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(
                thinking_level="HIGH",
            ),
            tools=None,
        )

        # The only productive network boundary in this module.
        response = self._chat.send_message(
            input_value,
            config=config,
        )

        response_id = getattr(
            response,
            "response_id",
            None,
        )
        output_text = getattr(
            response,
            "text",
            None,
        )

        if not isinstance(response_id, str) or not response_id:
            raise GoogleGenAITransportError(
                "provider response has no response_id"
            )

        if not isinstance(output_text, str) or not output_text:
            raise GoogleGenAITransportError(
                "provider response has no text output"
            )

        raw_output_text = output_text

        try:
            parsed_output = json.loads(raw_output_text)
        except (TypeError, ValueError) as exc:
            raise GoogleGenAITransportError(
                "provider response is not valid JSON"
            ) from exc

        normalized_output, normalization_actions = (
            self._normalize_to_schema(
                parsed_output,
                response_schema,
            )
        )

        output_text = json.dumps(
            normalized_output,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        self._request_count += 1
        self._last_response_id = response_id

        return GoogleGenAIInteractionResponse(
            id=response_id,
            output_text=output_text,
            raw_output_text=raw_output_text,
            normalization_actions=tuple(normalization_actions),
        )

    def close(self) -> None:
        if self._closed:
            return

        if self._client is not None:
            self._client.close()

        self._closed = True

    def __enter__(self) -> "GoogleGenAIChatTransport":
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc: Any,
        traceback: Any,
    ) -> None:
        self.close()
