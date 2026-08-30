# P10F Failed Attempt 01 — Clipboard Truncation

## Status

`rejected_transport_truncation`

## Cause

The ClickHouse web-console clipboard transfer truncated JSONEachRow
records YD-CANON-0003, YD-CANON-0004, and YD-CANON-0005 at exactly
4095 characters.

## Resolution

The affected records were retrieved as reduced base rows plus bounded
decision_json chunks, reconstructed locally, and fully validated.

The accepted snapshot is stored at:

`../03-read-only-canon-snapshot.jsonl`

This rejected artifact is not an authoritative Canon Story Bible input.
