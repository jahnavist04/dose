import asyncio, json
from datetime import datetime, timedelta
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

URL = "http://127.0.0.1:8000/mcp"

def parse(res):
    print("  raw:", res.content[0].text if res.content else res)
    if res.isError:
        raise SystemExit("Tool returned an error, see raw output above.")
    return json.loads(res.content[0].text)

async def main():
    async with streamablehttp_client(URL) as (r, w, _):
        async with ClientSession(r, w) as session:
            await session.initialize()

            print("PRESCRIPTION:")
            rx = parse(await session.call_tool("add_prescription", {
                "patient_id": "P001",
                "medicine": "Metformin",
                "dosage": "500mg",
                "schedule": "1-0-1",
                "quantity": 60,
                "doses_per_day": 2,
            }))
            pid = rx["prescription_id"]

            when = (datetime.now() + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
            print("REMINDER:")
            parse(await session.call_tool("create_medication_reminder", {
                "patient_id": "P001",
                "prescription_id": pid,
                "scheduled_at": when,
            }))

            print("REMINDER LIST:")
            parse(await session.call_tool("get_patient_reminders", {"patient_id": "P001"}))

asyncio.run(main())