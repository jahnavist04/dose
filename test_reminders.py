
from datetime import datetime
from reminders import (
    create_reminder,
    respond_to_reminder,
    record_no_response,
    get_reminders
)

result = create_reminder(
    patient_id="P001",
    prescription_id=1,
    scheduled_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
)
print("CREATED:", result)

reminder_id = result["reminder_id"]

print("LATER:", respond_to_reminder(reminder_id, "later"))
print("NO RESPONSE 1:", record_no_response(reminder_id))
print("NO RESPONSE 2:", record_no_response(reminder_id))
print("NO RESPONSE 3:", record_no_response(reminder_id))
print("REMINDERS:", get_reminders("P001"))
