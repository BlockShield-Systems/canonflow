# P10F Canon Story Bible

## Status

`awaiting_read_only_canon_snapshot`

## Project

- Project ID: `e8627781-5bf3-4c4d-905f-8dda49ab53d6`
- Project slug: `yd-when-paradise-glitches`
- Human authority: `Demian`

## Authoritative Inputs

- P10C accepted Gemini source audit
- P10D human decision matrix
- P10E completed and verified canon-decision ingestion
- Canon decisions `YD-CANON-0001..0006`

## Control Policy

- Read-only database access only
- No autonomous canon changes
- No inferred fact may silently become canon
- Primary-source citations are required
- Approved canon decisions override conflicting source material
- Unresolved contradictions must remain explicitly marked

## Next Action

Create and validate a read-only ClickHouse snapshot of all six
approved canon decisions before generating the Canon Story Bible.
