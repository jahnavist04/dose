import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

MCP_URL = "http://127.0.0.1:8000/mcp"


async def main():
    async with streamablehttp_client(MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                "get_family_dashboard",
                {"patient_id": "P001"}
            )

            print("FAMILY DASHBOARD TEST")
            print(result)


if __name__ == "__main__":
    asyncio.run(main())