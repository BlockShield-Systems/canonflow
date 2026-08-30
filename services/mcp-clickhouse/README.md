# canonflow-mcp-service

Read-only MCP server for the CanonFlow ClickHouse context store.

Wraps `mcp-clickhouse` and pins the runtime to a ClickHouse user that holds
only `GRANT SELECT ON canonflow.*`. Write access and DDL are additionally
disabled at application level via `CLICKHOUSE_ALLOW_WRITE_ACCESS=false`
and `CLICKHOUSE_ALLOW_DROP=false`.

## Transport

Streamable HTTP on `127.0.0.1:8000/mcp`, bearer-token authenticated.
In Cloud Run this container runs as a sidecar next to the ADK agent and is
never exposed through the service ingress.

## Configuration

All values are supplied as environment variables; secrets come from
Google Secret Manager. See `.env.example` for the full list.

## Entrypoint

`mcp-clickhouse` (console script of the upstream package).
