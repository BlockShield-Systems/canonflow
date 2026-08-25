#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from canonflow_agent.policy import enforce_read_only_clickhouse


class Tool:
    def __init__(self, name: str) -> None:
        self.name = name


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    summary = json.loads(
        args.summary.read_text(encoding="utf-8")
    )
    report = args.report.read_text(encoding="utf-8")

    if summary["status"] != "completed":
        raise RuntimeError("Audit run is not completed.")

    if summary["read_only"] is not True:
        raise RuntimeError("Audit run is not marked read-only.")

    if summary["tool_call_count"] == 0:
        raise RuntimeError("Audit made no MCP tool calls.")

    if summary["tool_call_count"] != summary["tool_response_count"]:
        raise RuntimeError(
            "Tool call and response counts do not match."
        )

    query_count = 0
    policy_failures: list[dict[str, Any]] = []

    for call in summary["tool_calls"]:
        name = call.get("name")

        if name == "run_query":
            query_count += 1
            result = enforce_read_only_clickhouse(
                tool=Tool(name="run_query"),
                args=call.get("args") or {},
                tool_context=None,
            )

            if result is not None:
                policy_failures.append(
                    {
                        "call": call,
                        "policy_result": result,
                    }
                )

    if policy_failures:
        raise RuntimeError(
            "Recorded SQL calls violate the read-only policy:\n"
            + json.dumps(
                policy_failures,
                ensure_ascii=False,
                indent=2,
            )
        )

    if query_count == 0:
        raise RuntimeError("Audit executed no ClickHouse queries.")

    required_sections = [
        "Executive Audit Status",
        "Verified Project Identity",
        "Approved Canon Decisions",
        "Source Coverage Ledger",
        "Document Classification",
        "Canon Inventory",
        "Proposed Continuity Findings",
        "Missing-information Questions",
        "Recommended Next Controlled Workflow",
    ]

    missing_sections = [
        section
        for section in required_sections
        if section.lower() not in report.lower()
    ]

    if missing_sections:
        raise RuntimeError(
            f"Report sections missing: {missing_sections}"
        )

    if len(report.strip()) < 3000:
        raise RuntimeError(
            "Audit report is unexpectedly short."
        )

    print(f'Run ID          : {summary["run_id"]}')
    print(f'Project ID      : {summary["project_id"]}')
    print(f'Tool calls      : {summary["tool_call_count"]}')
    print(f'Read-only SQL   : {query_count}')
    print(f'Policy failures : {len(policy_failures)}')
    print(f'Report chars    : {len(report)}')
    print(f'Missing sections: {len(missing_sections)}')
    print("GEMINI SOURCE AUDIT VALIDATION: OK")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
