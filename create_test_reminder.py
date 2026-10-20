
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main():
    async with streamablehttp_client(
        "http://127.0.0.1:8000/mcp"
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            result = await session.call_tool(
                "create_medication_reminder",
                {
                    "patient_id": "P001",
                    "prescription_id": 11,
                    "scheduled_at": "2026-10-20 16:49:23",
                },
            )

            for item in result.content:
                if hasattr(item, "text"):
                    print(item.text)
                else:
                    print(item)


asyncio.run(main())
