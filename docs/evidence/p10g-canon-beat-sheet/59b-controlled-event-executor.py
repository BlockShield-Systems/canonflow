#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_PROJECT_ID = "e8627781-5bf3-4c4d-905f-8dda49ab53d6"
EXPECTED_CONTRACT_ID = "e17828fb-49b1-5df0-9c45-385a68f5f9d1"
EXPECTED_EVENT_ID = "3b2a7e9f-f8bf-5f7c-8717-1a0a231e4177"
EXPECTED_EVENT_NAME = "nscl.force_amplification.set"
EXPECTED_DEDUPLICATION_KEY = (
    "cloud-run-smoke:bfc9b4ae-c196-4ef8-bc84-8e78f395570b"
)
EXPECTED_PROPOSAL_SHA256 = (
    "6211ed6096a55d6b54311921d102e8d650d6850e8e474a44f5fca9cd5888704e"
)
EXPECTED_INSERT_TOKEN = (
    "fae6a7ab8d532a5613dd0ead06a5ea7ad66728c5f7e592b302f88b27c8291aad"
)
EXPECTED_SERVICE_URL = (
    "https://canonflow-event-producer-ektxaloq2a-ez.a.run.app"
)
EXPECTED_SERVICE_ACCOUNT = (
    "canonflow-event-writer@"
    "canonflow-agentic-cinema.iam.gserviceaccount.com"
)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path}")

    return value


def validate(
    proposal_path: Path,
    approval_path: Path,
    service_url: str,
    service_account: str,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    proposal_bytes = proposal_path.read_bytes()
    proposal_sha256 = sha256_bytes(proposal_bytes)

    if proposal_sha256 != EXPECTED_PROPOSAL_SHA256:
        raise RuntimeError(
            "Proposal SHA-256 mismatch: "
            f"expected {EXPECTED_PROPOSAL_SHA256}, "
            f"got {proposal_sha256}"
        )

    proposal = load_json(proposal_path)
    approval = load_json(approval_path)

    if approval.get("approved") is not True:
        raise RuntimeError("Approval is not affirmative.")

    if approval.get("status") != "approved":
        raise RuntimeError("Approval status is not approved.")

    if approval.get("approved_by") != "Demian":
        raise RuntimeError("Unexpected approval authority.")

    if approval.get("proposal_sha256") != proposal_sha256:
        raise RuntimeError("Approval is bound to a different proposal.")

    if approval.get("execution_scope") != "single_exact_retry":
        raise RuntimeError("Approval scope is not single_exact_retry.")

    if approval.get("maximum_http_requests") != 1:
        raise RuntimeError("Approval does not permit exactly one request.")

    expected_proposal_fields = {
        "project_id": EXPECTED_PROJECT_ID,
        "contract_id": EXPECTED_CONTRACT_ID,
        "event_name": EXPECTED_EVENT_NAME,
        "deduplication_key": EXPECTED_DEDUPLICATION_KEY,
    }

    for name, expected in expected_proposal_fields.items():
        actual = proposal.get(name)

        if actual != expected:
            raise RuntimeError(
                f"Proposal field {name} mismatch: "
                f"expected {expected!r}, got {actual!r}"
            )

    canonical_request = canonical_json(proposal)
    insert_token = sha256_bytes(
        canonical_request.encode("utf-8")
    )

    if insert_token != EXPECTED_INSERT_TOKEN:
        raise RuntimeError(
            "Canonical insert token mismatch: "
            f"expected {EXPECTED_INSERT_TOKEN}, got {insert_token}"
        )

    event_id = uuid.uuid5(
        uuid.UUID(proposal["contract_id"]),
        ":".join(
            (
                proposal["project_id"],
                proposal["revision_run_id"],
                proposal["deduplication_key"],
            )
        ),
    )

    if str(event_id) != EXPECTED_EVENT_ID:
        raise RuntimeError(
            f"Deterministic event_id mismatch: {event_id}"
        )

    if service_url.rstrip("/") != EXPECTED_SERVICE_URL:
        raise RuntimeError("Unexpected Event Producer service URL.")

    if service_account != EXPECTED_SERVICE_ACCOUNT:
        raise RuntimeError("Unexpected executor service account.")

    return proposal, approval, canonical_request


def acquire_identity_token(
    service_url: str,
    service_account: str,
) -> str:
    command = [
        "gcloud",
        "auth",
        "print-identity-token",
        f"--impersonate-service-account={service_account}",
        f"--audiences={service_url}",
    ]

    result = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Identity-token generation failed: "
            f"{result.stderr.strip()}"
        )

    token = result.stdout.strip()

    if not token:
        raise RuntimeError("Identity-token generation returned an empty token.")

    return token


def execute_request(
    service_url: str,
    token: str,
    canonical_request: str,
) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        url=f"{service_url.rstrip('/')}/v1/events",
        data=canonical_request.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=120,
        ) as response:
            status = response.status
            response_bytes = response.read()
    except urllib.error.HTTPError as error:
        response_bytes = error.read()
        raise RuntimeError(
            f"Event Producer returned HTTP {error.code}: "
            f"{response_bytes.decode('utf-8', errors='replace')}"
        ) from error

    try:
        response_json = json.loads(response_bytes)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "Event Producer returned invalid JSON."
        ) from error

    if not isinstance(response_json, dict):
        raise RuntimeError("Event Producer response is not an object.")

    return status, response_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--service-url", required=True)
    parser.add_argument("--service-account", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    try:
        proposal, approval, canonical_request = validate(
            proposal_path=args.proposal,
            approval_path=args.approval,
            service_url=args.service_url,
            service_account=args.service_account,
        )

        print("PASS: Proposal SHA-256 matches approval.")
        print("PASS: Proposal is bound to the approved project and contract.")
        print("PASS: Deterministic event ID and insert token are stable.")
        print("PASS: Approval permits exactly one exact-retry request.")

        if not args.execute:
            print("DRY RUN: No HTTP request sent.")
            return 0

        if args.evidence.exists():
            raise RuntimeError(
                f"Refusing to overwrite evidence: {args.evidence}"
            )

        token = acquire_identity_token(
            service_url=args.service_url,
            service_account=args.service_account,
        )

        try:
            status, response = execute_request(
                service_url=args.service_url,
                token=token,
                canonical_request=canonical_request,
            )
        finally:
            del token

        if status != 202:
            raise RuntimeError(
                f"Expected HTTP 202, received {status}."
            )

        expected_response_fields = {
            "event_id": EXPECTED_EVENT_ID,
            "deduplication_key": EXPECTED_DEDUPLICATION_KEY,
            "insert_deduplication_token": EXPECTED_INSERT_TOKEN,
            "status": "accepted_or_deduplicated",
        }

        for name, expected in expected_response_fields.items():
            actual = response.get(name)

            if actual != expected:
                raise RuntimeError(
                    f"Response field {name} mismatch: "
                    f"expected {expected!r}, got {actual!r}"
                )

        evidence = {
            "schema_version": "1.0",
            "evidence_type": (
                "canonflow_controlled_event_exact_retry_execution"
            ),
            "status": "success",
            "executed_at_utc": datetime.now(timezone.utc).isoformat(),
            "approved_by": approval["approved_by"],
            "proposal_sha256": EXPECTED_PROPOSAL_SHA256,
            "service_url": EXPECTED_SERVICE_URL,
            "executor_service_account": EXPECTED_SERVICE_ACCOUNT,
            "maximum_http_requests": 1,
            "http_requests_executed": 1,
            "http_status": status,
            "event_id": response["event_id"],
            "ingest_attempt_id": response["ingest_attempt_id"],
            "deduplication_key": response["deduplication_key"],
            "insert_deduplication_token": (
                response["insert_deduplication_token"]
            ),
            "producer_status": response["status"],
            "expected_logical_effect": "exact_retry_no_new_logical_event",
            "identity_token_persisted": False,
        }

        args.evidence.write_text(
            json.dumps(
                evidence,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

        print(f"HTTP status     : {status}")
        print(f"Event ID        : {response['event_id']}")
        print(f"Ingest attempt  : {response['ingest_attempt_id']}")
        print(f"Execution proof : {args.evidence}")
        print("CONTROLLED EVENT EXACT RETRY: SUCCESS")
        return 0

    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
