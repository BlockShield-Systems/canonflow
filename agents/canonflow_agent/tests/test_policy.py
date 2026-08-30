from __future__ import annotations

from dataclasses import dataclass

from canonflow_agent.policy import (
    CONTRACT_ID,
    PROJECT_ID,
    enforce_read_only_clickhouse,
)


@dataclass
class DummyTool:
    name: str


def evaluate(
    query: str,
):
    return enforce_read_only_clickhouse(
        tool=DummyTool(name="run_query"),
        args={"query": query},
        tool_context=None,
    )


def evaluate_tool(
    name: str,
    args: dict,
):
    return enforce_read_only_clickhouse(
        tool=DummyTool(name=name),
        args=args,
        tool_context=None,
    )


def assert_allowed(query: str) -> None:
    result = evaluate(query)
    assert result is None, result


def assert_blocked(query: str) -> None:
    result = evaluate(query)
    assert result is not None
    assert result["status"] == "blocked"
    assert result["error"] == "CANONFLOW_READ_ONLY_POLICY"


def test_allows_scoped_select() -> None:
    assert_allowed(
        f"""
        SELECT chunk_id, locator, content
        FROM canonflow.source_chunks
        WHERE project_id = toUUID('{PROJECT_ID}')
          AND indexable = true
        LIMIT 10
        """
    )


def test_allows_project_slug_lookup() -> None:
    assert_allowed(
        """
        SELECT project_id, slug, title
        FROM canonflow.projects FINAL
        WHERE slug = 'yd-when-paradise-glitches'
        LIMIT 1
        """
    )


def test_allows_system_metadata() -> None:
    assert_allowed(
        """
        SELECT name
        FROM system.tables
        WHERE database = 'canonflow'
        ORDER BY name
        """
    )


def test_allows_information_schema_metadata() -> None:
    assert_allowed(
        """
        SELECT table_schema, table_name, column_name
        FROM information_schema.columns
        WHERE table_schema = 'canonflow'
        ORDER BY table_name, ordinal_position
        """
    )


def test_allows_scoped_inner_join() -> None:
    assert_allowed(
        f"""
        SELECT c.chunk_id, d.source_path
        FROM canonflow.source_chunks AS c
        INNER JOIN canonflow.source_documents AS d
            ON d.document_id = c.document_id
           AND d.project_id = c.project_id
        WHERE c.project_id = toUUID('{PROJECT_ID}')
          AND c.indexable = true
        LIMIT 10
        """
    )


def test_allows_contract_scope() -> None:
    assert_allowed(
        f"""
        SELECT event_name, event_version
        FROM canonflow.event_definitions
        WHERE contract_id = toUUID('{CONTRACT_ID}')
        ORDER BY event_name
        """
    )


def test_allows_blocked_word_inside_literal() -> None:
    assert_allowed(
        f"""
        SELECT count()
        FROM canonflow.source_chunks
        WHERE project_id = toUUID('{PROJECT_ID}')
          AND content ILIKE '%DELETE%'
        """
    )


def test_blocks_insert() -> None:
    assert_blocked(
        f"""
        INSERT INTO canonflow.agent_runs
        (run_id, project_id)
        VALUES (generateUUIDv4(), toUUID('{PROJECT_ID}'))
        """
    )


def test_blocks_multiple_statements() -> None:
    assert_blocked(
        f"""
        SELECT count()
        FROM canonflow.source_chunks
        WHERE project_id = toUUID('{PROJECT_ID}');
        DROP TABLE canonflow.source_chunks;
        """
    )


def test_blocks_unscoped_project_query() -> None:
    assert_blocked(
        """
        SELECT chunk_id, content
        FROM canonflow.source_chunks
        LIMIT 10
        """
    )


def test_blocks_uuid_as_meaningless_literal() -> None:
    assert_blocked(
        f"""
        SELECT
            '{PROJECT_ID}' AS unrelated_literal,
            chunk_id,
            content
        FROM canonflow.source_chunks
        LIMIT 10
        """
    )


def test_blocks_uuid_in_unrelated_predicate() -> None:
    assert_blocked(
        f"""
        SELECT chunk_id, content
        FROM canonflow.source_chunks
        WHERE content != '{PROJECT_ID}'
        LIMIT 10
        """
    )


def test_blocks_scope_inside_or() -> None:
    assert_blocked(
        f"""
        SELECT chunk_id, content
        FROM canonflow.source_chunks
        WHERE project_id = toUUID('{PROJECT_ID}')
           OR indexable = true
        LIMIT 10
        """
    )


def test_blocks_scope_inside_not() -> None:
    assert_blocked(
        f"""
        SELECT chunk_id, content
        FROM canonflow.source_chunks
        WHERE NOT (
            project_id != toUUID('{PROJECT_ID}')
        )
        LIMIT 10
        """
    )


def test_blocks_unscoped_union_branch() -> None:
    assert_blocked(
        f"""
        SELECT chunk_id
        FROM canonflow.source_chunks
        WHERE project_id = toUUID('{PROJECT_ID}')
        UNION ALL
        SELECT chunk_id
        FROM canonflow.source_chunks
        """
    )


def test_blocks_unscoped_join_alias() -> None:
    assert_blocked(
        f"""
        SELECT c.chunk_id, d.source_path
        FROM canonflow.source_chunks AS c
        CROSS JOIN canonflow.source_documents AS d
        WHERE c.project_id = toUUID('{PROJECT_ID}')
        LIMIT 10
        """
    )


def test_blocks_outer_join_for_scoped_data() -> None:
    assert_blocked(
        f"""
        SELECT c.chunk_id, d.source_path
        FROM canonflow.source_chunks AS c
        LEFT JOIN canonflow.source_documents AS d
            ON d.project_id = c.project_id
        WHERE c.project_id = toUUID('{PROJECT_ID}')
        LIMIT 10
        """
    )


def test_blocks_external_database() -> None:
    assert_blocked(
        f"""
        SELECT chunk_id
        FROM external_database.source_chunks
        WHERE project_id = toUUID('{PROJECT_ID}')
        """
    )


def test_blocks_url_table_function() -> None:
    assert_blocked(
        """
        SELECT *
        FROM url(
            'https://example.invalid/data.csv',
            'CSV'
        )
        """
    )


def test_blocks_file_table_function() -> None:
    assert_blocked(
        """
        SELECT *
        FROM file('/tmp/data.csv', CSV)
        """
    )


def test_blocks_remote_table_function() -> None:
    assert_blocked(
        """
        SELECT *
        FROM remote(
            '127.0.0.1',
            'default',
            'table'
        )
        """
    )


def test_blocks_query_settings() -> None:
    assert_blocked(
        """
        SELECT name
        FROM system.tables
        SETTINGS readonly = 0
        """
    )


def test_blocks_into_outfile() -> None:
    assert_blocked(
        """
        SELECT name
        FROM system.tables
        INTO OUTFILE '/tmp/export.tsv'
        """
    )


def test_allows_list_tables_for_canonflow() -> None:
    result = evaluate_tool(
        "list_tables",
        {
            "database": "canonflow",
            "include_detailed_columns": False,
        },
    )

    assert result is None


def test_blocks_list_tables_for_external_database() -> None:
    result = evaluate_tool(
        "list_tables",
        {
            "database": "external_database",
        },
    )

    assert result is not None
    assert result["status"] == "blocked"


def test_blocks_unscoped_contract_query() -> None:
    assert_blocked(
        """
        SELECT event_name, event_version
        FROM canonflow.event_definitions
        ORDER BY event_name
        """
    )



def test_allows_scoped_context_memory_tables() -> None:
    tables = [
        "context_assets",
        "context_authorizations",
        "context_gate_runs",
        "context_records",
        "context_retrieval_traces",
    ]

    for table in tables:
        assert_allowed(
            f"""
            SELECT count()
            FROM canonflow.{table}
            WHERE project_id = toUUID('{PROJECT_ID}')
            """
        )


def test_blocks_unscoped_context_memory_tables() -> None:
    tables = [
        "context_assets",
        "context_authorizations",
        "context_gate_runs",
        "context_records",
        "context_retrieval_traces",
    ]

    for table in tables:
        assert_blocked(
            f"""
            SELECT count()
            FROM canonflow.{table}
            """
        )


def main() -> None:
    tests = [
        test_allows_scoped_select,
        test_allows_project_slug_lookup,
        test_allows_system_metadata,
        test_allows_information_schema_metadata,
        test_allows_scoped_inner_join,
        test_allows_contract_scope,
        test_allows_scoped_context_memory_tables,
        test_blocks_unscoped_context_memory_tables,
        test_allows_blocked_word_inside_literal,
        test_blocks_insert,
        test_blocks_multiple_statements,
        test_blocks_unscoped_project_query,
        test_blocks_uuid_as_meaningless_literal,
        test_blocks_uuid_in_unrelated_predicate,
        test_blocks_scope_inside_or,
        test_blocks_scope_inside_not,
        test_blocks_unscoped_union_branch,
        test_blocks_unscoped_join_alias,
        test_blocks_outer_join_for_scoped_data,
        test_blocks_external_database,
        test_blocks_url_table_function,
        test_blocks_file_table_function,
        test_blocks_remote_table_function,
        test_blocks_query_settings,
        test_blocks_into_outfile,
        test_allows_list_tables_for_canonflow,
        test_blocks_list_tables_for_external_database,
        test_blocks_unscoped_contract_query,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print(f"\nPolicy tests passed: {len(tests)}")
    print("CANONFLOW AST READ-ONLY POLICY: OK")


if __name__ == "__main__":
    main()
