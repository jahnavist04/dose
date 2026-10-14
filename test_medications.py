
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

            print("\n1. ADD PRESCRIPTION")
            result = await session.call_tool("add_prescription", {
                "patient_id": "P001",
                "medicine": "DemoMedicine",
                "dosage": "1 tablet",
                "schedule": "9 AM",
                "quantity": 30,
                "doses_per_day": 1
            })
            print(result)

            print("\n2. GET SCHEDULE")
            result = await session.call_tool("get_schedule", {
                "patient_id": "P001"
            })
            print(result)

            print("\n3. LOG DOSE")
            result = await session.call_tool("log_dose", {
                "prescription_id": 1,
                "status": "taken"
            })
            print(result)

            print("\n4. REFILL STATUS")
            result = await session.call_tool("get_refill_status", {
                "prescription_id": 1
            })
            print(result)


asyncio.run(main())
