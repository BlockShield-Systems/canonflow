from __future__ import annotations

import re
from typing import Any


PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
PROJECT_SLUG = "yd-when-paradise-glitches"

READ_ONLY_PREFIXES = {
    "SELECT",
    "WITH",
    "SHOW",
    "DESCRIBE",
    "DESC",
    "EXPLAIN",
}

BLOCKED_SQL = re.compile(
    r"""
    \b(
        INSERT
        | UPDATE
        | DELETE
        | ALTER
        | CREATE
        | DROP
        | TRUNCATE
        | GRANT
        | REVOKE
        | ATTACH
        | DETACH
        | RENAME
        | OPTIMIZE
        | KILL
        | BACKUP
        | RESTORE
    )\b
    | \bINTO\s+OUTFILE\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

DATABASE_QUALIFIER = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\.",
)

PROJECT_TABLES = {
    "projects",
    "source_documents",
    "source_pages",
    "source_chunks",
    "source_quality_dispositions",
    "canon_decisions",
    "canon_entities",
    "continuity_findings",
    "scenes",
    "shot_specs",
    "media_assets",
    "agent_runs",
    "tool_events",
}


def _sanitize_sql(sql: str) -> str:
    """
    Remove comments and quoted content while preserving SQL structure.

    This intentionally favors false-positive blocking over allowing an
    ambiguous query through to the MCP server.
    """
    output: list[str] = []
    index = 0
    length = len(sql)
    state = "normal"

    while index < length:
        char = sql[index]
        next_char = sql[index + 1] if index + 1 < length else ""

        if state == "normal":
            if char == "-" and next_char == "-":
                output.extend((" ", " "))
                index += 2
                state = "line_comment"
                continue

            if char == "/" and next_char == "*":
                output.extend((" ", " "))
                index += 2
                state = "block_comment"
                continue

            if char == "'":
                output.append(" ")
                index += 1
                state = "single_quote"
                continue

            if char == '"':
                output.append(" ")
                index += 1
                state = "double_quote"
                continue

            if char == "`":
                output.append(" ")
                index += 1
                state = "backtick"
                continue

            output.append(char)
            index += 1
            continue

        if state == "line_comment":
            if char == "\n":
                output.append("\n")
                state = "normal"
            else:
                output.append(" ")

            index += 1
            continue

        if state == "block_comment":
            if char == "*" and next_char == "/":
                output.extend((" ", " "))
                index += 2
                state = "normal"
            else:
                output.append(" ")
                index += 1

            continue

        if state == "single_quote":
            if char == "\\" and next_char:
                output.extend((" ", " "))
                index += 2
                continue

            if char == "'" and next_char == "'":
                output.extend((" ", " "))
                index += 2
                continue

            if char == "'":
                output.append(" ")
                state = "normal"
            else:
                output.append(" ")

            index += 1
            continue

        if state == "double_quote":
            if char == '"':
                output.append(" ")
                state = "normal"
            else:
                output.append(" ")

            index += 1
            continue

        if state == "backtick":
            if char == "`":
                output.append(" ")
                state = "normal"
            else:
                output.append(" ")

            index += 1

    return "".join(output)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "status": "blocked",
        "error": "CANONFLOW_READ_ONLY_POLICY",
        "reason": reason,
    }


def enforce_read_only_clickhouse(
    tool: Any,
    args: dict[str, Any],
    tool_context: Any,
) -> dict[str, Any] | None:
    """
    ADK before_tool_callback for the existing MCP toolset.

    Returning a truthy dictionary prevents the MCP tool from being executed
    and exposes the policy result to the agent as the tool response.
    """
    del tool_context

    tool_name = getattr(tool, "name", "")

    if tool_name != "run_query":
        return None

    query = args.get("query")

    if not isinstance(query, str) or not query.strip():
        return _blocked("run_query requires a non-empty SQL query.")

    sanitized = _sanitize_sql(query).strip()

    if not sanitized:
        return _blocked("The SQL query is empty after normalization.")

    without_trailing_semicolon = sanitized.rstrip().removesuffix(";").rstrip()

    if ";" in without_trailing_semicolon:
        return _blocked("Multiple SQL statements are not allowed.")

    first_match = re.match(r"([A-Za-z]+)", without_trailing_semicolon)

    if not first_match:
        return _blocked("Unable to determine the SQL statement type.")

    statement_type = first_match.group(1).upper()

    if statement_type not in READ_ONLY_PREFIXES:
        return _blocked(
            f"SQL statement type {statement_type!r} is not read-only."
        )

    blocked_match = BLOCKED_SQL.search(without_trailing_semicolon)

    if blocked_match:
        return _blocked(
            "The query contains a prohibited SQL operation: "
            f"{blocked_match.group(0)!r}."
        )

    qualifiers = {
        match.group(1).lower()
        for match in DATABASE_QUALIFIER.finditer(
            without_trailing_semicolon
        )
    }

    disallowed_databases = qualifiers - {"canonflow", "system"}

    if disallowed_databases:
        return _blocked(
            "Queries may access only canonflow or approved system metadata. "
            f"Disallowed qualifiers: {sorted(disallowed_databases)}."
        )

    normalized_upper = without_trailing_semicolon.upper()

    touched_project_tables = {
        table
        for table in PROJECT_TABLES
        if re.search(
            rf"\b{re.escape(table.upper())}\b",
            normalized_upper,
        )
    }

    if touched_project_tables:
        has_project_id = PROJECT_ID.lower() in query.lower()
        has_project_slug = PROJECT_SLUG.lower() in query.lower()

        if not has_project_id and not has_project_slug:
            return _blocked(
                "Project-scoped queries must contain the approved project_id "
                f"or slug. Tables: {sorted(touched_project_tables)}."
            )

    return None
