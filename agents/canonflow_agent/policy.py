from __future__ import annotations

import re
from typing import Any

from sqlglot import exp, parse
from sqlglot.errors import ParseError


PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
PROJECT_SLUG = "yd-when-paradise-glitches"
CONTRACT_ID = "e17828fb-49b1-5df0-9c45-385a68f5f9d1"

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

ALLOWED_DATABASES = {
    "canonflow",
    "system",
    "information_schema",
}

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
    "event_ingest_attempts",
    "events",
    "mv_event_ingest_attempts_to_events",
    "v_events_current",
    "v_system_truth",
    "v_character_knowledge",
    "v_timeline_binding_validation",
}

CONTRACT_TABLES = {
    "event_definitions",
    "v_event_contract_violations",
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


def _referenced_databases(sql: str) -> set[str]:
    """
    Parse ClickHouse SQL and return actual database qualifiers from table
    references.

    Column qualifiers such as ``c.chunk_id`` are represented as column/table
    aliases by the AST and are therefore not mistaken for databases.
    """
    try:
        statements = parse(sql, read="clickhouse")
    except ParseError as exc:
        raise ValueError(f"Unable to parse ClickHouse SQL: {exc}") from exc

    statements = [
        statement
        for statement in statements
        if statement is not None
    ]

    if len(statements) != 1:
        raise ValueError("Exactly one SQL statement is required.")

    databases: set[str] = set()

    for table in statements[0].find_all(exp.Table):
        database = table.args.get("db")

        if database is None:
            continue

        database_name = getattr(database, "name", None)

        if not database_name:
            database_name = str(database)

        normalized = database_name.strip('`"').lower()

        if normalized:
            databases.add(normalized)

    return databases


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

    try:
        referenced_databases = _referenced_databases(query)
    except ValueError as exc:
        return _blocked(str(exc))

    disallowed_databases = referenced_databases - ALLOWED_DATABASES

    if disallowed_databases:
        return _blocked(
            "Queries may access only canonflow or approved system metadata. "
            f"Disallowed databases: {sorted(disallowed_databases)}."
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

    touched_contract_tables = {
        table
        for table in CONTRACT_TABLES
        if re.search(
            rf"\b{re.escape(table.upper())}\b",
            normalized_upper,
        )
    }

    if touched_contract_tables:
        has_contract_id = CONTRACT_ID.lower() in query.lower()

        if not has_contract_id:
            return _blocked(
                "Contract-scoped queries must contain the approved "
                f"contract_id. Tables: {sorted(touched_contract_tables)}."
            )

    return None
