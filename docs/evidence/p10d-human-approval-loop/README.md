# P10D — Human Approval Loop

## Status

`awaiting_human_review`

## Purpose

This stage converts source-audit findings into explicit human decisions
without allowing the agent to make autonomous canon decisions.

## Authority

- Canon authority: Demian
- Agent authority: proposal only
- Database writes: prohibited until explicit human approval
- P10C evidence: immutable

## Allowed dispositions

Each candidate must receive exactly one disposition:

- `approve`
- `reject`
- `defer`
- `needs_revision`

Only `approve` may become an approved canon decision. Approval still requires
a deterministic review record and a separate controlled ingestion step.

## Current files

- `01-source-audit-review-extract.md`
- `02-review-manifest.json`
- `README.md`
- `SHA256SUMS`
