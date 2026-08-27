from __future__ import annotations

from dataclasses import dataclass

from canonflow_agent.policy import enforce_read_only_clickhouse


PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
CONTRACT_ID = "e17828fb-49b1-5df0-9c45-385a68f5f9d1"


@dataclass
class DummyTool:
    name: str


def evaluate(query: str):
    return enforce_read_only_clickhouse(
        tool=DummyTool(name="run_query"),
        args={"query": query},
        tool_context=None,
    )


def test_allows_scoped_select() -> None:
    result = evaluate(
        f"""
        SELECT chunk_id, locator, content
        FROM canonflow.source_chunks
        WHERE project_id = toUUID('{PROJECT_ID}')
          AND indexable = true
        LIMIT 10
        """
    )

    assert result is None


def test_allows_project_slug_lookup() -> None:
    result = evaluate(
        """
        SELECT project_id, slug, title
        FROM canonflow.projects FINAL
        WHERE slug = 'yd-when-paradise-glitches'
        LIMIT 1
        """
    )

    assert result is None


def test_allows_system_metadata() -> None:
    result = evaluate(
        """
        SELECT name
        FROM system.tables
        WHERE database = 'canonflow'
        ORDER BY name
        """
    )

    assert result is None


def test_allows_aliased_project_join() -> None:
    result = evaluate(
        f"""
        SELECT
            c.chunk_id,
            c.locator,
            d.source_path
        FROM canonflow.source_chunks AS c
        INNER JOIN canonflow.source_documents AS d
            ON d.document_id = c.document_id
           AND d.project_id = c.project_id
        WHERE c.project_id = toUUID('{PROJECT_ID}')
          AND c.indexable = true
        ORDER BY d.source_path, c.locator
        LIMIT 10
        """
    )

    assert result is None


def test_allows_information_schema_metadata() -> None:
    result = evaluate(
        """
        SELECT
            table_schema,
            table_name,
            column_name
        FROM information_schema.columns
        WHERE table_schema = 'canonflow'
        ORDER BY table_name, ordinal_position
        """
    )

    assert result is None


def test_blocks_external_database_with_alias() -> None:
    result = evaluate(
        f"""
        SELECT e.chunk_id
        FROM external_database.source_chunks AS e
        WHERE e.project_id = toUUID('{PROJECT_ID}')
        LIMIT 10
        """
    )

    assert result is not None
    assert result["status"] == "blocked"
    assert "external_database" in result["reason"]


def test_blocks_insert() -> None:
    result = evaluate(
        f"""
        INSERT INTO canonflow.continuity_findings
        (finding_id, project_id)
        VALUES (generateUUIDv4(), toUUID('{PROJECT_ID}'))
        """
    )

    assert result is not None
    assert result["status"] == "blocked"


def test_blocks_unscoped_project_query() -> None:
    result = evaluate(
        """
        SELECT chunk_id, content
        FROM canonflow.source_chunks
        LIMIT 10
        """
    )

    assert result is not None
    assert result["status"] == "blocked"


def test_blocks_multiple_statements() -> None:
    result = evaluate(
        f"""
        SELECT count()
        FROM canonflow.source_chunks
        WHERE project_id = toUUID('{PROJECT_ID}');
        DROP TABLE canonflow.source_chunks;
        """
    )

    assert result is not None
    assert result["status"] == "blocked"


def test_ignores_blocked_word_inside_literal() -> None:
    result = evaluate(
        f"""
        SELECT count()
        FROM canonflow.source_chunks
        WHERE project_id = toUUID('{PROJECT_ID}')
          AND content ILIKE '%DELETE%'
        """
    )

    assert result is None



def test_allows_project_scoped_event_query() -> None:
    result = evaluate(
        f"""
        SELECT
            event_id,
            event_name,
            payload_json
        FROM canonflow.v_events_current
        WHERE project_id = toUUID('{PROJECT_ID}')
        LIMIT 10
        """
    )

    assert result is None


def test_blocks_unscoped_event_query() -> None:
    result = evaluate(
        """
        SELECT
            event_id,
            event_name,
            payload_json
        FROM canonflow.v_events_current
        LIMIT 10
        """
    )

    assert result is not None
    assert result["status"] == "blocked"
    assert "Project-scoped" in result["reason"]


def test_allows_contract_scoped_definition_query() -> None:
    result = evaluate(
        f"""
        SELECT
            event_name,
            event_version,
            truth_scope
        FROM canonflow.event_definitions
        WHERE contract_id = toUUID('{CONTRACT_ID}')
        ORDER BY event_name, event_version
        """
    )

    assert result is None


def test_blocks_unscoped_contract_violation_query() -> None:
    result = evaluate(
        """
        SELECT
            event_id,
            event_name,
            contract_status
        FROM canonflow.v_event_contract_violations
        LIMIT 10
        """
    )

    assert result is not None
    assert result["status"] == "blocked"
    assert "Contract-scoped" in result["reason"]


def main() -> None:
    tests = [
        test_allows_scoped_select,
        test_allows_project_slug_lookup,
        test_allows_system_metadata,
        test_allows_aliased_project_join,
        test_allows_information_schema_metadata,
        test_blocks_external_database_with_alias,
        test_blocks_insert,
        test_blocks_unscoped_project_query,
        test_blocks_multiple_statements,
        test_ignores_blocked_word_inside_literal,
        test_allows_project_scoped_event_query,
        test_blocks_unscoped_event_query,
        test_allows_contract_scoped_definition_query,
        test_blocks_unscoped_contract_violation_query,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print(f"\nPolicy tests passed: {len(tests)}")
    print("CANONFLOW READ-ONLY POLICY: OK")


if __name__ == "__main__":
    main()
