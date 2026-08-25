from __future__ import annotations

from dataclasses import dataclass

from canonflow_agent.policy import enforce_read_only_clickhouse


PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"


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


def main() -> None:
    tests = [
        test_allows_scoped_select,
        test_allows_project_slug_lookup,
        test_allows_system_metadata,
        test_blocks_insert,
        test_blocks_unscoped_project_query,
        test_blocks_multiple_statements,
        test_ignores_blocked_word_inside_literal,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print(f"\nPolicy tests passed: {len(tests)}")
    print("CANONFLOW READ-ONLY POLICY: OK")


if __name__ == "__main__":
    main()
