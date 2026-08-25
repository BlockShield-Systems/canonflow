import asyncio
import os
import uuid

from fastmcp import Client


MCP_URL = "http://127.0.0.1:8000/mcp"
PROJECT_SLUG = "yd-when-paradise-glitches"


async def call(client: Client, tool: str, arguments: dict):
    result = await client.call_tool(tool, arguments)

    if result.is_error:
        raise RuntimeError(f"{tool} failed: {result}")

    return result


async def main() -> None:
    token = os.environ["CLICKHOUSE_MCP_AUTH_TOKEN"]
    run_id = str(uuid.uuid4())

    async with Client(MCP_URL, auth=token) as client:
        tools = await client.list_tools()
        tool_names = sorted(tool.name for tool in tools)

        print("MCP tools:", tool_names)

        required_tools = {
            "list_databases",
            "list_tables",
            "run_query",
        }

        missing = required_tools.difference(tool_names)
        if missing:
            raise RuntimeError(f"Missing MCP tools: {sorted(missing)}")

        databases = await call(client, "list_databases", {})
        print("Databases:", databases.data)

        tables = await call(
            client,
            "list_tables",
            {
                "database": "canonflow",
                "include_detailed_columns": False,
                "page_size": 50,
            },
        )
        print("Tables:", tables.data)

        project = await call(
            client,
            "run_query",
            {
                "query": f"""
                    SELECT
                        project_id,
                        slug,
                        title,
                        status
                    FROM canonflow.projects FINAL
                    WHERE slug = '{PROJECT_SLUG}'
                    LIMIT 1
                """
            },
        )
        print("Project:", project.data)

        inserted = await call(
            client,
            "run_query",
            {
                "query": f"""
                    INSERT INTO canonflow.agent_runs
                    (
                        run_id,
                        project_id,
                        agent_name,
                        workflow_name,
                        model_name,
                        status,
                        input_summary,
                        output_summary,
                        completed_at,
                        duration_ms,
                        metadata_json
                    )
                    SELECT
                        toUUID('{run_id}'),
                        project_id,
                        'mcp-verification-agent',
                        'verify-mcp-runtime',
                        'none',
                        'completed',
                        'Verify MCP read and write access',
                        'MCP runtime verification succeeded',
                        now64(3),
                        0,
                        '{{"verification":true,"transport":"streamable-http"}}'
                    FROM canonflow.projects FINAL
                    WHERE slug = '{PROJECT_SLUG}'
                """
            },
        )
        print("Insert result:", inserted.data)

        verification = await call(
            client,
            "run_query",
            {
                "query": f"""
                    SELECT
                        run_id,
                        agent_name,
                        workflow_name,
                        status,
                        output_summary
                    FROM canonflow.agent_runs
                    WHERE run_id = toUUID('{run_id}')
                """
            },
        )
        print("Written record:", verification.data)

        print("MCP runtime verification: SUCCESS")


if __name__ == "__main__":
    asyncio.run(main())
