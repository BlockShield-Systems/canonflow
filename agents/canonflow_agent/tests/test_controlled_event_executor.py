from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path
from types import ModuleType
from unittest.mock import patch


AGENTS_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = AGENTS_ROOT.parent
SCRIPT_PATH = (
    AGENTS_ROOT
    / "scripts"
    / "execute_approved_event.py"
)
EVIDENCE_DIR = (
    REPOSITORY_ROOT
    / "docs"
    / "evidence"
    / "p10g-canon-beat-sheet"
)
PROPOSAL_PATH = (
    EVIDENCE_DIR
    / "59-controlled-event-proposal.json"
)
APPROVAL_PATH = (
    EVIDENCE_DIR
    / "59a-controlled-event-approval.json"
)


def load_executor() -> ModuleType:
    specification = importlib.util.spec_from_file_location(
        "canonflow_controlled_event_executor",
        SCRIPT_PATH,
    )

    assert specification is not None
    assert specification.loader is not None

    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)

    return module


executor = load_executor()


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_validates_archived_proposal_and_approval() -> None:
    proposal, approval, canonical_request = executor.validate(
        proposal_path=PROPOSAL_PATH,
        approval_path=APPROVAL_PATH,
        service_url=executor.EXPECTED_SERVICE_URL,
        service_account=executor.EXPECTED_SERVICE_ACCOUNT,
    )

    assert proposal["event_name"] == executor.EXPECTED_EVENT_NAME
    assert approval["approved"] is True

    canonical_value = json.loads(canonical_request)

    assert canonical_value == proposal
    assert (
        executor.sha256_bytes(
            canonical_request.encode("utf-8")
        )
        == executor.EXPECTED_INSERT_TOKEN
    )


def test_rejects_modified_proposal() -> None:
    proposal = json.loads(
        PROPOSAL_PATH.read_text(encoding="utf-8")
    )
    proposal["payload"]["value"] = 401

    with tempfile.TemporaryDirectory() as directory:
        modified_path = Path(directory) / "proposal.json"
        write_json(modified_path, proposal)

        try:
            executor.validate(
                proposal_path=modified_path,
                approval_path=APPROVAL_PATH,
                service_url=executor.EXPECTED_SERVICE_URL,
                service_account=executor.EXPECTED_SERVICE_ACCOUNT,
            )
        except RuntimeError as error:
            assert "Proposal SHA-256 mismatch" in str(error)
        else:
            raise AssertionError(
                "Modified proposal was unexpectedly accepted."
            )


def test_rejects_nonaffirmative_approval() -> None:
    approval = json.loads(
        APPROVAL_PATH.read_text(encoding="utf-8")
    )
    approval["approved"] = False

    with tempfile.TemporaryDirectory() as directory:
        approval_path = Path(directory) / "approval.json"
        write_json(approval_path, approval)

        try:
            executor.validate(
                proposal_path=PROPOSAL_PATH,
                approval_path=approval_path,
                service_url=executor.EXPECTED_SERVICE_URL,
                service_account=executor.EXPECTED_SERVICE_ACCOUNT,
            )
        except RuntimeError as error:
            assert "Approval is not affirmative" in str(error)
        else:
            raise AssertionError(
                "Nonaffirmative approval was unexpectedly accepted."
            )


def test_rejects_unapproved_service_url() -> None:
    try:
        executor.validate(
            proposal_path=PROPOSAL_PATH,
            approval_path=APPROVAL_PATH,
            service_url="https://example.invalid",
            service_account=executor.EXPECTED_SERVICE_ACCOUNT,
        )
    except RuntimeError as error:
        assert "Unexpected Event Producer service URL" in str(error)
    else:
        raise AssertionError(
            "Unexpected service URL was accepted."
        )


def test_rejects_unapproved_service_account() -> None:
    try:
        executor.validate(
            proposal_path=PROPOSAL_PATH,
            approval_path=APPROVAL_PATH,
            service_url=executor.EXPECTED_SERVICE_URL,
            service_account=(
                "unauthorized@"
                "canonflow-agentic-cinema.iam.gserviceaccount.com"
            ),
        )
    except RuntimeError as error:
        assert "Unexpected executor service account" in str(error)
    else:
        raise AssertionError(
            "Unexpected service account was accepted."
        )


def test_dry_run_performs_no_external_operation() -> None:
    with tempfile.TemporaryDirectory() as directory:
        evidence_path = Path(directory) / "execution.json"

        arguments = [
            str(SCRIPT_PATH),
            "--proposal",
            str(PROPOSAL_PATH),
            "--approval",
            str(APPROVAL_PATH),
            "--service-url",
            executor.EXPECTED_SERVICE_URL,
            "--service-account",
            executor.EXPECTED_SERVICE_ACCOUNT,
            "--evidence",
            str(evidence_path),
        ]

        with (
            patch.object(sys, "argv", arguments),
            patch.object(
                executor,
                "acquire_identity_token",
                side_effect=AssertionError(
                    "Dry-run attempted token acquisition."
                ),
            ) as token_mock,
            patch.object(
                executor,
                "execute_request",
                side_effect=AssertionError(
                    "Dry-run attempted an HTTP request."
                ),
            ) as request_mock,
        ):
            status = executor.main()

        assert status == 0
        assert token_mock.call_count == 0
        assert request_mock.call_count == 0
        assert not evidence_path.exists()


def test_mocked_execute_records_exactly_one_request() -> None:
    ingest_attempt_id = (
        "b2df470d-cf43-4dd2-a1e0-5e19713b833b"
    )

    response = {
        "event_id": executor.EXPECTED_EVENT_ID,
        "ingest_attempt_id": ingest_attempt_id,
        "deduplication_key": (
            executor.EXPECTED_DEDUPLICATION_KEY
        ),
        "status": "accepted_or_deduplicated",
        "insert_deduplication_token": (
            executor.EXPECTED_INSERT_TOKEN
        ),
    }

    with tempfile.TemporaryDirectory() as directory:
        evidence_path = Path(directory) / "execution.json"
        state_dir = Path(directory) / "execution-state"

        arguments = [
            str(SCRIPT_PATH),
            "--proposal",
            str(PROPOSAL_PATH),
            "--approval",
            str(APPROVAL_PATH),
            "--service-url",
            executor.EXPECTED_SERVICE_URL,
            "--service-account",
            executor.EXPECTED_SERVICE_ACCOUNT,
            "--evidence",
            str(evidence_path),
            "--execution-state-dir",
            str(state_dir),
            "--execute",
        ]

        with (
            patch.object(sys, "argv", arguments),
            patch.object(
                executor,
                "acquire_identity_token",
                return_value="unit-test-token",
            ) as token_mock,
            patch.object(
                executor,
                "execute_request",
                return_value=(202, response),
            ) as request_mock,
        ):
            status = executor.main()

        assert status == 0
        assert token_mock.call_count == 1
        assert request_mock.call_count == 1
        assert evidence_path.is_file()

        evidence = json.loads(
            evidence_path.read_text(encoding="utf-8")
        )

        assert evidence["status"] == "success"
        assert evidence["http_requests_executed"] == 1
        assert evidence["maximum_http_requests"] == 1
        assert evidence["http_status"] == 202
        assert evidence["identity_token_persisted"] is False
        assert evidence["execution_claim_persisted"] is True
        assert "unit-test-token" not in json.dumps(evidence)

        claims = list(state_dir.glob("*.claimed.json"))

        assert len(claims) == 1
        assert claims[0].is_file()


def test_execution_claim_is_single_use() -> None:
    with tempfile.TemporaryDirectory() as directory:
        state_dir = Path(directory) / "execution-state"

        first_claim = executor.claim_execution(
            state_dir=state_dir,
            proposal_sha256=executor.EXPECTED_PROPOSAL_SHA256,
        )

        assert first_claim.is_file()

        try:
            executor.claim_execution(
                state_dir=state_dir,
                proposal_sha256=executor.EXPECTED_PROPOSAL_SHA256,
            )
        except RuntimeError as error:
            assert "Execution claim already exists" in str(error)
        else:
            raise AssertionError(
                "A second execution claim was unexpectedly created."
            )

        claims = list(state_dir.glob("*.claimed.json"))

        assert claims == [first_claim]


def test_existing_evidence_blocks_before_token_acquisition() -> None:
    with tempfile.TemporaryDirectory() as directory:
        evidence_path = Path(directory) / "execution.json"
        evidence_path.write_text(
            '{"status":"existing"}\n',
            encoding="utf-8",
        )

        arguments = [
            str(SCRIPT_PATH),
            "--proposal",
            str(PROPOSAL_PATH),
            "--approval",
            str(APPROVAL_PATH),
            "--service-url",
            executor.EXPECTED_SERVICE_URL,
            "--service-account",
            executor.EXPECTED_SERVICE_ACCOUNT,
            "--evidence",
            str(evidence_path),
            "--execute",
        ]

        error_output = io.StringIO()

        with redirect_stderr(error_output):
            with (
                patch.object(sys, "argv", arguments),
                patch.object(
                    executor,
                    "acquire_identity_token",
                    side_effect=AssertionError(
                        "Token acquisition occurred after replay guard."
                    ),
                ) as token_mock,
                patch.object(
                    executor,
                    "execute_request",
                    side_effect=AssertionError(
                        "HTTP request occurred after replay guard."
                    ),
                ) as request_mock,
            ):
                status = executor.main()

        assert status == 1
        assert "Refusing to overwrite evidence" in error_output.getvalue()
        assert token_mock.call_count == 0
        assert request_mock.call_count == 0

        existing = json.loads(
            evidence_path.read_text(encoding="utf-8")
        )
        assert existing == {"status": "existing"}


def main() -> None:
    tests = [
        test_validates_archived_proposal_and_approval,
        test_rejects_modified_proposal,
        test_rejects_nonaffirmative_approval,
        test_rejects_unapproved_service_url,
        test_rejects_unapproved_service_account,
        test_dry_run_performs_no_external_operation,
        test_mocked_execute_records_exactly_one_request,
        test_execution_claim_is_single_use,
        test_existing_evidence_blocks_before_token_acquisition,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print(
        f"\nControlled-event executor tests passed: "
        f"{len(tests)}"
    )
    print("CANONFLOW CONTROLLED EVENT EXECUTOR: OK")


if __name__ == "__main__":
    main()
