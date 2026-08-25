#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import clickhouse_connect


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    normalized = value.strip().lower()

    if normalized in {"1", "true", "yes", "on"}:
        return True

    if normalized in {"0", "false", "no", "off"}:
        return False

    raise ValueError(f"Invalid boolean value for {name}: {value}")


def required(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")

    return value


def quote_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Unsafe ClickHouse identifier: {value}")

    return f"`{value}`"


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: migrate_source_intelligence.py OUTPUT_JSON"
        )

    output = Path(sys.argv[1])
    output.parent.mkdir(parents=True, exist_ok=True)

    database = os.getenv("CLICKHOUSE_DATABASE", "canonflow")
    db = quote_identifier(database)

    client = clickhouse_connect.get_client(
        host=required("CLICKHOUSE_HOST"),
        port=int(os.getenv("CLICKHOUSE_PORT", "8443")),
        username=required("CLICKHOUSE_USER"),
        password=required("CLICKHOUSE_PASSWORD"),
        database=database,
        secure=env_bool("CLICKHOUSE_SECURE", True),
        verify=env_bool("CLICKHOUSE_VERIFY", True),
        connect_timeout=int(
            os.getenv("CLICKHOUSE_CONNECT_TIMEOUT", "10")
        ),
        send_receive_timeout=int(
            os.getenv("CLICKHOUSE_SEND_RECEIVE_TIMEOUT", "30")
        ),
    )

    migrations = {
        "source_pages": f"""
            CREATE TABLE IF NOT EXISTS {db}.source_pages
            (
                page_id UUID,
                document_id UUID,
                project_id UUID,
                page_number UInt32,
                content String,
                checksum_sha256 FixedString(64),
                extraction_method LowCardinality(String),
                character_count UInt64,
                visible_character_count UInt64,
                quality LowCardinality(String),
                content_class LowCardinality(String),
                indexable Bool,
                ocr_required Bool,
                metadata_json String,
                extracted_at DateTime64(3, 'UTC')
            )
            ENGINE = MergeTree
            ORDER BY (project_id, document_id, page_number, page_id)
        """,
        "source_chunks": f"""
            CREATE TABLE IF NOT EXISTS {db}.source_chunks
            (
                chunk_id UUID,
                document_id UUID,
                project_id UUID,
                sequence UInt32,
                locator_type LowCardinality(String),
                page_number Nullable(UInt32),
                line_start UInt32,
                line_end UInt32,
                locator String,
                content String,
                checksum_sha256 FixedString(64),
                character_count UInt64,
                indexable Bool,
                metadata_json String,
                created_at DateTime64(3, 'UTC')
            )
            ENGINE = MergeTree
            ORDER BY (
                project_id,
                document_id,
                sequence,
                chunk_id
            )
        """,
        "source_quality_dispositions": f"""
            CREATE TABLE IF NOT EXISTS {db}.source_quality_dispositions
            (
                disposition_id UUID,
                project_id UUID,
                document_id UUID,
                source_path String,
                source_sha256 FixedString(64),
                page_number Nullable(UInt32),
                original_quality LowCardinality(String),
                quality_disposition LowCardinality(String),
                content_class LowCardinality(String),
                indexable Bool,
                ocr_required Bool,
                reason String,
                evidence_json String,
                reviewed_at DateTime64(3, 'UTC')
            )
            ENGINE = MergeTree
            ORDER BY (
                project_id,
                document_id,
                disposition_id
            )
        """,
        "canon_decisions": f"""
            CREATE TABLE IF NOT EXISTS {db}.canon_decisions
            (
                decision_id String,
                project_id UUID,
                entity_type LowCardinality(String),
                entity_id String,
                field LowCardinality(String),
                status LowCardinality(String),
                previous_value_json String,
                approved_value_json String,
                supersedes Array(String),
                scope Array(String),
                decision_source String,
                approved_by String,
                agent_directive String,
                decision_json String,
                approved_at DateTime64(3, 'UTC'),
                ingested_at DateTime64(3, 'UTC')
            )
            ENGINE = MergeTree
            ORDER BY (project_id, decision_id)
        """,
    }

    created = []

    try:
        for table_name, ddl in migrations.items():
            client.command(ddl)
            created.append(table_name)
            print(f"MIGRATION OK: {table_name}")

        table_result = client.query(
            """
            SELECT name, engine
            FROM system.tables
            WHERE database = {database:String}
              AND name IN
              (
                  'source_pages',
                  'source_chunks',
                  'source_quality_dispositions',
                  'canon_decisions'
              )
            ORDER BY name
            """,
            parameters={"database": database},
        )

        tables = [
            {"name": row[0], "engine": row[1]}
            for row in table_result.result_rows
        ]

        if len(tables) != 4:
            raise RuntimeError(
                f"Expected 4 migrated tables, found {len(tables)}."
            )

        report = {
            "schema_version": "1.0",
            "migration_id": "P09C-source-intelligence-v1",
            "database": database,
            "applied_at_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "tables": tables,
        }

        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        print()
        print(f"Tables verified: {len(tables)}")
        print(f"Report: {output}")
        print("SOURCE INTELLIGENCE MIGRATION: OK")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
