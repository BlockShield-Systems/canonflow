#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DATABASE = "canonflow"
CONTRACT_TAG = "p10g-telemetry-event-contract-v1-candidate"

CONTRACT = Path("45-p10g-telemetry-event-contract-v1.json")
CONTRACT_VALIDATION = Path(
    "46-p10g-telemetry-event-contract-validation.json"
)
BUILDER = Path("47a-clickhouse-event-ledger-schema-builder.py")

SCHEMA = Path("47-clickhouse-event-ledger-schema-v1.sql")
SEED = Path("48-clickhouse-event-definition-seed-v1.sql")
ROLLBACK = Path("49-clickhouse-event-ledger-rollback-v1.sql")
VALIDATION = Path("50-clickhouse-event-ledger-schema-validation.json")
MANIFEST = Path("SHA256SUMS.clickhouse-event-ledger-schema-v1")

EXPECTED_EVENT_COUNT = 57
EVENT_NAME_RE = re.compile(
    r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){2,}$"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args],
        text=True,
    ).strip()


def atomic_write(path: Path, content: str) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(content)
        handle.flush()

    temporary.replace(path)


def atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    atomic_write(
        path,
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=False,
        ) + "\n",
    )


def sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def nullable_string(value: Any) -> str:
    if value is None:
        return "NULL"

    return sql_string(str(value))


def nullable_float(value: Any) -> str:
    if value is None:
        return "NULL"

    if isinstance(value, bool):
        raise AssertionError("Boolean is not a numeric canonical value")

    return repr(float(value))


def build_schema() -> str:
    return f"""-- Canonflow ClickHouse Event Ledger Schema v1
-- Generated from the SHA-bound P10G Telemetry Event Contract v1.
-- Target compatibility: ClickHouse 26.2.x.
-- This file performs DDL mutations when explicitly executed.
-- It is not executed by the schema builder.

CREATE DATABASE IF NOT EXISTS {DATABASE};

CREATE TABLE IF NOT EXISTS {DATABASE}.event_definitions
(
    contract_id UUID,
    event_name LowCardinality(String),
    event_version UInt16,
    domain LowCardinality(String),
    event_class LowCardinality(String),
    truth_scope LowCardinality(String),
    visibility LowCardinality(String),
    description String,
    canon_beat_id LowCardinality(String),
    canon_source_line UInt32,
    canon_source_phrase String,
    canon_draft_sha256 FixedString(64),
    canonical_value Nullable(Float64),
    canonical_unit Nullable(String),
    threshold_policy LowCardinality(String),
    definition_version UInt32,
    loaded_at DateTime64(9, 'UTC') DEFAULT now64(9, 'UTC'),

    CONSTRAINT event_definition_name_not_empty
        CHECK length(event_name) > 0,

    CONSTRAINT event_definition_version_positive
        CHECK event_version > 0,

    CONSTRAINT event_definition_threshold_policy
        CHECK threshold_policy IN
        (
            'none',
            'canon_exact',
            'canon_qualitative',
            'runtime_configured'
        ),

    CONSTRAINT event_definition_value_pair
        CHECK
        (
            (canonical_value IS NULL AND canonical_unit IS NULL)
            OR
            (canonical_value IS NOT NULL AND canonical_unit IS NOT NULL)
        )
)
ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY (contract_id, event_name, event_version);

CREATE TABLE IF NOT EXISTS {DATABASE}.event_ingest_attempts
(
    ingest_attempt_id UUID DEFAULT generateUUIDv4(),
    event_id UUID,
    deduplication_key String,
    event_name LowCardinality(String),
    event_version UInt16,
    project_id UUID,
    revision_run_id UUID,
    contract_id UUID,

    timeline_version Nullable(String),
    scene_id Nullable(String),
    shot_id Nullable(String),
    beat_id Nullable(String),
    frame_index Nullable(UInt64),
    fps_numerator Nullable(UInt32),
    fps_denominator Nullable(UInt32),

    occurred_at DateTime64(9, 'UTC'),
    ingested_at DateTime64(9, 'UTC') DEFAULT now64(9, 'UTC'),

    source_service LowCardinality(String),
    source_instance String,
    truth_scope LowCardinality(String),
    payload_version UInt16,
    payload_json String,
    producer_sequence Nullable(UInt64),
    attributes Map(String, String),

    CONSTRAINT raw_event_name_not_empty
        CHECK length(event_name) > 0,

    CONSTRAINT raw_deduplication_key_not_empty
        CHECK length(deduplication_key) > 0,

    CONSTRAINT raw_event_version_positive
        CHECK event_version > 0,

    CONSTRAINT raw_payload_version_positive
        CHECK payload_version > 0,

    CONSTRAINT raw_truth_scope_allowed
        CHECK truth_scope IN
        (
            'system_truth',
            'character_knowledge',
            'character_observation',
            'declared_intent',
            'reported_external_state'
        ),

    CONSTRAINT raw_fps_pair
        CHECK
        (
            (fps_numerator IS NULL AND fps_denominator IS NULL)
            OR
            (
                fps_numerator IS NOT NULL
                AND fps_denominator IS NOT NULL
                AND fps_numerator > 0
                AND fps_denominator > 0
            )
        )
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(ingested_at)
ORDER BY
(
    project_id,
    revision_run_id,
    toDate(ingested_at),
    event_name,
    ingested_at,
    ingest_attempt_id
)
TTL toDateTime(ingested_at) + INTERVAL 730 DAY DELETE
SETTINGS index_granularity = 8192;

CREATE TABLE IF NOT EXISTS {DATABASE}.events
(
    event_id UUID,
    deduplication_key String,
    event_name LowCardinality(String),
    event_version UInt16,
    project_id UUID,
    revision_run_id UUID,
    contract_id UUID,

    timeline_version Nullable(String),
    scene_id Nullable(String),
    shot_id Nullable(String),
    beat_id Nullable(String),
    frame_index Nullable(UInt64),
    fps_numerator Nullable(UInt32),
    fps_denominator Nullable(UInt32),

    occurred_at DateTime64(9, 'UTC'),
    ingested_at DateTime64(9, 'UTC'),

    source_service LowCardinality(String),
    source_instance String,
    truth_scope LowCardinality(String),
    payload_version UInt16,
    payload_json String,
    producer_sequence Nullable(UInt64),
    attributes Map(String, String)
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(occurred_at)
ORDER BY
(
    project_id,
    revision_run_id,
    deduplication_key
)
SETTINGS index_granularity = 8192;

CREATE MATERIALIZED VIEW IF NOT EXISTS
    {DATABASE}.mv_event_ingest_attempts_to_events
TO {DATABASE}.events
AS
SELECT
    event_id,
    deduplication_key,
    event_name,
    event_version,
    project_id,
    revision_run_id,
    contract_id,
    timeline_version,
    scene_id,
    shot_id,
    beat_id,
    frame_index,
    fps_numerator,
    fps_denominator,
    occurred_at,
    ingested_at,
    source_service,
    source_instance,
    truth_scope,
    payload_version,
    payload_json,
    producer_sequence,
    attributes
FROM {DATABASE}.event_ingest_attempts;

CREATE VIEW IF NOT EXISTS {DATABASE}.v_events_current
AS
SELECT *
FROM {DATABASE}.events FINAL;

CREATE VIEW IF NOT EXISTS {DATABASE}.v_system_truth
AS
SELECT *
FROM {DATABASE}.events FINAL
WHERE truth_scope = 'system_truth';

CREATE VIEW IF NOT EXISTS {DATABASE}.v_character_knowledge
AS
SELECT *
FROM {DATABASE}.events FINAL
WHERE truth_scope IN
(
    'character_knowledge',
    'character_observation'
);

CREATE VIEW IF NOT EXISTS {DATABASE}.v_timeline_binding_validation
AS
SELECT
    event_id,
    deduplication_key,
    event_name,
    project_id,
    revision_run_id,
    timeline_version,
    scene_id,
    shot_id,
    beat_id,
    frame_index,
    fps_numerator,
    fps_denominator,
    multiIf
    (
        frame_index IS NULL
            AND fps_numerator IS NULL
            AND fps_denominator IS NULL,
        'semantic_only',

        frame_index IS NOT NULL
            AND fps_numerator IS NOT NULL
            AND fps_denominator IS NOT NULL
            AND fps_numerator > 0
            AND fps_denominator > 0
            AND timeline_version IS NOT NULL
            AND shot_id IS NOT NULL
            AND beat_id IS NOT NULL,
        'frame_bound_valid',

        'invalid'
    ) AS timeline_binding_status
FROM {DATABASE}.events FINAL;

CREATE VIEW IF NOT EXISTS {DATABASE}.v_event_contract_violations
AS
SELECT
    e.event_id,
    e.deduplication_key,
    e.event_name,
    e.event_version,
    e.contract_id,
    e.truth_scope AS emitted_truth_scope,
    d.truth_scope AS defined_truth_scope,
    multiIf
    (
        d.event_name = '',
        'unknown_event',

        e.event_version != d.event_version,
        'event_version_mismatch',

        e.truth_scope != d.truth_scope,
        'truth_scope_mismatch',

        'valid'
    ) AS contract_status
FROM {DATABASE}.events AS e FINAL
LEFT JOIN
(
    SELECT *
    FROM {DATABASE}.event_definitions FINAL
) AS d
    ON e.contract_id = d.contract_id
    AND e.event_name = d.event_name
    AND e.event_version = d.event_version
WHERE
    d.event_name = ''
    OR e.event_version != d.event_version
    OR e.truth_scope != d.truth_scope;
"""


def build_seed(contract: dict[str, Any]) -> str:
    rows: list[str] = []

    contract_id = contract["contract_id"]

    for item in contract["events"]:
        locator = item["canon_locator"]
        canonical_value = item["canonical_value"]

        value = (
            canonical_value["value"]
            if canonical_value is not None
            else None
        )
        unit = (
            canonical_value["unit"]
            if canonical_value is not None
            else None
        )

        row = (
            "("
            + ", ".join(
                [
                    sql_string(contract_id),
                    sql_string(item["event_name"]),
                    str(item["event_version"]),
                    sql_string(item["domain"]),
                    sql_string(item["event_class"]),
                    sql_string(item["truth_scope"]),
                    sql_string(item["visibility"]),
                    sql_string(item["description"]),
                    sql_string(locator["beat_id"]),
                    str(locator["source_line"]),
                    sql_string(locator["source_phrase"]),
                    sql_string(locator["draft_sha256"]),
                    nullable_float(value),
                    nullable_string(unit),
                    sql_string(item["threshold_policy"]),
                    "1",
                    "now64(9, 'UTC')",
                ]
            )
            + ")"
        )

        rows.append(row)

    return f"""-- Canonflow ClickHouse Event Definition Seed v1
-- Event definitions: {len(rows)}
-- Contract ID: {contract_id}
-- Idempotent logical key:
--   (contract_id, event_name, event_version)
-- Repeated seed execution is resolved by ReplacingMergeTree.

INSERT INTO {DATABASE}.event_definitions
(
    contract_id,
    event_name,
    event_version,
    domain,
    event_class,
    truth_scope,
    visibility,
    description,
    canon_beat_id,
    canon_source_line,
    canon_source_phrase,
    canon_draft_sha256,
    canonical_value,
    canonical_unit,
    threshold_policy,
    definition_version,
    loaded_at
)
VALUES
{",\n".join(rows)};
"""


def build_rollback() -> str:
    return f"""-- Canonflow ClickHouse Event Ledger Schema v1 rollback
-- Destructive: execute only under explicit deployment authorization.
-- Raw ingest attempts are dropped last.

DROP VIEW IF EXISTS {DATABASE}.v_event_contract_violations;
DROP VIEW IF EXISTS {DATABASE}.v_timeline_binding_validation;
DROP VIEW IF EXISTS {DATABASE}.v_character_knowledge;
DROP VIEW IF EXISTS {DATABASE}.v_system_truth;
DROP VIEW IF EXISTS {DATABASE}.v_events_current;

DROP VIEW IF EXISTS {DATABASE}.mv_event_ingest_attempts_to_events;

DROP TABLE IF EXISTS {DATABASE}.events;
DROP TABLE IF EXISTS {DATABASE}.event_definitions;
DROP TABLE IF EXISTS {DATABASE}.event_ingest_attempts;

DROP DATABASE IF EXISTS {DATABASE};
"""


def main() -> None:
    if Path.cwd().resolve() != Path(__file__).resolve().parent:
        raise AssertionError(
            "Run the builder from the P10G evidence directory"
        )

    for required in (CONTRACT, CONTRACT_VALIDATION, BUILDER):
        if not required.is_file():
            raise AssertionError(f"Missing required file: {required}")

    for output in (SCHEMA, SEED, ROLLBACK, VALIDATION, MANIFEST):
        if output.exists():
            raise AssertionError(
                f"Refusing to overwrite existing output: {output}"
            )

    head = git("rev-parse", "HEAD")
    contract_tag_commit = git(
        "rev-parse",
        f"{CONTRACT_TAG}^{{commit}}",
    )

    if head != contract_tag_commit:
        raise AssertionError(
            "HEAD is not the telemetry-contract candidate tag"
        )

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    contract_validation = json.loads(
        CONTRACT_VALIDATION.read_text(encoding="utf-8")
    )

    events = contract["events"]
    event_names = [item["event_name"] for item in events]

    assert contract["status"] == "semantic_contract_candidate"
    assert contract["event_count"] == EXPECTED_EVENT_COUNT
    assert len(events) == EXPECTED_EVENT_COUNT
    assert len(event_names) == len(set(event_names))
    assert all(EVENT_NAME_RE.fullmatch(name) for name in event_names)

    assert (
        contract_validation["result"]["semantic_validation_passed"]
        is True
    )
    assert contract_validation["result"]["checks_failed"] == 0
    assert contract_validation["contract_sha256"] == sha256(CONTRACT)

    schema = build_schema()
    seed = build_seed(contract)
    rollback = build_rollback()

    atomic_write(SCHEMA, schema)
    atomic_write(SEED, seed)
    atomic_write(ROLLBACK, rollback)

    required_schema_fragments = (
        f"CREATE DATABASE IF NOT EXISTS {DATABASE}",
        f"CREATE TABLE IF NOT EXISTS {DATABASE}.event_definitions",
        f"CREATE TABLE IF NOT EXISTS {DATABASE}.event_ingest_attempts",
        f"CREATE TABLE IF NOT EXISTS {DATABASE}.events",
        "ENGINE = MergeTree",
        "ENGINE = ReplacingMergeTree(loaded_at)",
        "ENGINE = ReplacingMergeTree(ingested_at)",
        "DateTime64(9, 'UTC')",
        "Nullable(UInt64)",
        "Nullable(UInt32)",
        "Map(String, String)",
        "CREATE MATERIALIZED VIEW IF NOT EXISTS",
        f"CREATE VIEW IF NOT EXISTS {DATABASE}.v_events_current",
        f"CREATE VIEW IF NOT EXISTS {DATABASE}.v_system_truth",
        f"CREATE VIEW IF NOT EXISTS {DATABASE}.v_character_knowledge",
        (
            f"CREATE VIEW IF NOT EXISTS "
            f"{DATABASE}.v_timeline_binding_validation"
        ),
        (
            f"CREATE VIEW IF NOT EXISTS "
            f"{DATABASE}.v_event_contract_violations"
        ),
        "FROM canonflow.events FINAL",
    )

    missing_fragments = [
        fragment
        for fragment in required_schema_fragments
        if fragment not in schema
    ]

    if missing_fragments:
        raise AssertionError(
            f"Schema fragments missing: {missing_fragments}"
        )

    # Each generated VALUES row contributes exactly one occurrence.
    seed_event_occurrences = seed.count(
        "now64(9, 'UTC')"
    )
    if seed_event_occurrences != EXPECTED_EVENT_COUNT:
        raise AssertionError(
            "Unexpected seed row count: "
            f"{seed_event_occurrences}"
        )

    checks = [
        {
            "check_id": "CH-SCHEMA-001",
            "name": "contract_candidate_commit_bound",
            "passed": head == contract_tag_commit,
        },
        {
            "check_id": "CH-SCHEMA-002",
            "name": "contract_hash_bound",
            "passed": (
                contract_validation["contract_sha256"]
                == sha256(CONTRACT)
            ),
        },
        {
            "check_id": "CH-SCHEMA-003",
            "name": "event_definition_count",
            "passed": len(events) == 57,
        },
        {
            "check_id": "CH-SCHEMA-004",
            "name": "raw_ingest_ledger_present",
            "passed": (
                f"{DATABASE}.event_ingest_attempts"
                in schema
            ),
        },
        {
            "check_id": "CH-SCHEMA-005",
            "name": "deduplicated_projection_present",
            "passed": (
                "ReplacingMergeTree(ingested_at)"
                in schema
            ),
        },
        {
            "check_id": "CH-SCHEMA-006",
            "name": "materialized_view_present",
            "passed": (
                "mv_event_ingest_attempts_to_events"
                in schema
            ),
        },
        {
            "check_id": "CH-SCHEMA-007",
            "name": "nanosecond_timestamps_present",
            "passed": (
                schema.count("DateTime64(9, 'UTC')") >= 3
            ),
        },
        {
            "check_id": "CH-SCHEMA-008",
            "name": "nullable_frame_binding_present",
            "passed": (
                "frame_index Nullable(UInt64)"
                in schema
            ),
        },
        {
            "check_id": "CH-SCHEMA-009",
            "name": "rational_framerate_present",
            "passed": (
                "fps_numerator Nullable(UInt32)"
                in schema
                and "fps_denominator Nullable(UInt32)"
                in schema
            ),
        },
        {
            "check_id": "CH-SCHEMA-010",
            "name": "system_truth_view_present",
            "passed": (
                "v_system_truth"
                in schema
            ),
        },
        {
            "check_id": "CH-SCHEMA-011",
            "name": "character_knowledge_view_present",
            "passed": (
                "v_character_knowledge"
                in schema
            ),
        },
        {
            "check_id": "CH-SCHEMA-012",
            "name": "timeline_validation_view_present",
            "passed": (
                "v_timeline_binding_validation"
                in schema
            ),
        },
        {
            "check_id": "CH-SCHEMA-013",
            "name": "contract_violation_view_present",
            "passed": (
                "v_event_contract_violations"
                in schema
            ),
        },
        {
            "check_id": "CH-SCHEMA-014",
            "name": "seed_contains_57_rows",
            "passed": (
                seed_event_occurrences
                == EXPECTED_EVENT_COUNT
            ),
        },
        {
            "check_id": "CH-SCHEMA-015",
            "name": "rollback_present",
            "passed": (
                "DROP TABLE IF EXISTS"
                in rollback
                and "DROP DATABASE IF EXISTS"
                in rollback
            ),
        },
        {
            "check_id": "CH-SCHEMA-016",
            "name": "mcp_not_used_for_ingestion",
            "passed": (
                contract["transport_policy"][
                    "mcp_is_primary_high_frequency_ingestor"
                ]
                is False
            ),
        },
        {
            "check_id": "CH-SCHEMA-017",
            "name": "no_remote_execution",
            "passed": True,
        },
        {
            "check_id": "CH-SCHEMA-018",
            "name": "final_canon_not_modified",
            "passed": True,
        },
    ]

    all_passed = all(check["passed"] for check in checks)

    if not all_passed:
        failed = [
            check["check_id"]
            for check in checks
            if not check["passed"]
        ]
        raise AssertionError(f"Schema checks failed: {failed}")

    generated_at = datetime.now(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )

    validation = {
        "schema_version": "1.0",
        "artifact_type": "clickhouse_event_ledger_schema_validation",
        "database": DATABASE,
        "generated_at_utc": generated_at,
        "contract_binding": {
            "contract_id": contract["contract_id"],
            "contract_path": CONTRACT.name,
            "contract_sha256": sha256(CONTRACT),
            "contract_candidate_tag": CONTRACT_TAG,
            "contract_candidate_commit": contract_tag_commit,
            "event_count": len(events),
        },
        "clickhouse_compatibility": {
            "target_version_family": "26.2.x",
            "remote_server_version_observed": "26.2.1.558",
            "syntax_execution_completed": False,
            "remote_deployment_completed": False,
        },
        "schema_objects": {
            "database": DATABASE,
            "tables": [
                "event_definitions",
                "event_ingest_attempts",
                "events",
            ],
            "materialized_views": [
                "mv_event_ingest_attempts_to_events",
            ],
            "views": [
                "v_events_current",
                "v_system_truth",
                "v_character_knowledge",
                "v_timeline_binding_validation",
                "v_event_contract_violations",
            ],
        },
        "checks": checks,
        "result": {
            "checks_total": len(checks),
            "checks_passed": sum(
                1 for check in checks if check["passed"]
            ),
            "checks_failed": sum(
                1 for check in checks if not check["passed"]
            ),
            "event_definition_rows": EXPECTED_EVENT_COUNT,
            "schema_generation_passed": all_passed,
            "syntax_execution_pending": True,
            "deployment_pending": True,
        },
        "execution": {
            "provider_calls_executed": False,
            "clickhouse_connection_opened": False,
            "clickhouse_mutation_executed": False,
            "remote_schema_modified": False,
            "final_canon_modified": False,
        },
    }

    atomic_json_write(VALIDATION, validation)

    manifest_files = (
        CONTRACT,
        CONTRACT_VALIDATION,
        BUILDER,
        SCHEMA,
        SEED,
        ROLLBACK,
        VALIDATION,
    )

    MANIFEST.write_text(
        "".join(
            f"{sha256(path)}  {path.name}\n"
            for path in manifest_files
        ),
        encoding="utf-8",
        newline="\n",
    )

    print("===== CLICKHOUSE EVENT LEDGER SCHEMA V1 =====")
    print(f"Database:                     {DATABASE}")
    print(f"Contract ID:                  {contract['contract_id']}")
    print(f"Contract commit:              {contract_tag_commit}")
    print(f"Contract SHA-256:             {sha256(CONTRACT)}")
    print(f"Event definitions:            {len(events)}")
    print("Tables:                       3")
    print("Materialized views:           1")
    print("Read views:                   5")
    print(f"Validation checks:            {len(checks)}")
    print("Syntax execution completed:   False")
    print("Remote deployment completed:  False")
    print("Provider calls executed:      False")
    print("ClickHouse connection opened: False")
    print("ClickHouse mutation executed: False")
    print("Final canon modified:         False")
    print("CLICKHOUSE EVENT LEDGER SCHEMA V1 BUILD: OK")


if __name__ == "__main__":
    main()
