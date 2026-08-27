from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any, Protocol

import clickhouse_connect
from clickhouse_connect.driver.exceptions import OperationalError
import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
    model_validator,
)

LOGGER = logging.getLogger("canonflow.event_producer")

NonEmptyString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=512),
]

ShortString = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]


class TruthScope(StrEnum):
    SYSTEM_TRUTH = "system_truth"
    CHARACTER_KNOWLEDGE = "character_knowledge"
    CHARACTER_OBSERVATION = "character_observation"
    DECLARED_INTENT = "declared_intent"
    REPORTED_EXTERNAL_STATE = "reported_external_state"


class EventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_name: ShortString
    event_version: int = Field(ge=1, le=65535)

    project_id: uuid.UUID
    revision_run_id: uuid.UUID
    contract_id: uuid.UUID
    deduplication_key: NonEmptyString

    timeline_version: str | None = Field(default=None, max_length=256)
    scene_id: str | None = Field(default=None, max_length=256)
    shot_id: str | None = Field(default=None, max_length=256)
    beat_id: str | None = Field(default=None, max_length=256)

    frame_index: int | None = Field(default=None, ge=0)
    fps_numerator: int | None = Field(default=None, ge=1, le=4_294_967_295)
    fps_denominator: int | None = Field(default=None, ge=1, le=4_294_967_295)

    occurred_at: datetime

    source_service: ShortString
    source_instance: NonEmptyString
    truth_scope: TruthScope

    payload_version: int = Field(ge=1, le=65535)
    payload: dict[str, JsonValue]
    producer_sequence: int | None = Field(
        default=None,
        ge=0,
        le=18_446_744_073_709_551_615,
    )
    attributes: dict[str, str] = Field(default_factory=dict)

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_must_be_timezone_aware(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")

        return value.astimezone(timezone.utc)

    @field_validator("attributes")
    @classmethod
    def validate_attributes(
        cls,
        value: dict[str, str],
    ) -> dict[str, str]:
        if len(value) > 64:
            raise ValueError("attributes may contain at most 64 entries")

        for key, item in value.items():
            if not key or len(key) > 128:
                raise ValueError(
                    "attribute keys must contain 1 to 128 characters"
                )

            if len(item) > 2048:
                raise ValueError(
                    "attribute values may contain at most 2048 characters"
                )

        return value

    @model_validator(mode="after")
    def validate_timeline_binding(self) -> EventRequest:
        fps_values = (self.fps_numerator, self.fps_denominator)

        if (fps_values[0] is None) != (fps_values[1] is None):
            raise ValueError(
                "fps_numerator and fps_denominator must both be set or null"
            )

        frame_fields_present = (
            self.frame_index is not None
            or self.fps_numerator is not None
            or self.fps_denominator is not None
        )

        if frame_fields_present:
            missing = [
                name
                for name, value in (
                    ("frame_index", self.frame_index),
                    ("fps_numerator", self.fps_numerator),
                    ("fps_denominator", self.fps_denominator),
                    ("timeline_version", self.timeline_version),
                    ("shot_id", self.shot_id),
                    ("beat_id", self.beat_id),
                )
                if value is None
            ]

            if missing:
                raise ValueError(
                    "frame-bound events require: " + ", ".join(missing)
                )

        return self


class IngestResponse(BaseModel):
    event_id: uuid.UUID
    ingest_attempt_id: uuid.UUID
    deduplication_key: str
    status: str
    insert_deduplication_token: str


class DefinitionNotFoundError(ValueError):
    pass


class EventVersionMismatchError(ValueError):
    pass


class TruthScopeMismatchError(ValueError):
    pass


class ContractBindingError(ValueError):
    pass


@dataclass(frozen=True)
class EventDefinition:
    event_version: int
    truth_scope: str


@dataclass(frozen=True)
class Settings:
    clickhouse_host: str
    clickhouse_port: int
    clickhouse_user: str
    clickhouse_password: str
    clickhouse_database: str
    clickhouse_secure: bool
    clickhouse_verify: bool
    clickhouse_connect_timeout: int
    clickhouse_send_receive_timeout: int
    contract_id: uuid.UUID
    project_id: uuid.UUID
    clickhouse_startup_max_attempts: int = 5
    clickhouse_startup_initial_delay_seconds: float = 5.0
    clickhouse_startup_max_delay_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.clickhouse_startup_max_attempts < 1:
            raise ValueError(
                "CLICKHOUSE_STARTUP_MAX_ATTEMPTS must be at least 1"
            )

        if self.clickhouse_startup_initial_delay_seconds < 0:
            raise ValueError(
                "CLICKHOUSE_STARTUP_INITIAL_DELAY_SECONDS must be non-negative"
            )

        if self.clickhouse_startup_max_delay_seconds < 0:
            raise ValueError(
                "CLICKHOUSE_STARTUP_MAX_DELAY_SECONDS must be non-negative"
            )

    @classmethod
    def from_environment(cls) -> Settings:
        database = os.getenv("CLICKHOUSE_DATABASE", "canonflow").strip()

        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database):
            raise RuntimeError(
                f"Unsafe CLICKHOUSE_DATABASE identifier: {database!r}"
            )

        return cls(
            clickhouse_host=required_environment("CLICKHOUSE_HOST"),
            clickhouse_port=int(
                os.getenv("CLICKHOUSE_PORT", "8443")
            ),
            clickhouse_user=required_environment("CLICKHOUSE_USER"),
            clickhouse_password=required_environment(
                "CLICKHOUSE_PASSWORD"
            ),
            clickhouse_database=database,
            clickhouse_secure=environment_bool(
                "CLICKHOUSE_SECURE",
                True,
            ),
            clickhouse_verify=environment_bool(
                "CLICKHOUSE_VERIFY",
                True,
            ),
            clickhouse_connect_timeout=int(
                os.getenv("CLICKHOUSE_CONNECT_TIMEOUT", "10")
            ),
            clickhouse_send_receive_timeout=int(
                os.getenv("CLICKHOUSE_SEND_RECEIVE_TIMEOUT", "30")
            ),
            clickhouse_startup_max_attempts=int(
                os.getenv("CLICKHOUSE_STARTUP_MAX_ATTEMPTS", "5")
            ),
            clickhouse_startup_initial_delay_seconds=float(
                os.getenv(
                    "CLICKHOUSE_STARTUP_INITIAL_DELAY_SECONDS",
                    "5",
                )
            ),
            clickhouse_startup_max_delay_seconds=float(
                os.getenv(
                    "CLICKHOUSE_STARTUP_MAX_DELAY_SECONDS",
                    "30",
                )
            ),
            contract_id=uuid.UUID(
                required_environment("CANONFLOW_EVENT_CONTRACT_ID")
            ),
            project_id=uuid.UUID(
                required_environment("CANONFLOW_PROJECT_ID")
            ),
        )


class EventRepository(Protocol):
    def find_definition(
        self,
        *,
        contract_id: uuid.UUID,
        event_name: str,
    ) -> EventDefinition | None:
        ...

    def insert_attempt(
        self,
        *,
        row: list[Any],
        deduplication_token: str,
    ) -> None:
        ...

    def ping(self) -> None:
        ...

    def close(self) -> None:
        ...


class ClickHouseEventRepository:
    COLUMN_NAMES = [
        "ingest_attempt_id",
        "event_id",
        "deduplication_key",
        "event_name",
        "event_version",
        "project_id",
        "revision_run_id",
        "contract_id",
        "timeline_version",
        "scene_id",
        "shot_id",
        "beat_id",
        "frame_index",
        "fps_numerator",
        "fps_denominator",
        "occurred_at",
        "ingested_at",
        "source_service",
        "source_instance",
        "truth_scope",
        "payload_version",
        "payload_json",
        "producer_sequence",
        "attributes",
    ]

    def __init__(self, settings: Settings) -> None:
        self._database = settings.clickhouse_database
        self._client = clickhouse_connect.get_client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password,
            database=settings.clickhouse_database,
            secure=settings.clickhouse_secure,
            verify=settings.clickhouse_verify,
            connect_timeout=settings.clickhouse_connect_timeout,
            send_receive_timeout=(
                settings.clickhouse_send_receive_timeout
            ),
            autogenerate_session_id=False,
        )

    def find_definition(
        self,
        *,
        contract_id: uuid.UUID,
        event_name: str,
    ) -> EventDefinition | None:
        result = self._client.query(
            f"""
            SELECT
                event_version,
                toString(truth_scope)
            FROM `{self._database}`.`event_definitions` FINAL
            WHERE contract_id = {{contract_id:UUID}}
              AND event_name = {{event_name:String}}
            ORDER BY event_version DESC
            LIMIT 1
            """,
            parameters={
                "contract_id": str(contract_id),
                "event_name": event_name,
            },
        )

        if not result.result_rows:
            return None

        event_version, truth_scope = result.result_rows[0]

        return EventDefinition(
            event_version=int(event_version),
            truth_scope=str(truth_scope),
        )

    def insert_attempt(
        self,
        *,
        row: list[Any],
        deduplication_token: str,
    ) -> None:
        self._client.insert(
            f"{self._database}.event_ingest_attempts",
            [row],
            column_names=self.COLUMN_NAMES,
            settings={
                "async_insert": 0,
                "deduplicate_insert": "enable",
                "deduplicate_blocks_in_dependent_materialized_views": 1,
                "insert_deduplication_token": deduplication_token,
            },
        )

    def ping(self) -> None:
        self._client.command("SELECT 1")

    def close(self) -> None:
        self._client.close()


class EventProducer:
    def __init__(
        self,
        *,
        settings: Settings,
        repository: EventRepository,
    ) -> None:
        self._settings = settings
        self._repository = repository

    def ingest(self, request: EventRequest) -> IngestResponse:
        if request.contract_id != self._settings.contract_id:
            raise ContractBindingError(
                "contract_id does not match the deployed contract"
            )

        if request.project_id != self._settings.project_id:
            raise ContractBindingError(
                "project_id does not match the configured project"
            )

        definition = self._repository.find_definition(
            contract_id=request.contract_id,
            event_name=request.event_name,
        )

        if definition is None:
            raise DefinitionNotFoundError(
                f"Unknown event definition: {request.event_name}"
            )

        if definition.event_version != request.event_version:
            raise EventVersionMismatchError(
                "event_version does not match the current definition: "
                f"expected {definition.event_version}, "
                f"received {request.event_version}"
            )

        if definition.truth_scope != request.truth_scope.value:
            raise TruthScopeMismatchError(
                "truth_scope does not match the event definition: "
                f"expected {definition.truth_scope}, "
                f"received {request.truth_scope.value}"
            )

        canonical_request = canonical_json(
            request.model_dump(mode="json")
        )
        payload_json = canonical_json(request.payload)

        deduplication_token = hashlib.sha256(
            canonical_request.encode("utf-8")
        ).hexdigest()

        event_id = uuid.uuid5(
            request.contract_id,
            ":".join(
                (
                    str(request.project_id),
                    str(request.revision_run_id),
                    request.deduplication_key,
                )
            ),
        )
        ingest_attempt_id = uuid.uuid4()
        ingested_at = datetime.now(timezone.utc)

        row: list[Any] = [
            ingest_attempt_id,
            event_id,
            request.deduplication_key,
            request.event_name,
            request.event_version,
            request.project_id,
            request.revision_run_id,
            request.contract_id,
            request.timeline_version,
            request.scene_id,
            request.shot_id,
            request.beat_id,
            request.frame_index,
            request.fps_numerator,
            request.fps_denominator,
            request.occurred_at,
            ingested_at,
            request.source_service,
            request.source_instance,
            request.truth_scope.value,
            request.payload_version,
            payload_json,
            request.producer_sequence,
            request.attributes,
        ]

        self._repository.insert_attempt(
            row=row,
            deduplication_token=deduplication_token,
        )

        LOGGER.info(
            "Event accepted event_id=%s event_name=%s revision_run_id=%s",
            event_id,
            request.event_name,
            request.revision_run_id,
        )

        return IngestResponse(
            event_id=event_id,
            ingest_attempt_id=ingest_attempt_id,
            deduplication_key=request.deduplication_key,
            status="accepted_or_deduplicated",
            insert_deduplication_token=deduplication_token,
        )

    def ping(self) -> None:
        self._repository.ping()

    def close(self) -> None:
        self._repository.close()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def required_environment(name: str) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise RuntimeError(f"Missing required environment variable: {name}")

    return value.strip()


def environment_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    normalized = value.strip().lower()

    if normalized in {"1", "true", "yes", "on"}:
        return True

    if normalized in {"0", "false", "no", "off"}:
        return False

    raise RuntimeError(f"Invalid boolean value for {name}: {value!r}")


async def create_clickhouse_repository_with_retry(
    settings: Settings,
) -> ClickHouseEventRepository:
    delay = settings.clickhouse_startup_initial_delay_seconds

    for attempt in range(
        1,
        settings.clickhouse_startup_max_attempts + 1,
    ):
        try:
            repository = await asyncio.to_thread(
                ClickHouseEventRepository,
                settings,
            )
        except OperationalError as error:
            if attempt >= settings.clickhouse_startup_max_attempts:
                LOGGER.error(
                    "ClickHouse startup connection exhausted "
                    "attempt=%d max_attempts=%d error=%s",
                    attempt,
                    settings.clickhouse_startup_max_attempts,
                    error,
                )
                raise

            retry_delay = min(
                delay,
                settings.clickhouse_startup_max_delay_seconds,
            )
            LOGGER.warning(
                "ClickHouse startup connection failed "
                "attempt=%d max_attempts=%d retry_delay_seconds=%.3f "
                "error=%s",
                attempt,
                settings.clickhouse_startup_max_attempts,
                retry_delay,
                error,
            )
            await asyncio.sleep(retry_delay)
            delay = min(
                max(delay * 2, retry_delay),
                settings.clickhouse_startup_max_delay_seconds,
            )
        else:
            if attempt > 1:
                LOGGER.info(
                    "ClickHouse startup connection recovered attempt=%d",
                    attempt,
                )
            return repository

    raise RuntimeError("Unreachable ClickHouse startup retry state")


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = Settings.from_environment()
    repository = await create_clickhouse_repository_with_retry(settings)
    producer = EventProducer(
        settings=settings,
        repository=repository,
    )
    application.state.producer = producer

    try:
        yield
    finally:
        producer.close()


app = FastAPI(
    title="CanonFlow Event Producer",
    version="0.1.1",
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
)


@app.get("/healthz")
@app.get("/livez")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
def readiness(request: Request) -> dict[str, str]:
    producer: EventProducer = request.app.state.producer

    try:
        producer.ping()
    except Exception:
        LOGGER.exception("ClickHouse readiness check failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ClickHouse unavailable",
        ) from None

    return {"status": "ready"}


@app.post(
    "/v1/events",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def ingest_event(
    event: EventRequest,
    request: Request,
) -> IngestResponse:
    producer: EventProducer = request.app.state.producer

    try:
        return producer.ingest(event)
    except DefinitionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    except (
        EventVersionMismatchError,
        TruthScopeMismatchError,
        ContractBindingError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    except Exception:
        LOGGER.exception("Event insertion failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Event Ledger unavailable",
        ) from None


def run() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format=(
            "%(asctime)s %(levelname)s %(name)s "
            "%(message)s"
        ),
    )
    uvicorn.run(
        "canonflow_event_producer.app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        access_log=True,
    )


if __name__ == "__main__":
    run()
