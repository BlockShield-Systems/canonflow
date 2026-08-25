#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import clickhouse_connect


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    normalized = value.strip().lower()

    if normalized in {"1", "true", "yes", "on"}:
        return True

    if normalized in {"0", "false", "no", "off"}:
        return False

    raise ValueError(f"Invalid boolean value for {name}: {value}")


def require_env(name: str) -> str:
    value = os.getenv(name)

    if value is None or not value.strip():
        raise RuntimeError(f"Required environment variable is missing: {name}")

    return value.strip()


def rows_as_dicts(result: Any) -> list[dict[str, Any]]:
    return [
        dict(zip(result.column_names, row, strict=True))
        for row in result.result_rows
    ]


def quote_identifier(value: str) -> str:
    return "`" + value.replace("`", "``") + "`"


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: inspect_clickhouse_schema.py OUTPUT_JSON"
        )

    output_path = Path(sys.argv[1])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    host = require_env("CLICKHOUSE_HOST")
    username = require_env("CLICKHOUSE_USER")
    password = require_env("CLICKHOUSE_PASSWORD")

    database = os.getenv("CLICKHOUSE_DATABASE", "canonflow").strip()
    port = int(os.getenv("CLICKHOUSE_PORT", "8443"))
    secure = env_bool("CLICKHOUSE_SECURE", True)
    verify = env_bool("CLICKHOUSE_VERIFY", True)

    client = clickhouse_connect.get_client(
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
        secure=secure,
        verify=verify,
        connect_timeout=int(
            os.getenv("CLICKHOUSE_CONNECT_TIMEOUT", "10")
        ),
        send_receive_timeout=int(
            os.getenv("CLICKHOUSE_SEND_RECEIVE_TIMEOUT", "30")
        ),
    )

    try:
        server = client.query(
            """
            SELECT
                version() AS server_version,
                currentDatabase() AS current_database,
                currentUser() AS current_user
            """
        )

        tables = client.query(
            """
            SELECT
                database,
                name,
                engine,
                total_rows,
                total_bytes
            FROM system.tables
            WHERE database = {database:String}
            ORDER BY name
            """,
            parameters={"database": database},
        )

        columns = client.query(
            """
            SELECT
                database,
                table,
                position,
                name,
                type,
                default_kind,
                default_expression,
                comment
            FROM system.columns
            WHERE database = {database:String}
            ORDER BY table, position
            """,
            parameters={"database": database},
        )

        table_rows = rows_as_dicts(tables)
        create_statements = []

        for table in table_rows:
            identifier = (
                f'{quote_identifier(table["database"])}.'
                f'{quote_identifier(table["name"])}'
            )
            result = client.query(f"SHOW CREATE TABLE {identifier}")

            create_statements.append(
                {
                    "database": table["database"],
                    "table": table["name"],
                    "create_statement": result.result_rows[0][0],
                }
            )

        report = {
            "schema_version": "1.0",
            "inspection_mode": "read_only",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "connection": {
                "host": host,
                "port": port,
                "database": database,
                "secure": secure,
                "verify": verify,
                "username": username,
                "password_included": False,
            },
            "server": rows_as_dicts(server)[0],
            "tables": table_rows,
            "columns": rows_as_dicts(columns),
            "create_statements": create_statements,
        }

        output_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str)
            + "\n",
            encoding="utf-8",
        )

        print(f'Server version : {report["server"]["server_version"]}')
        print(f'Current database: {report["server"]["current_database"]}')
        print(f'Tables found   : {len(report["tables"])}')
        print()

        column_records = report["columns"]

        for table in report["tables"]:
            table_name = table["name"]
            table_columns = [
                column
                for column in column_records
                if column["table"] == table_name
            ]

            print(
                f'{table_name} | '
                f'engine={table["engine"]} | '
                f'rows={table["total_rows"]} | '
                f'columns={len(table_columns)}'
            )

            for column in table_columns:
                print(f'  {column["position"]:2}. '
                      f'{column["name"]}: {column["type"]}')

        print()
        print(f"Report: {output_path}")
        print("CLICKHOUSE SCHEMA PREFLIGHT: OK")

        return 0
    finally:
        client.close()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
