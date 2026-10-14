import sqlite3
from mcp.server.fastmcp import FastMCP

from reminders import (
    start_scheduler,
    create_reminder as create_reminder_fn,
    respond_to_reminder as respond_to_reminder_fn,
    record_no_response as record_no_response_fn,
    get_reminders as get_reminders_fn,
)

mcp = FastMCP(
    "Medication Assistant",
    host="0.0.0.0",
    port=8000,
    stateless_http=True
)

DB_NAME = "medications.db"


def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prescriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL,
                medicine TEXT NOT NULL,
                dosage TEXT NOT NULL,
                schedule TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                doses_per_day INTEGER NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS dose_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prescription_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                logged_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (prescription_id)
                    REFERENCES prescriptions(id)
            )
        """)


# 1. Connection test
@mcp.tool()
def hello_world() -> str:
    """Test whether the MCP server is connected."""
    return "Medication Assistant MCP server is connected!"


# 2. Add prescription
@mcp.tool()
def add_prescription(
    patient_id: str,
    medicine: str,
    dosage: str,
    schedule: str,
    quantity: int,
    doses_per_day: int
) -> dict:
    """Save a patient's medicine prescription."""
    if not patient_id.strip() or not medicine.strip():
        return {"error": "Patient ID and medicine are required."}

    if quantity <= 0 or doses_per_day <= 0:
        return {"error": "Quantity and doses per day must be positive."}

    with get_db() as conn:
        cursor = conn.execute("""
            INSERT INTO prescriptions
            (patient_id, medicine, dosage, schedule,
             quantity, doses_per_day)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            patient_id.strip(),
            medicine.strip(),
            dosage.strip(),
            schedule.strip(),
            quantity,
            doses_per_day
        ))

        prescription_id = cursor.lastrowid

    return {
        "success": True,
        "prescription_id": prescription_id,
        "medicine": medicine,
        "message": "Prescription saved successfully."
    }


# 3. Get medication schedule
@mcp.tool()
def get_schedule(patient_id: str) -> list:
    """Get all saved prescriptions for a patient."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT id, medicine, dosage, schedule,
                   quantity, doses_per_day
            FROM prescriptions
            WHERE patient_id = ?
            ORDER BY id
        """, (patient_id,)).fetchall()

    return [dict(row) for row in rows]


# 4. Log dose
@mcp.tool()
def log_dose(prescription_id: int, status: str) -> dict:
    """Record a dose as taken, postponed, or missed."""
    status = status.lower().strip()

    if status not in ("taken", "later", "missed"):
        return {
            "error": "Status must be taken, later, or missed."
        }

    with get_db() as conn:
        prescription = conn.execute(
            "SELECT id FROM prescriptions WHERE id = ?",
            (prescription_id,)
        ).fetchone()

        if prescription is None:
            return {"error": "Prescription not found."}

        cursor = conn.execute("""
            INSERT INTO dose_logs (prescription_id, status)
            VALUES (?, ?)
        """, (prescription_id, status))

        log_id = cursor.lastrowid

    return {
        "success": True,
        "log_id": log_id,
        "status": status
    }


# 5. Refill status
@mcp.tool()
def get_refill_status(prescription_id: int) -> dict:
    """Estimate medicine supply from recorded taken doses."""
    with get_db() as conn:
        prescription = conn.execute("""
            SELECT medicine, quantity, doses_per_day
            FROM prescriptions
            WHERE id = ?
        """, (prescription_id,)).fetchone()

        if prescription is None:
            return {"error": "Prescription not found."}

        taken_count = conn.execute("""
            SELECT COUNT(*) AS total
            FROM dose_logs
            WHERE prescription_id = ? AND status = 'taken'
        """, (prescription_id,)).fetchone()["total"]

    remaining = max(0, prescription["quantity"] - taken_count)
    days_left = remaining // prescription["doses_per_day"]

    return {
        "medicine": prescription["medicine"],
        "estimated_units_remaining": remaining,
        "estimated_days_left": days_left,
        "note": (
            "Demo estimate only. Verify actual stock, units, "
            "and prescribed instructions."
        )
    }


# 6. Adherence report
@mcp.tool()
def get_adherence_report(patient_id: str) -> dict:
    """Summarize recorded dose events from the last seven days."""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT dl.status, COUNT(*) AS total
            FROM dose_logs dl
            JOIN prescriptions p ON p.id = dl.prescription_id
            WHERE p.patient_id = ?
              AND dl.logged_at >= datetime('now', '-7 days')
            GROUP BY dl.status
        """, (patient_id,)).fetchall()

    counts = {"taken": 0, "missed": 0, "later": 0}

    for row in rows:
        if row["status"] in counts:
            counts[row["status"]] = row["total"]

    denominator = counts["taken"] + counts["missed"]

    return {
        "patient_id": patient_id,
        "period": "last 7 days",
        "taken": counts["taken"],
        "missed": counts["missed"],
        "postponed": counts["later"],
        "logged_events": sum(counts.values()),
        "adherence_percentage": (
            round(counts["taken"] / denominator * 100, 2)
            if denominator else None
        ),
        "note": (
            "Based on recorded events, not proof of actual medication use. "
            "Unlogged doses are not included."
        )
    }


# 7. Create medication reminder
@mcp.tool()
def create_medication_reminder(
    patient_id: str,
    prescription_id: int,
    scheduled_at: str
) -> dict:
    """Create a reminder using YYYY-MM-DD HH:MM:SS format."""
    return create_reminder_fn(
        patient_id, prescription_id, scheduled_at
    )


# 8. Respond to reminder
@mcp.tool()
def respond_to_medication_reminder(
    reminder_id: int,
    response: str
) -> dict:
    """Record the patient's done or later response."""
    return respond_to_reminder_fn(reminder_id, response)


# 9. Record reminder silence
@mcp.tool()
def record_reminder_silence(reminder_id: int) -> dict:
    """Record an unanswered reminder and escalate after three attempts."""
    return record_no_response_fn(reminder_id)


# 10. Get patient reminders
@mcp.tool()
def get_patient_reminders(patient_id: str) -> list:
    """Get a patient's reminders and current statuses."""
    return get_reminders_fn(patient_id)


# 11. Family dashboard
@mcp.tool()
def get_family_dashboard(patient_id: str) -> dict:
    """Get medicine details, adherence, supply estimates, and family alerts."""

    if not patient_id.strip():
        return {"error": "Patient ID is required."}

    with get_db() as conn:
        prescriptions = conn.execute("""
            SELECT id, medicine, dosage, schedule,
                   quantity, doses_per_day
            FROM prescriptions
            WHERE patient_id = ?
            ORDER BY id
        """, (patient_id,)).fetchall()

        adherence_rows = conn.execute("""
            SELECT dl.status, COUNT(*) AS total
            FROM dose_logs dl
            JOIN prescriptions p ON p.id = dl.prescription_id
            WHERE p.patient_id = ?
              AND dl.logged_at >= datetime('now', '-7 days')
            GROUP BY dl.status
        """, (patient_id,)).fetchall()

        alerts = conn.execute("""
            SELECT id, prescription_id, scheduled_at,
                   status, retry_count, family_alerted
            FROM reminders
            WHERE patient_id = ?
              AND family_alerted = 1
            ORDER BY scheduled_at DESC
            LIMIT 10
        """, (patient_id,)).fetchall()

        medicines = []

        for p in prescriptions:
            taken = conn.execute("""
                SELECT COUNT(*) AS total
                FROM dose_logs
                WHERE prescription_id = ?
                  AND status = 'taken'
            """, (p["id"],)).fetchone()["total"]

            remaining = max(0, p["quantity"] - taken)

            medicines.append({
                "prescription_id": p["id"],
                "medicine": p["medicine"],
                "dosage": p["dosage"],
                "schedule": p["schedule"],
                "doses_per_day": p["doses_per_day"],
                "estimated_units_remaining": remaining,
                "estimated_days_left": (
                    remaining // p["doses_per_day"]
                )
            })

        counts = {
            "taken": 0,
            "missed": 0,
            "later": 0
        }

        for row in adherence_rows:
            if row["status"] in counts:
                counts[row["status"]] = row["total"]

        denominator = counts["taken"] + counts["missed"]

        adherence = (
            round(counts["taken"] / denominator * 100, 2)
            if denominator else None
        )

    return {
        "patient_id": patient_id,
        "medicines": medicines,
        "last_7_days": {
            "taken": counts["taken"],
            "missed": counts["missed"],
            "postponed": counts["later"],
            "adherence_percentage": adherence
        },
        "family_alerts": [dict(row) for row in alerts],
        "notes": [
            "Schedules are stored instructions, not verified dose completion.",
            "Supply figures are estimates based on recorded taken events.",
            "Family alerts are database records; no external notification is sent.",
            "Missed-dose counts include only explicitly logged missed events."
        ]
    }


# Initialize database and start server
init_db()

if __name__ == "__main__":
    start_scheduler()
    mcp.run(transport="streamable-http")