
import asyncio
from datetime import datetime, timedelta

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "https://lilac-oxford-amends.ngrok-free.dev/mcp"


async def main():
    scheduled_at = (
        datetime.now() + timedelta(seconds=30)
    ).strftime("%Y-%m-%d %H:%M:%S")

    async with streamablehttp_client(
        URL,
        headers={"ngrok-skip-browser-warning": "true"}
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            result = await session.call_tool(
                "create_medication_reminder",
                {
                    "patient_id": "P001",
                    "prescription_id": 1,
                    "scheduled_at": scheduled_at
                }
            )
            print("CREATED:", result)


asyncio.run(main())
