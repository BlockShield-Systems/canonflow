-- Canonflow ClickHouse Event Ledger Schema v1
-- Generated from the SHA-bound P10G Telemetry Event Contract v1.
-- Target compatibility: ClickHouse 26.2.x.
-- This file performs DDL mutations when explicitly executed.
-- It is not executed by the schema builder.

CREATE DATABASE IF NOT EXISTS canonflow;

CREATE TABLE IF NOT EXISTS canonflow.event_definitions
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

CREATE TABLE IF NOT EXISTS canonflow.event_ingest_attempts
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

CREATE TABLE IF NOT EXISTS canonflow.events
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
    canonflow.mv_event_ingest_attempts_to_events
TO canonflow.events
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
FROM canonflow.event_ingest_attempts;

CREATE VIEW IF NOT EXISTS canonflow.v_events_current
AS
SELECT *
FROM canonflow.events FINAL;

CREATE VIEW IF NOT EXISTS canonflow.v_system_truth
AS
SELECT *
FROM canonflow.events FINAL
WHERE truth_scope = 'system_truth';

CREATE VIEW IF NOT EXISTS canonflow.v_character_knowledge
AS
SELECT *
FROM canonflow.events FINAL
WHERE truth_scope IN
(
    'character_knowledge',
    'character_observation'
);

CREATE VIEW IF NOT EXISTS canonflow.v_timeline_binding_validation
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
FROM canonflow.events FINAL;

CREATE VIEW IF NOT EXISTS canonflow.v_event_contract_violations
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
FROM canonflow.events AS e FINAL
LEFT JOIN
(
    SELECT *
    FROM canonflow.event_definitions FINAL
) AS d
    ON e.contract_id = d.contract_id
    AND e.event_name = d.event_name
    AND e.event_version = d.event_version
WHERE
    d.event_name = ''
    OR e.event_version != d.event_version
    OR e.truth_scope != d.truth_scope;
