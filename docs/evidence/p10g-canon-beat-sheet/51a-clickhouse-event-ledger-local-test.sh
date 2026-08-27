#!/usr/bin/env bash
set -Eeuo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

readonly IMAGE="clickhouse/clickhouse-server:26.2.19.43"
readonly CONTAINER="canonflow-p10g-ch-local-test-$$"
readonly DATABASE="canonflow"

readonly CONTRACT_ID="e17828fb-49b1-5df0-9c45-385a68f5f9d1"
readonly PROJECT_ID="e8627781-5bf3-4c4d-905f-8dda49ab53d6"
readonly REVISION_RUN_ID="68c47a53-2725-47ae-a910-489bd8b894e0"

readonly SCHEMA="47-clickhouse-event-ledger-schema-v1.sql"
readonly SEED="48-clickhouse-event-definition-seed-v1.sql"
readonly ROLLBACK="49-clickhouse-event-ledger-rollback-v1.sql"
readonly SCHEMA_VALIDATION="50-clickhouse-event-ledger-schema-validation.json"
readonly RUNNER="51a-clickhouse-event-ledger-local-test.sh"
readonly EVIDENCE="51-clickhouse-event-ledger-local-test.json"
readonly MANIFEST="SHA256SUMS.clickhouse-event-ledger-local-test"

CONTAINER_STARTED=false

cleanup() {
    local rc=$?

    trap - EXIT

    if [[ "$CONTAINER_STARTED" == true ]]; then
        if (( rc != 0 )); then
            printf '\nClickHouse container logs after failure:\n' >&2
            docker logs "$CONTAINER" >&2 || true
        fi

        docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
    fi

    exit "$rc"
}
trap cleanup EXIT

die() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

assert_eq() {
    local actual="$1"
    local expected="$2"
    local description="$3"

    if [[ "$actual" != "$expected" ]]; then
        printf 'ASSERTION FAILED: %s\n' "$description" >&2
        printf '  expected: %q\n' "$expected" >&2
        printf '  actual:   %q\n' "$actual" >&2
        exit 1
    fi

    printf 'PASS: %-42s %s\n' "$description" "$actual"
}

for required_file in \
    "$SCHEMA" \
    "$SEED" \
    "$ROLLBACK" \
    "$SCHEMA_VALIDATION" \
    "$RUNNER"
do
    [[ -f "$required_file" ]] ||
        die "Required file missing: $required_file"
done

[[ ! -e "$EVIDENCE" ]] ||
    die "Refusing to overwrite existing evidence: $EVIDENCE"

[[ ! -e "$MANIFEST" ]] ||
    die "Refusing to overwrite existing manifest: $MANIFEST"

command -v docker >/dev/null 2>&1 ||
    die "docker is not available"

docker info >/dev/null 2>&1 ||
    die "Docker daemon is not available"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    printf 'Pulling pinned ClickHouse image: %s\n' "$IMAGE"

    pull_config="$(mktemp -d)"
    printf '{"auths":{}}\n' > "$pull_config/config.json"

    if DOCKER_CONFIG="$pull_config" docker pull "$IMAGE"; then
        rm -rf -- "$pull_config"
    else
        pull_status=$?
        rm -rf -- "$pull_config"
        exit "$pull_status"
    fi
fi

printf 'Starting isolated ClickHouse container: %s\n' "$CONTAINER"

docker run \
    --detach \
    --rm \
    --name "$CONTAINER" \
    --network none \
    --ulimit nofile=262144:262144 \
    --env CLICKHOUSE_SKIP_USER_SETUP=1 \
    "$IMAGE" >/dev/null

CONTAINER_STARTED=true

server_ready=false

for _ in $(seq 1 60); do
    if docker exec "$CONTAINER" \
        clickhouse-client --query "SELECT 1" >/dev/null 2>&1
    then
        server_ready=true
        break
    fi

    sleep 1
done

[[ "$server_ready" == true ]] ||
    die "ClickHouse did not become ready within 60 seconds"

chq() {
    docker exec "$CONTAINER" \
        clickhouse-client \
        --format TSVRaw \
        --query "$1"
}

SERVER_VERSION="$(chq "SELECT version()")"
assert_eq "$SERVER_VERSION" "26.2.19.43" \
    "ClickHouse server version"

printf '\nExecuting schema...\n'
docker exec -i "$CONTAINER" \
    clickhouse-client --multiquery < "$SCHEMA"

printf 'Loading event definitions...\n'
docker exec -i "$CONTAINER" \
    clickhouse-client --multiquery < "$SEED"

DEFINITION_COUNT="$(
    chq "
        SELECT count()
        FROM ${DATABASE}.event_definitions FINAL
        WHERE contract_id = toUUID('${CONTRACT_ID}')
    "
)"
assert_eq "$DEFINITION_COUNT" "57" \
    "Loaded event definitions"

printf '\nInserting six isolated test attempts...\n'

docker exec -i "$CONTAINER" clickhouse-client --multiquery <<SQL
INSERT INTO ${DATABASE}.event_ingest_attempts
(
    event_id,
    deduplication_key,
    event_name,
    event_version,
    project_id,
    revision_run_id,
    contract_id,
    timeline_version,
    scene_id,
    shot_id,
    beat_id,
    frame_index,
    fps_numerator,
    fps_denominator,
    occurred_at,
    ingested_at,
    source_service,
    source_instance,
    truth_scope,
    payload_version,
    payload_json,
    producer_sequence,
    attributes
)
VALUES
(
    toUUID('00000000-0000-4000-8000-000000000001'),
    'test-force-amplification',
    'nscl.force_amplification.set',
    1,
    toUUID('${PROJECT_ID}'),
    toUUID('${REVISION_RUN_ID}'),
    toUUID('${CONTRACT_ID}'),
    NULL,
    NULL,
    NULL,
    'P10G-BEAT-014',
    NULL,
    NULL,
    NULL,
    toDateTime64('2026-01-01 00:00:01.000000000', 9, 'UTC'),
    toDateTime64('2026-01-01 00:00:01.100000000', 9, 'UTC'),
    'canonflow-local-test',
    'local-test-01',
    'system_truth',
    1,
    '{"state":"initial","value":400,"unit":"percent"}',
    1,
    map('test_case', 'deduplication-initial')
),
(
    toUUID('00000000-0000-4000-8000-000000000001'),
    'test-force-amplification',
    'nscl.force_amplification.set',
    1,
    toUUID('${PROJECT_ID}'),
    toUUID('${REVISION_RUN_ID}'),
    toUUID('${CONTRACT_ID}'),
    NULL,
    NULL,
    NULL,
    'P10G-BEAT-014',
    NULL,
    NULL,
    NULL,
    toDateTime64('2026-01-01 00:00:01.000000000', 9, 'UTC'),
    toDateTime64('2026-01-01 00:00:01.200000000', 9, 'UTC'),
    'canonflow-local-test',
    'local-test-01',
    'system_truth',
    1,
    '{"state":"retry","value":400,"unit":"percent"}',
    2,
    map('test_case', 'deduplication-retry')
),
(
    toUUID('00000000-0000-4000-8000-000000000002'),
    'test-character-knowledge',
    'knowledge.demian.fabrication_activity_suspected',
    1,
    toUUID('${PROJECT_ID}'),
    toUUID('${REVISION_RUN_ID}'),
    toUUID('${CONTRACT_ID}'),
    NULL,
    NULL,
    NULL,
    'P10G-BEAT-008',
    NULL,
    NULL,
    NULL,
    toDateTime64('2026-01-01 00:00:02.000000000', 9, 'UTC'),
    toDateTime64('2026-01-01 00:00:02.100000000', 9, 'UTC'),
    'canonflow-local-test',
    'local-test-01',
    'character_knowledge',
    1,
    '{"state":"suspected"}',
    3,
    map('test_case', 'character-knowledge')
),
(
    toUUID('00000000-0000-4000-8000-000000000003'),
    'test-frame-valid',
    'villa.kitchen_flood.started',
    1,
    toUUID('${PROJECT_ID}'),
    toUUID('${REVISION_RUN_ID}'),
    toUUID('${CONTRACT_ID}'),
    'local-test-timeline-v1',
    'P10G-SCENE-TEST',
    'P10G-SHOT-TEST-001',
    'P10G-BEAT-011',
    240,
    24,
    1,
    toDateTime64('2026-01-01 00:00:03.000000000', 9, 'UTC'),
    toDateTime64('2026-01-01 00:00:03.100000000', 9, 'UTC'),
    'canonflow-local-test',
    'local-test-01',
    'system_truth',
    1,
    '{"state":"started"}',
    4,
    map('test_case', 'frame-bound-valid')
),
(
    toUUID('00000000-0000-4000-8000-000000000004'),
    'test-frame-invalid',
    'villa.digital_override.failed',
    1,
    toUUID('${PROJECT_ID}'),
    toUUID('${REVISION_RUN_ID}'),
    toUUID('${CONTRACT_ID}'),
    NULL,
    NULL,
    NULL,
    'P10G-BEAT-011',
    241,
    NULL,
    NULL,
    toDateTime64('2026-01-01 00:00:04.000000000', 9, 'UTC'),
    toDateTime64('2026-01-01 00:00:04.100000000', 9, 'UTC'),
    'canonflow-local-test',
    'local-test-01',
    'system_truth',
    1,
    '{"state":"failed"}',
    5,
    map('test_case', 'frame-bound-invalid')
),
(
    toUUID('00000000-0000-4000-8000-000000000005'),
    'test-unknown-event',
    'test.unknown.event',
    1,
    toUUID('${PROJECT_ID}'),
    toUUID('${REVISION_RUN_ID}'),
    toUUID('${CONTRACT_ID}'),
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    toDateTime64('2026-01-01 00:00:05.000000000', 9, 'UTC'),
    toDateTime64('2026-01-01 00:00:05.100000000', 9, 'UTC'),
    'canonflow-local-test',
    'local-test-01',
    'system_truth',
    1,
    '{"state":"unknown"}',
    6,
    map('test_case', 'contract-violation')
);
SQL

RAW_COUNT="$(
    chq "
        SELECT count()
        FROM ${DATABASE}.event_ingest_attempts
        WHERE project_id = toUUID('${PROJECT_ID}')
          AND revision_run_id = toUUID('${REVISION_RUN_ID}')
    "
)"

CURRENT_COUNT="$(
    chq "
        SELECT count()
        FROM ${DATABASE}.v_events_current
        WHERE project_id = toUUID('${PROJECT_ID}')
          AND revision_run_id = toUUID('${REVISION_RUN_ID}')
    "
)"

DEDUP_COUNT="$(
    chq "
        SELECT count()
        FROM
        (
            SELECT deduplication_key
            FROM ${DATABASE}.event_ingest_attempts
            WHERE project_id = toUUID('${PROJECT_ID}')
              AND revision_run_id = toUUID('${REVISION_RUN_ID}')
            GROUP BY deduplication_key
            HAVING count() > 1
        )
    "
)"

RETRY_PAYLOAD="$(
    chq "
        SELECT payload_json
        FROM ${DATABASE}.v_events_current
        WHERE project_id = toUUID('${PROJECT_ID}')
          AND revision_run_id = toUUID('${REVISION_RUN_ID}')
          AND deduplication_key = 'test-force-amplification'
    "
)"

SYSTEM_TRUTH_COUNT="$(
    chq "
        SELECT count()
        FROM ${DATABASE}.v_system_truth
        WHERE project_id = toUUID('${PROJECT_ID}')
          AND revision_run_id = toUUID('${REVISION_RUN_ID}')
    "
)"

KNOWLEDGE_COUNT="$(
    chq "
        SELECT count()
        FROM ${DATABASE}.v_character_knowledge
        WHERE project_id = toUUID('${PROJECT_ID}')
          AND revision_run_id = toUUID('${REVISION_RUN_ID}')
    "
)"

SEMANTIC_ONLY_COUNT="$(
    chq "
        SELECT count()
        FROM ${DATABASE}.v_timeline_binding_validation
        WHERE project_id = toUUID('${PROJECT_ID}')
          AND revision_run_id = toUUID('${REVISION_RUN_ID}')
          AND timeline_binding_status = 'semantic_only'
    "
)"

FRAME_VALID_COUNT="$(
    chq "
        SELECT count()
        FROM ${DATABASE}.v_timeline_binding_validation
        WHERE project_id = toUUID('${PROJECT_ID}')
          AND revision_run_id = toUUID('${REVISION_RUN_ID}')
          AND timeline_binding_status = 'frame_bound_valid'
    "
)"

FRAME_INVALID_COUNT="$(
    chq "
        SELECT count()
        FROM ${DATABASE}.v_timeline_binding_validation
        WHERE project_id = toUUID('${PROJECT_ID}')
          AND revision_run_id = toUUID('${REVISION_RUN_ID}')
          AND timeline_binding_status = 'invalid'
    "
)"

CONTRACT_VIOLATION_COUNT="$(
    chq "
        SELECT count()
        FROM ${DATABASE}.v_event_contract_violations
        WHERE event_name = 'test.unknown.event'
    "
)"

UNKNOWN_EVENT_STATUS="$(
    chq "
        SELECT contract_status
        FROM ${DATABASE}.v_event_contract_violations
        WHERE event_name = 'test.unknown.event'
        LIMIT 1
    "
)"

printf '\nFunctional assertions:\n'

assert_eq "$RAW_COUNT" "6" \
    "Raw ingest attempts"

assert_eq "$CURRENT_COUNT" "5" \
    "Current deduplicated events"

assert_eq "$DEDUP_COUNT" "1" \
    "Duplicate logical keys"

assert_eq "$RETRY_PAYLOAD" \
    '{"state":"retry","value":400,"unit":"percent"}' \
    "Latest retry payload selected"

assert_eq "$SYSTEM_TRUTH_COUNT" "4" \
    "System-truth events"

assert_eq "$KNOWLEDGE_COUNT" "1" \
    "Character-knowledge events"

assert_eq "$SEMANTIC_ONLY_COUNT" "3" \
    "Semantic-only bindings"

assert_eq "$FRAME_VALID_COUNT" "1" \
    "Valid frame bindings"

assert_eq "$FRAME_INVALID_COUNT" "1" \
    "Invalid frame bindings"

assert_eq "$CONTRACT_VIOLATION_COUNT" "1" \
    "Contract violations"

assert_eq "$UNKNOWN_EVENT_STATUS" "unknown_event" \
    "Unknown-event classification"

printf '\nExecuting rollback...\n'
docker exec -i "$CONTAINER" \
    clickhouse-client --multiquery < "$ROLLBACK"

DATABASE_COUNT="$(
    chq "
        SELECT count()
        FROM system.databases
        WHERE name = '${DATABASE}'
    "
)"
assert_eq "$DATABASE_COUNT" "0" \
    "Database removed by rollback"

docker rm -f "$CONTAINER" >/dev/null
CONTAINER_STARTED=false

SCHEMA_SHA256="$(sha256sum "$SCHEMA" | awk '{print $1}')"
SEED_SHA256="$(sha256sum "$SEED" | awk '{print $1}')"
ROLLBACK_SHA256="$(sha256sum "$ROLLBACK" | awk '{print $1}')"
SCHEMA_VALIDATION_SHA256="$(
    sha256sum "$SCHEMA_VALIDATION" | awk '{print $1}'
)"
RUNNER_SHA256="$(sha256sum "$RUNNER" | awk '{print $1}')"

export SERVER_VERSION
export CONTRACT_ID
export PROJECT_ID
export REVISION_RUN_ID
export IMAGE
export SCHEMA_SHA256
export SEED_SHA256
export ROLLBACK_SHA256
export SCHEMA_VALIDATION_SHA256
export RUNNER_SHA256
export DEFINITION_COUNT
export RAW_COUNT
export CURRENT_COUNT
export DEDUP_COUNT
export RETRY_PAYLOAD
export SYSTEM_TRUTH_COUNT
export KNOWLEDGE_COUNT
export SEMANTIC_ONLY_COUNT
export FRAME_VALID_COUNT
export FRAME_INVALID_COUNT
export CONTRACT_VIOLATION_COUNT
export UNKNOWN_EVENT_STATUS

python3 - "$EVIDENCE" <<'PY'
import json
import os
import sys
from pathlib import Path

output = Path(sys.argv[1])

def integer(name: str) -> int:
    return int(os.environ[name])

evidence = {
    "evidence_type": "clickhouse_event_ledger_local_test",
    "evidence_version": 1,
    "database": "canonflow",
    "contract_binding": {
        "contract_id": os.environ["CONTRACT_ID"],
        "project_id": os.environ["PROJECT_ID"],
        "revision_run_id": os.environ["REVISION_RUN_ID"],
    },
    "execution_environment": {
        "mode": "ephemeral_local_docker",
        "image": os.environ["IMAGE"],
        "server_version": os.environ["SERVER_VERSION"],
        "network_mode": "none",
        "container_removed": True,
        "database_removed": True,
    },
    "artifact_sha256": {
        "schema": os.environ["SCHEMA_SHA256"],
        "seed": os.environ["SEED_SHA256"],
        "rollback": os.environ["ROLLBACK_SHA256"],
        "schema_validation": os.environ["SCHEMA_VALIDATION_SHA256"],
        "runner": os.environ["RUNNER_SHA256"],
    },
    "results": {
        "event_definition_count": integer("DEFINITION_COUNT"),
        "raw_ingest_attempt_count": integer("RAW_COUNT"),
        "current_event_count": integer("CURRENT_COUNT"),
        "duplicate_logical_key_count": integer("DEDUP_COUNT"),
        "retry_payload": os.environ["RETRY_PAYLOAD"],
        "system_truth_count": integer("SYSTEM_TRUTH_COUNT"),
        "character_knowledge_count": integer("KNOWLEDGE_COUNT"),
        "semantic_only_count": integer("SEMANTIC_ONLY_COUNT"),
        "frame_bound_valid_count": integer("FRAME_VALID_COUNT"),
        "frame_bound_invalid_count": integer("FRAME_INVALID_COUNT"),
        "contract_violation_count": integer("CONTRACT_VIOLATION_COUNT"),
        "unknown_event_status": os.environ["UNKNOWN_EVENT_STATUS"],
    },
    "execution_policy": {
        "syntax_execution_completed": True,
        "functional_execution_completed": True,
        "rollback_completed": True,
        "provider_calls_executed": False,
        "clickhouse_cloud_connection_opened": False,
        "remote_mutation_executed": False,
        "final_canon_modified": False,
    },
}

expected = {
    "event_definition_count": 57,
    "raw_ingest_attempt_count": 6,
    "current_event_count": 5,
    "duplicate_logical_key_count": 1,
    "retry_payload": '{"state":"retry","value":400,"unit":"percent"}',
    "system_truth_count": 4,
    "character_knowledge_count": 1,
    "semantic_only_count": 3,
    "frame_bound_valid_count": 1,
    "frame_bound_invalid_count": 1,
    "contract_violation_count": 1,
    "unknown_event_status": "unknown_event",
}

assert evidence["results"] == expected
assert evidence["execution_environment"]["network_mode"] == "none"
assert evidence["execution_environment"]["container_removed"] is True
assert evidence["execution_environment"]["database_removed"] is True
assert evidence["execution_policy"]["syntax_execution_completed"] is True
assert evidence["execution_policy"]["functional_execution_completed"] is True
assert evidence["execution_policy"]["rollback_completed"] is True
assert evidence["execution_policy"]["provider_calls_executed"] is False
assert evidence["execution_policy"]["clickhouse_cloud_connection_opened"] is False
assert evidence["execution_policy"]["remote_mutation_executed"] is False
assert evidence["execution_policy"]["final_canon_modified"] is False

output.write_text(
    json.dumps(evidence, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

sha256sum \
    "$SCHEMA" \
    "$SEED" \
    "$ROLLBACK" \
    "$SCHEMA_VALIDATION" \
    "$RUNNER" \
    "$EVIDENCE" \
    > "$MANIFEST"

printf '\n===== CLICKHOUSE EVENT LEDGER LOCAL TEST =====\n'
printf 'Image:                       %s\n' "$IMAGE"
printf 'Server version:              %s\n' "$SERVER_VERSION"
printf 'Event definitions:           %s\n' "$DEFINITION_COUNT"
printf 'Raw ingest attempts:         %s\n' "$RAW_COUNT"
printf 'Current events:              %s\n' "$CURRENT_COUNT"
printf 'Duplicate logical keys:      %s\n' "$DEDUP_COUNT"
printf 'System-truth events:         %s\n' "$SYSTEM_TRUTH_COUNT"
printf 'Character-knowledge events:  %s\n' "$KNOWLEDGE_COUNT"
printf 'Semantic-only bindings:      %s\n' "$SEMANTIC_ONLY_COUNT"
printf 'Valid frame bindings:        %s\n' "$FRAME_VALID_COUNT"
printf 'Invalid frame bindings:      %s\n' "$FRAME_INVALID_COUNT"
printf 'Contract violations:         %s\n' "$CONTRACT_VIOLATION_COUNT"
printf 'Unknown-event status:        %s\n' "$UNKNOWN_EVENT_STATUS"
printf 'Rollback completed:          True\n'
printf 'Container removed:           True\n'
printf 'Cloud connection opened:     False\n'
printf 'Remote mutation executed:    False\n'
printf 'CLICKHOUSE EVENT LEDGER LOCAL TEST: OK\n'
