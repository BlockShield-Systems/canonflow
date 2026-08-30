# P10E — Controlled Canon Decision Ingestion

## Status

`awaiting_explicit_mutation_authorization`

## Source authority

- Human authority: Demian
- Source workflow: P10D Human Approval Loop
- Source matrix: `03-human-decision-matrix.json`
- Approved new canon candidates: 4
- Database mutation authorized: not yet
- Agent database access: read-only

## Intended Canon Decision IDs

- `YD-CANON-0003`
- `YD-CANON-0004`
- `YD-CANON-0005`
- `YD-CANON-0006`

## Excluded from insertion

- `YD-CANON-0001`: already exists
- `YD-CANON-0002`: already exists
- `P10D-REVIEW-007`: deferred; no Canon Decision may be created

## Control rule

No INSERT may be generated or executed until:

1. the current ClickHouse schema is verified;
2. candidate decision IDs are confirmed absent;
3. the deterministic ingestion payload is reviewed;
4. Demian explicitly authorizes the database mutation.
