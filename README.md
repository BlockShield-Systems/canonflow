# CanonFlow

CanonFlow is an agentic pipeline for canon-consistent AI film production.

Generative video pipelines lose continuity: a character changes face between
shots, a prop contradicts an earlier scene, a timeline breaks. CanonFlow treats
narrative canon as an event-sourced database rather than as prompt context.
Every canon decision, entity, source document and media asset is an immutable
event in ClickHouse. A Google ADK agent reasons over that store through a
read-only MCP tool layer, so the model can query canon but can never silently
rewrite it.

## Architecture

A single Cloud Run service running two containers that share a network
namespace:

| Container | Role | Port |
|---|---|---|
| `agent` | Google ADK web and API server, Gemini reasoning, RAG retrieval | 8080, ingress |
| `mcp` | `mcp-clickhouse` sidecar exposing ClickHouse as MCP tools | 8000, internal only |

The agent reaches the sidecar over loopback with a static bearer token. The
sidecar is never exposed publicly, because Cloud Run only publishes the port
declared by the ingress container.

Egress is pinned. The service uses Direct VPC Egress with all traffic routed
through a subnet with Private Google Access, behind a Cloud NAT bound to a
single reserved static address. That address is the only entry on the
ClickHouse Cloud IP access list, so the database is unreachable from anywhere
else.

Read access is enforced in three independent layers:

1. ClickHouse grants the service user SELECT on one database and nothing else.
2. The MCP sidecar runs with write access and DDL disabled.
3. A policy middleware rejects any query whose table references are not scoped
   to an authorised project, returning `CANONFLOW_READ_ONLY_POLICY`.

Layer three is the interesting one. The agent receives a structured refusal,
then self-corrects and re-issues a scoped query. Governance is enforced by the
runtime, not by prompt discipline.

## Data model

ClickHouse database `canonflow`. Core tables include `events` and
`event_definitions` as the append-only spine, `canon_decisions`,
`canon_entities`, `context_records` and `context_authorizations`,
`source_documents`, `source_pages` and `source_chunks` for the ingested story
bible, and `scenes`, `shot_specs` and `media_assets` for production output.
Current-state access goes through views such as `v_events_current`,
`v_system_truth`, `v_event_contract_violations` and
`v_timeline_binding_validation`.

## Repository layout

    agents/                   ADK agent package, tools, RAG retrieval, tests
    services/mcp-clickhouse/  MCP sidecar service and its container build
    services/event-producer/  event ingestion service on Cloud Run
    content/                  narrative source and derived assets, proprietary
    docs/evidence/            audit trail and runtime evidence

## Prerequisites

- Python 3.12 and uv 0.12 or newer
- Google Cloud SDK, and a project with Cloud Run, Artifact Registry, Secret
  Manager and Vertex AI enabled
- A ClickHouse Cloud service with an IP access list
- A Gemini API key from AI Studio, or Vertex AI credentials

## Local development

    uv sync --directory agents
    uv sync --directory services/mcp-clickhouse

    # terminal 1, MCP sidecar
    cd services/mcp-clickhouse && uv run mcp-clickhouse

    # terminal 2, agent dev UI
    cd agents && uv run adk web --host 127.0.0.1 --port 8080

Copy `services/mcp-clickhouse/.env.example` to `.env` and fill in your own
ClickHouse credentials. Never commit `.env`.

## Deployment

Both images are built with Cloud Build and deployed through one Knative
service definition with an explicit container dependency, so the agent waits
for the sidecar. Secrets are injected from Secret Manager and no credential is
baked into an image.

    TAG="$(date -u +%Y%m%d-%H%M%S)-$(git rev-parse --short HEAD)"
    gcloud builds submit agents                  --tag "$AR/canonflow-agent:$TAG"
    gcloud builds submit services/mcp-clickhouse --tag "$AR/canonflow-mcp:$TAG"
    gcloud run services replace service.yaml

Images are deployed by digest, not by tag. The Artifact Registry repository has
tag immutability enabled, so every build receives a unique timestamped tag.

## Configuration

| Variable | Container | Purpose |
|---|---|---|
| `CANONFLOW_MODEL` | agent | Gemini model id |
| `CANONFLOW_MCP_URL` | agent | sidecar endpoint on loopback |
| `CANONFLOW_MCP_TIMEOUT_SECONDS` | agent | MCP call timeout |
| `CANONFLOW_PROJECT_SLUG` | agent | active project scope |
| `CLICKHOUSE_HOST`, `_PORT`, `_USER`, `_DATABASE` | mcp | connection target |
| `CLICKHOUSE_SECURE`, `_VERIFY` | mcp | TLS enforcement |
| `CLICKHOUSE_ALLOW_WRITE_ACCESS`, `_ALLOW_DROP` | mcp | must stay false |

The secrets `GOOGLE_API_KEY`, `CLICKHOUSE_PASSWORD` and
`CLICKHOUSE_MCP_AUTH_TOKEN` are referenced from Secret Manager and are never
stored in this repository.

## Notes for reviewers

The hosted service runs on Cloud Run with `min-instances=0` to stay inside the
project budget. The **first request after an idle period takes about 50-60
seconds**: container cold start plus the first ClickHouse Cloud connection,
which itself needs roughly 25 seconds to wake the idle service. Every
subsequent request answers in about 1-3 seconds. This is expected behaviour,
not a failure.

Hosted endpoint: https://canonflow-agent-983202668214.europe-west4.run.app

Warm the service before evaluating:

    curl -s -o /dev/null -w '%{http_code}\n' \
      https://canonflow-agent-983202668214.europe-west4.run.app/list-apps

### Local development

    uv run --directory agents --with pytest pytest -q --no-header

110 tests, of which 28 cover the read-only ClickHouse guardrail in
`agents/canonflow_agent/policy.py`. The scene shot compiler requires the
character reference images under
`docs/evidence/p10g-canon-beat-sheet/reference-images/r4/`; without them 12
tests fail by design.

## Evidence

`docs/evidence/` contains the runtime audit trail: Cloud Run service
snapshots, Cloud NAT egress configuration, ADK dev UI traces, and a raw
transcript of the read-only policy blocking an unscoped query followed by the
agent recovering with a correctly scoped one.

## License

Source code is licensed under the Apache License 2.0, see `LICENSE`.
Narrative content, generated media and character reference images are not
covered by that license, see `NOTICE`.
