
import os

import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = os.getenv(
    "DOSE_MCP_URL",
    "http://127.0.0.1:8000/mcp"
)


@pytest.mark.asyncio
async def test_family_dashboard():
    async with streamablehttp_client(MCP_URL) as (
        read_stream,
        write_stream,
        _
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            result = await session.call_tool(
                "get_family_dashboard",
                {"patient_id": "P001"}
            )

            assert not result.isError, result
            assert result.content, "Dashboard returned no content"

            text_content = "\n".join(
                item.text
                for item in result.content
                if hasattr(item, "text")
            )

            assert "P001" in text_content
            assert "medicines" in text_content.lower()
