
import asyncio
import json
import os

import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = os.getenv(
    "DOSE_MCP_URL",
    "http://127.0.0.1:8000/mcp"
)


@pytest.mark.asyncio
async def test_medication_tools():
    async with streamablehttp_client(MCP_URL) as (
        read_stream,
        write_stream,
        _
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # Verify the medication tools are registered.
            tools_result = await session.list_tools()
            tool_names = {tool.name for tool in tools_result.tools}

            assert "add_prescription" in tool_names
            assert "get_schedule" in tool_names
            assert "log_dose" in tool_names
            assert "get_refill_status" in tool_names

            # Verify the schedule tool responds correctly.
            result = await session.call_tool(
                "get_schedule",
                {"patient_id": "P001"}
            )

            assert not result.isError, result
