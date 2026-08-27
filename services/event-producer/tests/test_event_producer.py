from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from canonflow_event_producer.app import (
    ContractBindingError,
    DefinitionNotFoundError,
    EventDefinition,
    EventProducer,
    EventRequest,
    EventVersionMismatchError,
    Settings,
    TruthScopeMismatchError,
)


CONTRACT_ID = uuid.UUID("e17828fb-49b1-5df0-9c45-385a68f5f9d1")
PROJECT_ID = uuid.UUID("e8627781-5bf3-4c4d-905f-8dda49ab53d6")
REVISION_RUN_ID = uuid.UUID("68c47a53-2725-47ae-a910-489bd8b894e0")


class FakeRepository:
    def __init__(
        self,
        definition: EventDefinition | None,
    ) -> None:
        self.definition = definition
        self.insertions: list[tuple[list[Any], str]] = []

    def find_definition(
        self,
        *,
        contract_id: uuid.UUID,
        event_name: str,
    ) -> EventDefinition | None:
        return self.definition

    def insert_attempt(
        self,
        *,
        row: list[Any],
        deduplication_token: str,
    ) -> None:
        self.insertions.append((row, deduplication_token))

    def ping(self) -> None:
        return None

    def close(self) -> None:
        return None


def settings() -> Settings:
    return Settings(
        clickhouse_host="localhost",
        clickhouse_port=8443,
        clickhouse_user="test",
        clickhouse_password="test",
        clickhouse_database="canonflow",
        clickhouse_secure=True,
        clickhouse_verify=True,
        clickhouse_connect_timeout=10,
        clickhouse_send_receive_timeout=30,
        contract_id=CONTRACT_ID,
        project_id=PROJECT_ID,
    )


def event_request(**overrides: Any) -> EventRequest:
    values: dict[str, Any] = {
        "event_name": "nscl.reactor.output.changed",
        "event_version": 1,
        "project_id": PROJECT_ID,
        "revision_run_id": REVISION_RUN_ID,
        "contract_id": CONTRACT_ID,
        "deduplication_key": "reactor-output:scene-001:000001",
        "timeline_version": None,
        "scene_id": "scene-001",
        "shot_id": None,
        "beat_id": None,
        "frame_index": None,
        "fps_numerator": None,
        "fps_denominator": None,
        "occurred_at": datetime(
            2026,
            8,
            27,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        "source_service": "canonflow-test",
        "source_instance": "unit-test-1",
        "truth_scope": "system_truth",
        "payload_version": 1,
        "payload": {
            "state": "active",
            "value": 400,
            "unit": "percent",
        },
        "producer_sequence": 1,
        "attributes": {"environment": "test"},
    }
    values.update(overrides)
    return EventRequest.model_validate(values)


class EventProducerTests(unittest.TestCase):
    def test_stable_event_id_and_insert_token_for_exact_retry(self) -> None:
        repository = FakeRepository(
            EventDefinition(
                event_version=1,
                truth_scope="system_truth",
            )
        )
        producer = EventProducer(
            settings=settings(),
            repository=repository,
        )
        event = event_request()

        first = producer.ingest(event)
        second = producer.ingest(event)

        self.assertEqual(first.event_id, second.event_id)
        self.assertEqual(
            first.insert_deduplication_token,
            second.insert_deduplication_token,
        )
        self.assertNotEqual(
            first.ingest_attempt_id,
            second.ingest_attempt_id,
        )
        self.assertEqual(len(repository.insertions), 2)
        self.assertEqual(
            repository.insertions[0][1],
            repository.insertions[1][1],
        )

    def test_changed_payload_creates_new_insert_token(self) -> None:
        repository = FakeRepository(
            EventDefinition(
                event_version=1,
                truth_scope="system_truth",
            )
        )
        producer = EventProducer(
            settings=settings(),
            repository=repository,
        )

        first = producer.ingest(event_request())
        second = producer.ingest(
            event_request(
                payload={
                    "state": "retry",
                    "value": 400,
                    "unit": "percent",
                }
            )
        )

        self.assertEqual(first.event_id, second.event_id)
        self.assertNotEqual(
            first.insert_deduplication_token,
            second.insert_deduplication_token,
        )

    def test_unknown_event_is_rejected(self) -> None:
        producer = EventProducer(
            settings=settings(),
            repository=FakeRepository(None),
        )

        with self.assertRaises(DefinitionNotFoundError):
            producer.ingest(event_request())

    def test_event_version_mismatch_is_rejected(self) -> None:
        producer = EventProducer(
            settings=settings(),
            repository=FakeRepository(
                EventDefinition(
                    event_version=2,
                    truth_scope="system_truth",
                )
            ),
        )

        with self.assertRaises(EventVersionMismatchError):
            producer.ingest(event_request())

    def test_truth_scope_mismatch_is_rejected(self) -> None:
        producer = EventProducer(
            settings=settings(),
            repository=FakeRepository(
                EventDefinition(
                    event_version=1,
                    truth_scope="character_knowledge",
                )
            ),
        )

        with self.assertRaises(TruthScopeMismatchError):
            producer.ingest(event_request())

    def test_contract_binding_is_rejected(self) -> None:
        producer = EventProducer(
            settings=settings(),
            repository=FakeRepository(
                EventDefinition(
                    event_version=1,
                    truth_scope="system_truth",
                )
            ),
        )

        with self.assertRaises(ContractBindingError):
            producer.ingest(
                event_request(contract_id=uuid.uuid4())
            )

    def test_project_binding_is_rejected(self) -> None:
        producer = EventProducer(
            settings=settings(),
            repository=FakeRepository(
                EventDefinition(
                    event_version=1,
                    truth_scope="system_truth",
                )
            ),
        )

        with self.assertRaises(ContractBindingError):
            producer.ingest(
                event_request(project_id=uuid.uuid4())
            )

    def test_partial_fps_pair_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            event_request(
                frame_index=100,
                fps_numerator=24,
                fps_denominator=None,
                timeline_version="timeline-v1",
                shot_id="shot-001",
                beat_id="beat-001",
            )

    def test_incomplete_frame_binding_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            event_request(
                frame_index=100,
                fps_numerator=24,
                fps_denominator=1,
                timeline_version=None,
                shot_id="shot-001",
                beat_id="beat-001",
            )

    def test_valid_frame_binding_is_accepted(self) -> None:
        request = event_request(
            frame_index=100,
            fps_numerator=24,
            fps_denominator=1,
            timeline_version="timeline-v1",
            shot_id="shot-001",
            beat_id="beat-001",
        )

        self.assertEqual(request.frame_index, 100)


if __name__ == "__main__":
    unittest.main()
