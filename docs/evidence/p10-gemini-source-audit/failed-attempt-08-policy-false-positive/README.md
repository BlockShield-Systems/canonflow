# Failed attempt 08 — SQL policy false positive

- Status: `rejected_policy_false_positive`
- Stage: P10C source-audit execution and validation
- Model: `gemini-3.1-pro-preview`
- API: Gemini Interactions API
- Disposition: archived; not canonical output
- Policy fix commit: `074c755a47f771594ed932ab4fbf89b4343ee1e7`

## Cause

The source-audit runner completed, but validation failed because the original
read-only SQL policy interpreted column/table aliases such as `c.chunk_id`
and `d.source_path` as database qualifiers.

The same qualifier implementation also rejected read-only metadata access
through `information_schema`.

## Impact

Seven source queries were blocked by the runtime callback and therefore were
not executed against ClickHouse. The generated report and summary may be
incomplete and must not be accepted as canonical audit output.

## Resolution

The regex-based qualifier check was replaced with ClickHouse SQL AST parsing
using SQLGlot. Actual database qualifiers are now distinguished from SQL
aliases. The allowed metadata databases are:

- `canonflow`
- `system`
- `information_schema`

External databases, write operations, multiple statements, and unscoped
project-table access remain blocked.

A fresh P10C audit is required.
