#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from canonflow_agent import root_agent


APP_NAME = "canonflow-source-audit"
USER_ID = "demian"
PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"

NO_CONTENT_ERROR_CODE = "MODEL_RETURNED_NO_CONTENT"

RECOVERY_PROMPT = """
The preceding source-audit turn completed all requested read-only tool calls,
and all tool responses are already present in this same session, but no final
textual response was produced.

Continue from the existing session context. Do not call any tools again.
Using only the source evidence, metadata, approved canon decisions, and tool
responses already available in this session, produce the complete final
Markdown source-audit report now.

The report must follow every requirement and required section from the
original source-audit request. Clearly distinguish verified source facts,
approved canon decisions, contradictions, unresolved questions, and proposed
findings. Do not invent canon and do not make autonomous canon decisions.
Return only the final Markdown report.
""".strip()

SENSITIVE_KEYS = {
    "authorization",
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_token",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}

        for key, item in value.items():
            normalized = str(key).lower()

            if any(secret in normalized for secret in SENSITIVE_KEYS):
                result[key] = "<REDACTED>"
            else:
                result[key] = redact(item)

        return result

    if isinstance(value, list):
        return [redact(item) for item in value]

    return value


def event_as_dict(event: Any) -> dict[str, Any]:
    if hasattr(event, "model_dump"):
        value = event.model_dump(
            mode="json",
            exclude_none=True,
        )

        if isinstance(value, dict):
            return redact(value)

    return {
        "event": redact(str(event)),
    }


def content_text(content: Any) -> str:
    if content is None:
        return ""

    parts = getattr(content, "parts", None) or []
    texts = []

    for part in parts:
        text = getattr(part, "text", None)

        if text:
            texts.append(text)

    return "\n".join(texts).strip()


def collect_tool_activity(
    event: Any,
    tool_calls: list[dict[str, Any]],
    tool_responses: list[dict[str, Any]],
) -> None:
    content = getattr(event, "content", None)

    if content is None:
        return

    for part in getattr(content, "parts", None) or []:
        function_call = getattr(part, "function_call", None)

        if function_call is not None:
            tool_calls.append(
                {
                    "id": getattr(function_call, "id", None),
                    "name": getattr(function_call, "name", None),
                    "args": redact(
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
                    "response": redact(
                        getattr(function_response, "response", None)
                    ),
                }
            )


async def execute(args: argparse.Namespace) -> int:
    request_path = args.request.resolve()
    output_dir = args.output_dir.resolve()

    if not request_path.is_file():
        raise RuntimeError(f"Request file not found: {request_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    events_path = output_dir / "07-source-audit-events.jsonl"
    report_path = output_dir / "08-source-audit-report.md"
    summary_path = output_dir / "09-source-audit-summary.json"

    request_text = request_path.read_text(encoding="utf-8")
    request_hash = sha256_file(request_path)

    run_id = str(uuid.uuid4())
    started_at = utc_now()

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        state={
            "workflow": "source_audit",
            "project_id": PROJECT_ID,
            "read_only": True,
            "run_id": run_id,
        },
    )

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    message = types.Content(
        role="user",
        parts=[types.Part(text=request_text)],
    )

    event_count = 0
    final_responses: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    tool_responses: list[dict[str, Any]] = []
    model_errors: list[dict[str, Any]] = []
    recovery_attempted = False
    recovery_succeeded = False

    with events_path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as events_file:

        async def run_turn(
            turn_message: types.Content,
            phase: str,
        ) -> None:
            nonlocal event_count

            async for event in runner.run_async(
                user_id=USER_ID,
                session_id=session.id,
                new_message=turn_message,
            ):
                event_count += 1

                collect_tool_activity(
                    event,
                    tool_calls,
                    tool_responses,
                )

                error_code = getattr(event, "error_code", None)
                error_message = getattr(event, "error_message", None)

                if error_code:
                    model_errors.append(
                        {
                            "phase": phase,
                            "code": str(error_code),
                            "message": str(error_message or ""),
                        }
                    )

                serialized = event_as_dict(event)
                serialized["canonflow_phase"] = phase

                events_file.write(
                    json.dumps(
                        serialized,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
                events_file.flush()

                is_final = getattr(
                    event,
                    "is_final_response",
                    lambda: False,
                )()

                if is_final:
                    response_text = content_text(
                        getattr(event, "content", None)
                    )

                    if response_text:
                        final_responses.append(response_text)

        await run_turn(
            turn_message=message,
            phase="primary",
        )

        primary_error_code = (
            model_errors[-1]["code"]
            if model_errors
            else None
        )

        eligible_for_recovery = (
            not final_responses
            and primary_error_code == NO_CONTENT_ERROR_CODE
            and len(tool_calls) > 0
            and len(tool_calls) == len(tool_responses)
        )

        if eligible_for_recovery:
            recovery_attempted = True

            recovery_message = types.Content(
                role="user",
                parts=[types.Part(text=RECOVERY_PROMPT)],
            )

            await run_turn(
                turn_message=recovery_message,
                phase="no_content_recovery",
            )

            recovery_succeeded = bool(final_responses)

    completed_at = utc_now()

    if not final_responses:
        last_model_error = (
            model_errors[-1]
            if model_errors
            else None
        )

        raise RuntimeError(
            "The ADK run completed without a final textual response. "
            f"Recovery attempted={recovery_attempted}; "
            f"tool calls={len(tool_calls)}; "
            f"tool responses={len(tool_responses)}; "
            f"last model error={last_model_error!r}."
        )

    report_text = final_responses[-1].strip() + "\n"
    report_path.write_text(
        report_text,
        encoding="utf-8",
    )

    summary = {
        "schema_version": "1.0",
        "workflow": "source_audit",
        "status": "completed",
        "read_only": True,
        "run_id": run_id,
        "project_id": PROJECT_ID,
        "app_name": APP_NAME,
        "agent_name": root_agent.name,
        "model": str(root_agent.model),
        "session_id": session.id,
        "started_at_utc": started_at.isoformat(),
        "completed_at_utc": completed_at.isoformat(),
        "duration_ms": int(
            (completed_at - started_at).total_seconds() * 1000
        ),
        "request_path": str(request_path),
        "request_sha256": request_hash,
        "event_count": event_count,
        "recovery": {
            "attempted": recovery_attempted,
            "trigger": (
                NO_CONTENT_ERROR_CODE
                if recovery_attempted
                else None
            ),
            "succeeded": recovery_succeeded,
        },
        "model_errors": model_errors,
        "tool_call_count": len(tool_calls),
        "tool_response_count": len(tool_responses),
        "tool_calls": tool_calls,
        "events_path": str(events_path),
        "events_sha256": sha256_file(events_path),
        "report_path": str(report_path),
        "report_sha256": sha256_file(report_path),
        "report_character_count": len(report_text),
    }

    summary_path.write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Run ID          : {run_id}")
    print(f"Session ID      : {session.id}")
    print(f"Model           : {root_agent.model}")
    print(f"Events          : {event_count}")
    print(f"Recovery used   : {recovery_attempted}")
    print(f"Recovery success: {recovery_succeeded}")
    print(f"Tool calls      : {len(tool_calls)}")
    print(f"Tool responses  : {len(tool_responses)}")
    print(f"Report chars    : {len(report_text)}")
    print(f"Events evidence : {events_path}")
    print(f"Audit report    : {report_path}")
    print(f"Run summary     : {summary_path}")
    print("GEMINI SOURCE AUDIT RUN: OK")

    return 0


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    try:
        return asyncio.run(execute(args))
    except KeyboardInterrupt:
        print("ERROR: Source audit interrupted.", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
