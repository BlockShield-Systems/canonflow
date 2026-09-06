# CANONFLOW — STATE

Generated: `2026-09-06T16:35:53Z` by `scripts/state.sh`.
Every number below comes from a live query, not from memory.

## Repo
```
branch: main
head:   b792128 2026-09-06 fix(deps): upgrade mcp-clickhouse to 0.6.0 and fastmcp to 4.0.3
origin: git@github.com:BlockShield-Systems/canonflow.git
dirty:  1 files
license: LICENSE
```

## Cloud Run
```
canonflow-agent           https://canonflow-agent-ektxaloq2a-ez.a.run.app           canonflow-agent-00012-9fp
canonflow-event-producer  https://canonflow-event-producer-ektxaloq2a-ez.a.run.app  canonflow-event-producer-00003-hf5
```

### canonflow-agent (containers / image digests)
```
agent;mcp
europe-west4-docker.pkg.dev/canonflow-agentic-cinema/canonflow-services/canonflow-agent:20260906-102809-ef979f5;europe-west4-docker.pkg.dev/canonflow-agentic-cinema/canonflow-services/canonflow-mcp:20260906-142533-b792128
--
sa:       canonflow-agent@canonflow-agentic-cinema.iam.gserviceaccount.com
ingress:  all
vpc:      [{"network":"canonflow-runtime","subnetwork":"canonflow-runtime-europe-west4"}]
env keys: CANONFLOW_MCP_URL CANONFLOW_MCP_TIMEOUT_SECONDS CANONFLOW_MODEL CANONFLOW_PROJECT_SLUG CANONFLOW_GEMINI_MIN_INTERVAL_SECONDS GOOGLE_CLOUD_PROJECT GOOGLE_CLOUD_LOCATION GOOGLE_API_KEY CLICKHOUSE_MCP_AUTH_TOKEN CF_PROJECT GOOGLE_GENAI_USE_ENTERPRISE
invoker:  ['allUsers']
```

## Network
```
canonflow-runtime
default
--
canonflow-lb-ip                      34.160.77.175                IN_USE
canonflow-event-producer-egress      34.12.74.126   europe-west4  IN_USE
serverless-ipv4-1788617979425920741  10.42.0.16     europe-west4  RESERVED
```
ClickHouse IP access list must contain the NAT IP of `canonflow-runtime`.

## Secrets (names only)
```
canonflow-clickhouse-context-writer-password
canonflow-clickhouse-event-producer-password
canonflow-clickhouse-mcp-password
canonflow-gemini-api-key
canonflow-mcp-auth-token
```

## Artifact Registry (latest tags)
```
-- canonflow
-- canonflow-services
canonflow-agent	v1	2026-08-29
canonflow-agent	20260829-235302-5ed043d	2026-08-29
canonflow-agent	20260906-102751-ef979f5	2026-09-06
canonflow-agent	20260905-094825-ef979f5	2026-09-05
canonflow-agent	20260830-004458-5ed043d	2026-08-30
canonflow-agent	20260906-102809-ef979f5	2026-09-06
```

## Local artifacts
```
var/runs:        206 dirs, 63M
snapshot beats:  45 files
web bundle:      728K
attic backups:   27 files
```

### Snapshot index metrics
```
generated_at               2026-09-02T01:43:43+00:00
beat_count                 45
canon_beat_count           44
shot_count                 117
total_duration_s           820
canon_duration_s           790
canon_bound_duration_s     510
canon_unbound_duration_s   280
intro_duration_s           30
showcase_duration_s        820
media_count                0
verdicts                   {'PASS': 45}
ctx_state_errors           []
segments                   ['prologue', 'act_1', 'act_2a', 'act_2b', 'act_3', 'epilogue', 'unbound']
intro                      P10G-BEAT-000
```

## Frontend toolchain
```
├── @tailwindcss/postcss@4.3.3
├── @types/node@26.4.0
├── @types/react@19.2.18
├── next@16.3.4
├── postcss@8.5.26
├── react-dom@19.2.8
├── react@19.2.8
├── tailwindcss@4.3.3
└── typescript@7.0.2

```

## Open items
Maintained by hand below this line — the sections above are overwritten on every run.

- (none recorded; put manual notes in docs/STATE.open.md)
