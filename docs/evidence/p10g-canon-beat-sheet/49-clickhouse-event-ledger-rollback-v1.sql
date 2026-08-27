-- Canonflow ClickHouse Event Ledger Schema v1 rollback
-- Destructive: execute only under explicit deployment authorization.
-- Raw ingest attempts are dropped last.

DROP VIEW IF EXISTS canonflow.v_event_contract_violations;
DROP VIEW IF EXISTS canonflow.v_timeline_binding_validation;
DROP VIEW IF EXISTS canonflow.v_character_knowledge;
DROP VIEW IF EXISTS canonflow.v_system_truth;
DROP VIEW IF EXISTS canonflow.v_events_current;

DROP VIEW IF EXISTS canonflow.mv_event_ingest_attempts_to_events;

DROP TABLE IF EXISTS canonflow.events;
DROP TABLE IF EXISTS canonflow.event_definitions;
DROP TABLE IF EXISTS canonflow.event_ingest_attempts;

DROP DATABASE IF EXISTS canonflow;
