#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import re
import sys
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from canonflow_agent import root_agent
from canonflow_agent.policy import enforce_read_only_clickhouse


APP_NAME = "canonflow-event-ledger-readonly-validation"
USER_ID = "demian"

EVENT_ID = "3b2a7e9f-f8bf-5f7c-8717-1a0a231e4177"
DEDUPLICATION_KEY = (
    "cloud-run-smoke:bfc9b4ae-c196-4ef8-bc84-8e78f395570b"
)
EXPECTED_EVENT_NAME = "nscl.force_amplification.set"
EXPECTED_PAYLOAD_STATE = "remote-validation"

EXPECTED_QUERY = f"""
SELECT
    toString(e.event_id) AS event_id_text,
    e.deduplication_key,
    e.event_name,
    e.event_version,
    e.truth_scope,
    e.source_service,
    e.source_instance,
    e.payload_json
FROM canonflow.v_events_current AS e
WHERE e.project_id = toUUID(
    'e8627781-5bf3-4c4d-905f-8dda49ab53d6'
)
  AND e.event_id = toUUID('{EVENT_ID}')
  AND e.deduplication_key = '{DEDUPLICATION_KEY}'
LIMIT 1
""".strip()

PROMPT = f"""
Perform one narrowly scoped, read-only Event Ledger verification.

You must call the MCP tool `run_query` exactly once.

Execute exactly this SQL query and do not call any other tool:

{EXPECTED_QUERY}

After receiving the tool response, report only:
- event_id
- deduplication_key
- event_name
- event_version
- truth_scope
- source_service
- source_instance
- payload_json

Do not execute INSERT, UPDATE, DELETE, ALTER, CREATE, DROP, TRUNCATE,
OPTIMIZE, GRANT, REVOKE, or any other state-changing operation.
Do not inspect unrelated projects or events.
""".strip()


class PolicyTool:
    name = "run_query"


def to_jsonable(value: Any) -> Any:
    if value is None:
        return None

    if hasattr(value, "model_dump"):
        return to_jsonable(
            value.model_dump(
                mode="json",
                exclude_none=True,
            )
        )

    if isinstance(value, Mapping):
        return {
            str(key): to_jsonable(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]

    if isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


def content_text(content: Any) -> str:
    if content is None:
        return ""

    texts: list[str] = []

    for part in getattr(content, "parts", None) or []:
        text = getattr(part, "text", None)

        if text:
            texts.append(str(text))

    return "\n".join(texts).strip()


def normalized_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip().rstrip(";").strip()


def collect_activity(
    event: Any,
    tool_calls: list[dict[str, Any]],
    tool_responses: list[dict[str, Any]],
    final_responses: list[str],
    model_errors: list[dict[str, str]],
) -> None:
    error_code = getattr(event, "error_code", None)

    if error_code:
        model_errors.append(
            {
                "code": str(error_code),
                "message": str(
                    getattr(event, "error_message", None) or ""
                ),
            }
        )

    content = getattr(event, "content", None)

    if content is not None:
        for part in getattr(content, "parts", None) or []:
            function_call = getattr(part, "function_call", None)

            if function_call is not None:
                tool_calls.append(
                    {
                        "id": getattr(function_call, "id", None),
                        "name": getattr(function_call, "name", None),
                        "args": to_jsonable(
                            getattr(function_call, "args", None)
                        ),
                    }
                )

            function_response = getattr(
                part,
                "function_response",
                None,
            )

            if function_response is not None:
                tool_responses.append(
                    {
                        "id": getattr(function_response, "id", None),
                        "name": getattr(function_response, "name", None),
                        "response": to_jsonable(
                            getattr(
                                function_response,
                                "response",
                                None,
                            )
                        ),
                    }
                )

    is_final = getattr(
        event,
        "is_final_response",
        lambda: False,
    )()

    if is_final:
        text = content_text(content)

        if text:
            final_responses.append(text)


def validate_trace(
    tool_calls: list[dict[str, Any]],
    tool_responses: list[dict[str, Any]],
    final_responses: list[str],
    model_errors: list[dict[str, str]],
) -> None:
    if model_errors:
        raise RuntimeError(
            f"ADK model errors were returned: {model_errors!r}"
        )

    if len(tool_calls) != 1:
        raise RuntimeError(
            "Expected exactly one MCP tool call, "
            f"received {len(tool_calls)}: {tool_calls!r}"
        )

    tool_call = tool_calls[0]

    if tool_call.get("name") != "run_query":
        raise RuntimeError(
            "Expected only run_query, received: "
            f"{tool_call.get('name')!r}"
        )

    args = tool_call.get("args")

    if not isinstance(args, dict):
        raise RuntimeError(
            f"run_query arguments are not a dictionary: {args!r}"
        )

    query = args.get("query")

    if not isinstance(query, str) or not query.strip():
        raise RuntimeError(
            "The captured run_query call has no SQL query."
        )

    policy_result = enforce_read_only_clickhouse(
        tool=PolicyTool(),
        args={"query": query},
        tool_context=None,
    )

    if policy_result is not None:
        raise RuntimeError(
            "Captured SQL did not pass the local read-only policy: "
            f"{policy_result!r}"
        )

    if normalized_sql(query) != normalized_sql(EXPECTED_QUERY):
        raise RuntimeError(
            "The agent changed the prescribed SQL query.\n"
            f"Expected: {EXPECTED_QUERY}\n"
            f"Actual:   {query}"
        )

    if len(tool_responses) != 1:
        raise RuntimeError(
            "Expected exactly one MCP tool response, "
            f"received {len(tool_responses)}."
        )

    if tool_responses[0].get("name") != "run_query":
        raise RuntimeError(
            "Unexpected MCP tool response name: "
            f"{tool_responses[0].get('name')!r}"
        )

    response_text = json.dumps(
        tool_responses[0].get("response"),
        ensure_ascii=False,
        sort_keys=True,
    )

    required_response_markers = {
        EVENT_ID,
        DEDUPLICATION_KEY,
        EXPECTED_EVENT_NAME,
        EXPECTED_PAYLOAD_STATE,
        "system_truth",
        "canonflow-cloud-run-validation",
        "manual-smoke-test",
    }

    missing_response_markers = sorted(
        marker
        for marker in required_response_markers
        if marker not in response_text
    )

    if missing_response_markers:
        raise RuntimeError(
            "MCP response is missing expected event markers: "
            f"{missing_response_markers}"
        )

    if not final_responses:
        raise RuntimeError(
            "The agent produced no final textual response."
        )

    final_text = final_responses[-1]

    required_final_markers = {
        EVENT_ID,
        DEDUPLICATION_KEY,
        EXPECTED_EVENT_NAME,
        "system_truth",
    }

    missing_final_markers = sorted(
        marker
        for marker in required_final_markers
        if marker not in final_text
    )

    if missing_final_markers:
        raise RuntimeError(
            "Final agent response is missing expected markers: "
            f"{missing_final_markers}"
        )


async def execute(result_path: Path) -> None:
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        state={
            "workflow": "event_ledger_readonly_validation",
            "read_only": True,
            "event_id": EVENT_ID,
            "deduplication_key": DEDUPLICATION_KEY,
        },
    )

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    message = types.Content(
        role="user",
        parts=[types.Part(text=PROMPT)],
    )

    tool_calls: list[dict[str, Any]] = []
    tool_responses: list[dict[str, Any]] = []
    final_responses: list[str] = []
    model_errors: list[dict[str, str]] = []
    event_count = 0

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=message,
    ):
        event_count += 1
        collect_activity(
            event=event,
            tool_calls=tool_calls,
            tool_responses=tool_responses,
            final_responses=final_responses,
            model_errors=model_errors,
        )

    validate_trace(
        tool_calls=tool_calls,
        tool_responses=tool_responses,
        final_responses=final_responses,
        model_errors=model_errors,
    )

    result = {
        "schema_version": "1.0",
        "status": "success",
        "read_only": True,
        "app_name": APP_NAME,
        "agent_name": root_agent.name,
        "model": str(root_agent.model),
        "run_id": str(uuid.uuid4()),
        "session_id": session.id,
        "event_count": event_count,
        "target": {
            "event_id": EVENT_ID,
            "deduplication_key": DEDUPLICATION_KEY,
        },
        "tool_call_count": len(tool_calls),
        "tool_response_count": len(tool_responses),
        "tool_calls": tool_calls,
        "tool_responses": tool_responses,
        "final_response": final_responses[-1],
        "model_errors": model_errors,
    }

    result_path.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Agent           : {root_agent.name}")
    print(f"Model           : {root_agent.model}")
    print(f"Session ID      : {session.id}")
    print(f"ADK events      : {event_count}")
    print(f"Tool calls      : {len(tool_calls)}")
    print(f"Tool responses  : {len(tool_responses)}")
    print(f"Tool name       : {tool_calls[0]['name']}")
    print(f"Remote event    : {EVENT_ID}")
    print(f"Result          : {result_path}")
    print("ADK READ-ONLY EVENT LEDGER VERIFICATION: SUCCESS")


def main() -> int:
    if len(sys.argv) != 2:
        print(
            f"Usage: {Path(sys.argv[0]).name} RESULT.json",
            file=sys.stderr,
        )
        return 2

    result_path = Path(sys.argv[1]).resolve()

    if result_path.exists():
        print(
            f"Refusing to overwrite existing result: {result_path}",
            file=sys.stderr,
        )
        return 2

    try:
        asyncio.run(execute(result_path))
    except KeyboardInterrupt:
        print("ERROR: ADK verification interrupted.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
