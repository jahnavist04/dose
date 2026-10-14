
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "https://lilac-oxford-amends.ngrok-free.dev/mcp"


async def main():
    async with streamablehttp_client(
        URL,
        headers={"ngrok-skip-browser-warning": "true"}
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            result = await session.call_tool(
                "get_adherence_report",
                {"patient_id": "P001"}
            )

            print(result)


asyncio.run(main())
