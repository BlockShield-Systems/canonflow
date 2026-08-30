# P10E Read-only Schema Preflight

## Status

`passed`

## Table

`canonflow.canon_decisions`

## Verified schema

| Column | Type |
|---|---|
| decision_id | String |
| project_id | UUID |
| entity_type | LowCardinality(String) |
| entity_id | String |
| field | LowCardinality(String) |
| status | LowCardinality(String) |
| previous_value_json | String |
| approved_value_json | String |
| supersedes | Array(String) |
| scope | Array(String) |
| decision_source | String |
| approved_by | String |
| agent_directive | String |
| decision_json | String |
| approved_at | DateTime64(3, 'UTC') |
| ingested_at | DateTime64(3, 'UTC') |

## ID preflight

- `YD-CANON-0001`: exists exactly once
- `YD-CANON-0002`: exists exactly once
- `YD-CANON-0003`: absent
- `YD-CANON-0004`: absent
- `YD-CANON-0005`: absent
- `YD-CANON-0006`: absent

## Mutation state

No mutation was executed during this preflight.
