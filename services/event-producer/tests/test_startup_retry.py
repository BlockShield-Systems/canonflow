from __future__ import annotations

import unittest
import uuid
from unittest.mock import AsyncMock, patch

from clickhouse_connect.driver.exceptions import OperationalError

import canonflow_event_producer.app as app_module
from canonflow_event_producer.app import (
    Settings,
    create_clickhouse_repository_with_retry,
)


def settings(
    *,
    max_attempts: int = 3,
    initial_delay: float = 0.1,
    max_delay: float = 0.2,
) -> Settings:
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
        contract_id=uuid.UUID("e17828fb-49b1-5df0-9c45-385a68f5f9d1"),
        project_id=uuid.UUID("e8627781-5bf3-4c4d-905f-8dda49ab53d6"),
        clickhouse_startup_max_attempts=max_attempts,
        clickhouse_startup_initial_delay_seconds=initial_delay,
        clickhouse_startup_max_delay_seconds=max_delay,
    )


class StartupRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_recovers_after_transient_operational_errors(self) -> None:
        repository = object()
        to_thread = AsyncMock(
            side_effect=[
                OperationalError("transient-1"),
                OperationalError("transient-2"),
                repository,
            ]
        )
        sleep = AsyncMock()

        with (
            patch.object(app_module.asyncio, "to_thread", to_thread),
            patch.object(app_module.asyncio, "sleep", sleep),
        ):
            result = await create_clickhouse_repository_with_retry(
                settings()
            )

        self.assertIs(result, repository)
        self.assertEqual(to_thread.await_count, 3)
        self.assertEqual(
            [call.args[0] for call in sleep.await_args_list],
            [0.1, 0.2],
        )

    async def test_raises_after_attempts_are_exhausted(self) -> None:
        to_thread = AsyncMock(
            side_effect=[
                OperationalError("transient-1"),
                OperationalError("transient-2"),
                OperationalError("transient-3"),
            ]
        )
        sleep = AsyncMock()

        with (
            patch.object(app_module.asyncio, "to_thread", to_thread),
            patch.object(app_module.asyncio, "sleep", sleep),
        ):
            with self.assertRaises(OperationalError):
                await create_clickhouse_repository_with_retry(settings())

        self.assertEqual(to_thread.await_count, 3)
        self.assertEqual(sleep.await_count, 2)

    def test_livez_route_is_registered(self) -> None:
        paths = {
            route.path
            for route in app_module.app.routes
        }

        self.assertIn("/healthz", paths)
        self.assertIn("/livez", paths)
        self.assertIn("/readyz", paths)


if __name__ == "__main__":
    unittest.main()
