from __future__ import annotations

import re
from collections import defaultdict, deque
from typing import Any, Iterable

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
    | \bSETTINGS\b
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
    "context_assets",
    "context_authorizations",
    "context_gate_runs",
    "context_records",
    "context_retrieval_traces",
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
    """Remove comments and quoted text for lexical operation checks."""
    output: list[str] = []
    index = 0
    state = "normal"

    while index < len(sql):
        char = sql[index]
        next_char = (
            sql[index + 1]
            if index + 1 < len(sql)
            else ""
        )

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

            output.append(" ")

            if char == "'":
                state = "normal"

            index += 1
            continue

        if state == "double_quote":
            output.append(" ")

            if char == '"':
                state = "normal"

            index += 1
            continue

        if state == "backtick":
            output.append(" ")

            if char == "`":
                state = "normal"

            index += 1

    return "".join(output)


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "status": "blocked",
        "error": "CANONFLOW_READ_ONLY_POLICY",
        "reason": reason,
    }


def _parse_single_statement(sql: str) -> exp.Expression:
    try:
        statements = [
            statement
            for statement in parse(
                sql,
                read="clickhouse",
            )
            if statement is not None
        ]
    except ParseError as exc:
        raise ValueError(
            f"Unable to parse ClickHouse SQL: {exc}"
        ) from exc

    if len(statements) != 1:
        raise ValueError(
            "Exactly one SQL statement is required."
        )

    return statements[0]


def _nearest_select(
    node: exp.Expression,
) -> exp.Select | None:
    current = node.parent

    while current is not None:
        if isinstance(current, exp.Select):
            return current

        current = current.parent

    return None


def _identifier_name(value: Any) -> str:
    if value is None:
        return ""

    name = getattr(value, "name", None)

    if isinstance(name, str):
        return name.strip('`"').lower()

    return str(value).strip('`"').lower()


def _table_name(table: exp.Table) -> str:
    return _identifier_name(table.this)


def _table_database(table: exp.Table) -> str:
    return _identifier_name(table.args.get("db"))


def _table_alias(table: exp.Table) -> str:
    alias = str(table.alias_or_name or "").strip('`"').lower()

    if alias:
        return alias

    return _table_name(table)


def _is_table_function(table: exp.Table) -> bool:
    return not isinstance(table.this, exp.Identifier)


def _direct_tables(select: exp.Select) -> list[exp.Table]:
    return [
        table
        for table in select.find_all(exp.Table)
        if _nearest_select(table) is select
    ]


def _literal_text(
    expression: exp.Expression,
) -> str | None:
    current = expression

    while isinstance(
        current,
        (exp.Paren, exp.Cast, exp.TryCast),
    ):
        current = current.this

    if isinstance(current, exp.Literal):
        if current.is_string:
            return str(current.this)

        return None

    if isinstance(current, exp.Func):
        if isinstance(current, exp.Anonymous):
            function_name = str(
                current.name
                or current.this
                or ""
            ).upper()
            arguments = list(current.expressions)
        else:
            function_name = str(
                current.sql_name()
            ).upper()
            arguments = list(current.iter_expressions())

        if function_name != "TOUUID":
            return None

        if len(arguments) != 1:
            return None

        return _literal_text(arguments[0])

    return None


def _column_identity(
    expression: exp.Expression,
) -> tuple[str, str] | None:
    current = expression

    while isinstance(current, exp.Paren):
        current = current.this

    if not isinstance(current, exp.Column):
        return None

    column_name = current.name.strip('`"').lower()
    table_alias = current.table.strip('`"').lower()

    return table_alias, column_name


def _has_disjunctive_ancestor(
    node: exp.Expression,
    select: exp.Select,
) -> bool:
    current = node.parent

    while current is not None and current is not select:
        if isinstance(current, (exp.Or, exp.Not)):
            return True

        current = current.parent

    return False


def _inside_filter(
    node: exp.Expression,
    select: exp.Select,
) -> bool:
    current = node.parent

    while current is not None and current is not select:
        if isinstance(current, exp.Where):
            return True

        if str(getattr(current, "key", "")).lower() == "prewhere":
            return True

        current = current.parent

    return False


def _inside_filter_or_join(
    node: exp.Expression,
    select: exp.Select,
) -> bool:
    current = node.parent

    while current is not None and current is not select:
        if isinstance(current, (exp.Where, exp.Join)):
            return True

        if str(getattr(current, "key", "")).lower() == "prewhere":
            return True

        current = current.parent

    return False


def _direct_equalities(
    select: exp.Select,
) -> Iterable[exp.EQ]:
    for equality in select.find_all(exp.EQ):
        if _nearest_select(equality) is select:
            yield equality


def _resolved_aliases(
    *,
    alias: str,
    relevant_aliases: set[str],
) -> set[str]:
    if alias:
        return (
            {alias}
            if alias in relevant_aliases
            else set()
        )

    if len(relevant_aliases) == 1:
        return set(relevant_aliases)

    return set()


def _scope_graph(
    *,
    select: exp.Select,
    relevant_aliases: set[str],
    scope_column: str,
    scope_value: str,
    value_aliases: set[str] | None = None,
) -> tuple[set[str], dict[str, set[str]]]:
    seeds: set[str] = set()
    edges: dict[str, set[str]] = defaultdict(set)

    for equality in _direct_equalities(select):
        if _has_disjunctive_ancestor(
            equality,
            select,
        ):
            continue

        left_column = _column_identity(equality.left)
        right_column = _column_identity(equality.right)

        if (
            left_column is not None
            and right_column is not None
            and _inside_filter_or_join(equality, select)
        ):
            left_alias, left_name = left_column
            right_alias, right_name = right_column

            if (
                left_name == scope_column
                and right_name == scope_column
                and left_alias in relevant_aliases
                and right_alias in relevant_aliases
            ):
                edges[left_alias].add(right_alias)
                edges[right_alias].add(left_alias)

        if not _inside_filter(equality, select):
            continue

        comparisons = (
            (equality.left, equality.right),
            (equality.right, equality.left),
        )

        for column_expression, value_expression in comparisons:
            column = _column_identity(
                column_expression
            )

            if column is None:
                continue

            alias, column_name = column

            if column_name != scope_column:
                continue

            literal = _literal_text(
                value_expression
            )

            if literal != scope_value:
                continue

            candidate_aliases = _resolved_aliases(
                alias=alias,
                relevant_aliases=relevant_aliases,
            )

            if value_aliases is not None:
                candidate_aliases &= value_aliases

            seeds.update(candidate_aliases)

    return seeds, edges


def _reachable_aliases(
    seeds: set[str],
    edges: dict[str, set[str]],
) -> set[str]:
    reached = set(seeds)
    queue = deque(seeds)

    while queue:
        alias = queue.popleft()

        for neighbor in edges.get(alias, set()):
            if neighbor not in reached:
                reached.add(neighbor)
                queue.append(neighbor)

    return reached


def _validate_select_scope(
    select: exp.Select,
) -> None:
    tables = _direct_tables(select)

    aliases: dict[str, str] = {}

    for table in tables:
        if _is_table_function(table):
            raise ValueError(
                "ClickHouse table functions are not permitted."
            )

        database = _table_database(table)

        if database and database not in ALLOWED_DATABASES:
            raise ValueError(
                "Queries may access only canonflow or approved "
                "system metadata. "
                f"Disallowed database: {database!r}."
            )

        alias = _table_alias(table)
        name = _table_name(table)

        if alias in aliases and aliases[alias] != name:
            raise ValueError(
                f"Ambiguous table alias: {alias!r}."
            )

        aliases[alias] = name

    relevant_names = set(PROJECT_TABLES) | set(CONTRACT_TABLES)

    if any(
        name in relevant_names
        for name in aliases.values()
    ):
        for join in select.find_all(exp.Join):
            if _nearest_select(join) is not select:
                continue

            side = str(
                join.args.get("side") or ""
            ).upper()
            kind = str(
                join.args.get("kind") or ""
            ).upper()

            if side in {"LEFT", "RIGHT", "FULL"} or kind == "FULL":
                raise ValueError(
                    "Outer joins over scoped CanonFlow data are "
                    "not permitted by the read-only policy."
                )

    project_aliases = {
        alias
        for alias, name in aliases.items()
        if name in PROJECT_TABLES
    }

    if project_aliases:
        project_seeds, project_edges = _scope_graph(
            select=select,
            relevant_aliases=project_aliases,
            scope_column="project_id",
            scope_value=PROJECT_ID,
        )

        project_table_aliases = {
            alias
            for alias, name in aliases.items()
            if name == "projects"
        }

        slug_seeds, _ = _scope_graph(
            select=select,
            relevant_aliases=project_aliases,
            scope_column="slug",
            scope_value=PROJECT_SLUG,
            value_aliases=project_table_aliases,
        )

        reached = _reachable_aliases(
            project_seeds | slug_seeds,
            project_edges,
        )

        unscoped = sorted(
            project_aliases - reached
        )

        if unscoped:
            raise ValueError(
                "Every project-scoped table must be constrained "
                "through the approved project_id or project slug. "
                f"Unscoped aliases: {unscoped}."
            )

    contract_aliases = {
        alias
        for alias, name in aliases.items()
        if name in CONTRACT_TABLES
    }

    if contract_aliases:
        contract_seeds, contract_edges = _scope_graph(
            select=select,
            relevant_aliases=contract_aliases,
            scope_column="contract_id",
            scope_value=CONTRACT_ID,
        )

        reached = _reachable_aliases(
            contract_seeds,
            contract_edges,
        )

        unscoped = sorted(
            contract_aliases - reached
        )

        if unscoped:
            raise ValueError(
                "Every contract-scoped table must be constrained "
                "through the approved contract_id. "
                f"Unscoped aliases: {unscoped}."
            )


def _validate_statement(
    statement: exp.Expression,
) -> None:
    for table in statement.find_all(exp.Table):
        if _is_table_function(table):
            raise ValueError(
                "ClickHouse table functions are not permitted."
            )

        database = _table_database(table)

        if database and database not in ALLOWED_DATABASES:
            raise ValueError(
                "Queries may access only canonflow or approved "
                "system metadata. "
                f"Disallowed database: {database!r}."
            )

    for select in statement.find_all(exp.Select):
        _validate_select_scope(select)


def enforce_read_only_clickhouse(
    tool: Any,
    args: dict[str, Any],
    tool_context: Any,
) -> dict[str, Any] | None:
    """Enforce the CanonFlow read-only and exact-scope MCP policy."""
    del tool_context

    tool_name = getattr(tool, "name", "")

    if tool_name == "list_databases":
        return None

    if tool_name == "list_tables":
        database = args.get("database")

        if not isinstance(database, str) or not database.strip():
            return _blocked(
                "list_tables requires a database name."
            )

        normalized_database = database.strip('`"').lower()

        if normalized_database not in ALLOWED_DATABASES:
            return _blocked(
                "list_tables may access only canonflow or "
                "approved system metadata."
            )

        return None

    if tool_name != "run_query":
        return None

    query = args.get("query")

    if not isinstance(query, str) or not query.strip():
        return _blocked(
            "run_query requires a non-empty SQL query."
        )

    sanitized = _sanitize_sql(query).strip()

    if not sanitized:
        return _blocked(
            "The SQL query is empty after normalization."
        )

    without_trailing_semicolon = (
        sanitized.rstrip().removesuffix(";").rstrip()
    )

    if ";" in without_trailing_semicolon:
        return _blocked(
            "Multiple SQL statements are not allowed."
        )

    first_match = re.match(
        r"([A-Za-z]+)",
        without_trailing_semicolon,
    )

    if not first_match:
        return _blocked(
            "Unable to determine the SQL statement type."
        )

    statement_type = first_match.group(1).upper()

    if statement_type not in READ_ONLY_PREFIXES:
        return _blocked(
            f"SQL statement type {statement_type!r} "
            "is not read-only."
        )

    blocked_match = BLOCKED_SQL.search(
        without_trailing_semicolon
    )

    if blocked_match:
        return _blocked(
            "The query contains a prohibited SQL operation: "
            f"{blocked_match.group(0)!r}."
        )

    try:
        statement = _parse_single_statement(query)
        _validate_statement(statement)
    except ValueError as exc:
        return _blocked(str(exc))

    return None
