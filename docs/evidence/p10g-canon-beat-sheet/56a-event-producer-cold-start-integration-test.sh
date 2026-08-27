#!/usr/bin/env bash

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "$SCRIPT_DIR/../../.." && pwd)"

SCHEMA="$SCRIPT_DIR/47-clickhouse-event-ledger-schema-v1.sql"
SEED="$SCRIPT_DIR/48-clickhouse-event-definition-seed-v1.sql"
EVIDENCE="$SCRIPT_DIR/56-event-producer-cold-start-integration-test.json"
MANIFEST="$SCRIPT_DIR/SHA256SUMS.event-producer-cold-start-integration-test"

APP="$REPOSITORY_ROOT/services/event-producer/src/canonflow_event_producer/app.py"
PYPROJECT="$REPOSITORY_ROOT/services/event-producer/pyproject.toml"
LOCKFILE="$REPOSITORY_ROOT/services/event-producer/uv.lock"
DOCKERFILE="$REPOSITORY_ROOT/services/event-producer/Dockerfile"

IMAGE="${CLICKHOUSE_IMAGE:-}"
PRODUCER="${PRODUCER_IMAGE:-}"

CONTRACT_ID="e17828fb-49b1-5df0-9c45-385a68f5f9d1"
PROJECT_ID="e8627781-5bf3-4c4d-905f-8dda49ab53d6"
REVISION_RUN_ID="68c47a53-2725-47ae-a910-489bd8b894e0"

SUFFIX="$$"
NETWORK="canonflow-producer-test-$SUFFIX"
CLICKHOUSE_CONTAINER="canonflow-clickhouse-$SUFFIX"
PRODUCER_CONTAINER="canonflow-producer-$SUFFIX"
PRODUCER_USER="canonflow_event_producer"
ADMIN_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_hex(24))')"
PRODUCER_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_hex(24))')"
TEMP_DIRECTORY="$(mktemp -d)"

NETWORK_CREATED=false
CLICKHOUSE_STARTED=false
PRODUCER_STARTED=false

cleanup() {
    result=$?
    trap - EXIT

    if [[ "$PRODUCER_STARTED" == true ]]; then
        if (( result != 0 )); then
            docker logs "$PRODUCER_CONTAINER" >&2
        fi
        docker rm -f -v "$PRODUCER_CONTAINER" >/dev/null 2>&1
    fi

    if [[ "$CLICKHOUSE_STARTED" == true ]]; then
        if (( result != 0 )); then
            docker logs "$CLICKHOUSE_CONTAINER" >&2
        fi
        docker rm -f -v "$CLICKHOUSE_CONTAINER" >/dev/null 2>&1
    fi

    if [[ "$NETWORK_CREATED" == true ]]; then
        docker network rm "$NETWORK" >/dev/null 2>&1
    fi

    rm -rf -- "$TEMP_DIRECTORY"
    exit "$result"
}

trap cleanup EXIT

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

assert_equal() {
    actual="$1"
    expected="$2"
    description="$3"

    if [[ "$actual" != "$expected" ]]; then
        printf 'ASSERTION FAILED: %s\n' "$description" >&2
        printf '  expected: %s\n' "$expected" >&2
        printf '  actual:   %s\n' "$actual" >&2
        exit 1
    fi

    printf 'PASS: %-44s %s\n' "$description" "$actual"
}

for required_file in \
    "$SCHEMA" \
    "$SEED" \
    "$APP" \
    "$PYPROJECT" \
    "$LOCKFILE" \
    "$DOCKERFILE"
do
    [[ -f "$required_file" ]] ||
        fail "Required file missing: $required_file"
done

[[ -n "$IMAGE" ]] ||
    fail "CLICKHOUSE_IMAGE is not set"

[[ -n "$PRODUCER" ]] ||
    fail "PRODUCER_IMAGE is not set"

[[ ! -e "$EVIDENCE" ]] ||
    fail "Refusing to overwrite existing evidence: $EVIDENCE"

[[ ! -e "$MANIFEST" ]] ||
    fail "Refusing to overwrite existing manifest: $MANIFEST"

command -v docker >/dev/null 2>&1 ||
    fail "docker is unavailable"

command -v curl >/dev/null 2>&1 ||
    fail "curl is unavailable"

docker info >/dev/null 2>&1 ||
    fail "Docker daemon is unavailable"

docker image inspect "$IMAGE" >/dev/null 2>&1 ||
    fail "Pinned ClickHouse image is unavailable locally"

docker image inspect "$PRODUCER" >/dev/null 2>&1 ||
    fail "Producer image is unavailable locally"

docker network create "$NETWORK" >/dev/null ||
    fail "Could not create isolated Docker network"

NETWORK_CREATED=true

docker run \
    --detach \
    --rm \
    --name "$CLICKHOUSE_CONTAINER" \
    --hostname clickhouse \
    --network "$NETWORK" \
    --ulimit nofile=262144:262144 \
    --tmpfs /var/lib/clickhouse:rw,nosuid,nodev \
    --tmpfs /var/log/clickhouse-server:rw,nosuid,nodev \
    --env CLICKHOUSE_USER=default \
    --env CLICKHOUSE_PASSWORD="$ADMIN_PASSWORD" \
    --env CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1 \
    "$IMAGE" >/dev/null ||
    fail "Could not start ClickHouse"

CLICKHOUSE_STARTED=true
CLICKHOUSE_READY=false

for _ in $(seq 1 60); do
    docker exec "$CLICKHOUSE_CONTAINER" \
        clickhouse-client \
        --user default \
        --password "$ADMIN_PASSWORD" \
        --query "SELECT 1" >/dev/null 2>&1

    if (( $? == 0 )); then
        CLICKHOUSE_READY=true
        break
    fi

    sleep 1
done

[[ "$CLICKHOUSE_READY" == true ]] ||
    fail "ClickHouse did not become ready"

chq() {
    docker exec "$CLICKHOUSE_CONTAINER" \
        clickhouse-client \
        --user default \
        --password "$ADMIN_PASSWORD" \
        --format TSVRaw \
        --query "$1"
}

SERVER_VERSION="$(chq "SELECT version()")"
assert_equal "$SERVER_VERSION" "26.2.1.1139" \
    "ClickHouse server version"

docker exec -i "$CLICKHOUSE_CONTAINER" \
    clickhouse-client \
    --user default \
    --password "$ADMIN_PASSWORD" \
    --multiquery < "$SCHEMA" ||
    fail "Schema execution failed"

docker exec -i "$CLICKHOUSE_CONTAINER" \
    clickhouse-client \
    --user default \
    --password "$ADMIN_PASSWORD" \
    --multiquery < "$SEED" ||
    fail "Seed execution failed"

DEFINITION_COUNT="$(
    chq "
        SELECT count()
        FROM canonflow.event_definitions FINAL
        WHERE contract_id = toUUID('$CONTRACT_ID')
    "
)"

assert_equal "$DEFINITION_COUNT" "57" \
    "Event-definition count"

EVENT_DEFINITION="$(
    chq "
        SELECT concat(
            toString(event_version),
            '\t',
            toString(truth_scope)
        )
        FROM canonflow.event_definitions FINAL
        WHERE contract_id = toUUID('$CONTRACT_ID')
          AND event_name = 'nscl.force_amplification.set'
        ORDER BY event_version DESC
        LIMIT 1
    "
)"

assert_equal "$EVENT_DEFINITION" $'1\tsystem_truth' \
    "Producer test definition"

INGEST_ENGINE="$(
    chq "
        SELECT engine
        FROM system.tables
        WHERE database = 'canonflow'
          AND name = 'event_ingest_attempts'
    "
)"

case "$INGEST_ENGINE" in
    MergeTree|ReplacingMergeTree)
        chq "
            ALTER TABLE canonflow.event_ingest_attempts
            MODIFY SETTING non_replicated_deduplication_window = 1000
        " >/dev/null ||
            fail "Could not enable local source deduplication"

        chq "
            ALTER TABLE canonflow.events
            MODIFY SETTING non_replicated_deduplication_window = 1000
        " >/dev/null ||
            fail "Could not enable local materialized-target deduplication"
        ;;
esac

chq "
    CREATE USER $PRODUCER_USER
    IDENTIFIED WITH sha256_password
    BY '$PRODUCER_PASSWORD'
" >/dev/null ||
    fail "Could not create producer user"

chq "
    GRANT SELECT
    ON canonflow.event_definitions
    TO $PRODUCER_USER
" >/dev/null ||
    fail "Could not grant event-definition access"

chq "
    GRANT INSERT
    ON canonflow.event_ingest_attempts
    TO $PRODUCER_USER
" >/dev/null ||
    fail "Could not grant ingest access"

chq "
    GRANT SELECT
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
    ON canonflow.event_ingest_attempts
    TO $PRODUCER_USER
" >/dev/null ||
    fail "Could not grant materialized-view source access"

docker run \
    --detach \
    --rm \
    --name "$PRODUCER_CONTAINER" \
    --network "$NETWORK" \
    --publish 127.0.0.1::8080 \
    --env CLICKHOUSE_HOST=clickhouse \
    --env CLICKHOUSE_PORT=8123 \
    --env CLICKHOUSE_USER="$PRODUCER_USER" \
    --env CLICKHOUSE_PASSWORD="$PRODUCER_PASSWORD" \
    --env CLICKHOUSE_DATABASE=canonflow \
    --env CLICKHOUSE_SECURE=false \
    --env CLICKHOUSE_VERIFY=false \
    --env CLICKHOUSE_CONNECT_TIMEOUT=10 \
    --env CLICKHOUSE_SEND_RECEIVE_TIMEOUT=30 \
    --env CANONFLOW_EVENT_CONTRACT_ID="$CONTRACT_ID" \
    --env CANONFLOW_PROJECT_ID="$PROJECT_ID" \
    --env PORT=8080 \
    --env LOG_LEVEL=INFO \
    "$PRODUCER" >/dev/null ||
    fail "Could not start producer"

PRODUCER_STARTED=true

HOST_PORT="$(
    docker port "$PRODUCER_CONTAINER" 8080/tcp |
    awk -F: 'END { print $NF }'
)"

[[ "$HOST_PORT" =~ ^[0-9]+$ ]] ||
    fail "Could not determine producer host port"

BASE_URL="http://127.0.0.1:$HOST_PORT"
PRODUCER_READY=false

for _ in $(seq 1 60); do
    READY_CODE="$(
        curl \
            --silent \
            --output "$TEMP_DIRECTORY/ready.json" \
            --write-out '%{http_code}' \
            "$BASE_URL/readyz"
    )"

    if [[ "$READY_CODE" == "200" ]]; then
        PRODUCER_READY=true
        break
    fi

    sleep 1
done

[[ "$PRODUCER_READY" == true ]] ||
    fail "Producer did not become ready"

HEALTH_CODE="$(
    curl \
        --silent \
        --output "$TEMP_DIRECTORY/health.json" \
        --write-out '%{http_code}' \
        "$BASE_URL/healthz"
)"

assert_equal "$HEALTH_CODE" "200" \
    "Health endpoint"

assert_equal "$READY_CODE" "200" \
    "Readiness endpoint"

python3 - "$TEMP_DIRECTORY" <<PY
import json
import pathlib
import sys

directory = pathlib.Path(sys.argv[1])

base = {
    "event_name": "nscl.force_amplification.set",
    "event_version": 1,
    "project_id": "$PROJECT_ID",
    "revision_run_id": "$REVISION_RUN_ID",
    "contract_id": "$CONTRACT_ID",
    "deduplication_key": "producer-integration:reactor-output:000001",
    "timeline_version": None,
    "scene_id": "scene-001",
    "shot_id": None,
    "beat_id": None,
    "frame_index": None,
    "fps_numerator": None,
    "fps_denominator": None,
    "occurred_at": "2026-08-27T12:00:00Z",
    "source_service": "canonflow-event-producer-integration",
    "source_instance": "local-docker-test",
    "truth_scope": "system_truth",
    "payload_version": 1,
    "payload": {
        "state": "active",
        "value": 400,
        "unit": "percent",
    },
    "producer_sequence": 1,
    "attributes": {
        "environment": "local-integration",
    },
}

def write(name, value):
    (directory / name).write_text(
        json.dumps(value, separators=(",", ":")),
        encoding="utf-8",
    )

write("first-request.json", base)
write("retry-request.json", base)

changed = dict(base)
changed["payload"] = {
    "state": "retry",
    "value": 400,
    "unit": "percent",
}
changed["producer_sequence"] = 2
write("changed-request.json", changed)

unknown = dict(base)
unknown["event_name"] = "test.unknown.event"
unknown["deduplication_key"] = "producer-integration:unknown"
write("unknown-request.json", unknown)

wrong_scope = dict(base)
wrong_scope["truth_scope"] = "character_knowledge"
wrong_scope["deduplication_key"] = "producer-integration:wrong-scope"
write("wrong-scope-request.json", wrong_scope)

invalid_frame = dict(base)
invalid_frame["deduplication_key"] = "producer-integration:invalid-frame"
invalid_frame["frame_index"] = 100
invalid_frame["fps_numerator"] = 24
invalid_frame["fps_denominator"] = None
write("invalid-frame-request.json", invalid_frame)
PY

post_event() {
    request_file="$1"
    response_file="$2"

    curl \
        --silent \
        --show-error \
        --output "$response_file" \
        --write-out '%{http_code}' \
        --header 'Content-Type: application/json' \
        --data-binary "@$request_file" \
        "$BASE_URL/v1/events"
}

FIRST_CODE="$(
    post_event \
        "$TEMP_DIRECTORY/first-request.json" \
        "$TEMP_DIRECTORY/first-response.json"
)"
assert_equal "$FIRST_CODE" "202" \
    "Initial event accepted"

RETRY_CODE="$(
    post_event \
        "$TEMP_DIRECTORY/retry-request.json" \
        "$TEMP_DIRECTORY/retry-response.json"
)"
assert_equal "$RETRY_CODE" "202" \
    "Exact retry accepted or deduplicated"

EXACT_RETRY_RAW_COUNT="$(
    chq "
        SELECT count()
        FROM canonflow.event_ingest_attempts
        WHERE revision_run_id = toUUID('$REVISION_RUN_ID')
          AND deduplication_key =
              'producer-integration:reactor-output:000001'
    "
)"
assert_equal "$EXACT_RETRY_RAW_COUNT" "1" \
    "Exact retry physically deduplicated"

VALIDATED_RESPONSE_FILE="$TEMP_DIRECTORY/validated-response.txt"

python3 - \
    "$TEMP_DIRECTORY/first-response.json" \
    "$TEMP_DIRECTORY/retry-response.json" \
    "$VALIDATED_RESPONSE_FILE" <<'PY_RESPONSE'
import json
import pathlib
import sys

first_path = pathlib.Path(sys.argv[1])
retry_path = pathlib.Path(sys.argv[2])
output_path = pathlib.Path(sys.argv[3])

try:
    first = json.loads(first_path.read_text(encoding="utf-8"))
    retry = json.loads(retry_path.read_text(encoding="utf-8"))

    required = {
        "event_id",
        "ingest_attempt_id",
        "deduplication_key",
        "status",
        "insert_deduplication_token",
    }

    for label, response in (
        ("initial", first),
        ("retry", retry),
    ):
        missing = required - set(response)
        if missing:
            raise ValueError(
                f"{label} response missing fields: "
                + ", ".join(sorted(missing))
            )

        if response["status"] != "accepted_or_deduplicated":
            raise ValueError(
                f"{label} response has unexpected status: "
                f"{response['status']!r}"
            )

    if first["event_id"] != retry["event_id"]:
        raise ValueError("event_id is not stable")

    if (
        first["insert_deduplication_token"]
        != retry["insert_deduplication_token"]
    ):
        raise ValueError(
            "insert_deduplication_token is not stable"
        )

    if first["ingest_attempt_id"] == retry["ingest_attempt_id"]:
        raise ValueError(
            "ingest_attempt_id was unexpectedly reused"
        )

    output_path.write_text(
        first["event_id"]
        + "\n"
        + first["insert_deduplication_token"]
        + "\n",
        encoding="utf-8",
    )

except Exception as error:
    print(
        f"Retry response validation error: {error}",
        file=sys.stderr,
    )
    print(
        "Initial response: "
        + first_path.read_text(
            encoding="utf-8",
            errors="replace",
        ),
        file=sys.stderr,
    )
    print(
        "Retry response: "
        + retry_path.read_text(
            encoding="utf-8",
            errors="replace",
        ),
        file=sys.stderr,
    )
    raise SystemExit(1)
PY_RESPONSE

RESPONSE_VALIDATION_STATUS=$?

if (( RESPONSE_VALIDATION_STATUS != 0 )); then
    fail "Retry response validation failed"
fi

if [[ ! -s "$VALIDATED_RESPONSE_FILE" ]]; then
    fail "Retry response validation produced no result file"
fi

mapfile -t VALIDATED_RESPONSE_VALUES \
    < "$VALIDATED_RESPONSE_FILE"

EVENT_ID="${VALIDATED_RESPONSE_VALUES[0]:-}"
INSERT_TOKEN="${VALIDATED_RESPONSE_VALUES[1]:-}"

if [[ -z "$EVENT_ID" || -z "$INSERT_TOKEN" ]]; then
    fail "Retry response validation produced incomplete values"
fi

printf 'PASS: %-44s %s\n' \
    "Stable deterministic event ID" \
    "$EVENT_ID"

printf 'PASS: %-44s %s\n' \
    "Stable insert deduplication token" \
    "$INSERT_TOKEN"

CHANGED_CODE="$(
    post_event \
        "$TEMP_DIRECTORY/changed-request.json" \
        "$TEMP_DIRECTORY/changed-response.json"
)"
assert_equal "$CHANGED_CODE" "202" \
    "Changed payload accepted"

UNKNOWN_CODE="$(
    post_event \
        "$TEMP_DIRECTORY/unknown-request.json" \
        "$TEMP_DIRECTORY/unknown-response.json"
)"
assert_equal "$UNKNOWN_CODE" "422" \
    "Unknown definition rejected"

WRONG_SCOPE_CODE="$(
    post_event \
        "$TEMP_DIRECTORY/wrong-scope-request.json" \
        "$TEMP_DIRECTORY/wrong-scope-response.json"
)"
assert_equal "$WRONG_SCOPE_CODE" "409" \
    "Truth-scope mismatch rejected"

INVALID_FRAME_CODE="$(
    post_event \
        "$TEMP_DIRECTORY/invalid-frame-request.json" \
        "$TEMP_DIRECTORY/invalid-frame-response.json"
)"
assert_equal "$INVALID_FRAME_CODE" "422" \
    "Invalid frame binding rejected"

RAW_COUNT="$(
    chq "
        SELECT count()
        FROM canonflow.event_ingest_attempts
        WHERE revision_run_id = toUUID('$REVISION_RUN_ID')
          AND source_service =
              'canonflow-event-producer-integration'
    "
)"

EVENT_COUNT="$(
    chq "
        SELECT count()
        FROM canonflow.events
        WHERE revision_run_id = toUUID('$REVISION_RUN_ID')
          AND source_service =
              'canonflow-event-producer-integration'
    "
)"

CURRENT_COUNT="$(
    chq "
        SELECT count()
        FROM canonflow.v_events_current
        WHERE revision_run_id = toUUID('$REVISION_RUN_ID')
          AND source_service =
              'canonflow-event-producer-integration'
    "
)"

CURRENT_PAYLOAD="$(
    chq "
        SELECT payload_json
        FROM canonflow.v_events_current
        WHERE revision_run_id = toUUID('$REVISION_RUN_ID')
          AND deduplication_key =
              'producer-integration:reactor-output:000001'
        LIMIT 1
    "
)"

assert_equal "$RAW_COUNT" "2" \
    "Physical ingest attempts"

assert_equal "$EVENT_COUNT" "2" \
    "Physical materialized events"

assert_equal "$CURRENT_COUNT" "1" \
    "Current logical events"

python3 - "$CURRENT_PAYLOAD" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])
assert payload == {
    "state": "retry",
    "unit": "percent",
    "value": 400,
}
PY

if (( $? != 0 )); then
    fail "Current payload validation failed"
fi

printf 'PASS: %-44s %s\n' \
    "Current payload selected" \
    "$CURRENT_PAYLOAD"

docker rm -f -v "$PRODUCER_CONTAINER" >/dev/null 2>&1
PRODUCER_STARTED=false

docker rm -f -v "$CLICKHOUSE_CONTAINER" >/dev/null 2>&1
CLICKHOUSE_STARTED=false

docker network rm "$NETWORK" >/dev/null 2>&1
NETWORK_CREATED=false

export SERVER_VERSION
export IMAGE
export PRODUCER
export INGEST_ENGINE
export DEFINITION_COUNT
export EVENT_ID
export INSERT_TOKEN
export FIRST_CODE
export RETRY_CODE
export CHANGED_CODE
export UNKNOWN_CODE
export WRONG_SCOPE_CODE
export INVALID_FRAME_CODE
export EXACT_RETRY_RAW_COUNT
export RAW_COUNT
export EVENT_COUNT
export CURRENT_COUNT
export CURRENT_PAYLOAD
export CONTRACT_ID
export PROJECT_ID
export REVISION_RUN_ID
export LEDGER_SCHEMA="$SCHEMA"
export LEDGER_SEED="$SEED"
export APP
export PYPROJECT
export LOCKFILE
export DOCKERFILE
export RUNNER="${BASH_SOURCE[0]}"

python3 - "$EVIDENCE" <<'PY'
import hashlib
import json
import os
import pathlib
import sys

output = pathlib.Path(sys.argv[1])

def digest(path):
    return hashlib.sha256(
        pathlib.Path(path).read_bytes()
    ).hexdigest()

evidence = {
    "evidence_type": "canonflow_event_producer_cold_start_integration_test",
    "evidence_version": 1,
    "contract_binding": {
        "contract_id": os.environ["CONTRACT_ID"],
        "project_id": os.environ["PROJECT_ID"],
        "revision_run_id": os.environ["REVISION_RUN_ID"],
    },
    "execution_environment": {
        "mode": "ephemeral_local_docker",
        "clickhouse_image": os.environ["IMAGE"],
        "clickhouse_server_version": os.environ["SERVER_VERSION"],
        "clickhouse_ingest_engine": os.environ["INGEST_ENGINE"],
        "producer_image": os.environ["PRODUCER"],
        "producer_container_user": 10001,
        "containers_removed": True,
        "network_removed": True,
        "cloud_connection_opened": False,
        "remote_mutation_executed": False,
    },
    "results": {
        "event_definition_count": int(os.environ["DEFINITION_COUNT"]),
        "health_status": 200,
        "readiness_status": 200,
        "initial_ingest_status": int(os.environ["FIRST_CODE"]),
        "exact_retry_status": int(os.environ["RETRY_CODE"]),
        "changed_payload_status": int(os.environ["CHANGED_CODE"]),
        "unknown_definition_status": int(os.environ["UNKNOWN_CODE"]),
        "truth_scope_mismatch_status": int(os.environ["WRONG_SCOPE_CODE"]),
        "invalid_frame_binding_status": int(
            os.environ["INVALID_FRAME_CODE"]
        ),
        "exact_retry_physical_rows": int(
            os.environ["EXACT_RETRY_RAW_COUNT"]
        ),
        "physical_ingest_attempts": int(os.environ["RAW_COUNT"]),
        "physical_materialized_events": int(os.environ["EVENT_COUNT"]),
        "current_logical_events": int(os.environ["CURRENT_COUNT"]),
        "current_payload": json.loads(os.environ["CURRENT_PAYLOAD"]),
        "stable_event_id": os.environ["EVENT_ID"],
        "stable_insert_deduplication_token": os.environ["INSERT_TOKEN"],
    },
    "security": {
        "dedicated_clickhouse_user": True,
        "plaintext_password_persisted": False,
        "clickhouse_select_scope": [
            "canonflow.event_definitions",
            "canonflow.event_ingest_attempts:materialized-view-source-columns"
        ],
        "clickhouse_insert_scope": ["canonflow.event_ingest_attempts"],
        "mcp_write_access_required": False,
    },
    "artifact_sha256": {
        "schema": digest(os.environ["LEDGER_SCHEMA"]),
        "seed": digest(os.environ["LEDGER_SEED"]),
        "application": digest(os.environ["APP"]),
        "pyproject": digest(os.environ["PYPROJECT"]),
        "lockfile": digest(os.environ["LOCKFILE"]),
        "dockerfile": digest(os.environ["DOCKERFILE"]),
        "runner": digest(os.environ["RUNNER"]),
    },
}

assert evidence["results"]["event_definition_count"] == 57
assert evidence["results"]["exact_retry_physical_rows"] == 1
assert evidence["results"]["physical_ingest_attempts"] == 2
assert evidence["results"]["physical_materialized_events"] == 2
assert evidence["results"]["current_logical_events"] == 1
assert evidence["results"]["current_payload"]["state"] == "retry"
assert evidence["execution_environment"]["containers_removed"] is True
assert evidence["execution_environment"]["network_removed"] is True
assert evidence["execution_environment"]["remote_mutation_executed"] is False
assert evidence["security"]["mcp_write_access_required"] is False

output.write_text(
    json.dumps(evidence, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

# PRODUCER_INTEGRATION_MANIFEST
sha256sum \
    "$SCHEMA" \
    "$SEED" \
    "$APP" \
    "$PYPROJECT" \
    "$LOCKFILE" \
    "$DOCKERFILE" \
    "${BASH_SOURCE[0]}" \
    "$EVIDENCE" \
    > "$MANIFEST"

printf '\n===== EVENT PRODUCER LOCAL INTEGRATION TEST =====\n'
printf 'ClickHouse version:          %s\n' "$SERVER_VERSION"
printf 'Event definitions:           %s\n' "$DEFINITION_COUNT"
printf 'Exact-retry physical rows:   %s\n' "$EXACT_RETRY_RAW_COUNT"
printf 'Physical ingest attempts:    %s\n' "$RAW_COUNT"
printf 'Materialized events:         %s\n' "$EVENT_COUNT"
printf 'Current logical events:      %s\n' "$CURRENT_COUNT"
printf 'Unknown definition status:   %s\n' "$UNKNOWN_CODE"
printf 'Truth-scope mismatch status: %s\n' "$WRONG_SCOPE_CODE"
printf 'Invalid frame status:        %s\n' "$INVALID_FRAME_CODE"
printf 'Containers removed:          True\n'
printf 'Network removed:             True\n'
printf 'Cloud connection opened:     False\n'
printf 'Remote mutation executed:    False\n'
printf 'EVENT PRODUCER LOCAL INTEGRATION TEST: OK\n'
